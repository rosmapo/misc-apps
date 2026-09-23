#!/usr/bin/env python3
"""
Sväté Písmo – GTK4 aplikácia pre štúdium Biblie
Slovenský katolícky preklad + komentáre SSV
"""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Adw, GLib, Pango, Gdk
import sqlite3
import re
import os
import sys
import json
import threading
import subprocess
import unicodedata
from datetime import datetime

DB_PATH        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SkKatol.SQLite3")
HISTORY_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.json")
DB_COMM_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SSV-c_commentaries.SQLite3")
DB_USER_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "biblia_user.db")
DB_DICT_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Novotny_dictionary.SQLite3")
DB_PREDSLOV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "predslov.SQLite3")


def remove_diacritics(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )

# ─────────────────────────────── Farebné odlíšenie kníh ──────────────────────
# Farby sú definované v biblia.css (triedy book-pentateuch, book-historical, …)

BOOK_CSS_CLASSES = {
    "book-pentateuch": [10, 20, 30, 40, 50],
    "book-historical":  [60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190],
    "book-wisdom":      [220, 230, 240, 250, 260, 270, 280],
    "book-prophets":    [290, 300, 310, 320, 330, 340, 350, 360, 370, 380, 390, 400, 410, 420, 430, 440, 450, 455, 460],
    "book-maccabees":   [462, 464],
    "book-gospels":     [470, 480, 490, 500],
    "book-acts":        [510],
    "book-paul":        [520, 530, 540, 550, 560, 570, 580, 590, 600, 610, 620, 630, 640, 650],
    "book-catholic":    [660, 670, 680, 690, 700, 710, 720],
    "book-revelation":  [730],
}

# Predpočítaná mapa: book_id → css trieda (pre rýchle vyhľadanie)
_BOOK_ID_TO_CSS = {
    bid: cls
    for cls, ids in BOOK_CSS_CLASSES.items()
    for bid in ids
}

def get_book_css_class(book_id: int) -> str:
    """Vráti CSS triedu pre danú knihu (napr. 'book-gospels')."""
    return _BOOK_ID_TO_CSS.get(book_id, "book-default")


# ─────────────────────────────── Pomocné funkcie ─────────────────────────────

