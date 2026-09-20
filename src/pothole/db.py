"""SQLite storage."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
    id          TEXT PRIMARY KEY,
    captured_at INTEGER NOT NULL,      -- epoch milliseconds (UTC)
    lat         REAL NOT NULL,
    lon         REAL NOT NULL,
    heading     REAL,                  -- camera compass angle, degrees
    url         TEXT,
    path        TEXT,                  -- local file once downloaded
    processed   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS detections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id   TEXT NOT NULL REFERENCES images(id),
    lat        REAL NOT NULL,          -- estimated pothole position
    lon        REAL NOT NULL,
    conf       REAL NOT NULL,
    area_ratio REAL,
    severity   TEXT,
    x1 REAL, y1 REAL, x2 REAL, y2 REAL
);
CREATE INDEX IF NOT EXISTS idx_det_image ON detections(image_id);
CREATE INDEX IF NOT EXISTS idx_img_time ON images(captured_at);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_images(conn: sqlite3.Connection, rows: Iterable[dict]) -> int:
    n = 0
    with conn:
        for r in rows:
            conn.execute(
                """INSERT INTO images (id, captured_at, lat, lon, heading, url)
                   VALUES (:id, :captured_at, :lat, :lon, :heading, :url)
                   ON CONFLICT(id) DO UPDATE SET url = excluded.url""",
                r,
            )
            n += 1
    return n


def images_to_download(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM images WHERE path IS NULL AND url IS NOT NULL").fetchall()


def set_image_path(conn: sqlite3.Connection, image_id: str, path: str) -> None:
    with conn:
        conn.execute("UPDATE images SET path = ? WHERE id = ?", (path, image_id))


def images_to_process(conn: sqlite3.Connection, limit: int | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM images WHERE path IS NOT NULL AND processed = 0"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql).fetchall()


def save_detections(conn: sqlite3.Connection, image_id: str, dets: Iterable[dict]) -> None:
    with conn:
        for d in dets:
            conn.execute(
                """INSERT INTO detections
                   (image_id, lat, lon, conf, area_ratio, severity, x1, y1, x2, y2)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    image_id, d["lat"], d["lon"], d["conf"], d["area_ratio"],
                    d["severity"], d["x1"], d["y1"], d["x2"], d["y2"],
                ),
            )
        conn.execute("UPDATE images SET processed = 1 WHERE id = ?", (image_id,))


def load_detections(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT d.lat, d.lon, d.conf, i.captured_at
           FROM detections d JOIN images i ON i.id = d.image_id"""
    ).fetchall()


def load_coverage(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Locations of images that have been run through the detector."""
    return conn.execute("SELECT lat, lon, captured_at FROM images WHERE processed = 1").fetchall()


def date_range(conn: sqlite3.Connection) -> tuple[int, int] | None:
    row = conn.execute(
        "SELECT MIN(captured_at) AS lo, MAX(captured_at) AS hi FROM images WHERE processed = 1"
    ).fetchone()
    if row is None or row["lo"] is None:
        return None
    return row["lo"], row["hi"]
