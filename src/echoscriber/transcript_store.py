"""SQLite-backed TranscriptFeed implementation with FTS5 full-text search."""

from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path
from typing import Callable

from .models import AgentMode, SegmentSource, TranscriptSegment

_DB_DIR = Path.home() / ".local" / "share" / "echoscriber"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    started_at REAL NOT NULL,
    ended_at   REAL,
    language   TEXT
);

CREATE TABLE IF NOT EXISTS segments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    timestamp  REAL NOT NULL,
    source     TEXT NOT NULL,
    text       TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts USING fts5(
    text,
    content=segments,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS segments_ai AFTER INSERT ON segments BEGIN
    INSERT INTO segments_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TABLE IF NOT EXISTS chunk_summaries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    chunk_start REAL NOT NULL,
    chunk_end   REAL NOT NULL,
    segment_ids TEXT NOT NULL,
    summary     TEXT NOT NULL,
    model_used  TEXT NOT NULL,
    created_at  REAL NOT NULL
);
"""


class TranscriptStore:
    """Implements the TranscriptFeed protocol backed by SQLite + FTS5."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            _DB_DIR.mkdir(parents=True, exist_ok=True)
            db_path = _DB_DIR / "transcripts.db"
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._session_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO sessions (id, started_at) VALUES (?, ?)",
            (self._session_id, time.time()),
        )
        self._conn.commit()
        self._subscribers: list[Callable[[TranscriptSegment], None]] = []

    # -- TranscriptFeed protocol ------------------------------------------

    def subscribe(self, callback: Callable[[TranscriptSegment], None]) -> None:
        self._subscribers.append(callback)

    def recent(self, n_minutes: float) -> list[TranscriptSegment]:
        cutoff = time.time() - (n_minutes * 60)
        rows = self._conn.execute(
            "SELECT timestamp, source, text FROM segments "
            "WHERE session_id = ? AND timestamp >= ? ORDER BY timestamp",
            (self._session_id, cutoff),
        ).fetchall()
        return [
            TranscriptSegment(
                text=r[2], source=SegmentSource(r[1]), is_final=True, timestamp=r[0]
            )
            for r in rows
        ]

    def search(self, query: str, limit: int = 20) -> list[TranscriptSegment]:
        rows = self._conn.execute(
            "SELECT s.timestamp, s.source, s.text "
            "FROM segments_fts f "
            "JOIN segments s ON s.id = f.rowid "
            "WHERE f.text MATCH ? AND s.session_id = ? "
            "ORDER BY rank LIMIT ?",
            (query, self._session_id, limit),
        ).fetchall()
        return [
            TranscriptSegment(
                text=r[2], source=SegmentSource(r[1]), is_final=True, timestamp=r[0]
            )
            for r in rows
        ]

    def all_segments(self) -> list[TranscriptSegment]:
        rows = self._conn.execute(
            "SELECT timestamp, source, text FROM segments "
            "WHERE session_id = ? ORDER BY timestamp",
            (self._session_id,),
        ).fetchall()
        return [
            TranscriptSegment(
                text=r[2], source=SegmentSource(r[1]), is_final=True, timestamp=r[0]
            )
            for r in rows
        ]

    @property
    def session_id(self) -> str:
        return self._session_id

    # -- Write path (called by SessionController) -------------------------

    def append(self, segment: TranscriptSegment) -> None:
        if not segment.is_final:
            return
        now = time.time()
        self._conn.execute(
            "INSERT INTO segments (session_id, timestamp, source, text, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (self._session_id, segment.timestamp, segment.source.value, segment.text, now),
        )
        self._conn.commit()
        for cb in self._subscribers:
            cb(segment)

    # -- Chunk summary cache ----------------------------------------------

    def get_cached_summaries(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT chunk_start, chunk_end, summary FROM chunk_summaries "
            "WHERE session_id = ? ORDER BY chunk_start",
            (self._session_id,),
        ).fetchall()
        return [
            {"chunk_start": r[0], "chunk_end": r[1], "summary": r[2]} for r in rows
        ]

    def latest_summary_end(self) -> float | None:
        row = self._conn.execute(
            "SELECT MAX(chunk_end) FROM chunk_summaries WHERE session_id = ?",
            (self._session_id,),
        ).fetchone()
        return row[0] if row and row[0] is not None else None

    def save_chunk_summary(
        self,
        chunk_start: float,
        chunk_end: float,
        segment_ids: list[int],
        summary: str,
        model_used: str,
    ) -> None:
        import json

        self._conn.execute(
            "INSERT INTO chunk_summaries "
            "(session_id, chunk_start, chunk_end, segment_ids, summary, model_used, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                self._session_id,
                chunk_start,
                chunk_end,
                json.dumps(segment_ids),
                summary,
                model_used,
                time.time(),
            ),
        )
        self._conn.commit()

    def segments_in_range(self, start: float, end: float) -> list[tuple[int, TranscriptSegment]]:
        rows = self._conn.execute(
            "SELECT id, timestamp, source, text FROM segments "
            "WHERE session_id = ? AND timestamp >= ? AND timestamp < ? ORDER BY timestamp",
            (self._session_id, start, end),
        ).fetchall()
        return [
            (
                r[0],
                TranscriptSegment(
                    text=r[3], source=SegmentSource(r[2]), is_final=True, timestamp=r[1]
                ),
            )
            for r in rows
        ]

    # -- Lifecycle --------------------------------------------------------

    def end_session(self) -> None:
        self._conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (time.time(), self._session_id),
        )
        self._conn.commit()

    def close(self) -> None:
        self.end_session()
        self._conn.close()
