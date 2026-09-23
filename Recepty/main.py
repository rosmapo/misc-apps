"""
GTK4 klient pre Simplenote (cez Simperium REST API) s podporou:
  - tagov (rolovacia ponuka "Kategória" v hornej lište, filtrovanie podľa tagu;
    ľavý stĺpec zobrazuje len nadpisy poznámok)
  - zväčšovania/zmenšovania písma editora (Ctrl + koliesko myši, alebo Ctrl +/-)
  - offline cache (SQLite) - appka naštartuje a funguje úplne offline;
    synchronizácia so serverom prebieha len po stlačení tlačidla
    synchronizácie v hornej lište (žiadna automatika na pozadí)
  - import zo Simplenote JSON exportu (Ctrl+I, bez viditeľného tlačidla) -
    umožňuje aplikáciu používať čisto offline aj keby prestalo fungovať
    API; pred importom sa lokálna databáza úplne vymaže a nahradí sa
    obsahom vybraného JSON súboru

Hlavné okno je len na čítanie. Nová poznámka a úprava sa otvárajú
v samostatnom okne s tlačidlom Uložiť (žiadne automatické ukladanie
pri písaní v hlavnom okne).

Spustenie:
    pip install requests
    python3 main.py
"""

import json
import threading
import time
import uuid
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, GLib, Pango, Adw

import config
import local_store
from simplenote_client import SimplenoteClient

ALL_NOTES = object()  # sentinel pre "žiadny filter podľa tagu"

# Pevné kategórie receptov (tlačidlá v toolbare)
RECIPE_TAGS = ("Hlavné_jedlo", "Polievky", "Dezerty", "Nápoje")


class Note:
    def __init__(self, note_id, version, content="", tags=None,
                 deleted=False, modification_date=0, dirty=False):
        self.id = note_id
        self.version = version
        self.content = content
        self.tags = list(tags or [])
        self.deleted = deleted
        self.modification_date = modification_date or 0
        self.dirty = dirty

    @property
    def title(self):
        stripped = self.content.strip()
        if not stripped:
            return "(Nový recept)"
        return stripped.splitlines()[0][:80]

    @classmethod
    def from_local_row(cls, row):
        return cls(
            row["id"], row["version"], row["content"], row["tags"],
            row["deleted"], row["modification_date"], row["dirty"],
        )

    @classmethod
    def from_server_item(cls, item):
        data = item.get("d", {})
        return cls(
            item.get("id"), item.get("v"), data.get("content", ""),
            data.get("tags", []), data.get("deleted", False),
            data.get("modificationDate", 0), dirty=False,
        )


class TokenDialog(Adw.MessageDialog):
    """Moderný Adwaita dialóg pre vyžiadanie tokenu."""
    def __init__(self, parent, message="Vlož Simperium access token:"):
        super().__init__(transient_for=parent, heading="Prihlásenie", body=message)
        
        self.add_response("cancel", "Zrušiť")
        self.add_response("ok", "OK")
        self.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        self.set_default_response("ok")
        self.set_close_response("cancel")

        self.entry = Gtk.Entry()
        self.entry.set_activates_default(True)
        self.set_extra_child(self.entry)

    def get_token(self):
        return self.entry.get_text().strip()


