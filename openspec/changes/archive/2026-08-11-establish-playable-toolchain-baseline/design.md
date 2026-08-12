## Context

The repository currently contains a legacy Python simulation, a `requirements.txt` file with lower-bounded runtime dependencies, and a small unittest-style test suite. It has no declared Python runtime policy, no dependency lock, no Godot project, no GdUnit4 addon, and no playable-runtime test runner. The local developer environment has more than one Python 3.11 interpreter, demonstrating that an unqualified `python` command is not a reproducible contract.

The playable roadmap introduces a Godot desktop client and a Python sidecar while requiring the legacy runner and its JSONL persistence contracts to remain independent. The agreed baseline is CPython 3.14.6 with the standard GIL build, pytest 9.1.1, Godot Standard 4.7.1 with GDScript and matching export templates, and GdUnit4 6.2.0.

## Goals / Non-Goals

**Goals:**

- Record the playable-runtime toolchain in one machine-readable, version-controlled baseline manifest.
- Provide an isolated project-local Python test environment with an exact pytest version.
- Document manual Godot Standard and export-template verification for macOS Apple Silicon.
- Make version upgrades deliberate while preserving the existing legacy test baseline and runner contracts.

**Non-Goals:**

- Provide a custom preflight command, tool discovery, or machine-readable environment report.
- Create the `server/`, `godot/`, `tests/playable/`, or `tests/e2e/` skeletons planned for F0.3.
- Install or validate a GdUnit4 addon before a Godot project exists.
- Verify Windows x86_64, lock all Python application dependencies, introduce CI, build a distributable sidecar, or create a Godot project.
- Implement FakeClock, FakeLLM, SQLite fixtures, HTTP APIs, or user-facing game features.
- Support Python free-threaded builds, C#/.NET Godot projects, multiplayer, or a new source of truth for legacy run data.

## Decisions

### Store the baseline in a dedicated manifest

The implementation SHALL add a small TOML baseline manifest dedicated to the playable runtime. It SHALL declare exact tool versions, the Godot Standard/GDScript variant, matching export-template version, the recorded GdUnit4 version, and the current verification target. TOML is readable, supported by Python's standard library, and keeps game-runtime constraints separate from the legacy project's currently loose `requirements.txt`.

**Alternatives considered:**

- Put the versions only in `GAME_DEVELOPMENT_PLAN.md`: rejected because versioned data should be easy to inspect and validate without parsing prose.
- Convert the whole repository to `pyproject.toml` now: deferred to F0.3 because it would conflate toolchain policy with dependency and packaging migration.
- Use a developer-version-manager-specific file: rejected because the project needs a portable, inspectable contract.

### Use a project-local Python environment

The documented setup SHALL create `.venv` with CPython 3.14.6 using the standard GIL build and install `pytest==9.1.1` into that environment. The initial setup may obtain the interpreter, but it MUST NOT modify or replace a host Python installation. A separate exact development-test requirements file keeps the F0.1 test dependency distinct from the legacy runtime dependency list.

**Alternatives considered:**

- Rely on whichever `python` and `pytest` appear first on `PATH`: rejected because the local machine already demonstrates interpreter ambiguity.
- Lock all application and transitive dependencies now: deferred to F0.3, when the Python sidecar and its full runtime dependency set exist.

### Do not add a preflight command

F0.1 SHALL declare and document the baseline rather than implement a new command solely to compare local version strings. The manifest, focused validation tests, virtual-environment instructions, and explicit manual Godot version/template check make the selected versions visible without creating a second tool surface to maintain.

**Alternatives considered:**

- A standard-library-only preflight program: rejected as unnecessary ceremony before a Godot project or playable test runner exists.
- A shell-only checker: rejected for the same reason and because it would introduce platform-specific behavior before it has a consumer.

### Validate macOS Apple Silicon first

macOS Apple Silicon is the only F0.1 host verification target. Windows x86_64 remains a planned desktop target, but its clean-environment validation belongs to a later change once the project, test runner, and distribution choices exist. Intel Mac support is not implied by this change.

### Record GdUnit4 now and validate it with the project

The manifest records GdUnit4 6.2.0 because it is part of the chosen future Godot testing stack. Addon installation and validation are deferred to F0.3, when a `godot/` project gives the addon a legitimate home.

### Pin upgrades deliberately

The manifest SHALL use exact versions rather than ranges. A patch, minor, or major baseline upgrade SHALL update the manifest, focused validation, and relevant documentation before adoption. A Godot minor or major upgrade SHALL additionally record a migration and compatibility assessment; a major upgrade is a separate migration change.

## Risks / Trade-offs

- [A developer uses a Conda or system interpreter instead of `.venv`] → The setup documentation uses the `.venv` interpreter explicitly, and focused tests make the expected manifest values visible in review.
- [A local Godot installation drifts] → The documented manual command checks the exact engine version; matching export templates are checked in the editor before packaging work begins.
- [Windows-specific behavior emerges later] → Windows is explicitly deferred rather than reported as verified by F0.1.
- [GdUnit4 compatibility changes] → Its version is fixed now, while real addon validation starts only after F0.3 creates a project.
- [The manifest becomes a second dependency lock] → It contains only toolchain identity; complete runtime and transitive dependency locking remains F0.3 work.

## Migration Plan

This is additive because no playable runtime exists yet. Introduce the manifest, focused validation, and documentation without changing `scripts/run_world.py`, existing data packs, or their persistence behavior. Existing developers may continue to run the legacy runner with its current environment; new playable-runtime work follows the declared baseline.

Rollback consists of removing the new baseline files and documentation. No database, API, player data, or legacy simulation migration is involved.

## Open Questions

- Which distribution mechanism will later install Godot, GdUnit4, and matching export templates in local development and CI?
- Will the desktop alpha support Intel Macs, requiring universal validation, or only Apple Silicon Macs initially?
- What platform-neutral game-test entry point should F0.3 introduce for macOS and Windows?
