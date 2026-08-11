## Why

F0.1 declares the supported Python and Godot versions, but the repository still
has no loadable Godot project, isolated homes for playable-runtime tests, or
reproducible locked dependencies. Contributors cannot yet verify that the
declared toolchain can load a project and run a test without touching the legacy
simulation.

## What Changes

- Add an additive playable-runtime skeleton: an importable Python `server`
  package, root test packages for playable and end-to-end work, and a minimal
  GDScript Godot project with a bootstrap scene.
- Pin the Python dependency resolution produced from the existing requirements
  inputs using uv, without migrating the legacy application to a new packaging
  model or changing the legacy runner's dependency contract.
- Vendor the official GdUnit4 6.2.0 addon under the Godot project so one
  headless GDScript test can verify the project and its test infrastructure.
- Add focused checks that prove the Python package skeleton imports and the
  Godot bootstrap scene can be loaded and tested without a real model, network
  service, GUI, player data, or gameplay implementation.

## Capabilities

### New Capabilities

- `playable-runtime-skeleton`: Defines the isolated, reproducible project and
  test skeleton required before playable-runtime behavior is implemented.

### Modified Capabilities

- None.

## Impact

- Adds `server/`, `tests/playable/`, `tests/e2e/`, and `godot/` project areas,
  a uv-generated dependency lock, a pinned third-party test addon, and focused
  verification.
- Preserves `requirements.txt`, `scripts/run_world.py`, legacy JSONL contracts,
  existing world data, and all current OpenSpec capabilities.
- Does not add a sidecar API, SQLite persistence, player-facing Godot UI,
  assets, real model integration, or an exportable game build.
