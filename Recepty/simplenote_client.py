"""
Minimalný klient pre Simplenote (cez Simperium REST API) s manuálne
získaným tokenom (viď DevTools -> Network -> websocket -> Messages).

Token treba raz za čas obnoviť rovnakým postupom (vypršanie nie je
presne zdokumentované, ale nie je krátkodobé - skús a uvidíš).
"""

import time
import unicodedata
from urllib.parse import quote

import requests

APP_ID = "chalk-bump-f49"
BASE_URL = f"https://api.simperium.com/1/{APP_ID}"


def hash_tag(name: str) -> str:
    """
    Simplenote tag object id (rovnaký algoritmus ako oficiálny Android klient):
    NFC normalize → lowercase (en_US) → URL-encode → nahradenie špeciálnych znakov.
    """
    normalized = unicodedata.normalize("NFC", name)
    lowercased = normalized.lower()
    encoded = quote(lowercased, safe="")
    return (
        encoded
        .replace("+", "%20")
        .replace("*", "%2A")
        .replace("-", "%2D")
        .replace(".", "%2E")
        .replace("_", "%5F")
    )


class SimplenoteClient:
    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({"X-Simperium-Token": token})

    def list_notes(self, data: bool = True):
        """Vráti zoznam poznámok (index). Ak data=True, obsahuje aj obsah."""
        params = {"data": "true" if data else "false"}
        r = self.session.get(f"{BASE_URL}/note/index", params=params)
        r.raise_for_status()
        return r.json()

    def get_note(self, note_id: str, version: int | None = None):
        """Stiahne konkrétnu poznámku podľa id (voliteľne konkrétnu verziu)."""
        url = f"{BASE_URL}/note/i/{note_id}"
        if version is not None:
            url += f"/v/{version}"
        r = self.session.get(url)
        r.raise_for_status()
        return r.json()

    def save_note(self, note_id: str, content: str, version: int | None = None,
                  tags=None, modification_date: float | None = None,
                  extra: dict | None = None):
        """
        Vytvorí alebo aktualizuje poznámku.
        - Pri novej poznámke nechaj version=None.
        - Pri update existujúcej pošli aktuálnu verziu (inak dostaneš 412 conflict).

        Pri create (version=None) sa musí poslať kompletná schéma poznámky,
        inak API vráti HTTP 400 Bad Request.

        Verzia sa vždy číta z HTTP hlavičky X-Simperium-Version (tá je
        prítomná pri každej odpovedi, aj bez ?response=1).
        """
        payload = {
            "content": content,
            "tags": tags or [],
        }

        # Pri vytváraní novej poznámky musíme poslať kompletnú schému,
        # inak API vráti 400 Bad Request (content+tags nestačí).
        if version is None:
            now = modification_date if modification_date else time.time()
            payload.update({
                "systemTags": [],
                "creationDate": now,
                "modificationDate": now,
                "deleted": False,
                "shareURL": "",
                "publishURL": "",
            })
        elif modification_date is not None:
            payload["modificationDate"] = modification_date

        if extra:
            payload.update(extra)

        url = f"{BASE_URL}/note/i/{note_id}"
        if version is not None:
            url += f"/v/{version}"

        r = self.session.post(url, json=payload)

        if r.status_code == 412:
            # "empty change" - dáta sa oproti aktuálnej verzii nezmenili.
            # Nie je to chyba - len zistíme aktuálnu verziu, aby sa lokálna
            # poznámka prestala navždy tváriť ako "nesynchronizovaná".
            version_header = r.headers.get("X-Simperium-Version")
            return {"v": int(version_header) if version_header else version}

        r.raise_for_status()

        version_header = r.headers.get("X-Simperium-Version")
        try:
            data = r.json() if r.content else {}
        except ValueError:
            data = {}
        if version_header:
            data["v"] = int(version_header)
        return data

    # ------------------------------------------------------------------
    # Tag bucket (oficiálne klienty majú samostatný bucket "tag";
    # bez neho sa tag ukáže na poznámke, ale nie v bočnom zozname tagov)
    # ------------------------------------------------------------------

    def list_tags(self, data: bool = True):
        """Vráti index tagov z bucketu tag."""
        params = {"data": "true" if data else "false"}
        r = self.session.get(f"{BASE_URL}/tag/index", params=params)
        r.raise_for_status()
        return r.json()

    def ensure_tag(self, name: str, index: int = 0):
        """
        Zabezpečí, že tag existuje v bucketu tag (sidebar na webe/appke).
        Ak už existuje, 412 empty change nie je chyba.
        """
        if not name or not name.strip():
            return None
        name = name.strip()
        tag_id = hash_tag(name)
        payload = {"name": name, "index": index}
        url = f"{BASE_URL}/tag/i/{tag_id}"
        r = self.session.post(url, json=payload)
        if r.status_code == 412:
            version_header = r.headers.get("X-Simperium-Version")
            return {"id": tag_id, "v": int(version_header) if version_header else None}
        r.raise_for_status()
        version_header = r.headers.get("X-Simperium-Version")
        try:
            data = r.json() if r.content else {}
        except ValueError:
            data = {}
        data["id"] = tag_id
        if version_header:
            data["v"] = int(version_header)
        return data

    def trash_note(self, note_id: str, version: int):
        """Presunie poznámku do koša (nastaví deleted=True)."""
        return self.save_note(note_id, content="", version=version,
                               extra={"deleted": True})

    def delete_note(self, note_id: str, version: int):
        """Natrvalo vymaže poznámku (DELETE request)."""
        url = f"{BASE_URL}/note/i/{note_id}/v/{version}"
        r = self.session.delete(url)
        r.raise_for_status()
        return True


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Použitie: python simplenote_client.py <TOKEN>")
        sys.exit(1)

    client = SimplenoteClient(sys.argv[1])
    index = client.list_notes()

    print(f"Počet poznámok: {len(index.get('index', []))}")
    for item in index.get("index", [])[:5]:
        note_id = item.get("id")
        note_data = item.get("d", {})
        content = note_data.get("content", "")
        preview = content.splitlines()[0] if content else "(prázdna)"
        print(f"- {note_id}: {preview[:60]}")
