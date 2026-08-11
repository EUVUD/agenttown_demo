from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_SCHOOL_FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "f0_school.json"


def load_school_fixture() -> dict[str, Any]:
    """Decode a fresh copy of the fixed F0 school fixture."""
    return json.loads(_SCHOOL_FIXTURE_PATH.read_text(encoding="utf-8"))