def clean_verse_text(text: str) -> str:
    text = re.sub(r"<pb/>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def verse_text_to_pango(text: str, jesus_color: str = "#c8a0f0") -> str:
    """Prevedie text verša na Pango markup. Zachová <J>...</J> s určenou farbou,
    ostatné tagy odstráni."""
    # <pb/> → medzera
    text = re.sub(r"<pb/>", " ", text)
    # Rozdelíme text na segmenty podľa <J>...</J> tagov.
    # Párne segmenty (0, 2, ...) sú normálny text, nepárne sú Ježišove slová.
    parts = re.split(r"<J>(.*?)</J>", text, flags=re.DOTALL)
    result = []
    for i, part in enumerate(parts):
        part = re.sub(r"<[^>]+>", "", part)   # odstráň ostatné tagy
        part = GLib.markup_escape_text(part)  # escapuj pre Pango
        if i % 2 == 1:
            # Použijeme farbu, ktorá prišla v parametri
            result.append(f'<span foreground="{jesus_color}">{part}</span>')
        else:
            result.append(part)
    return "".join(result).strip()


def html_to_pango(html: str) -> str:
    """Prevedie HTML z DB na Pango markup. Zachováva odkazy a základné formátovanie."""
    html = re.sub(r"<h[1-4][^>]*>(.*?)</h[1-4]>", r"\n<b>\1</b>\n", html, flags=re.DOTALL)
    html = re.sub(r"</p>\s*<p[^>]*>", "\n\n", html)
    html = re.sub(r"<br\s*/?>", "\n", html)
    html = re.sub(r"<p[^>]*>", "", html)
    html = re.sub(r"</p>", "\n", html)
    html = re.sub(r"<(?!/?(a|b|i|u)\b)[^>]+>", "", html)
    html = re.sub(r"&(?!(amp|lt|gt|quot|apos);)", "&amp;", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


# ─────────────────────────── Používateľské dáta ──────────────────────────────

class UserData:
    """Správa záložiek a poznámok uložených lokálne."""

    def __init__(self):
        self.db = sqlite3.connect(DB_USER_PATH)
        self.db.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                book_number INTEGER,
                chapter     INTEGER,
                verse       INTEGER,
                created_at  TEXT,
                PRIMARY KEY (book_number, chapter, verse)
            );
            CREATE TABLE IF NOT EXISTS notes (
                book_number INTEGER,
                chapter     INTEGER,
                verse       INTEGER,
                note_text   TEXT,
                updated_at  TEXT,
                PRIMARY KEY (book_number, chapter, verse)
            );
        """)
        self.db.commit()

    # ── záložky ──────────────────────────────────────────────────────────────

    def toggle_bookmark(self, book, chapter, verse) -> bool:
        """Prepne záložku. Vráti True ak bola pridaná, False ak odstránená."""
        if self.is_bookmarked(book, chapter, verse):
            self.db.execute(
                "DELETE FROM bookmarks WHERE book_number=? AND chapter=? AND verse=?",
                (book, chapter, verse)
            )
            self.db.commit()
            return False
        self.db.execute(
            "INSERT INTO bookmarks VALUES (?,?,?,?)",
            (book, chapter, verse, datetime.now().isoformat())
        )
        self.db.commit()
        return True

    def is_bookmarked(self, book, chapter, verse) -> bool:
        r = self.db.execute(
            "SELECT 1 FROM bookmarks WHERE book_number=? AND chapter=? AND verse=?",
            (book, chapter, verse)
        ).fetchone()
        return r is not None

    def get_bookmarks_for_chapter(self, book, chapter) -> set:
        rows = self.db.execute(
            "SELECT verse FROM bookmarks WHERE book_number=? AND chapter=?",
            (book, chapter)
        ).fetchall()
        return {r["verse"] for r in rows}

    # ── poznámky ─────────────────────────────────────────────────────────────

    def get_note(self, book, chapter, verse) -> str:
        r = self.db.execute(
            "SELECT note_text FROM notes WHERE book_number=? AND chapter=? AND verse=?",
            (book, chapter, verse)
        ).fetchone()
        return r["note_text"] if r else ""

    def save_note(self, book, chapter, verse, text: str):
        if text.strip():
            self.db.execute(
                "INSERT OR REPLACE INTO notes VALUES (?,?,?,?,?)",
                (book, chapter, verse, text, datetime.now().isoformat())
            )
        else:
            self.db.execute(
                "DELETE FROM notes WHERE book_number=? AND chapter=? AND verse=?",
                (book, chapter, verse)
            )
        self.db.commit()

    def get_notes_for_chapter(self, book, chapter) -> set:
        rows = self.db.execute(
            "SELECT verse FROM notes WHERE book_number=? AND chapter=? AND note_text != ''",
            (book, chapter)
        ).fetchall()
        return {r["verse"] for r in rows}


# ─────────────────────────────────── Aplikácia ───────────────────────────────

class BibleApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="sk.biblia.katolicka")
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        win = BibleWindow(application=app)
        win.present()


class BibleWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Sväté Písmo – Katolícky preklad")
        self.set_default_size(1250, 780)

        self.db = sqlite3.connect(DB_PATH)
        self.db.row_factory = sqlite3.Row

        self._has_comm = os.path.exists(DB_COMM_PATH)
        if self._has_comm:
            self.db_comm = sqlite3.connect(DB_COMM_PATH)
            self.db_comm.row_factory = sqlite3.Row
        else:
            self.db_comm = None

        self._has_dict = os.path.exists(DB_DICT_PATH)
        if self._has_dict:
            self.db_dict = sqlite3.connect(DB_DICT_PATH)
            self.db_dict.row_factory = sqlite3.Row
        else:
            self.db_dict = None
        self._dict_search_timeout = None

        self.user_data = UserData()

        self.current_book    = None
        self.current_chapter = None  # 0 = úvod, 1..N = kapitoly
        self.chapters_count  = 0
        self._has_intro      = False  # má aktuálna kniha úvod?
        self._verse_rows     = {}
        self._comm_map       = {}
        self._bookmark_btns  = {}
        self._note_btns      = {}
        self._current_left_tab   = "st"   # aktívny tab v ľavom paneli
        self._predslov_sections  = []     # lazy-loaded sekcie z uvody.htm
        self._showing_predslov   = False  # True keď je zobrazený predslov (nie kniha)

        # Navigačná história
        self._nav_history      = []   # zoznam (book, chapter)
        self._nav_pos          = -1   # aktuálna pozícia v histórii
        self._in_history_nav   = False  # True počas back/forward navigácie

        # Odložený skok na verš po načítaní kapitoly (používa sa pri záložkách/poznámkach)
        self._pending_verse    = None
        self._pending_scroll_pos = None  # obnoví scroll po načítaní kapitoly

        # TTS
        self._tts_proc         = None   # aktuálny subprocess

        # Nastavenie predvolenej témy (tmavá)
        self.is_dark_theme     = True

        # Pre zväčšovanie textu
        self.zoom_level = 1.0
        self.zoom_css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            self.zoom_css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
        )
        
        # ══════════════════════════════════════════════════════════════
        # NOVÉ: Jednorazové zväčšenie celého UI pre notebook
        # ══════════════════════════════════════════════════════════════
        base_font_pt = 12  # Tu si môžete meniť veľkosť, všetko sa prispôsobí
        
        ui_scale_provider = Gtk.CssProvider()
        ui_scale_provider.load_from_data(f"window {{ font-size: {base_font_pt}pt; }}".encode('utf-8'))
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            ui_scale_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        # Dynamický výpočet šírky ľavého panela (pôvodný font mal 11pt, šírka bola 340)
        scale_ratio = base_font_pt / 11.0
        self._dynamic_panel_width = int(340 * scale_ratio)
        # ══════════════════════════════════════════════════════════════

        self._build_ui()
        self._load_books()
        self._populate_predslov_list()
        self._setup_shortcuts()
        self._restore_last_position()
        self.connect("close-request", self._on_close_request)

    # ═══════════════════════════════════════════ Navigačná história ═════════

    def _push_history(self, book, chapter):
        """Pridá aktuálnu pozíciu do histórie (ignoruje sa počas back/forward)."""
        if self._in_history_nav or book is None:
            return
        entry = (book, chapter, 0)
        # Nepridávaj duplicitu po sebe (porovnávame len book+chapter)
        if self._nav_history and self._nav_pos >= 0 and \
                self._nav_history[self._nav_pos][:2] == entry[:2]:
            return
        # Odrežeme "budúcnosť" ak sme skočili späť a navigujeme nový smer
        self._nav_history = self._nav_history[:self._nav_pos + 1]
        self._nav_history.append(entry)
        # Limit histórie na 50 položiek (orežeme začiatok)
        if len(self._nav_history) > 50:
            trim = len(self._nav_history) - 50
            self._nav_history = self._nav_history[trim:]
        self._nav_pos = len(self._nav_history) - 1
        self._update_nav_buttons()
        self._save_history()


    def _save_scroll_to_history(self):
        """Uloží aktuálnu scroll pozíciu do aktuálneho záznamu v histórii."""
        if 0 <= self._nav_pos < len(self._nav_history):
            b, c, _ = self._nav_history[self._nav_pos]
            scroll = self._scroll_window.get_vadjustment().get_value()
            self._nav_history[self._nav_pos] = (b, c, scroll)

    def _go_back(self):
        if self._nav_pos <= 0:
            return
        self._save_scroll_to_history()
        self._nav_pos -= 1
        self._in_history_nav = True
        book, chapter, scroll = self._nav_history[self._nav_pos]
        self._pending_scroll_pos = scroll
        self._navigate_to_position(book, chapter)
        self._in_history_nav = False
        self._update_nav_buttons()
        self._save_history()

    def _go_forward(self):
        if self._nav_pos >= len(self._nav_history) - 1:
            return
        self._save_scroll_to_history()
        self._nav_pos += 1
        self._in_history_nav = True
        book, chapter, scroll = self._nav_history[self._nav_pos]
        self._pending_scroll_pos = scroll
        self._navigate_to_position(book, chapter)
        self._in_history_nav = False
        self._update_nav_buttons()
        self._save_history()

    def _navigate_to_position(self, book, chapter):
        """Navigácia na danú knihu/kapitolu bez zápisu do histórie."""
        if book != self.current_book:
            self._navigate_to_book(book)
        # Nastavenie kapitoly cez dropdown (spustí _on_chapter_changed)
        if self._has_intro:
            idx = chapter
        else:
            idx = max(0, chapter - 1)
        n_items = self.chapter_model.get_n_items()
        if n_items > 0:
            idx = min(idx, n_items - 1)
            self.chapter_drop.set_selected(idx)

    def _update_nav_buttons(self):
        self._btn_back.set_sensitive(self._nav_pos > 0)
        self._btn_fwd.set_sensitive(self._nav_pos < len(self._nav_history) - 1)

    def _save_history(self):
        try:
            data = {
                "history": [{"book": b, "chapter": c, "scroll": s}
                            for b, c, s in self._nav_history],
                "pos": self._nav_pos,
            }
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _restore_last_position(self):
        """Pri štarte obnoví poslednú čítanú pozíciu z history.json."""
        if not os.path.exists(HISTORY_PATH):
            return
        try:
            with open(HISTORY_PATH, encoding="utf-8") as f:
                data = json.load(f)
            history = [(e["book"], e["chapter"], e.get("scroll", 0)) for e in data.get("history", [])]
            pos     = data.get("pos", -1)
            if not history:
                return
            pos = max(0, min(pos, len(history) - 1))
            # Nastav históriu pred navigáciou (aby sa pri načítaní nepridával duplicit)
            self._nav_history = history
            self._nav_pos     = pos
            book, chapter, scroll = history[pos]
            self._in_history_nav = True
            self._pending_scroll_pos = scroll
            self._navigate_to_book(book)
            # Počkaj, kým sa model naplní, potom nastav kapitolu
            def _set_chapter():
                if self._has_intro:
                    idx = chapter
                else:
                    idx = max(0, chapter - 1)
                n = self.chapter_model.get_n_items()
                if n > 0:
                    self.chapter_drop.set_selected(min(idx, n - 1))
                self._in_history_nav = False
                self._update_nav_buttons()
                return False
            GLib.idle_add(_set_chapter)
        except Exception:
            self._in_history_nav = False

    def _on_close_request(self, window):
        """Uloží históriu a uprace zdroje pred zatvorením."""
        self._stop_tts()
        self._save_history()
        
        # Zrušenie naplánovaného časovača pre slovník
        if hasattr(self, '_dict_search_timeout') and self._dict_search_timeout is not None:
            GLib.source_remove(self._dict_search_timeout)
            self._dict_search_timeout = None
    
        # Explicitné ukončenie aplikácie – zabezpečí, že proces skutočne skončí
        app = self.get_application()
        if app:
            app.quit()
        
        return False   # False = okno sa normálne zavrie

    # ═══════════════════════════════════════════ Klávesové skratky ══════════

    def _setup_shortcuts(self):
        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if state & Gdk.ModifierType.CONTROL_MASK:
            if keyval in [Gdk.KEY_plus, Gdk.KEY_KP_Add, Gdk.KEY_equal]:
                self._update_zoom(self.zoom_level + 0.1)
                return True
            elif keyval in [Gdk.KEY_minus, Gdk.KEY_KP_Subtract]:
                self._update_zoom(self.zoom_level - 0.1)
                return True
            elif keyval in [Gdk.KEY_0, Gdk.KEY_KP_0]:
                self._update_zoom(1.0)
                return True
            elif keyval == Gdk.KEY_f:
                self.search_toggle.set_active(not self.search_toggle.get_active())
                return True
        if state & Gdk.ModifierType.ALT_MASK:
            if keyval == Gdk.KEY_Left:
                self._go_back()
                return True
            elif keyval == Gdk.KEY_Right:
                self._go_forward()
                return True
        if keyval == Gdk.KEY_Escape and self.search_toggle.get_active():
            self.search_toggle.set_active(False)
            return True
        return False

    def _update_zoom(self, new_level):
        self.zoom_level = max(0.5, min(new_level, 3.0))
        css = f"""
            .verse-text {{ font-size: {1.05 * self.zoom_level}em; }}
            .verse-number {{ font-size: {0.78 * self.zoom_level}em; }}
            .comm-text {{ font-size: {0.97 * self.zoom_level}em; }}
        """
        self.zoom_css_provider.load_from_data(css.encode('utf-8'))

    # ═══════════════════════════════════════════ Stavba rozhrania ═══════════

    def _build_ui(self):
        self.split_main = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.split_main.set_position(self._dynamic_panel_width)
        self.split_main.set_resize_start_child(False)   # ľavý panel drží šírku
        self.split_main.set_shrink_start_child(False)   # nedá sa zmenšiť pod min
        self.split_main.set_resize_end_child(True)      # pravý panel berie zvyšok
        self.set_content(self.split_main)
        self._build_book_panel()
        self._build_reading_panel()
        self._apply_css()

    # ─────────────────────────── Ľavý panel – knihy ──────────────────────────

    def _build_book_panel(self):
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left_box.set_size_request(self._dynamic_panel_width, -1)
        
        # ── 3 horizontálne prepínacie taby ────────────────────────────────────
        tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tab_box.add_css_class("linked")
        tab_box.set_homogeneous(True)
        tab_box.set_margin_start(6)
        tab_box.set_margin_end(6)
        tab_box.set_margin_top(8)
        tab_box.set_margin_bottom(6)

        self._left_tab_btns = {}
        for key, label in [
            ("predslov", "Predslov"),
            ("st",       "Starý zákon"),
            ("nt",       "Nový zákon"),
        ]:
            btn = Gtk.ToggleButton(label=label)
            btn.add_css_class("left-tab-btn")
            btn.connect("clicked", self._on_left_tab_clicked, key)
            tab_box.append(btn)
            self._left_tab_btns[key] = btn

        left_box.append(tab_box)
        left_box.append(Gtk.Separator())

        # ── Stack pre tri pohľady ──────────────────────────────────────────────
        self.left_stack = Gtk.Stack()
        self.left_stack.set_vexpand(True)
        self.left_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.left_stack.set_transition_duration(120)

        # Strana "predslov" – zoznam tém z uvody.htm
        scroll_ps = Gtk.ScrolledWindow()
        scroll_ps.set_vexpand(True)
        scroll_ps.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.predslov_list = Gtk.ListBox()
        self.predslov_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.predslov_list.add_css_class("navigation-sidebar")
        self.predslov_list.connect("row-selected", self._on_predslov_topic_selected)
        scroll_ps.set_child(self.predslov_list)
        self.left_stack.add_named(scroll_ps, "predslov")

        # Strana "st" – knihy Starého zákona
        scroll_st = Gtk.ScrolledWindow()
        scroll_st.set_vexpand(True)
        scroll_st.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.st_list = Gtk.ListBox()
        self.st_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.st_list.add_css_class("navigation-sidebar")
        self.st_list.connect("row-selected", self._on_book_selected)
        scroll_st.set_child(self.st_list)
        self.left_stack.add_named(scroll_st, "st")

        # Strana "nt" – knihy Nového zákona
        scroll_nt = Gtk.ScrolledWindow()
        scroll_nt.set_vexpand(True)
        scroll_nt.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.nt_list = Gtk.ListBox()
        self.nt_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nt_list.add_css_class("navigation-sidebar")
        self.nt_list.connect("row-selected", self._on_book_selected)
        scroll_nt.set_child(self.nt_list)
        self.left_stack.add_named(scroll_nt, "nt")

        left_box.append(self.left_stack)
        self.split_main.set_start_child(left_box)

        # Predvolene: Starý zákon
        self._left_tab_btns["st"].set_active(True)
        self.left_stack.set_visible_child_name("st")

    # ─────────────────────── Prepínanie tabov ľavého panela ──────────────────

    def _on_left_tab_clicked(self, btn, key):
        if not btn.get_active():
            # Zabráni odznačeniu aktívneho tlaičdla kliknutím naň
            if self._current_left_tab == key:
                btn.set_active(True)
            return
        # Odznač ostatné
        for k, b in self._left_tab_btns.items():
            if k != key:
                b.set_active(False)
        self._current_left_tab = key
        self.left_stack.set_visible_child_name(key)

    # ─────────────────────── Navigácia na knihu (helper) ────────────────────

    def _navigate_to_book(self, book_num):
        """Prepne na správny tab a vyberie knihu v zozname."""
        tab = "st" if book_num < 470 else "nt"
        if self._current_left_tab != tab:
            self._left_tab_btns[tab].set_active(True)
            self._on_left_tab_clicked(self._left_tab_btns[tab], tab)
        listbox = self.st_list if tab == "st" else self.nt_list
        child = listbox.get_first_child()
        while child:
            if hasattr(child, "_book_number") and child._book_number == book_num:
                # Ak je riadok už vybraný (napr. pri návrate z predslov),
                # GTK4 nevyšle row-selected znovu – odznačíme a znovu vyberieme
                if listbox.get_selected_row() == child:
                    listbox.select_row(None)
                listbox.select_row(child)
                break
            child = child.get_next_sibling()

    # ─────────────────────────── Pravý panel – čítanie ───────────────────────

    def _build_reading_panel(self):
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)

        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        nav_box.set_margin_start(12)
        nav_box.set_margin_end(4)

        # Tlačidlá histórie: Späť / Vpred
        self._btn_back = Gtk.Button(icon_name="edit-undo-symbolic")
        self._btn_back.set_tooltip_text("Späť v histórii")
        self._btn_back.set_sensitive(False)
        self._btn_back.connect("clicked", lambda _: self._go_back())
        nav_box.append(self._btn_back)

        self._btn_fwd = Gtk.Button(icon_name="edit-redo-symbolic")
        self._btn_fwd.set_tooltip_text("Vpred v histórii")
        self._btn_fwd.set_sensitive(False)
        self._btn_fwd.connect("clicked", lambda _: self._go_forward())
        nav_box.append(self._btn_fwd)

        sep_hist = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep_hist.set_margin_start(2)
        sep_hist.set_margin_end(2)
        nav_box.append(sep_hist)

        self._lbl_kapitola = Gtk.Label(label="Kapitola:")
        nav_box.append(self._lbl_kapitola)

        self.chapter_model = Gtk.StringList()
        self.chapter_drop = Gtk.DropDown(model=self.chapter_model)
        self.chapter_drop.set_valign(Gtk.Align.CENTER)
        self.chapter_drop.connect("notify::selected", self._on_chapter_changed)
        nav_box.append(self.chapter_drop)

        self._btn_chap_prev = Gtk.Button(icon_name="go-previous-symbolic")
        self._btn_chap_prev.set_tooltip_text("Predchádzajúca kapitola")
        self._btn_chap_prev.connect("clicked", lambda _: self._step_chapter(-1))
        nav_box.append(self._btn_chap_prev)

        self._btn_chap_next = Gtk.Button(icon_name="go-next-symbolic")
        self._btn_chap_next.set_tooltip_text("Nasledujúca kapitola")
        self._btn_chap_next.connect("clicked", lambda _: self._step_chapter(1))
        nav_box.append(self._btn_chap_next)

        self._sep_verse = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self._sep_verse.set_margin_start(6)
        self._sep_verse.set_margin_end(6)
        nav_box.append(self._sep_verse)

        self._lbl_vers = Gtk.Label(label="Verš:")
        nav_box.append(self._lbl_vers)

        self.verse_model = Gtk.StringList()
        self.verse_drop = Gtk.DropDown(model=self.verse_model)
        self.verse_drop.set_valign(Gtk.Align.CENTER)
        self.verse_drop.connect("notify::selected", self._on_verse_jump)
        nav_box.append(self.verse_drop)

        header.pack_start(nav_box)
        self.set_title("")

        # Tlačidlo prehľadu záložiek a poznámok
        self.bookmarks_toggle = Gtk.ToggleButton(icon_name="starred-symbolic")
        self.bookmarks_toggle.set_tooltip_text("Záložky a poznámky")
        self.bookmarks_toggle.connect("toggled", self._on_bookmarks_toggled)
        header.pack_end(self.bookmarks_toggle)

        # Tlačidlo slovníka
        self.dict_toggle = Gtk.ToggleButton(icon_name="accessories-dictionary-symbolic")
        self.dict_toggle.set_tooltip_text("Biblický slovník (Novotný)")
        self.dict_toggle.connect("toggled", self._on_dict_toggled)
        header.pack_end(self.dict_toggle)

        # Tlačidlo vyhľadávania (pred zatváracím X)
        self.search_toggle = Gtk.ToggleButton(icon_name="system-search-symbolic")
        self.search_toggle.set_tooltip_text("Hľadaj v Biblii (Ctrl+F)")
        self.search_toggle.connect("toggled", self._on_search_toggled)
        header.pack_end(self.search_toggle)

        # Tlačidlo TTS – prečítaj zobrazený text
        self.tts_toggle = Gtk.ToggleButton(icon_name="media-playback-start-symbolic")
        self.tts_toggle.set_tooltip_text("Prečítaj zobrazený text")
        self.tts_toggle.connect("toggled", self._on_tts_toggled)
        header.pack_end(self.tts_toggle)

        # NOVÉ: Tlačidlo pre prepínanie tém (svetlá / tmavá)
        # Použijeme ikonu slnka, ak začíname v tmavej téme
        self.theme_btn = Gtk.Button(icon_name="display-brightness-symbolic")
        self.theme_btn.set_tooltip_text("Prepnúť svetlú/tmavú tému")
        self.theme_btn.connect("clicked", self._on_theme_toggle_clicked)
        header.pack_end(self.theme_btn)

        right_box.append(header)

        # ── Panel vyhľadávania (skrytý, vysunie sa pod headrom) ──────────────
        self._build_search_bar(right_box)

        self.book_title_label = Gtk.Label()
        self.book_title_label.set_markup("<b>Vyberte knihu</b>")
        self.book_title_label.set_margin_top(10)
        self.book_title_label.set_margin_bottom(4)
        self.book_title_label.set_margin_start(16)
        self.book_title_label.set_halign(Gtk.Align.START)
        self.book_title_label.add_css_class("title-2")
        right_box.append(self.book_title_label)

        self.info_label = Gtk.Label()
        self.info_label.set_margin_start(16)
        self.info_label.set_margin_bottom(6)
        self.info_label.set_halign(Gtk.Align.START)
        self.info_label.add_css_class("caption")
        right_box.append(self.info_label)

        right_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Zásobník: čítanie ↔ výsledky vyhľadávania
        self.content_stack = Gtk.Stack()
        self.content_stack.set_vexpand(True)
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.set_transition_duration(150)

        # Strana čítania
        self.split_vert = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.split_vert.set_vexpand(True)

        scroll_verses = Gtk.ScrolledWindow()
        scroll_verses.set_vexpand(True)
        scroll_verses.set_hexpand(True)
        scroll_verses.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.verses_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.verses_box.set_margin_start(16)
        self.verses_box.set_margin_end(16)
        self.verses_box.set_margin_bottom(24)
        scroll_verses.set_child(self.verses_box)
        self._scroll_window = scroll_verses
        self.split_vert.set_start_child(scroll_verses)

        self._build_commentary_panel()
        self.content_stack.add_named(self.split_vert, "reading")

        # Strana výsledkov hľadania
        self._build_search_results_panel()

        # Strana záložiek a poznámok
        self._build_bookmarks_panel()

        # Strana slovníka
        self._build_dict_panel()

        self.content_stack.set_visible_child_name("reading")
        right_box.append(self.content_stack)
        self.split_main.set_end_child(right_box)

    # ─────────────────────────────── Panel vyhľadávania ──────────────────────

    def _build_search_bar(self, parent_box):
        """Panel vyhľadávania – vysunie sa animovane pod headrom."""
        self.search_revealer = Gtk.Revealer()
        self.search_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.search_revealer.set_transition_duration(200)
        self.search_revealer.set_reveal_child(False)

        bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar_box.set_margin_start(12)
        bar_box.set_margin_end(12)
        bar_box.set_margin_top(8)
        bar_box.set_margin_bottom(8)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Hľadaj v Biblii…")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("activate", lambda _: self._do_search())
        self.search_entry.connect("search-changed", self._on_search_text_changed)
        bar_box.append(self.search_entry)

        # Rozsah vyhľadávania
        scope_model = Gtk.StringList()
        for s in ["Celá Biblia", "Starý zákon", "Nový zákon", "Aktuálna kniha"]:
            scope_model.append(s)
        self.search_scope_drop = Gtk.DropDown(model=scope_model)
        self.search_scope_drop.set_valign(Gtk.Align.CENTER)
        bar_box.append(self.search_scope_drop)

        btn_search = Gtk.Button(label="Hľadaj")
        btn_search.add_css_class("suggested-action")
        btn_search.connect("clicked", lambda _: self._do_search())
        bar_box.append(btn_search)

        self.search_revealer.set_child(bar_box)
        parent_box.append(self.search_revealer)

    def _build_search_results_panel(self):
        """Panel s výsledkami vyhľadávania."""
        results_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.search_results_info = Gtk.Label()
        self.search_results_info.set_margin_start(16)
        self.search_results_info.set_margin_top(8)
        self.search_results_info.set_margin_bottom(4)
        self.search_results_info.set_halign(Gtk.Align.START)
        self.search_results_info.add_css_class("caption")
        results_outer.append(self.search_results_info)

        scroll_results = Gtk.ScrolledWindow()
        scroll_results.set_vexpand(True)
        scroll_results.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.search_results_list = Gtk.ListBox()
        self.search_results_list.add_css_class("boxed-list")
        self.search_results_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.search_results_list.set_margin_start(12)
        self.search_results_list.set_margin_end(12)
        self.search_results_list.set_margin_top(4)
        self.search_results_list.set_margin_bottom(16)
        self.search_results_list.connect("row-activated", self._on_search_result_activated)
        scroll_results.set_child(self.search_results_list)
        results_outer.append(scroll_results)

        self.content_stack.add_named(results_outer, "results")

    def _build_bookmarks_panel(self):
        """Panel so záložkami a poznámkami."""
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Predvolený stav pre prepínanie
        self._bookmarks_active_tab = "bookmarks"

        # ── Hlavička panela (Taby a Export/Import) ──
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header_box.set_margin_start(16)
        header_box.set_margin_end(12)
        header_box.set_margin_top(12)
        header_box.set_margin_bottom(8)

        # Ľavá strana: Prepínacie tlačidlá (Záložky / Poznámky)
        tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tab_box.add_css_class("linked")
        
        self.btn_tab_bm = Gtk.ToggleButton(label="Záložky")
        self.btn_tab_bm.set_active(True)
        self.btn_tab_bm.connect("toggled", self._on_bookmark_tab_toggled, "bookmarks")
        tab_box.append(self.btn_tab_bm)

        self.btn_tab_notes = Gtk.ToggleButton(label="Poznámky")
        self.btn_tab_notes.set_group(self.btn_tab_bm) # Prepojenie správania ako rádio tlačidlá
        self.btn_tab_notes.connect("toggled", self._on_bookmark_tab_toggled, "notes")
        tab_box.append(self.btn_tab_notes)

        header_box.append(tab_box)

        # Vyplnenie priestoru uprostred
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_box.append(spacer)

        # Pravá strana: Import / Export tlačidlá
        io_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        btn_import = Gtk.Button()
        btn_import.set_icon_name("document-open-symbolic")
        btn_import.set_tooltip_text("Importovať")
        btn_import.add_css_class("flat")
        btn_import.connect("clicked", self._on_import_clicked)
        io_box.append(btn_import)

        btn_export = Gtk.Button()
        btn_export.set_icon_name("document-save-symbolic")
        btn_export.set_tooltip_text("Exportovať")
        btn_export.add_css_class("flat")
        btn_export.connect("clicked", self._on_export_clicked)
        io_box.append(btn_export)

        header_box.append(io_box)
        outer.append(header_box)

        # Informačný text o počte (pod hlavičkou)
        self.bookmarks_info = Gtk.Label()
        self.bookmarks_info.set_margin_start(16)
        self.bookmarks_info.set_margin_bottom(4)
        self.bookmarks_info.set_halign(Gtk.Align.START)
        self.bookmarks_info.add_css_class("caption")
        outer.append(self.bookmarks_info)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.bookmarks_list = Gtk.ListBox()
        self.bookmarks_list.add_css_class("boxed-list")
        self.bookmarks_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.bookmarks_list.set_margin_start(12)
        self.bookmarks_list.set_margin_end(12)
        self.bookmarks_list.set_margin_top(4)
        self.bookmarks_list.set_margin_bottom(16)
        self.bookmarks_list.connect("row-activated", self._on_bookmark_result_activated)
        scroll.set_child(self.bookmarks_list)
        outer.append(scroll)

        self.content_stack.add_named(outer, "bookmarks")

    def _on_bookmarks_toggled(self, toggle):
        active = toggle.get_active()
        if active:
            self.search_toggle.set_active(False)
            self.dict_toggle.set_active(False)
            self._populate_bookmarks_panel()
            self.content_stack.set_visible_child_name("bookmarks")
        else:
            self.content_stack.set_visible_child_name("reading")

    def _on_bookmark_tab_toggled(self, btn, tab_name):
        if btn.get_active():
            self._bookmarks_active_tab = tab_name
            self._populate_bookmarks_panel()

    # ── Export a Import záložiek/poznámok ──
    
    def _on_export_clicked(self, btn):
        dialog = Gtk.FileDialog(title="Exportovať záložky a poznámky", initial_name="biblia_zalozky.json")
        dialog.save(self, None, self._on_export_save_ready)

    def _on_export_save_ready(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                self._do_export(file.get_path())
        except GLib.Error:
            pass  # Používateľ zrušil dialóg

    def _do_export(self, filepath):
        try:
            bm_rows = self.user_data.db.execute("SELECT * FROM bookmarks").fetchall()
            note_rows = self.user_data.db.execute("SELECT * FROM notes").fetchall()
            
            data = {
                "bookmarks": [dict(r) for r in bm_rows],
                "notes": [dict(r) for r in note_rows]
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            self.bookmarks_info.set_markup("<span alpha='70%'>Úspešne exportované.</span>")
        except Exception as e:
            self.bookmarks_info.set_markup(f"<span alpha='70%' foreground='red'>Chyba exportu: {e}</span>")

    def _on_import_clicked(self, btn):
        dialog = Gtk.FileDialog(title="Importovať záložky a poznámky")
        dialog.open(self, None, self._on_import_open_ready)

    def _on_import_open_ready(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self._do_import(file.get_path())
        except GLib.Error:
            pass  # Používateľ zrušil dialóg

    def _do_import(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if "bookmarks" in data:
                for b in data["bookmarks"]:
                    self.user_data.db.execute(
                        "INSERT OR REPLACE INTO bookmarks VALUES (?,?,?,?)",
                        (b["book_number"], b["chapter"], b["verse"], b.get("created_at", datetime.now().isoformat()))
                    )
            if "notes" in data:
                for n in data["notes"]:
                    self.user_data.db.execute(
                        "INSERT OR REPLACE INTO notes VALUES (?,?,?,?,?)",
                        (n["book_number"], n["chapter"], n["verse"], n["note_text"], n.get("updated_at", datetime.now().isoformat()))
                    )
            
            self.user_data.db.commit()
            self._populate_bookmarks_panel()
            
            # Rýchla vizuálna spätná väzba
            self.bookmarks_info.set_markup("<span alpha='70%' foreground='green'>Úspešne importované.</span>")
            GLib.timeout_add(3000, self._populate_bookmarks_panel) # Obnoví pôvodný label po 3 sekundách
            
        except Exception as e:
            self.bookmarks_info.set_markup(f"<span alpha='70%' foreground='red'>Chyba importu: {e}</span>")

    def _populate_bookmarks_panel(self):
        """Naplní panel aktuálne vybraným typom položiek (Záložky alebo Poznámky)."""
        # Vymazanie starých položiek
        child = self.bookmarks_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.bookmarks_list.remove(child)
            child = nxt

        self.db.execute(f"ATTACH DATABASE '{DB_USER_PATH}' AS udb")
        try:
            if self._bookmarks_active_tab == "bookmarks":
                rows = self.db.execute(
                    """SELECT bm.book_number, bm.chapter, bm.verse, bm.created_at,
                              b.short_name, b.long_name
                       FROM udb.bookmarks bm
                       JOIN books b ON b.book_number = bm.book_number
                       ORDER BY bm.book_number, bm.chapter, bm.verse"""
                ).fetchall()
            else:
                rows = self.db.execute(
                    """SELECT n.book_number, n.chapter, n.verse, n.note_text, n.updated_at,
                              b.short_name, b.long_name
                       FROM udb.notes n
                       JOIN books b ON b.book_number = n.book_number
                       WHERE n.note_text != ''
                       ORDER BY n.book_number, n.chapter, n.verse"""
                ).fetchall()
        finally:
            self.db.execute("DETACH DATABASE udb")

        # Aktualizácia informačného textu
        count = len(rows)
        if self._bookmarks_active_tab == "bookmarks":
            label_txt = f"{count} záložiek" if count != 1 else "1 záložka"
            if count == 0: label_txt = "Nemáte zatiaľ žiadne záložky."
        else:
            label_txt = f"{count} poznámok" if count != 1 else "1 poznámka"
            if count == 0: label_txt = "Nemáte zatiaľ žiadne poznámky."

        self.bookmarks_info.set_markup(f"<span alpha='70%'>{label_txt}</span>")

        # Pridanie samotných riadkov do zoznamu
        for r in rows:
            if self._bookmarks_active_tab == "bookmarks":
                self.bookmarks_list.append(self._make_bookmark_row(r))
            else:
                self.bookmarks_list.append(self._make_note_row(r))
        
        return False # Dôležité pre timeout callback

    def _ref_label_text(self, r) -> str:
        book_name = r["long_name"]
        if "(" in book_name:
            book_name = book_name[:book_name.index("(")].strip()
        return (
            f"<b>{GLib.markup_escape_text(r['short_name'])}</b>"
            f"  <span alpha='70%'>"
            f"{GLib.markup_escape_text(book_name)}  "
            f"{r['chapter']},{r['verse']}</span>"
        )

    def _make_bookmark_row(self, r) -> Gtk.ListBoxRow:
        book_num, chapter, verse = r["book_number"], r["chapter"], r["verse"]

        list_row = Gtk.ListBoxRow()
        list_row.set_activatable(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        outer.set_margin_start(12); outer.set_margin_end(4)
        outer.set_margin_top(4);   outer.set_margin_bottom(4)

        # Ľavá časť – ikona + referencia + prípadná poznámka
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left.set_hexpand(True)
        left.set_valign(Gtk.Align.CENTER)

        ref_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        icon = Gtk.Image.new_from_icon_name("starred-symbolic")
        icon.add_css_class("bookmark-btn-on")
        ref_box.append(icon)
        ref_lbl = Gtk.Label()
        ref_lbl.set_markup(self._ref_label_text(r))
        ref_lbl.set_halign(Gtk.Align.START)
        ref_box.append(ref_lbl)
        left.append(ref_box)

        outer.append(left)

        # Pravá časť – akčné tlačidlá
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        btn_box.set_valign(Gtk.Align.CENTER)

        # Tlačidlo: pridať/upraviť poznámku
        existing_note = self.user_data.get_note(book_num, chapter, verse)
        btn_note = Gtk.Button(
            icon_name="document-edit-symbolic" if existing_note else "document-new-symbolic"
        )
        btn_note.add_css_class("flat")
        btn_note.set_tooltip_text("Upraviť poznámku" if existing_note else "Pridať poznámku k záložke")
        btn_note.set_valign(Gtk.Align.CENTER)

        def _on_note_for_bookmark(btn, bn=book_num, ch=chapter, vs=verse,
                                   nb=btn_note):
            def _after_save():
                new_note = self.user_data.get_note(bn, ch, vs)
                nb.set_icon_name(
                    "document-edit-symbolic" if new_note else "document-new-symbolic"
                )
                nb.set_tooltip_text(
                    "Upraviť poznámku" if new_note else "Pridať poznámku k záložke"
                )
                # Obnov aj panel záložiek (počet sa mohol zmeniť)
                self._populate_bookmarks_panel()

            self._show_note_dialog_with_callback(bn, ch, vs, _after_save)

        btn_note.connect("clicked", _on_note_for_bookmark)
        btn_box.append(btn_note)

        # Tlačidlo: zmazať záložku
        btn_del = Gtk.Button(icon_name="user-trash-symbolic")
        btn_del.add_css_class("flat")
        btn_del.set_tooltip_text("Odstrániť záložku")
        btn_del.set_valign(Gtk.Align.CENTER)

        def _on_delete_bookmark(btn, bn=book_num, ch=chapter, vs=verse):
            self.user_data.toggle_bookmark(bn, ch, vs)  # odstráni (je tam)
            # Skry indikátor v čítaní ak je tá istá kapitola
            if bn == self.current_book and ch == self.current_chapter:
                bm_icon = self._bookmark_btns.get(vs)
                if bm_icon:
                    bm_icon.set_visible(False)
            self._populate_bookmarks_panel()

        btn_del.connect("clicked", _on_delete_bookmark)
        btn_box.append(btn_del)

        outer.append(btn_box)
        list_row.set_child(outer)
        list_row._nav = (book_num, chapter, verse)
        return list_row

    def _make_note_row(self, r) -> Gtk.ListBoxRow:
        book_num, chapter, verse = r["book_number"], r["chapter"], r["verse"]
        note_text = r["note_text"]

        # Poznámka je "dlhá" ak má viac ako 3 riadky alebo viac ako 200 znakov
        _lines = note_text.split("\n")
        _is_long = len(_lines) > 3 or len(note_text) > 200

        list_row = Gtk.ListBoxRow()
        list_row.set_activatable(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        outer.set_margin_start(12); outer.set_margin_end(4)
        outer.set_margin_top(4);   outer.set_margin_bottom(4)

        # Ľavá časť – ikona + referencia + text poznámky
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left.set_hexpand(True)
        left.set_valign(Gtk.Align.START)

        ref_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        icon = Gtk.Image.new_from_icon_name("document-edit-symbolic")
        icon.add_css_class("note-btn-on")
        ref_box.append(icon)
        ref_lbl = Gtk.Label()
        ref_lbl.set_markup(self._ref_label_text(r))
        ref_lbl.set_halign(Gtk.Align.START)
        ref_box.append(ref_lbl)
        left.append(ref_box)

        # Skrátený náhľad (max 3 riadky)
        preview_text = "\n".join(_lines[:3])
        if len(_lines) > 3:
            preview_text += " …"

        note_preview = Gtk.Label(label=preview_text)
        note_preview.set_halign(Gtk.Align.START)
        note_preview.set_wrap(True)
        note_preview.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        note_preview.add_css_class("caption")
        left.append(note_preview)

        if _is_long:
            # Plný text – skrytý kým nie je rozbalený
            note_full = Gtk.Label(label=note_text)
            note_full.set_halign(Gtk.Align.START)
            note_full.set_wrap(True)
            note_full.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            note_full.add_css_class("caption")
            note_full.set_visible(False)
            left.append(note_full)

            _expanded = [False]
            btn_expand = Gtk.Button()
            btn_expand.add_css_class("flat")
            btn_expand.add_css_class("note-expand-btn")
            btn_expand.set_halign(Gtk.Align.START)
            btn_expand.set_margin_top(1)

            expand_lbl = Gtk.Label()
            expand_lbl.set_markup(
                "<span size='small' alpha='75%'>▸ Zobraziť celú poznámku</span>"
            )
            btn_expand.set_child(expand_lbl)

            def _toggle_expand(btn, lbl=expand_lbl,
                               preview=note_preview, full=note_full,
                               state=_expanded):
                state[0] = not state[0]
                if state[0]:
                    preview.set_visible(False)
                    full.set_visible(True)
                    lbl.set_markup(
                        "<span size='small' alpha='75%'>▾ Zobraziť menej</span>"
                    )
                else:
                    full.set_visible(False)
                    preview.set_visible(True)
                    lbl.set_markup(
                        "<span size='small' alpha='75%'>▸ Zobraziť celú poznámku</span>"
                    )

            btn_expand.connect("clicked", _toggle_expand)
            left.append(btn_expand)

        outer.append(left)

        # Pravá časť – akčné tlačidlá
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        btn_box.set_valign(Gtk.Align.CENTER)

        # Tlačidlo: upraviť poznámku
        btn_edit = Gtk.Button(icon_name="document-edit-symbolic")
        btn_edit.add_css_class("flat")
        btn_edit.set_tooltip_text("Upraviť poznámku")
        btn_edit.set_valign(Gtk.Align.CENTER)

        def _on_edit_note(btn, bn=book_num, ch=chapter, vs=verse):
            def _after_save():
                self._populate_bookmarks_panel()
                # Obnov indikátor v čítaní ak je tá istá kapitola
                if bn == self.current_book and ch == self.current_chapter:
                    note_icon = self._note_btns.get(vs)
                    if note_icon:
                        has = bool(self.user_data.get_note(bn, ch, vs))
                        note_icon.set_visible(has)

            self._show_note_dialog_with_callback(bn, ch, vs, _after_save)

        btn_edit.connect("clicked", _on_edit_note)
        btn_box.append(btn_edit)

        # Tlačidlo: zmazať poznámku
        btn_del = Gtk.Button(icon_name="user-trash-symbolic")
        btn_del.add_css_class("flat")
        btn_del.set_tooltip_text("Odstrániť poznámku")
        btn_del.set_valign(Gtk.Align.CENTER)

        def _on_delete_note(btn, bn=book_num, ch=chapter, vs=verse):
            self.user_data.save_note(bn, ch, vs, "")  # prázdny text = zmazanie
            if bn == self.current_book and ch == self.current_chapter:
                note_icon = self._note_btns.get(vs)
                if note_icon:
                    note_icon.set_visible(False)
            self._populate_bookmarks_panel()

        btn_del.connect("clicked", _on_delete_note)
        btn_box.append(btn_del)

        outer.append(btn_box)
        list_row.set_child(outer)
        list_row._nav = (book_num, chapter, verse)
        return list_row

    def _show_note_dialog_with_callback(self, book, chapter, verse, on_save_cb):
        """Otvorí dialóg poznámky; po uložení zavolá on_save_cb()."""
        book_row = self.db.execute(
            "SELECT short_name FROM books WHERE book_number=?", (book,)
        ).fetchone()
        abbr = book_row["short_name"] if book_row else "?"

        dialog = Gtk.Window()
        dialog.set_title(f"Poznámka – {abbr} {chapter},{verse}")
        dialog.set_modal(True)
        dialog.set_transient_for(self)
        dialog.set_default_size(440, 300)
        dialog.set_resizable(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        dialog.set_child(outer)

        dlg_header = Adw.HeaderBar()
        dlg_header.set_show_end_title_buttons(False)
        btn_cancel = Gtk.Button(label="Zrušiť")
        btn_cancel.connect("clicked", lambda _: dialog.close())
        dlg_header.pack_start(btn_cancel)
        btn_save = Gtk.Button(label="Uložiť")
        btn_save.add_css_class("suggested-action")
        dlg_header.pack_end(btn_save)
        outer.append(dlg_header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        text_view = Gtk.TextView()
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_margin_start(14); text_view.set_margin_end(14)
        text_view.set_margin_top(12);  text_view.set_margin_bottom(12)
        text_view.set_accepts_tab(False)
        buf = text_view.get_buffer()
        buf.set_text(self.user_data.get_note(book, chapter, verse))
        buf.place_cursor(buf.get_end_iter())
        scroll.set_child(text_view)
        outer.append(scroll)

        def _save(_btn):
            start, end = buf.get_bounds()
            self.user_data.save_note(book, chapter, verse, buf.get_text(start, end, False))
            dialog.close()
            on_save_cb()

        btn_save.connect("clicked", _save)

        key_ctrl = Gtk.EventControllerKey.new()
        def _dlg_key(ctrl, keyval, keycode, state):
            if (state & Gdk.ModifierType.CONTROL_MASK) and keyval == Gdk.KEY_Return:
                _save(None); return True
            if keyval == Gdk.KEY_Escape:
                dialog.close(); return True
            return False
        key_ctrl.connect("key-pressed", _dlg_key)
        dialog.add_controller(key_ctrl)

        dialog.present()
        GLib.idle_add(text_view.grab_focus)

    def _on_bookmark_result_activated(self, listbox, row):
        if not hasattr(row, "_nav"):
            return
        book_num, chapter, verse = row._nav

        self.bookmarks_toggle.set_active(False)
        self.content_stack.set_visible_child_name("reading")

        # Ak je zobrazený predslov, chapter_model je prázdny – treba vždy
        # znovu inicializovať knihu, aj keď je to tá istá ako current_book
        if book_num != self.current_book or self._showing_predslov:
            self._navigate_to_book(book_num)

        # Uložíme cieľový verš; _load_chapter ho aplikuje po zostavení widgetov
        self._pending_verse = verse

        def _jump_chapter():
            if chapter != self.current_chapter:
                chap_idx = chapter if self._has_intro else max(0, chapter - 1)
                chap_idx = min(chap_idx, self.chapter_model.get_n_items() - 1)
                self.chapter_drop.set_selected(chap_idx)
            else:
                # Kapitola sa nezmenila – _load_chapter sa nespustí,
                # skočíme na verš priamo
                if self._pending_verse is not None:
                    target = self._pending_verse
                    self._pending_verse = None
                    def _direct_jump():
                        v_idx = max(0, target - 1)
                        if v_idx < self.verse_model.get_n_items():
                            self.verse_drop.set_selected(v_idx)
                        return False
                    GLib.idle_add(_direct_jump)
            return False

        GLib.idle_add(_jump_chapter)

    # ─────────────────────────────── Logika vyhľadávania ─────────────────────

    def _on_search_toggled(self, toggle):
        active = toggle.get_active()
        self.search_revealer.set_reveal_child(active)
        if active:
            self.bookmarks_toggle.set_active(False)
            self.dict_toggle.set_active(False)
            GLib.idle_add(self.search_entry.grab_focus)
        else:
            self.content_stack.set_visible_child_name("reading")

    def _on_search_text_changed(self, entry):
        q = entry.get_text().strip()
        if len(q) >= 3:
            self._do_search()
        elif len(q) == 0:
            self.content_stack.set_visible_child_name("reading")

    def _do_search(self):
        query = self.search_entry.get_text().strip()
        if len(query) < 2:
            return

        scope_idx = self.search_scope_drop.get_selected()

        if scope_idx == 0:        # Celá Biblia
            cond   = ""
            params = (f"%{query}%",)
        elif scope_idx == 1:      # Starý zákon
            cond   = "AND v.book_number < 470"
            params = (f"%{query}%",)
        elif scope_idx == 2:      # Nový zákon
            cond   = "AND v.book_number >= 470"
            params = (f"%{query}%",)
        else:                     # Aktuálna kniha
            if self.current_book is None:
                return
            cond   = "AND v.book_number = ?"
            params = (f"%{query}%", self.current_book)

        sql = f"""
            SELECT v.book_number, v.chapter, v.verse, v.text,
                   b.short_name, b.long_name
            FROM verses v
            JOIN books b ON b.book_number = v.book_number
            WHERE v.text LIKE ? {cond}
            ORDER BY v.book_number, v.chapter, v.verse
            LIMIT 500
        """
        rows = self.db.execute(sql, params).fetchall()
        self._display_search_results(rows, query)

    def _display_search_results(self, rows, query):
        # Vymazanie starých výsledkov
        child = self.search_results_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.search_results_list.remove(child)
            child = nxt

        count = len(rows)
        if count == 0:
            self.search_results_info.set_markup("<span alpha='70%'>Žiadne výsledky.</span>")
        elif count >= 500:
            self.search_results_info.set_markup(
                "<span alpha='70%'>Zobrazených prvých 500 výsledkov – spresni hľadanie.</span>"
            )
        else:
            s = "výsledok" if count == 1 else ("výsledky" if count < 5 else "výsledkov")
            self.search_results_info.set_markup(
                f"<span alpha='70%'>{count} {s}</span>"
            )

        for row in rows:
            list_row = self._build_search_result_row(row, query)
            self.search_results_list.append(list_row)

        self.content_stack.set_visible_child_name("results")

    def _build_search_result_row(self, row, query):
        list_row = Gtk.ListBoxRow()
        list_row.set_activatable(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        # Referencia: skratka + názov knihy + kapitola,verš
        book_name = row["long_name"]
        if "(" in book_name:
            book_name = book_name[:book_name.index("(")].strip()
        ref_lbl = Gtk.Label()
        ref_lbl.set_markup(
            f"<b>{GLib.markup_escape_text(row['short_name'])}</b>"
            f"  <span size='small' alpha='70%'>"
            f"{GLib.markup_escape_text(book_name)}  "
            f"{row['chapter']},{row['verse']}</span>"
        )
        ref_lbl.set_halign(Gtk.Align.START)
        box.append(ref_lbl)

        # Text verša s vyznačeným hľadaným výrazom (tučné)
        raw_text = clean_verse_text(row["text"])
        escaped  = GLib.markup_escape_text(raw_text)
        escaped_q = GLib.markup_escape_text(query)
        highlighted = re.sub(
            re.escape(escaped_q),
            lambda m: f"<b>{m.group()}</b>",
            escaped,
            flags=re.IGNORECASE
        )
        snippet = Gtk.Label()
        snippet.set_halign(Gtk.Align.START)
        snippet.set_wrap(True)
        snippet.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        try:
            snippet.set_markup(f"<span size='medium'>{highlighted}</span>")
        except Exception:
            snippet.set_text(raw_text)
        box.append(snippet)

        list_row.set_child(box)
        list_row._nav = (row["book_number"], row["chapter"], row["verse"])
        return list_row

    def _on_search_result_activated(self, listbox, row):
        if not hasattr(row, "_nav"):
            return
        book_num, chapter, verse = row._nav

        # Zavrieme vyhľadávanie, prepneme na čítanie
        self.search_toggle.set_active(False)
        self.content_stack.set_visible_child_name("reading")

        # Navigácia na knihu
        if book_num != self.current_book:
            self._navigate_to_book(book_num)

        def _jump_chapter():
            if chapter != self.current_chapter:
                chap_idx = chapter if self._has_intro else max(0, chapter - 1)
                chap_idx = min(chap_idx, self.chapter_model.get_n_items() - 1)
                self.chapter_drop.set_selected(chap_idx)
            return False

        def _jump_verse():
            v_idx = max(0, verse - 1)
            if v_idx < self.verse_model.get_n_items():
                self.verse_drop.set_selected(v_idx)
            return False

        GLib.idle_add(_jump_chapter)
        GLib.timeout_add(80, _jump_verse)

   # ─────────────────────────────────── CSS a Témy ──────────────────────────

    def _apply_css(self):
        """Inicializácia hlavného CSS providera."""
        self.main_css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            self.main_css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        # Načítanie vybranej témy zo súboru
        self._load_css_theme()
        
        # Prispôsobenie globálnych Adwaita prvkov (ako pozadie, scrollovanie, atď.)
        style_manager = Adw.StyleManager.get_default()
        if self.is_dark_theme:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)

    def _load_css_theme(self):
        """Načíta príslušný CSS súbor podľa stavu self.is_dark_theme"""
        css_file = "biblia-dark.css" if self.is_dark_theme else "biblia-light.css"
        css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), css_file)

        if os.path.exists(css_path):
            self.main_css_provider.load_from_path(css_path)
        else:
            print(f"Upozornenie: Chýba súbor témy -> {css_file}", file=sys.stderr)

    def _on_theme_toggle_clicked(self, button):
        """Prepnutie témy a zmena ikony na tlačidle"""
        self.is_dark_theme = not self.is_dark_theme
        
        # Aplikácia našich vlastných CSS pravidiel
        self._load_css_theme()
        
        # Zmena ikony (slnko pre prepnutie na svetlú, mesiac na prepnutie na tmavú)
        icon = "display-brightness-symbolic" if self.is_dark_theme else "weather-clear-night-symbolic"
        button.set_icon_name(icon)
        
        # Aplikácia pre GTK prvky rozhrania
        style_manager = Adw.StyleManager.get_default()
        if self.is_dark_theme:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)

        # Znovunačítanie aktuálnej kapitoly, aby sa aktualizovali Pango farby (Ježišove slová)
        if hasattr(self, 'current_book') and self.current_book is not None and not self._showing_predslov:
            # Uložíme si aktuálnu pozíciu scrollovania, aby obrazovka neposkočila
            adj = self._scroll_window.get_vadjustment()
            current_scroll = adj.get_value()
            
            # Znovu načítame kapitolu (tým sa aplikuje nová farba)
            self._load_chapter(self.current_chapter)
            
            # Vrátime scrollovanie na pôvodné miesto
            GLib.idle_add(lambda: adj.set_value(current_scroll) or False)


    # ════════════════════════════════════════════════ Knihy ══════════════════

    def _load_books(self):
        rows = self.db.execute(
            "SELECT book_number, short_name, long_name, book_color "
            "FROM books ORDER BY book_number"
        ).fetchall()
        self._all_books = rows
        st_books = [r for r in rows if r["book_number"] < 470]
        nt_books = [r for r in rows if r["book_number"] >= 470]
        self._populate_book_list(self.st_list, st_books)
        self._populate_book_list(self.nt_list, nt_books)

    def _populate_book_list(self, listbox, books):
        child = listbox.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            listbox.remove(child)
            child = nxt

        for row in books:
            bn = row["book_number"]
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_start(8); box.set_margin_end(8)
            box.set_margin_top(4);   box.set_margin_bottom(4)

            abbr = Gtk.Label(label=row["short_name"])
            abbr.add_css_class(get_book_css_class(bn))
            abbr.set_width_chars(5)
            abbr.set_halign(Gtk.Align.END)
            box.append(abbr)

            long = row["long_name"]
            if "(" in long:
                long = long[:long.index("(")].strip()
            name_lbl = Gtk.Label(label=long)
            name_lbl.set_halign(Gtk.Align.START)
            name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            box.append(name_lbl)

            list_row = Gtk.ListBoxRow()
            list_row.set_child(box)
            list_row._book_number    = row["book_number"]
            list_row._book_long_name = row["long_name"]
            listbox.append(list_row)

    def _on_book_selected(self, listbox, row):
        if row is None or not hasattr(row, "_book_number"):
            return
        # Zruš výber v druhom zozname
        other = self.nt_list if listbox == self.st_list else self.st_list
        other.select_row(None)
        self.current_book  = row._book_number
        self._showing_predslov = False
        self._stop_tts()
        self._close_commentary(None)

        result = self.db.execute(
            "SELECT MAX(chapter) as mc FROM verses WHERE book_number=?",
            (self.current_book,)
        ).fetchone()
        self.chapters_count = result["mc"] or 1

        # Zisti, či existuje úvod pre túto knihu
        intro_row = self.db.execute(
            "SELECT 1 FROM introductions WHERE book_number=?",
            (self.current_book,)
        ).fetchone()
        self._has_intro = intro_row is not None

        chapters = (["Úvod"] if self._has_intro else []) + \
                   [str(i) for i in range(1, self.chapters_count + 1)]
        self.chapter_model.splice(0, self.chapter_model.get_n_items(), chapters)
        self.current_chapter = 0 if self._has_intro else 1
        # Reset dropdown na index 0 – bez toho ostane vizuálne na starom čísle
        self.chapter_drop.set_selected(0)

        self.book_title_label.set_markup(
            f"<b>{GLib.markup_escape_text(row._book_long_name)}</b>"
        )
        self._load_chapter(self.current_chapter)

    # ════════════════════════════════════════════════ Kapitoly ═══════════════

    def _on_chapter_changed(self, dropdown, param):
        pos = dropdown.get_selected()
        if pos == Gtk.INVALID_LIST_POSITION:
            return
        # pos 0 = Úvod (ak existuje), inak kapitola 1
        if self._has_intro:
            chap = 0 if pos == 0 else pos   # pos 1 → kap 1, pos 2 → kap 2 ...
        else:
            chap = pos + 1
        if chap != self.current_chapter:
            self.current_chapter = chap
            self._stop_tts()
            self._close_commentary(None)
            self._load_chapter(chap)

    def _step_chapter(self, delta):
        if self.current_book is None:
            return
        min_chap = 0 if self._has_intro else 1
        new_chap = max(min_chap, min(self.chapters_count, (self.current_chapter or min_chap) + delta))
        # Preveď číslo kapitoly na index v dropdown
        if self._has_intro:
            idx = new_chap  # 0→0, 1→1, 2→2 ...
        else:
            idx = new_chap - 1
        self.chapter_drop.set_selected(idx)

    # ════════════════════════════════════════════════ Úvod ku knihe ══════════

    def _build_book_abbr_map(self) -> dict:
        """Zostaví slovník skratiek kníh → číslo knihy (vrátane variantov s medzerou)."""
        rows = self.db.execute(
            "SELECT book_number, short_name FROM books"
        ).fetchall()
        book_map = {}
        for r in rows:
            sn = r["short_name"]
            bn = r["book_number"]
            book_map[sn] = bn
            # Variant s medzerou za číslom: '1Kor' → '1 Kor'
            m = re.match(r'^([123])(.*)', sn)
            if m:
                book_map[m.group(1) + ' ' + m.group(2)] = bn
        return book_map

    def _linkify_plain_refs(self, html: str) -> str:
        """
        Konvertuje holé textové biblické odkazky (napr. 'Mt 16,17', '1 Kor 15,5')
        na <a href='B:číslo kapitola:verš'> tagy.
        Používa sa pre úvody, ktoré neobsahujú <a href> (napr. 1. Petrov list).
        """
        if not hasattr(self, '_book_abbr_map'):
            self._book_abbr_map = self._build_book_abbr_map()

        # Zoradíme skratky od najdlhšej po najkratšiu (zabránime čiastočným zhod ám)
        abbrs = sorted(self._book_abbr_map.keys(), key=len, reverse=True)
        abbr_pattern = '|'.join(re.escape(a) for a in abbrs)

        # Vzor: skratka + medzera + kapitola + voliteľne(čiarka + verš + voliteľne rozsah)
        pattern = rf'(?<!["\'])(?<!\w)\b({abbr_pattern})\s+(\d+)(?:\s*,\s*(\d+)(?:\s*[-–]\s*\d+)?(?:\s*\.\s*\d+)?)?'

        def _replace(m):
            abbr  = m.group(1)
            chap  = m.group(2)
            verse = m.group(3)
            book_num = self._book_abbr_map.get(abbr)
            if book_num is None:
                return m.group(0)
            href = f"B:{book_num} {chap}:{verse}" if verse else f"B:{book_num} {chap}"
            return f"<a href='{href}'>{m.group(0)}</a>"

        # Spracujeme len textový obsah mimo existujúcich HTML tagov
        def _replace_outside_tags(text):
            result = []
            pos = 0
            for tag_m in re.finditer(r'<[^>]+>', text):
                # Textová časť pred tagom
                segment = text[pos:tag_m.start()]
                result.append(re.sub(pattern, _replace, segment))
                result.append(tag_m.group(0))
                pos = tag_m.end()
            result.append(re.sub(pattern, _replace, text[pos:]))
            return ''.join(result)

        return _replace_outside_tags(html)

    def _on_intro_link_clicked(self, label, uri):
        """Handler pre kliknutie na odkaz v úvode knihy."""
        if uri.startswith("B:"):
            return self._on_comm_link_clicked(label, uri[2:])
        return False

    # ════════════════════════════════════════════════ Predslov SSV ══════════

    def _load_predslov_from_db(self) -> list:
        """Načíta len anchor + title sekcií predslov (bez html – to sa načíta až po kliknutí)."""
        if not os.path.exists(DB_PREDSLOV_PATH):
            return []
        db = sqlite3.connect(DB_PREDSLOV_PATH)
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT id, anchor, title FROM sections ORDER BY id"
        ).fetchall()
        db.close()
        return [{"id": r["id"], "anchor": r["anchor"], "title": r["title"]}
                for r in rows]

    def _load_predslov_html(self, section_id: int) -> str:
        """Načíta html obsah jednej sekcie predslov z oddelenej tabuľky sections_html."""
        db = sqlite3.connect(DB_PREDSLOV_PATH)
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT html FROM sections_html WHERE id=?", (section_id,)
        ).fetchone()
        db.close()
        return row["html"] if row else ""

    def _populate_predslov_list(self):
        """Naplní zoznam tém predslovov pri štarte (rovnako ako ST/NT)."""

        self._predslov_sections = self._load_predslov_from_db()

        if not self._predslov_sections:
            err_row = Gtk.ListBoxRow()
            err_row.set_selectable(False)
            err_lbl = Gtk.Label(label="Súbor predslov.db nebol nájdený.\n"
                                      "Spustite convert_uvody.py na jeho vytvorenie.")
            err_lbl.set_margin_start(10)
            err_lbl.set_margin_top(8)
            err_row.set_child(err_lbl)
            self.predslov_list.append(err_row)
            return

        for i, sec in enumerate(self._predslov_sections):
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=sec["title"])
            lbl.set_halign(Gtk.Align.START)
            lbl.set_margin_start(10)
            lbl.set_margin_end(8)
            lbl.set_margin_top(6)
            lbl.set_margin_bottom(6)
            lbl.set_wrap(True)
            row._predslov_idx = i
            row.set_child(lbl)
            self.predslov_list.append(row)

    def _on_predslov_topic_selected(self, listbox, row):
        if row is None or not hasattr(row, "_predslov_idx"):
            return
        sec = self._predslov_sections[row._predslov_idx]
        # Ak je HTML už načítané (cache), zobraz hneď
        if "html" in sec:
            self._show_predslov_content(sec)
            return
        # Inak načítaj asynchrónne – nablokuje GTK, zoznam sa zobrazí okamžite
        def _load():
            sec["html"] = self._load_predslov_html(sec["id"])
            GLib.idle_add(self._show_predslov_content, sec)
        threading.Thread(target=_load, daemon=True).start()

    def _set_nav_visibility(self, chap: bool, verse: bool):
        """Skryje/zobrazí navigačné prvky kapitoly a/alebo verša."""
        for w in (self._lbl_kapitola, self.chapter_drop,
                  self._btn_chap_prev, self._btn_chap_next):
            w.set_visible(chap)
        for w in (self._sep_verse, self._lbl_vers, self.verse_drop):
            w.set_visible(verse)

    def _show_predslov_content(self, section: dict):
        """Zobrazí obsah predslovnej témy v hlavnom čítacom paneli."""
        self._showing_predslov = True
        self.book_title_label.set_markup("<b>Predslov — Sväté Písmo SSV</b>")
        self.info_label.set_text(section["title"])

        # Skry celú navigáciu (prázdny model by zobrazoval "žiaden")
        self._set_nav_visibility(chap=False, verse=False)
        self.verse_model.splice(0, self.verse_model.get_n_items(), [])
        self.chapter_model.splice(0, self.chapter_model.get_n_items(), [])

        # Vymaž obsah
        child = self.verses_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.verses_box.remove(child)
            child = nxt
        self._verse_rows    = {}
        self._bookmark_btns = {}
        self._note_btns     = {}
        self._close_commentary(None)

        # Nadpis sekcie
        title_lbl = Gtk.Label()
        title_lbl.set_markup(
            "<b><big>" + GLib.markup_escape_text(section["title"]) + "</big></b>"
        )
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_margin_top(8)
        title_lbl.set_margin_bottom(12)
        self.verses_box.append(title_lbl)

        # Obsah
        html = section["html"]
        if "<a href" not in html:
            html = self._linkify_plain_refs(html)
        pango = html_to_pango(html)

        lbl = Gtk.Label()
        lbl.set_halign(Gtk.Align.START)
        lbl.set_wrap(True)
        lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        lbl.set_use_markup(True)
        lbl.set_margin_bottom(24)
        lbl.add_css_class("verse-text")
        lbl.connect("activate-link", self._on_intro_link_clicked)
        try:
            lbl.set_markup(pango)
        except GLib.Error:
            lbl.set_text(re.sub(r"<[^>]+>", "", pango))
        self.verses_box.append(lbl)

        self.content_stack.set_visible_child_name("reading")
        GLib.idle_add(self._scroll_to_top)

    def _load_introduction(self):
        """Zobrazí úvod ku knihe z tabuľky introductions."""
        # Úvod knihy – kapitola viditeľná, verš skrytý
        self._set_nav_visibility(chap=True, verse=False)
        self.verse_model.splice(0, self.verse_model.get_n_items(), [])
        row = self.db.execute(
            "SELECT introduction FROM introductions WHERE book_number=?",
            (self.current_book,)
        ).fetchone()

        intro_html = row["introduction"] if row else "(Úvod nie je k dispozícii.)"

        # Ak úvod neobsahuje žiadne <a href> tagy (napr. 1. Petrov list),
        # automaticky prelinkujeme holé textové biblické odkazky.
        if '<a href' not in intro_html:
            intro_html = self._linkify_plain_refs(intro_html)

        self.info_label.set_text("Úvod ku knihe")

        # Vyprázdni verše
        child = self.verses_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.verses_box.remove(child)
            child = nxt
        self._verse_rows    = {}
        self._bookmark_btns = {}
        self._note_btns     = {}

        # Prázdny verse model – úvod nemá verše
        self.verse_model.splice(0, self.verse_model.get_n_items(), [])

        # Úvod ako Label s Pango markup
        intro_pango = html_to_pango(intro_html)
        lbl = Gtk.Label()
        lbl.set_halign(Gtk.Align.START)
        lbl.set_wrap(True)
        lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        lbl.set_use_markup(True)
        lbl.set_margin_top(8)
        lbl.set_margin_bottom(16)
        lbl.add_css_class("verse-text")
        lbl.connect("activate-link", self._on_intro_link_clicked)
        try:
            lbl.set_markup(intro_pango)
        except GLib.Error:
            lbl.set_text(re.sub(r"<[^>]+>", "", intro_pango))

        self.verses_box.append(lbl)
        GLib.idle_add(self._scroll_to_top)
        self._push_history(self.current_book, 0)

    # ════════════════════════════════════════════════ Kapitoly ═══════════════

    def _load_chapter(self, chapter: int):
        if self.current_book is None:
            return
        if chapter == 0:
            self._load_introduction()
            return
        # Normálna kapitola – zobraz celú navigáciu
        self._set_nav_visibility(chap=True, verse=True)

        verses = self.db.execute(
            "SELECT verse, text FROM verses WHERE book_number=? AND chapter=? ORDER BY verse",
            (self.current_book, chapter)
        ).fetchall()

        stories = self.db.execute(
            "SELECT verse, title FROM stories WHERE book_number=? AND chapter=? ORDER BY verse",
            (self.current_book, chapter)
        ).fetchall()
        story_map = {s["verse"]: s["title"] for s in stories}

        self._comm_map = self._load_commentaries(chapter, [v["verse"] for v in verses])

        # Záložky a poznámky pre túto kapitolu (načítame naraz)
        chapter_bookmarks = self.user_data.get_bookmarks_for_chapter(self.current_book, chapter)
        chapter_notes     = self.user_data.get_notes_for_chapter(self.current_book, chapter)

        comm_count = sum(1 for v in verses if v["verse"] in self._comm_map)
        comm_info  = f"  •  {comm_count} komentárov" if (self._has_comm and comm_count) else ""
        self.info_label.set_text(
            f"Kapitola {chapter} / {self.chapters_count}  •  {len(verses)} veršov{comm_info}"
        )

        verse_list = [str(i) for i in range(1, max(len(verses), 1) + 1)]
        self.verse_model.splice(0, self.verse_model.get_n_items(), verse_list)

        child = self.verses_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.verses_box.remove(child)
            child = nxt

        self._verse_rows    = {}
        self._bookmark_btns = {}
        self._note_btns     = {}
        _comm_show_btn = self._comm_map.get("__show_btn__", set())

        for v in verses:
            vnum = v["verse"]

            if vnum in story_map:
                title_lbl = Gtk.Label(label=story_map[vnum])
                title_lbl.set_halign(Gtk.Align.START)
                title_lbl.set_wrap(True)
                title_lbl.add_css_class("section-title")
                self.verses_box.append(title_lbl)

            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row_box.set_margin_top(2)
            row_box.set_margin_bottom(2)

            num_lbl = Gtk.Label(label=str(vnum))
            num_lbl.set_valign(Gtk.Align.START)
            num_lbl.set_margin_top(2)
            num_lbl.add_css_class("verse-number")
            row_box.append(num_lbl)

            text_lbl = Gtk.Label()
            text_lbl.set_halign(Gtk.Align.START)
            text_lbl.set_wrap(True)
            text_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            text_lbl.set_hexpand(False)
            text_lbl.set_selectable(True)
            text_lbl.set_use_markup(True)
            text_lbl.add_css_class("verse-text")
            
            # Definovanie farby podľa aktuálnej témy
            j_color = "#c8a0f0" if self.is_dark_theme else "#c00000"
            
            try:
                text_lbl.set_markup(verse_text_to_pango(v["text"], j_color))
            except GLib.Error:
                text_lbl.set_text(clean_verse_text(v["text"]))
            row_box.append(text_lbl)

            # ── Komentár ──────────────────────────────────────────────────────
            if vnum in _comm_show_btn:
                btn = Gtk.Button()
                btn.add_css_class("flat")
                btn.add_css_class("comm-btn")
                btn.set_valign(Gtk.Align.START)
                btn.set_margin_top(1)

                # text namiesto ikony
                label = Gtk.Label(label="")
                label.add_css_class("comm-label")  # voliteľné (na štýlovanie)
                btn.set_child(label)

                n = len(self._comm_map[vnum])
                label_n = "komentár" if n == 1 else ("komentáre" if n < 5 else "komentárov")
                btn.set_tooltip_text(f"Zobraziť komentár ({n} {label_n})")

                btn.connect("clicked", self._on_comm_btn_clicked, vnum, row_box)
                row_box.append(btn)

            # ── Indikátor záložky (len ak existuje) ───────────────────────────
            is_bm = vnum in chapter_bookmarks
            bm_icon = Gtk.Image.new_from_icon_name("starred-symbolic")
            bm_icon.add_css_class("bookmark-btn-on")
            bm_icon.set_valign(Gtk.Align.START)
            bm_icon.set_margin_top(3)
            bm_icon.set_visible(is_bm)
            row_box.append(bm_icon)
            self._bookmark_btns[vnum] = bm_icon

            # ── Tlačidlo poznámky (kliknutím zobrazí text dolu) ──────────────
            has_note = vnum in chapter_notes
            note_icon = Gtk.Button(icon_name="document-edit-symbolic")
            note_icon.add_css_class("flat")
            note_icon.add_css_class("note-btn")
            note_icon.add_css_class("note-btn-on")
            note_icon.set_valign(Gtk.Align.START)
            note_icon.set_margin_top(1)
            note_icon.set_tooltip_text("Zobraziť poznámku")
            note_icon.set_visible(has_note)
            note_icon.connect("clicked", self._on_note_icon_clicked, vnum, row_box)
            row_box.append(note_icon)
            self._note_btns[vnum] = note_icon

            # ── Kontextové menu (pravé tlačidlo myši) ─────────────────────────
            verse_text_clean = clean_verse_text(v["text"])

            # Gesture na row_box (číslo verša, medzery)
            gesture = Gtk.GestureClick.new()
            gesture.set_button(3)
            gesture.connect(
                "pressed",
                self._on_verse_right_click,
                vnum, verse_text_clean, bm_icon, note_icon
            )
            row_box.add_controller(gesture)

            # Gesture na text_lbl s CAPTURE fázou – potlačí štandardné menu labelu
            gesture_txt = Gtk.GestureClick.new()
            gesture_txt.set_button(3)
            gesture_txt.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            gesture_txt.connect(
                "pressed",
                self._on_verse_right_click,
                vnum, verse_text_clean, bm_icon, note_icon
            )
            text_lbl.add_controller(gesture_txt)

            self.verses_box.append(row_box)
            self._verse_rows[vnum] = row_box

        # Ak bol odložený skok na verš (napr. z záložiek/poznámok), vykonáme ho teraz
        if self._pending_verse is not None:
            target_verse = self._pending_verse
            self._pending_verse = None
            def _jump_pending():
                v_idx = max(0, target_verse - 1)
                if v_idx < self.verse_model.get_n_items():
                    self.verse_drop.set_selected(v_idx)
                return False
            GLib.idle_add(_jump_pending)
        else:
            GLib.idle_add(self._scroll_to_top)
        self._push_history(self.current_book, chapter)

    # ════════════════════════════════════════════════ Záložky ════════════════

    def _toggle_bookmark_for_verse(self, vnum, bm_icon=None):
        """Prepne záložku pre verš a aktualizuje indikátor."""
        is_now = self.user_data.toggle_bookmark(
            self.current_book, self.current_chapter, vnum
        )
        icon = bm_icon or self._bookmark_btns.get(vnum)
        if icon:
            icon.set_visible(is_now)

    # ════════════════════════════════════════════════ TTS ════════════════════

    def _stop_tts(self):
        """Zastaví prebiehajúce čítanie cez speech-dispatcher a resetuje tlačidlo."""
        # Pošli cancel do speech-dispatcher (zastavi hlas okamžite)
        try:
            subprocess.Popen(
                ["spd-say", "--cancel"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
        # Ukonči aj čakajúci subprocess ak beží
        if self._tts_proc is not None:
            try:
                self._tts_proc.terminate()
            except Exception:
                pass
            self._tts_proc = None
        # Resetuj toggle bez spustenia handlera
        try:
            self.tts_toggle.handler_block_by_func(self._on_tts_toggled)
            self.tts_toggle.set_active(False)
            self.tts_toggle.set_icon_name("media-playback-start-symbolic")
            self.tts_toggle.set_tooltip_text("Prečítaj zobrazený text")
            self.tts_toggle.handler_unblock_by_func(self._on_tts_toggled)
        except Exception:
            pass

    def _collect_chapter_text(self) -> str:
        """Zozbiera text od aktuálne vybraného verša (alebo od začiatku) po koniec kapitoly."""
        if self.current_book is None and not self._showing_predslov:
            return ""
        # Predslov alebo úvod ku knihe (chapter == 0) – text zo widgetov
        if self._showing_predslov or self.current_chapter == 0:
            parts = []
            child = self.verses_box.get_first_child()
            while child:
                if isinstance(child, Gtk.Label):
                    t = child.get_text().strip()
                    if t:
                        parts.append(t)
                child = child.get_next_sibling()
            return "\n".join(parts)

        # Zisti od ktorého verša začať (dropdown verší, pozícia 0 = verš 1)
        sel = self.verse_drop.get_selected()
        start_verse = (sel + 1) if sel != Gtk.INVALID_LIST_POSITION else 1

        rows = self.db.execute(
            "SELECT verse, text FROM verses "
            "WHERE book_number=? AND chapter=? AND verse>=? ORDER BY verse",
            (self.current_book, self.current_chapter, start_verse)
        ).fetchall()
        return "\n".join(
            clean_verse_text(r['text']) for r in rows
        )

    def _on_tts_toggled(self, toggle):
        if not toggle.get_active():
            self._stop_tts()
            return

        text = self._collect_chapter_text()
        if not text:
            toggle.set_active(False)
            return

        toggle.set_icon_name("media-playback-stop-symbolic")
        toggle.set_tooltip_text("Zastaviť čítanie")

        def _run():
            try:
                # spd-say odovzdá text daemonu a skončí; -w čaká kým daemon dočíta
                proc = subprocess.Popen(
                    ["spd-say", "-w", text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._tts_proc = proc
                proc.wait()
            except Exception:
                pass
            finally:
                GLib.idle_add(self._stop_tts)

        threading.Thread(target=_run, daemon=True).start()

    # ════════════════════════════════════════════════ Poznámky ═══════════════

    def _on_note_icon_clicked(self, btn, vnum, row_box):
        """Zobrazí text poznámky v spodnom paneli (podobne ako komentár)."""
        # Zrušíme highlight komentára, nastavíme highlight pre poznámku
        for rb in self._verse_rows.values():
            rb.remove_css_class("verse-highlight-comm")
            rb.remove_css_class("verse-highlight")
        row_box.add_css_class("verse-highlight-comm")

        note_text = self.user_data.get_note(
            self.current_book, self.current_chapter, vnum
        )
        if not note_text:
            return

        book_row = self.db.execute(
            "SELECT short_name FROM books WHERE book_number=?", (self.current_book,)
        ).fetchone()
        abbr = book_row["short_name"] if book_row else "?"

        self.comm_title.set_markup(
            f"<b>Poznámka</b>  "
            f"<span alpha='70%' size='small'>"
            f"{GLib.markup_escape_text(abbr)} "
            f"{self.current_chapter},{vnum}</span>"
        )
        self.comm_text.set_text(note_text)

        self.comm_revealer.set_visible(True)
        if not self.comm_revealer.get_reveal_child():
            total = self.split_vert.get_allocated_height()
            pos   = self.split_vert.get_position()
            if total > 0 and (total - pos) < 240:
                self.split_vert.set_position(max(200, total - 265))
            self.comm_revealer.set_reveal_child(True)

    # ════════════════════════════════════════════════ Kontextové menu ═══════

    def _on_verse_right_click(self, gesture, n_press, x, y, vnum, verse_text, bm_icon, note_icon):
        """Zobrazí kontextové menu pre verš pri pravom kliknutí."""
        # Obsadenie sekvencie – potlačí štandardné menu Gtk.Label
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

        book = self.current_book
        chapter = self.current_chapter

        row = self.db.execute(
            "SELECT short_name FROM books WHERE book_number=?", (book,)
        ).fetchone()
        abbr = row["short_name"] if row else "?"

        widget = gesture.get_widget()

        popover = Gtk.Popover()
        popover.set_parent(widget)
        popover.set_has_arrow(False)
        popover.add_css_class("menu")

        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        popover.set_child(box)

        # ── 1. Kopírovať verš s referenciou ───────────────────────────────────
        def _copy_verse(_btn):
            ref = f"{abbr} {chapter},{vnum}"
            full_text = f"{ref} {verse_text}"
            self.get_clipboard().set(full_text)
            popover.popdown()

        btn_copy = Gtk.Button()
        btn_copy.add_css_class("flat")
        copy_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        copy_box.set_margin_start(4); copy_box.set_margin_end(8)
        copy_icon = Gtk.Image.new_from_icon_name("edit-copy-symbolic")
        copy_box.append(copy_icon)
        copy_lbl = Gtk.Label(label=f"Kopírovať  {abbr} {chapter},{vnum}")
        copy_lbl.set_halign(Gtk.Align.START)
        copy_box.append(copy_lbl)
        btn_copy.set_child(copy_box)
        btn_copy.connect("clicked", _copy_verse)
        box.append(btn_copy)

        box.append(Gtk.Separator())

        # ── 2. Pridať / Odstrániť záložku ─────────────────────────────────────
        is_bm = self.user_data.is_bookmarked(book, chapter, vnum)
        bm_label = "Odstrániť záložku" if is_bm else "Pridať záložku"
        bm_icon_name = "starred-symbolic" if is_bm else "non-starred-symbolic"

        def _toggle_bm(_btn):
            self._toggle_bookmark_for_verse(vnum, bm_icon)
            popover.popdown()

        btn_bm = Gtk.Button()
        btn_bm.add_css_class("flat")
        bm_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bm_box.set_margin_start(4); bm_box.set_margin_end(8)
        bm_img = Gtk.Image.new_from_icon_name(bm_icon_name)
        bm_box.append(bm_img)
        bm_lbl = Gtk.Label(label=bm_label)
        bm_lbl.set_halign(Gtk.Align.START)
        bm_box.append(bm_lbl)
        btn_bm.set_child(bm_box)
        btn_bm.connect("clicked", _toggle_bm)
        box.append(btn_bm)

        # ── 3. Pridať / Upraviť poznámku ──────────────────────────────────────
        has_note = bool(self.user_data.get_note(book, chapter, vnum))
        note_label = "Upraviť poznámku" if has_note else "Pridať poznámku"
        note_icon_name = "document-edit-symbolic" if has_note else "document-new-symbolic"

        def _open_note(_btn):
            popover.popdown()
            def _after_save():
                has = bool(self.user_data.get_note(book, chapter, vnum))
                note_icon.set_visible(has)
                note_icon.set_tooltip_text("Zobraziť poznámku" if has else "")
                self._populate_bookmarks_panel()
            self._show_note_dialog_with_callback(book, chapter, vnum, _after_save)

        btn_note = Gtk.Button()
        btn_note.add_css_class("flat")
        note_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        note_box.set_margin_start(4); note_box.set_margin_end(8)
        note_img = Gtk.Image.new_from_icon_name(note_icon_name)
        note_box.append(note_img)
        note_lbl = Gtk.Label(label=note_label)
        note_lbl.set_halign(Gtk.Align.START)
        note_box.append(note_lbl)
        btn_note.set_child(note_box)
        btn_note.connect("clicked", _open_note)
        box.append(btn_note)

        popover.popup()

    # ════════════════════════════════════════════════ Slovník ═══════════════

    def _build_dict_panel(self):
        """Vertikálne rozdelený panel slovníka: vľavo zoznam hesiel, vpravo definícia."""
        if not self._has_dict:
            placeholder = Gtk.Label(label="Slovník nie je k dispozícii.")
            placeholder.add_css_class("dict-placeholder")
            self.content_stack.add_named(placeholder, "dictionary")
            return

        outer = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        outer.set_position(250)

        # ── Ľavá strana: vyhľadávanie + zoznam ────────────────────────────────
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left_box.set_size_request(200, -1)

        self.dict_search_entry = Gtk.SearchEntry()
        self.dict_search_entry.set_placeholder_text("Hľadaj heslo…")
        self.dict_search_entry.set_margin_start(8)
        self.dict_search_entry.set_margin_end(8)
        self.dict_search_entry.set_margin_top(8)
        self.dict_search_entry.set_margin_bottom(6)
        self.dict_search_entry.connect("search-changed", self._on_dict_search_changed)
        self.dict_search_entry.connect("activate", lambda _: self._do_dict_search())
        left_box.append(self.dict_search_entry)

        left_box.append(Gtk.Separator())

        scroll_list = Gtk.ScrolledWindow()
        scroll_list.set_vexpand(True)
        scroll_list.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.dict_list = Gtk.ListBox()
        self.dict_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.dict_list.add_css_class("navigation-sidebar")
        self.dict_list.connect("row-selected", self._on_dict_row_selected)
        scroll_list.set_child(self.dict_list)
        left_box.append(scroll_list)

        outer.set_start_child(left_box)
        outer.set_shrink_start_child(False)

        # ── Pravá strana: text definície ──────────────────────────────────────
        scroll_def = Gtk.ScrolledWindow()
        scroll_def.set_vexpand(True)
        scroll_def.set_hexpand(True)
        scroll_def.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.dict_text = Gtk.Label()
        self.dict_text.set_wrap(True)
        self.dict_text.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.dict_text.set_halign(Gtk.Align.START)
        self.dict_text.set_valign(Gtk.Align.START)
        self.dict_text.set_selectable(True)
        self.dict_text.set_use_markup(True)
        self.dict_text.set_margin_start(16)
        self.dict_text.set_margin_end(16)
        self.dict_text.set_margin_top(12)
        self.dict_text.set_margin_bottom(16)
        self.dict_text.add_css_class("dict-text")
        self.dict_text.connect("activate-link", self._on_dict_link_clicked)

        # Placeholder text keď nie je vybrané heslo
        self.dict_text.set_text(
         "Biblický slovník Adolfa Novotného"
        )
        self.dict_text.add_css_class("dict-placeholder")

        scroll_def.set_child(self.dict_text)
        outer.set_end_child(scroll_def)
        outer.set_shrink_end_child(True)

        self.content_stack.add_named(outer, "dictionary")

    def _on_dict_toggled(self, toggle):
        active = toggle.get_active()
        if active:
            self.search_toggle.set_active(False)
            self.bookmarks_toggle.set_active(False)
            self.content_stack.set_visible_child_name("dictionary")
            GLib.idle_add(self.dict_search_entry.grab_focus)
        else:
            self.content_stack.set_visible_child_name("reading")

    def _on_dict_search_changed(self, entry):
        # Debounce – počkaj 300 ms po poslednom znaku
        if self._dict_search_timeout is not None:
            GLib.source_remove(self._dict_search_timeout)
        self._dict_search_timeout = GLib.timeout_add(300, self._do_dict_search)

    def _do_dict_search(self):
        self._dict_search_timeout = None
        if not self._has_dict:
            return False
        query = self.dict_search_entry.get_text().strip()

        # Vymaž starý zoznam
        child = self.dict_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.dict_list.remove(child)
            child = nxt

        if len(query) == 0:
            return False

        query_norm = remove_diacritics(query).lower()

        rows = []
        for r in self.db_dict.execute(
          "SELECT topic FROM dictionary ORDER BY topic"
        ):
            topic_norm = remove_diacritics(r["topic"]).lower()
            if topic_norm.startswith(query_norm):
                rows.append(r)
            if len(rows) >= 200:
                break

        # Ak nič nenájdeme začiatkom, skúsime hľadanie kdekoľvek
        if not rows:
            rows = self.db_dict.execute(
                "SELECT topic FROM dictionary WHERE topic LIKE ? ORDER BY topic LIMIT 200",
                (f"%{query}%",)
            ).fetchall()

        for r in rows:
            lbl = Gtk.Label(label=r["topic"])
            lbl.set_halign(Gtk.Align.START)
            lbl.set_margin_start(10)
            lbl.set_margin_end(8)
            lbl.set_margin_top(4)
            lbl.set_margin_bottom(4)
            lbl.add_css_class("dict-topic-lbl")
            list_row = Gtk.ListBoxRow()
            list_row.set_child(lbl)
            list_row._dict_topic = r["topic"]
            self.dict_list.append(list_row)

        # Vyber a zobraz prvý výsledok
        first = self.dict_list.get_row_at_index(0)
        if first:
            self.dict_list.select_row(first)

        return False  # GLib.timeout jednorazovo

    def _on_dict_row_selected(self, listbox, row):
        if row is None or not hasattr(row, "_dict_topic"):
            return
        self._show_dict_entry(row._dict_topic)

    def _show_dict_entry(self, topic: str):
        r = self.db_dict.execute(
            "SELECT topic, definition FROM dictionary WHERE topic=?", (topic,)
        ).fetchone()
        if not r:
            return

        markup = (
            "<b><big>" + GLib.markup_escape_text(r["topic"]) + "</big></b>\n\n"
            + self._dict_html_to_pango(r["definition"])
        )
        try:
            self.dict_text.set_markup(markup)
        except GLib.Error:
            self.dict_text.set_text(re.sub(r"<[^>]+>", "", markup))

    def _dict_html_to_pango(self, html: str) -> str:
        """Prevedie HTML definície slovníka na Pango markup."""
        # Mäkký spojovník (soft hyphen)
        html = html.replace("\xad", "").replace("&shy;", "")

        # Odseky
        html = re.sub(r"<p\s*/>", "\n\n", html)
        html = re.sub(r"<p[^>]*>", "\n\n", html)
        html = re.sub(r"</p>", "\n", html)
        html = re.sub(r"<br\s*/?>", "\n", html)

        # Nadpisy
        html = re.sub(r"<h[1-4][^>]*>(.*?)</h[1-4]>", r"\n<b>\1</b>\n", html, flags=re.DOTALL)

        # Zoznamy
        html = re.sub(r"<li>(.*?)</li>", "\n• \\1", html, flags=re.DOTALL)
        html = re.sub(r"</?ul>", "", html)

        # Tabuľky – prevedieme na plain text
        html = re.sub(r"<tr[^>]*>", "\n", html)
        html = re.sub(r"<td[^>]*>", "  ", html)
        html = re.sub(r"</td>", "", html)
        html = re.sub(r"</?t(?:able|r|body|head)[^>]*>", "", html)

        # Obrázky – ignorujeme
        html = re.sub(r"<img[^>]+>", "", html)

        # Interné slovníkové odkazy (S:heslo)
        def _dict_link(m):
            href = m.group(1)
            text = re.sub(r"<[^>]+>", "", m.group(2))
            return '<a href="' + GLib.markup_escape_text(href) + '">' + GLib.markup_escape_text(text) + '</a>'

        html = re.sub(
            r"<a\s+(?:class='S'\s+)?href='(S:[^']+)'[^>]*>(.*?)</a>",
            _dict_link, html, flags=re.DOTALL
        )

        # Biblické odkazy (B:kniha kapitola:verš)
        def _bible_link(m):
            href = m.group(1)
            text = re.sub(r"<[^>]+>", "", m.group(2))
            return '<a href="' + GLib.markup_escape_text(href) + '">' + GLib.markup_escape_text(text) + '</a>'

        html = re.sub(
            r"<a\s+href='(B:[^']+)'[^>]*>(.*?)</a>",
            _bible_link, html, flags=re.DOTALL
        )

        # Zostatok tagov – ponecháme i, sup, b; ostatné odstránime
        html = re.sub(r"<(?!/?(i|sup|b)\b)[^>]+>", "", html)

        # Escapovanie voľného &
        html = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[\da-fA-F]+);)", "&amp;", html)

        # Viacnásobné prázdne riadky
        html = re.sub(r"\n{3,}", "\n\n", html)

        return html.strip()

    def _on_dict_link_clicked(self, label, uri):
        """Kliknutie na odkaz v slovníku – buď biblický verš alebo iné heslo."""
        if uri.startswith("S:"):
            # Interný odkaz na iné heslo
            topic = uri[2:]
            self._show_dict_entry(topic)
            # Vyber heslo v zozname ak existuje
            child = self.dict_list.get_first_child()
            while child:
                if hasattr(child, "_dict_topic") and child._dict_topic == topic:
                    self.dict_list.select_row(child)
                    break
                child = child.get_next_sibling()
            return True

        if uri.startswith("B:"):
            # Biblický odkaz – navigujeme na verš
            return self._on_comm_link_clicked(label, uri[2:])

        return False

    # ════════════════════════════════════════════════ Komentáre ══════════════

    def _load_commentaries(self, chapter: int, verse_nums: list) -> dict:
        if not self._has_comm or not verse_nums:
            return {}

        rows = self.db_comm.execute(
            """
            SELECT chapter_number_from, verse_number_from,
                   chapter_number_to,   verse_number_to,
                   text
            FROM commentaries
            WHERE book_number = ?
              AND chapter_number_from = ?
            ORDER BY verse_number_from
            """,
            (self.current_book, chapter)
        ).fetchall()

        comm_map: dict = {}
        # Množina veršov, pri ktorých sa má zobraziť symbol (len prvý verš rozsahu)
        comm_show_btn: set = set()
        last_verse = verse_nums[-1] if verse_nums else 1

        for r in rows:
            v_from   = r["verse_number_from"]
            chap_to  = r["chapter_number_to"]
            v_to     = r["verse_number_to"]

            if chap_to is not None and chap_to != chapter:
                v_to = last_verse
            elif v_to is None:
                v_to = v_from

            plain = html_to_pango(r["text"])
            first_in_range = None
            for vn in verse_nums:
                if v_from <= vn <= v_to:
                    comm_map.setdefault(vn, []).append(plain)
                    if first_in_range is None:
                        first_in_range = vn
            if first_in_range is not None:
                comm_show_btn.add(first_in_range)

        # Uložíme množinu "prvých veršov" ako atribút slovníka
        comm_map["__show_btn__"] = comm_show_btn
        return comm_map

    def _on_comm_btn_clicked(self, btn, verse_num, row_box):
        for rb in self._verse_rows.values():
            rb.remove_css_class("verse-highlight-comm")
            rb.remove_css_class("verse-highlight")

        row_box.add_css_class("verse-highlight-comm")

        texts = self._comm_map.get(verse_num, [])
        if not texts:
            return

        book_short = self.db.execute(
            "SELECT short_name FROM books WHERE book_number=?", (self.current_book,)
        ).fetchone()
        abbr = book_short["short_name"] if book_short else "?"
        self.comm_title.set_markup(
            f"<b>Komentár</b>  "
            f"<span alpha='70%' size='small'>{GLib.markup_escape_text(abbr)} "
            f"{self.current_chapter},{verse_num}</span>"
        )

        full_text = "\n\n─────\n\n".join(texts)
        try:
            self.comm_text.set_markup(full_text)
        except GLib.Error:
            self.comm_text.set_text(re.sub(r"<[^>]+>", full_text))

        self.comm_revealer.set_visible(True)
        if not self.comm_revealer.get_reveal_child():
            total = self.split_vert.get_allocated_height()
            pos   = self.split_vert.get_position()
            if total > 0 and (total - pos) < 240:
                self.split_vert.set_position(max(200, total - 265))
            self.comm_revealer.set_reveal_child(True)

    def _close_commentary(self, _btn):
        self.comm_revealer.set_reveal_child(False)
        self.comm_revealer.set_visible(False)
        for rb in self._verse_rows.values():
            rb.remove_css_class("verse-highlight-comm")

    def _on_comm_link_clicked(self, label, uri):
        """Handler pre kliknutie na krížový odkaz v komentári."""
        book_num  = self.current_book
        chap_num  = self.current_chapter
        verse_num = 1

        b_match = re.search(r'b\D*(\d+)', uri, re.IGNORECASE)
        c_match = re.search(r'c\D*(\d+)', uri, re.IGNORECASE)
        v_match = re.search(r'v\D*(\d+)', uri, re.IGNORECASE)

        if b_match or c_match or v_match:
            if b_match: book_num  = int(b_match.group(1))
            if c_match: chap_num  = int(c_match.group(1))
            if v_match: verse_num = int(v_match.group(1))
        else:
            nums = re.findall(r'\d+', uri)
            if len(nums) >= 2:
                book_num  = int(nums[0])
                chap_num  = int(nums[1])
                verse_num = int(nums[2]) if len(nums) >= 3 else 1

        if book_num is None or chap_num is None:
            return True

        if book_num != self.current_book:
            self._navigate_to_book(book_num)

        if chap_num != self.current_chapter:
            chap_idx = chap_num if self._has_intro else max(0, chap_num - 1)
            chap_idx = min(chap_idx, self.chapter_model.get_n_items() - 1)
            self.chapter_drop.set_selected(chap_idx)

        def _jump():
            v_idx = max(0, verse_num - 1)
            if v_idx < self.verse_model.get_n_items():
                self.verse_drop.set_selected(v_idx)
            return False

        GLib.idle_add(_jump)
        return True

    # ════════════════════════════════════════════════ Verše ══════════════════

    def _on_verse_jump(self, dropdown, param):
        pos = dropdown.get_selected()
        if pos == Gtk.INVALID_LIST_POSITION:
            return
        target = pos + 1
        row = self._verse_rows.get(target)
        if row is None:
            return
        for r in self._verse_rows.values():
            r.remove_css_class("verse-highlight")
            r.remove_css_class("verse-highlight-comm")
        row.add_css_class("verse-highlight")
        GLib.idle_add(self._scroll_to_widget, row)

    def _scroll_to_widget(self, widget):
        alloc = widget.get_allocation()
        self._scroll_window.get_vadjustment().set_value(max(0, alloc.y - 60))
        return False

    def _scroll_to_top(self):
        if self._pending_scroll_pos is not None:
            pos = self._pending_scroll_pos
            self._pending_scroll_pos = None
            self._scroll_window.get_vadjustment().set_value(pos)
        else:
            self._scroll_window.get_vadjustment().set_value(0)
        return False

    # ════════════════════════════════════════════════ Komentárový panel ══════

    def _build_commentary_panel(self):
        comm_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        comm_outer.add_css_class("comm-panel")

        comm_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        comm_header.set_margin_start(12)
        comm_header.set_margin_end(8)
        comm_header.set_margin_top(6)
        comm_header.set_margin_bottom(6)

        comm_icon = Gtk.Image.new_from_icon_name("accessories-text-editor-symbolic")
        comm_header.append(comm_icon)

        self.comm_title = Gtk.Label(label="Komentár")
        self.comm_title.add_css_class("heading")
        self.comm_title.set_hexpand(True)
        self.comm_title.set_halign(Gtk.Align.START)
        comm_header.append(self.comm_title)

        btn_close = Gtk.Button(icon_name="window-close-symbolic")
        btn_close.add_css_class("flat")
        btn_close.set_tooltip_text("Zatvoriť komentár")
        btn_close.connect("clicked", self._close_commentary)
        comm_header.append(btn_close)

        comm_outer.append(comm_header)
        comm_outer.append(Gtk.Separator())

        scroll_comm = Gtk.ScrolledWindow()
        scroll_comm.set_vexpand(True)
        scroll_comm.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.comm_text = Gtk.Label()
        self.comm_text.set_wrap(True)
        self.comm_text.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.comm_text.set_halign(Gtk.Align.START)
        self.comm_text.set_valign(Gtk.Align.START)
        self.comm_text.set_selectable(True)
        self.comm_text.set_use_markup(True)
        self.comm_text.connect("activate-link", self._on_comm_link_clicked)
        self.comm_text.set_margin_start(14)
        self.comm_text.set_margin_end(14)
        self.comm_text.set_margin_top(8)
        self.comm_text.set_margin_bottom(14)
        self.comm_text.add_css_class("comm-text")
        scroll_comm.set_child(self.comm_text)
        comm_outer.append(scroll_comm)

        self.comm_revealer = Gtk.Revealer()
        self.comm_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.comm_revealer.set_transition_duration(200)
        self.comm_revealer.set_reveal_child(False)
        self.comm_revealer.set_child(comm_outer)
        self.comm_revealer.set_size_request(-1, 260)
        self.comm_revealer.set_visible(False)

        self.split_vert.set_end_child(self.comm_revealer)
        self.split_vert.set_resize_end_child(False)


# ─────────────────────────────────────── main ────────────────────────────────

def main():
    if not os.path.exists(DB_PATH):
        print(f"CHYBA: Databáza nenájdená: {DB_PATH}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(DB_COMM_PATH):
        print(
            f"UPOZORNENIE: Komentáre nenájdené ({DB_COMM_PATH}), "
            "aplikácia beží bez komentárov.",
            file=sys.stderr,
        )
    app = BibleApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    main()