class NoteEditorWindow(Adw.Window):
    """Samostatné okno na vytvorenie alebo úpravu poznámky (explicitné Uložiť)."""

    def __init__(self, parent: "SimplenoteWindow", note: Note | None = None):
        is_new = note is None
        title = "Nový recept" if is_new else f"Upraviť: {note.title}"
        super().__init__(title=title, transient_for=parent, modal=True)
        self.set_default_size(680, 520)
        self.set_application(parent.get_application())

        self.parent_win = parent
        self.note_id = None if is_new else note.id
        self.is_new = is_new
        self.all_tags = list(parent.all_tags)

        toolbar_view = Adw.ToolbarView()
        
        header_bar = Adw.HeaderBar()
        header_bar.set_show_start_title_buttons(False)
        header_bar.set_show_end_title_buttons(False)
        toolbar_view.add_top_bar(header_bar)
        
        cancel_btn = Gtk.Button(label="Zrušiť")
        cancel_btn.connect("clicked", lambda b: self.close())
        header_bar.pack_start(cancel_btn)

        save_btn = Gtk.Button(label="Uložiť")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        header_bar.pack_end(save_btn)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # --- editor ---
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_left_margin(12)
        self.text_view.set_right_margin(12)
        self.text_view.set_top_margin(12)
        self.text_view.set_bottom_margin(12)
        self.text_buffer = self.text_view.get_buffer()
        self.text_view.set_pixels_below_lines(6)
        self.text_view.set_pixels_inside_wrap(5)
        if note is not None:
            self.text_buffer.set_text(note.content)

        self.font_css = Gtk.CssProvider()
        css = f"textview {{ font-size: {parent.font_size}pt; }}".encode()
        self.font_css.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.font_css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        editor_scroller = Gtk.ScrolledWindow()
        editor_scroller.set_child(self.text_view)
        editor_scroller.set_vexpand(True)
        editor_scroller.set_hexpand(True)
        root.append(editor_scroller)

        root.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # --- tagy ---
        tags_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(tags_box, m)(12)

        tags_box.append(Gtk.Label(label="Tagy:"))
        self.tags_entry = Gtk.Entry()
        self.tags_entry.set_placeholder_text(
            "napr. práca, nápady, recepty (oddeľ čiarkou)"
        )
        self.tags_entry.set_hexpand(True)
        if note is not None:
            self.tags_entry.set_text(", ".join(note.tags))
        self.tags_entry.connect("changed", self._on_tags_changed)
        tags_box.append(self.tags_entry)
        root.append(tags_box)

        # popover s návrhmi existujúcich tagov
        self.tag_suggestions_popover = Gtk.Popover()
        self.tag_suggestions_popover.set_parent(self.tags_entry)
        self.tag_suggestions_popover.set_autohide(True)
        self.tag_suggestions_popover.set_has_arrow(False)
        self.tag_suggestions_list = Gtk.ListBox()
        self.tag_suggestions_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.tag_suggestions_list.connect(
            "row-activated", self._on_tag_suggestion_activated
        )
        self.tag_suggestions_popover.set_child(self.tag_suggestions_list)

        toolbar_view.set_content(root)
        self.set_content(toolbar_view)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)
        self.connect("close-request", self._on_close_request)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _on_close_request(self, *args):
        return False

    def _current_tags(self):
        raw = self.tags_entry.get_text()
        return [t.strip() for t in raw.split(",") if t.strip()]

    def _on_save(self, button):
        tags = self._current_tags()
        if not tags:
            self._confirm_save_without_tag()
            return
        self._do_save()

    def _confirm_save_without_tag(self):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Nie je zvolený tag",
            body="Recept nemá priradený žiadny tag. Naozaj ho chceš uložiť bez tagu?",
        )
        dialog.add_response("cancel", "Zrušiť")
        dialog.add_response("save", "Uložiť bez tagu")
        dialog.set_response_appearance("cancel", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_confirm_save_response)
        dialog.present()

    def _on_confirm_save_response(self, dialog, response):
        if response == "save":
            self._do_save()

    def _do_save(self):
        start, end = self.text_buffer.get_bounds()
        content = self.text_buffer.get_text(start, end, True)
        tags = self._current_tags()
        self.parent_win.save_note_from_editor(self.note_id, content, tags)
        self.close()

    def _current_tag_fragment(self):
        text = self.tags_entry.get_text()
        cursor_pos = self.tags_entry.get_position()
        before_cursor = text[:cursor_pos]
        last_comma = before_cursor.rfind(",")
        prefix = before_cursor[: last_comma + 1] if last_comma >= 0 else ""
        partial = before_cursor[last_comma + 1:].strip()
        return prefix, partial

    def _on_tags_changed(self, entry):
        self._update_tag_suggestions()

    def _update_tag_suggestions(self):
        _, partial = self._current_tag_fragment()
        already_used = {
            t.strip().lower()
            for t in self.tags_entry.get_text().split(",")
            if t.strip()
        }

        child = self.tag_suggestions_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.tag_suggestions_list.remove(child)
            child = nxt

        if not partial:
            self.tag_suggestions_popover.popdown()
            return

        matches = [
            t for t in self.all_tags
            if t.lower().startswith(partial.lower()) and t.lower() not in already_used
        ]
        if not matches:
            self.tag_suggestions_popover.popdown()
            return

        for tag in matches[:8]:
            row = Gtk.ListBoxRow()
            row.tag_text = tag
            label = Gtk.Label(label=tag, xalign=0)
            label.set_margin_top(4)
            label.set_margin_bottom(4)
            label.set_margin_start(8)
            label.set_margin_end(8)
            row.set_child(label)
            self.tag_suggestions_list.append(row)

        self.tag_suggestions_popover.set_size_request(
            max(160, self.tags_entry.get_width()), -1
        )
        self.tag_suggestions_popover.popup()

    def _on_tag_suggestion_activated(self, list_box, row):
        tag = row.tag_text
        prefix, _ = self._current_tag_fragment()
        text = self.tags_entry.get_text()
        cursor_pos = self.tags_entry.get_position()
        after = text[cursor_pos:].lstrip()

        if prefix and not prefix.endswith(" "):
            prefix += " "

        new_before = f"{prefix}{tag}, "
        new_text = new_before + after
        self.tags_entry.set_text(new_text)
        self.tags_entry.set_position(len(new_before))
        self.tag_suggestions_popover.popdown()
        self.tags_entry.grab_focus()


class SimplenoteWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Simplenote")
        self.set_default_size(900, 650)

        self.client = None
        self.notes = {}
        self.current_note_id = None
        self.selected_tag = ALL_NOTES
        self.all_tags = []

        self.font_size = config.load_font_size()
        self.font_css = Gtk.CssProvider()
        self._import_dialog = None
        self._build_ui()
        self._apply_font_size()
        self._load_from_cache()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        
        header_bar = Adw.HeaderBar()
        toolbar_view.add_top_bar(header_bar)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_size_request(240, -1)
        self.search_entry.connect("search-changed", self.on_search_changed)
        header_bar.set_title_widget(self.search_entry)

        new_btn = Gtk.Button(icon_name="list-add-symbolic")
        new_btn.set_tooltip_text("Nový recept")
        new_btn.connect("clicked", self.on_new_note)
        header_bar.pack_start(new_btn)

        self.edit_btn = Gtk.Button(icon_name="document-edit-symbolic")
        self.edit_btn.set_tooltip_text("Upraviť recept")
        self.edit_btn.set_sensitive(False)
        self.edit_btn.connect("clicked", self.on_edit_note)
        header_bar.pack_start(self.edit_btn)

        tag_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        tag_box.add_css_class("linked")
        tag_box.set_margin_start(12)
        
        self.tag_buttons = {}
        for tag_name in RECIPE_TAGS:
            btn = Gtk.ToggleButton(label=tag_name.replace("_", " "))
            btn.set_tooltip_text(f"Filter: {tag_name}")
            btn.connect("toggled", self.on_tag_button_toggled, tag_name)
            self.tag_buttons[tag_name] = btn
            tag_box.append(btn)
        header_bar.pack_start(tag_box)

        sync_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        sync_btn.set_tooltip_text("Synchronizovať")
        sync_btn.connect("clicked", lambda b: self.sync_now())
        header_bar.pack_end(sync_btn)

        # --- Ľavý panel: nadpisy ---
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.connect("row-selected", self.on_row_selected)
        self.list_box.add_css_class("navigation-sidebar")
        
        notes_scroller = Gtk.ScrolledWindow()
        notes_scroller.set_child(self.list_box)
        notes_scroller.set_vexpand(True)

        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left_box.append(notes_scroller)
        left_box.set_size_request(280, -1)

        # --- Pravý panel: READ-ONLY zobrazenie ---
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_left_margin(12)
        self.text_view.set_right_margin(12)
        self.text_view.set_top_margin(12)
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_buffer = self.text_view.get_buffer()
        self.text_view.set_pixels_below_lines(6)
        self.text_view.set_pixels_inside_wrap(5)

        self.title_tag = self.text_buffer.create_tag(
            "title",
            weight=Pango.Weight.BOLD,
            scale=1.3,
        )

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.font_css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        scroll_controller = Gtk.EventControllerScroll(
            flags=Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll_controller.connect("scroll", self.on_editor_scroll)
        self.text_view.add_controller(scroll_controller)

        editor_scroller = Gtk.ScrolledWindow()
        editor_scroller.set_child(self.text_view)
        editor_scroller.set_vexpand(True)
        editor_scroller.set_hexpand(True)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_start_child(left_box)
        paned.set_end_child(editor_scroller)
        paned.set_position(300)
        paned.set_vexpand(True)

        # stavový riadok (vycentrovaný)
        self.status_label = Gtk.Label(label="Pripravené (offline)")
        self.status_label.set_hexpand(True)
        self.status_label.set_halign(Gtk.Align.CENTER)
        self.status_label.add_css_class("dim-label")
        self.status_label.set_margin_start(12)
        self.status_label.set_margin_end(12)
        self.status_label.set_margin_top(4)
        self.status_label.set_margin_bottom(4)

        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        status_box.append(self.status_label)
        
        toolbar_view.set_content(paned)
        toolbar_view.add_bottom_bar(status_box)

        self.set_content(toolbar_view)

        # klávesové skratky
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)

    def on_key_pressed(self, controller, keyval, keycode, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if not ctrl:
            return False
        if keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            self.change_font_size(1)
            return True
        if keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
            self.change_font_size(-1)
            return True
        if keyval == Gdk.KEY_n:
            self.on_new_note(None)
            return True
        if keyval == Gdk.KEY_e:
            self.on_edit_note(None)
            return True
        if keyval == Gdk.KEY_i:
            self.on_import_notes()
            return True
        return False

    # ------------------------------------------------------------------
    # Theme / font CSS
    # ------------------------------------------------------------------

    def _apply_font_size(self):
        css = f"textview {{ font-size: {self.font_size}pt; }}".encode()
        self.font_css.load_from_data(css)

    def change_font_size(self, delta):
        self.font_size = max(8, min(32, self.font_size + delta))
        self._apply_font_size()
        config.save_font_size(self.font_size)

    def on_editor_scroll(self, controller, dx, dy):
        state = controller.get_current_event_state()
        if state & Gdk.ModifierType.CONTROL_MASK:
            self.change_font_size(-1 if dy > 0 else 1)
            return True
        return False

    # ------------------------------------------------------------------
    # Token / client setup
    # ------------------------------------------------------------------

    def set_client(self, client: SimplenoteClient):
        self.client = client

    def prompt_for_token(self, message="Vlož Simperium access token:"):
        dialog = TokenDialog(self, message)

        def on_response(dlg, response_name):
            if response_name == "ok":
                token = dlg.get_token()
                if token:
                    config.save_token(token)
                    self.set_client(SimplenoteClient(token))
                else:
                    self.set_status("Token nebol zadaný.")
            else:
                self.set_status("Prihlásenie zrušené.")
            dlg.close()

        dialog.connect("response", on_response)
        dialog.present()

    # ------------------------------------------------------------------
    # Async helper
    # ------------------------------------------------------------------

    def run_async(self, fn, on_done=None, on_error=None):
        def worker():
            try:
                result = fn()
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                GLib.idle_add(self._handle_error, e, status, on_error)
                return
            if on_done:
                GLib.idle_add(on_done, result)

        threading.Thread(target=worker, daemon=True).start()

    def _handle_error(self, err, status, on_error):
        if status == 401:
            config.clear_token()
            self.set_status("Token vypršal, prihlás sa znova.")
            self.prompt_for_token("Token vypršal. Vlož nový Simperium access token:")
        elif on_error:
            on_error(err)
        else:
            detail = self._describe_error(err)
            self._log_error(f"sync zlyhal: {self._describe_error_full(err)}")
            self.set_status(f"Chyba: {detail}")
        return False

    def set_status(self, text):
        self.status_label.set_text(text)

    # ------------------------------------------------------------------
    # Offline-first loading
    # ------------------------------------------------------------------

    def _load_from_cache(self):
        rows = local_store.load_all()
        self.notes = {}
        for note_id, row in rows.items():
            if row["deleted"] and not row["dirty"]:
                continue
            self.notes[note_id] = Note.from_local_row(row)

        self._populate_tags()
        self._populate_list()
        if self.notes:
            self.set_status(f"{len(self.notes)} receptov (lokálne)")

    def sync_now(self):
        if not self.client:
            self.set_status("Nie si prihlásený - synchronizácia nie je možná")
            return
        self.set_status("Synchronizujem...")
        self.run_async(self._sync_work, self._on_sync_done)

    def _sync_work(self):
        failed = 0
        pushed = 0
        last_error = None
        for note_id in local_store.get_dirty_ids():
            rows = local_store.load_all()
            row = rows.get(note_id)
            if not row:
                continue
            try:
                tags = row.get("tags") or []
                result = self.client.save_note(
                    note_id, row["content"], version=row["version"],
                    tags=tags,
                    modification_date=row.get("modification_date") or None,
                )
                for tag_name in tags:
                    try:
                        self.client.ensure_tag(tag_name)
                    except Exception as te:
                        self._log_error(
                            f"ensure_tag {tag_name!r} zlyhal: "
                            f"{self._describe_error_full(te)}"
                        )
                local_store.mark_synced(note_id, result.get("v"))
                pushed += 1
            except Exception as e:
                failed += 1
                last_error = self._describe_error(e)
                self._log_error(f"push {note_id} zlyhal: {self._describe_error_full(e)}")

        index_response = self.client.list_notes()
        return index_response, pushed, failed, last_error

    def _describe_error(self, e: Exception) -> str:
        resp = getattr(e, "response", None)
        if resp is not None:
            body = (resp.text or "")[:200]
            return f"HTTP {resp.status_code}: {body}"
        return f"{type(e).__name__}: {e}"

    def _describe_error_full(self, e: Exception) -> str:
        resp = getattr(e, "response", None)
        if resp is not None:
            body = (resp.text or "")[:500]
            req = getattr(resp, "request", None)
            req_info = ""
            if req is not None:
                req_body = req.body
                if isinstance(req_body, bytes):
                    req_body = req_body.decode("utf-8", errors="replace")
                req_info = f" | request: {req.method} {req.url} body={req_body}"
            return f"HTTP {resp.status_code}: {body}{req_info}"
        return f"{type(e).__name__}: {e}"

    def _log_error(self, text: str):
        try:
            log_path = config.CONFIG_DIR / "debug.log"
            config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")
        except Exception:
            pass

    def _on_sync_done(self, result):
        index_response, pushed, failed, last_error = result
        server_ids = set()
        for item in index_response.get("index", []):
            note = Note.from_server_item(item)
            server_ids.add(note.id)

            local_rows = local_store.load_all()
            local_row = local_rows.get(note.id)

            if local_row and local_row["dirty"]:
                continue

            local_store.upsert(
                note.id, note.version, note.content, note.tags,
                note.deleted, note.modification_date, dirty=False,
            )

        local_rows = local_store.load_all()
        for note_id, row in local_rows.items():
            if note_id not in server_ids and not row["dirty"]:
                local_store.remove(note_id)

        prev_id = self.current_note_id
        self._load_from_cache()
        if prev_id and prev_id in self.notes:
            self._select_note(prev_id)

        status = f"{len(self.notes)} receptov (synchronizované)"
        if pushed:
            status += f", odoslaných {pushed}"
        if failed:
            status += f", {failed} zlyhalo"
            if last_error:
                status += f" [{last_error}]"
        self.set_status(status)
        return False

    # ------------------------------------------------------------------
    # Tags panel
    # ------------------------------------------------------------------

    def _populate_tags(self):
        all_tags = set(RECIPE_TAGS)
        for note in self.notes.values():
            all_tags.update(note.tags)
        self.all_tags = sorted(all_tags)

    def on_tag_button_toggled(self, button, tag_name):
        if button.get_active():
            for name, btn in self.tag_buttons.items():
                if name != tag_name and btn.get_active():
                    btn.handler_block_by_func(self.on_tag_button_toggled)
                    btn.set_active(False)
                    btn.handler_unblock_by_func(self.on_tag_button_toggled)
            self.selected_tag = tag_name
        else:
            self.selected_tag = ALL_NOTES
        self._populate_list(self.search_entry.get_text())

    def _clear_tag_filter(self):
        self.selected_tag = ALL_NOTES
        for btn in self.tag_buttons.values():
            if btn.get_active():
                btn.handler_block_by_func(self.on_tag_button_toggled)
                btn.set_active(False)
                btn.handler_unblock_by_func(self.on_tag_button_toggled)

    # ------------------------------------------------------------------
    # Notes list
    # ------------------------------------------------------------------

    def _populate_list(self, filter_text=""):
        child = self.list_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.list_box.remove(child)
            child = nxt

        filter_text = (filter_text or "").lower().strip()

        sorted_notes = sorted(
            self.notes.values(),
            key=lambda n: n.modification_date,
            reverse=True,
        )

        for note in sorted_notes:
            if self.selected_tag is not ALL_NOTES and self.selected_tag not in note.tags:
                continue
            if filter_text and filter_text not in note.title.lower():
                continue

            row = Gtk.ListBoxRow()
            row.note_id = note.id

            title_label = Gtk.Label(label=note.title, xalign=0)
            title_label.set_ellipsize(Pango.EllipsizeMode.END)
            title_label.set_margin_top(8)
            title_label.set_margin_bottom(8)
            title_label.set_margin_start(10)
            title_label.set_margin_end(10)

            row.set_child(title_label)
            self.list_box.append(row)

    def on_search_changed(self, entry):
        self._populate_list(entry.get_text())

    # ------------------------------------------------------------------
    # Selection / display (read-only)
    # ------------------------------------------------------------------

    def on_row_selected(self, list_box, row):
        if row is None:
            self.current_note_id = None
            self.edit_btn.set_sensitive(False)
            self.text_buffer.set_text("")
            return
        note = self.notes.get(row.note_id)
        if not note:
            return
        self.current_note_id = note.id
        self.edit_btn.set_sensitive(True)
        self._show_note_content(note.content)

    def _show_note_content(self, content: str):
        self.text_buffer.set_text(content)
        if not content:
            return
        first_nl = content.find("\n")
        end_offset = first_nl if first_nl >= 0 else len(content)
        if end_offset <= 0:
            return
        start = self.text_buffer.get_start_iter()
        end = self.text_buffer.get_iter_at_offset(end_offset)
        self.text_buffer.apply_tag(self.title_tag, start, end)

    # ------------------------------------------------------------------
    # New / Edit (v samostatnom okne)
    # ------------------------------------------------------------------

    def on_new_note(self, button):
        self._open_editor(None)

    def on_edit_note(self, button):
        if not self.current_note_id:
            return
        note = self.notes.get(self.current_note_id)
        if note:
            self._open_editor(note)

    def _open_editor(self, note: Note | None):
        editor = NoteEditorWindow(self, note)
        editor.present()

    def save_note_from_editor(self, note_id: str | None, content: str, tags: list):
        now = time.time()

        if note_id is None:
            note_id = uuid.uuid4().hex
            note = Note(
                note_id, None, content=content, tags=tags,
                modification_date=now, dirty=True,
            )
            self.notes[note_id] = note
            local_store.upsert(
                note_id, None, content, tags,
                deleted=False, modification_date=now, dirty=True,
            )
            self._clear_tag_filter()
            self.search_entry.set_text("")
            self._populate_tags()
            self._populate_list()
            self._select_note(note_id)
            self.set_status("Vytvorené lokálne - čaká na synchronizáciu")
        else:
            note = self.notes.get(note_id)
            if not note:
                return
            note.content = content
            note.tags = tags
            note.modification_date = now
            note.dirty = True
            local_store.upsert(
                note.id, note.version, content, tags,
                deleted=False, modification_date=now, dirty=True,
            )
            self._populate_tags()
            self._populate_list()
            self._select_note(note_id)
            self.set_status("Uložené lokálne - čaká na synchronizáciu")

    def _select_note(self, note_id):
        row = self.list_box.get_first_child()
        while row:
            if getattr(row, "note_id", None) == note_id:
                self.list_box.select_row(row)
                break
            row = row.get_next_sibling()

    # ------------------------------------------------------------------
    # Import zo Simplenote JSON exportu (Ctrl+I, bez viditeľného tlačidla)
    # ------------------------------------------------------------------

    def on_import_notes(self, *args):
        dialog = Gtk.FileChooserNative.new(
            "Importovať recepty z JSON",
            self,
            Gtk.FileChooserAction.OPEN,
            "Importovať",
            "Zrušiť",
        )
        json_filter = Gtk.FileFilter()
        json_filter.set_name("JSON súbory")
        json_filter.add_pattern("*.json")
        dialog.add_filter(json_filter)
        dialog.connect("response", self._on_import_file_chosen)
        self._import_dialog = dialog  # drž referenciu, nech dialóg nezanikne
        dialog.show()

    def _on_import_file_chosen(self, dialog, response):
        path = None
        if response == Gtk.ResponseType.ACCEPT:
            gfile = dialog.get_file()
            if gfile:
                path = gfile.get_path()
        self._import_dialog = None
        if path:
            self._confirm_import(path)

    def _confirm_import(self, path):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Importovať recepty?",
            body=(
                "Import vymaže všetky recepty aktuálne uložené v aplikácii "
                "a nahradí ich obsahom vybraného JSON súboru. Táto akcia sa "
                "nedá vrátiť späť. Naozaj chceš pokračovať?"
            ),
        )
        dialog.add_response("cancel", "Zrušiť")
        dialog.add_response("import", "Importovať")
        dialog.set_response_appearance("import", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_confirm_import_response, path)
        dialog.present()

    def _on_confirm_import_response(self, dialog, response, path):
        if response == "import":
            self._do_import(path)

    def _do_import(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.set_status(f"Import zlyhal: {e}")
            return

        active_notes = data.get("activeNotes", [])
        if not isinstance(active_notes, list):
            self.set_status("Import zlyhal: neplatný formát JSON")
            return

        # vyčistiť lokálnu databázu - po importe v nej má byť len to,
        # čo je v JSON súbore
        for note_id in list(local_store.load_all().keys()):
            local_store.remove(note_id)

        imported = 0
        for item in active_notes:
            note_id = item.get("id")
            if not note_id:
                continue
            content = item.get("content", "")
            tags = list(dict.fromkeys(item.get("tags") or []))
            mod_date = self._parse_iso_timestamp(
                item.get("lastModified") or item.get("creationDate")
            )
            local_store.upsert(
                note_id, None, content, tags,
                deleted=False, modification_date=mod_date, dirty=False,
            )
            imported += 1

        self.current_note_id = None
        self._clear_tag_filter()
        self.search_entry.set_text("")
        self._load_from_cache()
        self.set_status(f"Naimportovaných {imported} receptov z JSON")

    def _parse_iso_timestamp(self, ts):
        if not ts:
            return time.time()
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except Exception:
            return time.time()


class SimplenoteApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="sk.example.simplenotegtk")
        # Korektná správa vzhľadu pre Libadwaita
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = SimplenoteWindow(self)
        win.present()

        token = config.load_token()
        if token:
            win.set_client(SimplenoteClient(token))
        else:
            win.prompt_for_token()


def main():
    app = SimplenoteApp()
    app.run(None)


if __name__ == "__main__":
    main()