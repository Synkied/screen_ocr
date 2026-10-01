"""History of captures: SQLite for the text, one PNG per capture for the crop."""

import os
import sqlite3
import sys
import time
from typing import Optional

from PIL import Image


def data_dir() -> str:
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "screen-ocr")


DATA_DIR = data_dir()
DB_PATH = os.path.join(DATA_DIR, "history.db")
IMAGE_DIR = os.path.join(DATA_DIR, "images")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS captures (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL    NOT NULL,
    text       TEXT    NOT NULL,
    category   TEXT    NOT NULL DEFAULT '',
    image      TEXT
);
CREATE INDEX IF NOT EXISTS captures_created ON captures(created_at);
"""


def connect() -> sqlite3.Connection:
    os.makedirs(IMAGE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def add(text: str, image: Optional[Image.Image], category: str = "") -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO captures (created_at, text, category) VALUES (?, ?, ?)",
            (time.time(), text, category),
        )
        capture_id = cur.lastrowid
        if image is not None:
            name = f"{capture_id}.png"
            image.save(os.path.join(IMAGE_DIR, name))
            conn.execute("UPDATE captures SET image = ? WHERE id = ?", (name, capture_id))
    return capture_id


def search(query: str = "", category: Optional[str] = None) -> list:
    sql = "SELECT * FROM captures WHERE 1=1"
    params = []
    if query:
        sql += " AND text LIKE ?"
        params.append(f"%{query}%")
    if category is not None:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY created_at DESC"
    with connect() as conn:
        return [dict(row) for row in conn.execute(sql, params)]


def categories() -> list:
    with connect() as conn:
        rows = conn.execute(
            "SELECT category, COUNT(*) AS n FROM captures GROUP BY category ORDER BY category"
        )
        return [dict(row) for row in rows]


def set_category(capture_id: int, category: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE captures SET category = ? WHERE id = ?", (category, capture_id))


def delete(ids: list) -> int:
    if not ids:
        return 0
    marks = ",".join("?" * len(ids))
    with connect() as conn:
        images = [r["image"] for r in conn.execute(
            f"SELECT image FROM captures WHERE id IN ({marks})", ids) if r["image"]]
        deleted = conn.execute(f"DELETE FROM captures WHERE id IN ({marks})", ids).rowcount
    for name in images:
        try:
            os.remove(os.path.join(IMAGE_DIR, name))
        except FileNotFoundError:
            pass
    return deleted
