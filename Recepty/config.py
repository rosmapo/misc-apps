"""Uloženie tokenu a nastavení (napr. veľkosť písma) do
~/.config/simplenote-gtk/config.json"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "simplenote-gtk"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_FONT_SIZE = 13


def _load():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save(data: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data))
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass


def load_token():
    return _load().get("token")


def save_token(token: str):
    data = _load()
    data["token"] = token
    _save(data)


def clear_token():
    data = _load()
    data.pop("token", None)
    _save(data)


def load_font_size() -> int:
    return _load().get("font_size", DEFAULT_FONT_SIZE)


def save_font_size(size: int):
    data = _load()
    data["font_size"] = size
    _save(data)
