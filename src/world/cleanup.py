from __future__ import annotations

import json
from pathlib import Path

from src.utils import get_logger
from src.world.clock import TimeState

_LOGGER = get_logger("cleanup", quiet=True)

# advantages.jsonl: time is a dict {"start": ..., "end": ...}, not a TimeState string
_EXCLUDED_NAMES = {"advantages.jsonl"}

# Director-authored inputs and the client timeline are not simulation outputs:
# their rows carry the time they are scheduled for (which may lie ahead of the
# resume point) and nothing re-creates them, so a resume must leave them alone.
# ``director/applications.jsonl`` is a simulation output and is trimmed normally.
_EXCLUDED_RELATIVE_PATHS = {
    Path("director/events.jsonl"),
    Path("director/results.jsonl"),
    Path("visualization/timeline.jsonl"),
}


def _cutoff_index(lines: list[str], *, start_time: TimeState) -> tuple[int | None, int]:
    """Find the first index to cut from.

    Traverse from the start; every line should contain a `time` field and be
    ordered non-decreasingly by time. As soon as a line is encountered where:
    - the current line's time < the previous line's time; or
    - the current line's time >= start_time;
    return that line's index, meaning that line and all following lines should
    be removed.

    Returns (idx, kept), where idx is the cut start point (None means no cut is
    needed) and kept is the number of lines that should be retained.
    """
    prev_t: TimeState | None = None
    kept = 0
    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s:
            # Skip empty lines (these are never written, but handle defensively).
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON at line {i + 1}") from e

        if "time" not in obj:
            raise ValueError(f"Missing time at line {i + 1}")
        try:
            cur_t = TimeState.from_string(obj["time"])
        except Exception as e:
            raise ValueError(
                f"Invalid time format at line {i + 1}: {obj['time']}"
            ) from e

        if prev_t is not None and cur_t < prev_t:
            return i, kept
        if cur_t >= start_time:
            return i, kept

        prev_t = cur_t
        kept += 1

    return None, kept


def _clean_one_file(path: Path, *, start_time: TimeState) -> bool:
    """Clean a single jsonl file; return True if modified.

    Strategy: find the first position that needs trimming and remove that line
    along with all lines after it; otherwise leave the file unchanged.
    """
    logger = _LOGGER
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False

    # Process line by line, keeping the original line text for writing back to
    # avoid unnecessary formatting changes.
    lines = raw.splitlines()
    idx, kept = _cutoff_index(lines, start_time=start_time)
    if idx is None:
        return False

    removed = len(lines) - idx
    new_lines = [ln for ln in lines[:idx] if ln.strip()]
    if new_lines:
        tmp = "\n".join(new_lines) + "\n"
        path.write_text(tmp, encoding="utf-8")
        logger.info(
            "trimmed %s: kept=%d, removed=%d",
            path.as_posix(),
            len(new_lines),
            removed,
        )
    else:
        # All records removed: delete the file entirely to avoid
        # an empty-file ghost that blocks future recreation.
        # System-required files (general.jsonl, working_memory.jsonl)
        # will be recreated by DataManager.__post_init__ via _ensure_file.
        path.unlink()
        logger.warning(
            "deleted %s: all %d records removed (time >= %s)",
            path.as_posix(),
            removed,
            start_time,
        )
    return True


def clean_append_only_jsonl_before(*, world_name: str, start_time: TimeState) -> None:
    """Trim all append-only jsonl files under data/{world} to < start_time.

    - Traverses: data/{world}/**/*.jsonl
    - Excludes: advantages.jsonl (its "time" is a dict interval, a post-simulation artifact),
      director/events.jsonl, director/results.jsonl and visualization/timeline.jsonl
      (player-authored inputs and their timeline entries; see _EXCLUDED_RELATIVE_PATHS)
    - Rule: trim from the first entry where time goes in reverse or out of bounds (see _cutoff_index).
    - Only writes back the file if trimming actually occurred.
    """
    logger = _LOGGER
    root = Path("data") / world_name
    if not root.exists():
        return

    trimmed = 0
    deleted = 0
    scanned = 0
    for p in sorted(root.rglob("*.jsonl")):
        if p.name in _EXCLUDED_NAMES:
            continue
        if p.relative_to(root) in _EXCLUDED_RELATIVE_PATHS:
            continue
        scanned += 1
        try:
            if _clean_one_file(p, start_time=start_time):
                if p.exists():
                    trimmed += 1
                else:
                    deleted += 1
        except Exception as e:
            # Backend error: re-raise so the caller sees the problem; avoid silently swallowing it
            raise RuntimeError(f"cleanup failed for {p.as_posix()}: {e}") from e

    logger.info(
        "[CLEANUP SUMMARY] start_time=%s | scanned=%d, trimmed=%d, deleted=%d, untouched=%d",
        start_time,
        scanned,
        trimmed,
        deleted,
        scanned - trimmed - deleted,
    )
