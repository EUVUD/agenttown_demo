"""SQLite persistence: one state row per world plus append-only events, messages and letters."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

SCHEMA = """
CREATE TABLE IF NOT EXISTS worlds (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    blueprint TEXT NOT NULL,
    state TEXT NOT NULL,
    version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(id),
    seq INTEGER NOT NULL,
    day INTEGER NOT NULL,
    slot INTEGER NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload TEXT NOT NULL,
    causes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (world_id, seq)
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(id),
    client_id TEXT,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    day INTEGER NOT NULL,
    slot INTEGER NOT NULL,
    reply_to TEXT,
    meta TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS messages_client_id
    ON messages (world_id, client_id) WHERE client_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS letters (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(id),
    day INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    causes TEXT NOT NULL,
    read_at TEXT,
    created_at TEXT NOT NULL
);
"""


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class Store:
    """A short-lived connection; callers open one per operation and serialize writes."""

    def __init__(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.conn.close()

    @contextmanager
    def tx(self) -> Iterator[None]:
        with self.conn:
            yield

    def migrate(self) -> None:
        self.conn.executescript(SCHEMA)

    # Worlds ----------------------------------------------------------------

    def create_world(
        self, world_id: str, blueprint: Mapping[str, Any], state: Mapping[str, Any], now: datetime
    ) -> None:
        self.conn.execute(
            "INSERT INTO worlds (id, created_at, blueprint, state, version) VALUES (?, ?, ?, ?, 1)",
            (world_id, now.isoformat(), _dump(blueprint), _dump(state)),
        )

    def latest_world_id(self) -> str | None:
        row = self.conn.execute(
            "SELECT id FROM worlds ORDER BY created_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None

    def load_blueprint(self, world_id: str) -> dict:
        row = self.conn.execute("SELECT blueprint FROM worlds WHERE id = ?", (world_id,)).fetchone()
        if row is None:
            raise LookupError(f"unknown world: {world_id}")
        return json.loads(row["blueprint"])

    def load_state(self, world_id: str) -> dict:
        row = self.conn.execute("SELECT state FROM worlds WHERE id = ?", (world_id,)).fetchone()
        if row is None:
            raise LookupError(f"unknown world: {world_id}")
        return json.loads(row["state"])

    def save_state(self, world_id: str, state: Mapping[str, Any]) -> None:
        self.conn.execute(
            "UPDATE worlds SET state = ?, version = version + 1 WHERE id = ?",
            (_dump(state), world_id),
        )

    # Events ----------------------------------------------------------------

    def append_event(
        self,
        world_id: str,
        *,
        day: int,
        slot: int,
        kind: str,
        title: str,
        summary: str,
        payload: Mapping[str, Any],
        causes: Sequence[Mapping[str, Any]],
        now: datetime,
    ) -> str:
        seq = self.conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE world_id = ?", (world_id,)
        ).fetchone()[0]
        event_id = new_id("evt")
        self.conn.execute(
            "INSERT INTO events (id, world_id, seq, day, slot, kind, title, summary, payload, causes, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, world_id, seq, day, slot, kind, title, summary, _dump(payload), _dump(causes), now.isoformat()),
        )
        return event_id

    def list_events(
        self, world_id: str, *, limit: int = 60, kinds: Sequence[str] | None = None
    ) -> list[dict]:
        """Newest first."""
        sql, params = "SELECT * FROM events WHERE world_id = ?", [world_id]
        if kinds:
            sql += f" AND kind IN ({', '.join('?' for _ in kinds)})"
            params.extend(kinds)
        sql += " ORDER BY seq DESC LIMIT ?"
        params.append(limit)
        return [_event(row) for row in self.conn.execute(sql, params)]

    def events_for_day(self, world_id: str, day: int, kind: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM events WHERE world_id = ? AND day = ? AND kind = ? ORDER BY seq",
            (world_id, day, kind),
        )
        return [_event(row) for row in rows]

    # Messages --------------------------------------------------------------

    def add_message(
        self,
        world_id: str,
        *,
        role: str,
        text: str,
        day: int,
        slot: int,
        now: datetime,
        client_id: str | None = None,
        reply_to: str | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> str:
        message_id = new_id("msg")
        self.conn.execute(
            "INSERT INTO messages (id, world_id, client_id, role, text, day, slot, reply_to, meta, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (message_id, world_id, client_id, role, text, day, slot, reply_to, _dump(meta or {}), now.isoformat()),
        )
        return message_id

    def find_message_by_client_id(self, world_id: str, client_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM messages WHERE world_id = ? AND client_id = ?", (world_id, client_id)
        ).fetchone()
        return _message(row) if row else None

    def find_reply(self, message_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM messages WHERE reply_to = ? ORDER BY rowid LIMIT 1", (message_id,)
        ).fetchone()
        return _message(row) if row else None

    def recent_messages(self, world_id: str, limit: int) -> list[dict]:
        """The last `limit` messages, oldest first."""
        rows = self.conn.execute(
            "SELECT * FROM (SELECT rowid AS r, * FROM messages WHERE world_id = ? ORDER BY rowid DESC LIMIT ?)"
            " ORDER BY r",
            (world_id, limit),
        )
        return [_message(row) for row in rows]

    def count_messages(self, world_id: str, *, day: int, role: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM messages WHERE world_id = ? AND day = ? AND role = ?",
            (world_id, day, role),
        ).fetchone()[0]

    # Letters ---------------------------------------------------------------

    def add_letter(
        self,
        world_id: str,
        *,
        day: int,
        title: str,
        body: str,
        causes: Sequence[Mapping[str, Any]],
        now: datetime,
    ) -> str:
        letter_id = new_id("letter")
        self.conn.execute(
            "INSERT INTO letters (id, world_id, day, title, body, causes, read_at, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, NULL, ?)",
            (letter_id, world_id, day, title, body, _dump(causes), now.isoformat()),
        )
        return letter_id

    def list_letters(self, world_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM letters WHERE world_id = ? ORDER BY created_at DESC, rowid DESC", (world_id,)
        )
        return [
            {
                "id": row["id"],
                "day": row["day"],
                "title": row["title"],
                "body": row["body"],
                "causes": json.loads(row["causes"]),
                "read": row["read_at"] is not None,
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def mark_letter_read(self, world_id: str, letter_id: str, now: datetime) -> None:
        row = self.conn.execute(
            "SELECT read_at FROM letters WHERE world_id = ? AND id = ?", (world_id, letter_id)
        ).fetchone()
        if row is None:
            raise LookupError(f"unknown letter: {letter_id}")
        if row["read_at"] is None:
            self.conn.execute("UPDATE letters SET read_at = ? WHERE id = ?", (now.isoformat(), letter_id))


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _event(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "seq": row["seq"],
        "day": row["day"],
        "slot": row["slot"],
        "kind": row["kind"],
        "title": row["title"],
        "summary": row["summary"],
        "payload": json.loads(row["payload"]),
        "causes": json.loads(row["causes"]),
        "created_at": row["created_at"],
    }


def _message(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "text": row["text"],
        "day": row["day"],
        "slot": row["slot"],
        "reply_to": row["reply_to"],
        "meta": json.loads(row["meta"]),
    }
