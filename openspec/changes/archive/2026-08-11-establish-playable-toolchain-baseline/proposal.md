## Why

The playable runtime is planned as a Godot desktop client with a Python sidecar, but the repository currently contains only the legacy Python simulation and does not declare a reproducible game-runtime toolchain. Contributors therefore risk using incompatible Python, pytest, Godot, or GdUnit4 versions before any playable code exists.

F0.1 should make those version choices explicit, not add a custom preflight program. The immediate goal is a small, inspectable baseline and a verified macOS Apple Silicon development environment.

## What Changes

- Establish a version-controlled playable-runtime baseline:
  - CPython 3.14.6 using the standard GIL build.
  - pytest 9.1.1 in a project-local virtual environment.
  - Godot Standard 4.7.1 using GDScript and matching 4.7.1 export templates.
  - GdUnit4 6.2.0, recorded for the future Godot project.
- Add a small machine-readable manifest and focused validation tests so baseline changes are intentional and reviewable.
- Document a macOS Apple Silicon setup using a project-local `.venv`, the manual Godot/template check, and the upgrade policy.
- Keep default test verification isolated from network services, model credentials, real LLMs, and an interactive Godot GUI after dependencies are installed.
- Defer Windows x86_64 verification and GdUnit4 addon validation until later playable-runtime work introduces the required project and test infrastructure.

## Capabilities

### New Capabilities

- `playable-toolchain-baseline`: Declares the supported Python, Python-test, Godot, and future Godot-test environment for the playable runtime.

### Modified Capabilities

- None.

## Impact

- Adds a toolchain manifest, focused baseline validation, isolated Python-test setup, and documentation.
- Does not add a preflight command, Godot project, CI system, dependency lock for the full application, or playable runtime.
- Preserves the behavior and JSONL persistence contracts of `scripts/run_world.py` and the legacy simulation.
