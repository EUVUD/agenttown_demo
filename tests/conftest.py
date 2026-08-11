from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.support.temporary_database import TemporaryDatabase, create_temporary_database


@pytest.fixture
def temporary_database(tmp_path: Path) -> Iterator[TemporaryDatabase]:
    """Yield one file-backed SQLite database and close it after the test."""
    database = create_temporary_database(tmp_path)
    try:
        yield database
    finally:
        database.connection.close()
