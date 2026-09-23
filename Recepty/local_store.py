"""
Lokálna offline cache poznámok (SQLite), aby appka štartovala rýchlo
aj bez siete a zmeny sa dali robiť offline (a doplniť na server neskôr).
"""

import json
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path.home() / ".config" / "simplenote-gtk" / "notes.db"

_lock = threading.Lock()


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY,
            version INTEGER,
            content TEXT,
            tags TEXT,
            deleted INTEGER DEFAULT 0,
            modification_date REAL DEFAULT 0,
            dirty INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    return conn


_conn = _connect()


def load_all() -> dict:
    """Vráti všetky (nevymazané aj vymazané) poznámky z lokálnej cache."""
    with _lock:
        cur = _conn.execute(
            "SELECT id, version, content, tags, deleted, modification_date, dirty FROM notes"
        )
        rows = cur.fetchall()

    result = {}
    for note_id, version, content, tags_json, deleted, mod_date, dirty in rows:
        result[note_id] = {
            "id": note_id,
            "version": version,
            "content": content or "",
            "tags": json.loads(tags_json) if tags_json else [],
            "deleted": bool(deleted),
            "modification_date": mod_date or 0,
            "dirty": bool(dirty),
        }
    return result


def upsert(note_id, version, content, tags, deleted=False,
           modification_date=0, dirty=False):
    with _lock:
        _conn.execute(
            """
            INSERT INTO notes (id, version, content, tags, deleted, modification_date, dirty)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                version=excluded.version,
                content=excluded.content,
                tags=excluded.tags,
                deleted=excluded.deleted,
                modification_date=excluded.modification_date,
                dirty=excluded.dirty
            """,
            (note_id, version, content, json.dumps(tags), int(deleted),
             modification_date, int(dirty)),
        )
        _conn.commit()


def mark_synced(note_id, version):
    with _lock:
        _conn.execute(
            "UPDATE notes SET version=?, dirty=0 WHERE id=?",
            (version, note_id),
        )
        _conn.commit()


def remove(note_id):
    with _lock:
        _conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        _conn.commit()


def get_dirty_ids():
    with _lock:
        cur = _conn.execute("SELECT id FROM notes WHERE dirty=1")
        return [row[0] for row in cur.fetchall()]
