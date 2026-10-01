"""History of captures: SQLite for the text, one PNG per capture for the crop."""

import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from typing import Optional

from PIL import Image

from . import romanize


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
    image      TEXT,
    labels     TEXT    NOT NULL DEFAULT '[]', -- JSON list, at most MAX_LABELS
    roman      TEXT,                          -- readings in Latin letters; NULL until made
    furigana   TEXT                           -- JSON [[kanji, kana], ...]; NULL until made
);
CREATE INDEX IF NOT EXISTS captures_created ON captures(created_at);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""
MAX_LABELS = 3
MAX_LABEL_LEN = 40


def fold(text: str) -> str:
    """Search key: full/half width, katakana/hiragana and case all match each other."""
    text = unicodedata.normalize("NFKC", text).lower()
    return "".join(chr(ord(ch) - 0x60) if "ァ" <= ch <= "ヶ" else ch for ch in text)


def connect() -> sqlite3.Connection:
    os.makedirs(IMAGE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.create_function("fold", 1, fold, deterministic=True)
    conn.create_function("romankey", 1, romanize.key, deterministic=True)
    conn.executescript(_SCHEMA)
    # Histories from older versions: add the newer columns in place.
    have = {r["name"] for r in conn.execute("PRAGMA table_info(captures)")}
    for column, decl in (("labels", "TEXT NOT NULL DEFAULT '[]'"), ("roman", "TEXT"), ("furigana", "TEXT")):
        if column not in have:
            conn.execute(f"ALTER TABLE captures ADD COLUMN {column} {decl}")
    return conn


def _fill_readings(conn: sqlite3.Connection) -> None:
    """Make the missing readings. Done here, when the history is read, rather than
    at capture time, so a capture never waits on the dictionaries loading."""
    engine = romanize.engine()
    row = conn.execute("SELECT value FROM meta WHERE key = 'roman'").fetchone()
    if not row or row["value"] != engine:  # e.g. pykakasi got installed: redo them all
        conn.execute("UPDATE captures SET roman = NULL, furigana = NULL")
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('roman', ?)", (engine,))
    done = {}
    rows = conn.execute("SELECT id, text FROM captures WHERE roman IS NULL OR furigana IS NULL").fetchall()
    for r in rows:
        if r["text"] not in done:
            done[r["text"]] = (romanize.romanize(r["text"]),
                               json.dumps(romanize.furigana(r["text"]), ensure_ascii=False))
    conn.executemany("UPDATE captures SET roman = ?, furigana = ? WHERE id = ?",
                     [(*done[r["text"]], r["id"]) for r in rows])


def clean_labels(labels: list) -> list:
    """Trim, squash spaces, drop empties and repeats (ignoring case and kana).
    Raises ValueError past MAX_LABELS or MAX_LABEL_LEN."""
    out, seen = [], set()
    for label in labels:
        label = " ".join(label.split())
        if not label or fold(label) in seen:
            continue
        if len(label) > MAX_LABEL_LEN:
            raise ValueError(f"a label can be at most {MAX_LABEL_LEN} characters")
        seen.add(fold(label))
        out.append(label)
    if len(out) > MAX_LABELS:
        raise ValueError(f"an entry can have at most {MAX_LABELS} labels")
    return out


def _row(row: sqlite3.Row) -> dict:
    capture = dict(row)
    capture["labels"] = json.loads(capture["labels"] or "[]")
    capture["furigana"] = json.loads(capture["furigana"] or "[]")
    return capture


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


def search(query: str = "", category: Optional[str] = None, label: Optional[str] = None) -> list:
    """The query matches the text, the category, any label, or (typed in Latin
    letters) the reading of Japanese, Chinese or Korean text."""
    sql = "SELECT * FROM captures WHERE 1=1"
    rq = romanize.key(query) if re.search("[a-z]", fold(query)) else ""
    if len(rq) < 2:  # one letter would match nearly every reading
        rq = ""
    if query:
        sql += """ AND (instr(fold(text), :q) > 0 OR instr(fold(category), :q) > 0
                   OR EXISTS (SELECT 1 FROM json_each(captures.labels) WHERE instr(fold(value), :q) > 0)
                   OR (:rq != '' AND instr(romankey(roman), :rq) > 0))"""
    if category is not None:
        sql += " AND category = :category"
    if label is not None:
        sql += " AND EXISTS (SELECT 1 FROM json_each(captures.labels) WHERE value = :label)"
    sql += " ORDER BY created_at DESC"
    params = {"q": fold(query), "rq": rq, "category": category, "label": label}
    with connect() as conn:
        _fill_readings(conn)
        return [_row(row) for row in conn.execute(sql, params)]


def categories() -> list:
    with connect() as conn:
        rows = conn.execute(
            # Repeats of the same text are one entry on the page, so count them once.
            "SELECT category, COUNT(DISTINCT text) AS n FROM captures GROUP BY category ORDER BY category"
        )
        return [dict(row) for row in rows]


def labels() -> list:
    with connect() as conn:
        rows = conn.execute(
            "SELECT value AS label, COUNT(DISTINCT captures.text) AS n FROM captures, json_each(captures.labels)"
            " GROUP BY value ORDER BY value"
        )
        return [dict(row) for row in rows]


def set_labels(changes: list) -> None:
    """Apply many (id, labels) pairs at once; labels must already be clean."""
    with connect() as conn:
        conn.executemany("UPDATE captures SET labels = ? WHERE id = ?",
                         [(json.dumps(labels, ensure_ascii=False), capture_id)
                          for capture_id, labels in changes])


def set_category(capture_id: int, category: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE captures SET category = ? WHERE id = ?", (category, capture_id))


def set_categories(changes: list) -> None:
    """Apply many (id, category) pairs at once, e.g. a bulk move or its undo."""
    with connect() as conn:
        conn.executemany("UPDATE captures SET category = ? WHERE id = ?",
                         [(category, capture_id) for capture_id, category in changes])


def rename_category(old: str, new: str) -> list:
    """Move every capture filed under `old` to `new` ("" removes the category).
    Returns the ids that moved, so the change can be undone."""
    with connect() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM captures WHERE category = ?", (old,))]
        conn.execute("UPDATE captures SET category = ? WHERE category = ?", (new, old))
    return ids


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
