from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_in_fresh_interpreter(
    code: str, *, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run ``code`` in a new isolated interpreter with the project root importable.

    Several checks must not share a process with the rest of the suite: by the
    time pytest runs a test, other modules have imported ``src.world`` and loaded
    configuration, so before/after comparisons inside the test process can never
    fail. ``-I`` keeps the environment and the current directory off ``sys.path``.
    """
    prelude = f"import sys\nsys.path.insert(0, {str(PROJECT_ROOT)!r})\n"
    return subprocess.run(
        [sys.executable, "-I", "-c", prelude + code],
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def legacy_modules_loaded_by(import_statement: str) -> set[str]:
    """Return the ``src.world`` modules a fresh interpreter loads for an import."""
    completed = run_in_fresh_interpreter(
        "\n".join(
            [
                "import json",
                import_statement,
                "print(json.dumps(sorted(name for name in sys.modules"
                " if name == 'src.world' or name.startswith('src.world.'))))",
            ]
        )
    )
    assert completed.returncode == 0, completed.stderr
    return set(json.loads(completed.stdout.strip().splitlines()[-1]))
