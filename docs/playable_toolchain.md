# Playable Toolchain Baseline

This document defines the F0.1 development baseline for **Tomorrow's Reply**.
The machine-readable source of truth is [`toolchain.toml`](../toolchain.toml).

## F0.1 Scope

| Tool | Required baseline |
| --- | --- |
| Python | CPython 3.14.6, standard GIL build |
| Python test runner | pytest 9.1.1 |
| Engine | Godot Standard 4.7.1 using GDScript |
| Export templates | Godot Standard 4.7.1 templates |
| Godot test addon | GdUnit4 6.2.0, vendored under `godot/addons/gdUnit4/` |

F0.1 is verified on macOS Apple Silicon only. Windows x86_64 is a target for
later playable-runtime work; it is not verified by this baseline. F0.3 adds
the minimal Godot project and validates the vendored GdUnit4 addon on macOS
Apple Silicon.

## Create the Isolated Python Test Environment

The project uses `.venv` to avoid changing the host Python installation. The
following commands use [uv](https://docs.astral.sh/uv/) to install a managed,
standard-GIL CPython 3.14.6 and create the local environment:

```bash
uv python install 3.14.6
uv venv --python 3.14.6 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
```

Do not request a free-threaded Python build (for example, a version ending in
`t`). The `.venv/` directory is ignored by Git.

Run the baseline and legacy tests through that environment:

```bash
.venv/bin/python -m pytest tests/test_playable_toolchain_baseline.py -q
.venv/bin/python -m pytest -q
```

## F0.3 Project Skeleton

The playable runtime starts as isolated, intentionally inert boundaries:

- `server/` is reserved for the future Python sidecar and does not import the
  legacy simulation runtime.
- `tests/playable/` and `tests/e2e/` are reserved for the new runtime's focused
  and end-to-end tests.
- `godot/` contains the Godot project, its inert `Node` bootstrap scene, the
  vendored GdUnit4 addon, and its first scene test.

`requirements.lock` is the exact, hash-checked resolution of
`requirements.txt` and `requirements-dev.txt`. Regenerate it only when either
input changes:

```bash
uv pip compile --python .venv/bin/python --generate-hashes \
  requirements.txt requirements-dev.txt --output-file requirements.lock
```

To install the locked Python set into the isolated environment, run:

```bash
uv pip sync --python .venv/bin/python requirements.lock
```

For a newly cloned Godot project, initialize Godot's local import cache once
before running the GdUnit4 test. The cache and test reports are ignored by Git:

```bash
cd godot
/Applications/Godot.app/Contents/MacOS/Godot --headless --editor --path . --quit
GODOT_BIN=/Applications/Godot.app/Contents/MacOS/Godot \
  ./addons/gdUnit4/runtest.sh -a tests/test_bootstrap_scene.gd
```

The GdUnit4 provenance and archive SHA-256 are recorded in
`godot/gdunit4.lock`. The addon is development-only and must be excluded from
future exported game builds.

F0.3 is verified on macOS Apple Silicon only. Running the Godot project and
GdUnit4 runner on Windows x86_64 remains deferred to a later platform-
validation change.

After the local environment has been created, these tests use only local files
and tools. They must not require a network service, model credentials, a real
LLM, or an interactive Godot GUI.

## Verify Godot Manually

F0.1 intentionally has no custom preflight command. Confirm the engine
version with the executable installed on the machine; a typical macOS app path
is shown below:

```bash
/Applications/Godot.app/Contents/MacOS/Godot --headless --version
```

The command must report Godot 4.7.1. Use the **Standard** editor, not the .NET
editor, and use GDScript for the playable Godot project.

Export templates are the platform-specific runtime pieces Godot uses when it
packages a game. Open the repository's `godot/` project, then use **Editor →
Manage Export Templates** to install or confirm the matching 4.7.1 Standard
templates. Export-template availability remains a manual editor check; the
automated GdUnit4 test does not package a game export.

## Upgrade Policy

The baseline uses exact versions. Any patch, minor, or major upgrade must:

1. Update `toolchain.toml`, the focused baseline validation, and this document
   in the same reviewed change.
2. Recreate the local environment and run the focused baseline and legacy test
   suite on macOS Apple Silicon.
3. Record a Godot migration and compatibility assessment for a Godot minor or
   major update. Treat a Godot major update as a separate migration change.

Do not silently treat an ambient Python, pytest, Godot, export-template, or
GdUnit4 version as supported.
