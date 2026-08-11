from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TemporaryDatabase:
    """The file and open connection for one isolated test database."""

    path: Path
    connection: sqlite3.Connection


def create_temporary_database(tmp_path: Path) -> TemporaryDatabase:
    """Create an empty file-backed SQLite database for a single test."""
    database_path = tmp_path / "world.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return TemporaryDatabase(path=database_path, connection=connection)
