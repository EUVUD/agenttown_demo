## Context

F0.1 established the supported CPython, Godot, and GdUnit4 versions, but the
repository remains a legacy Python simulation with no playable-runtime project
root, test homes, or transitive dependency lock. The F0.3 roadmap slice must
add only the infrastructure needed to prove that the declared toolchain can
load a GDScript project and execute a test.

Research inputs are intentionally narrow: the repository already documents and
has uv available for local environments; uv supports compiling existing
requirements-format inputs without a packaging migration; and GdUnit4 provides
an official addon distribution and headless command-line runner. The checked
host is macOS Apple Silicon with Godot 4.7.1. Windows validation remains outside
this slice.

## Goals / Non-Goals

**Goals:**

- Create isolated, importable homes for the future Python sidecar and its
  playable/e2e tests.
- Lock the existing Python and test dependency inputs reproducibly with uv.
- Create a loadable GDScript Godot project with one bootstrap scene and one
  headless GdUnit4 test.
- Pin and record the exact GdUnit4 6.2.0 addon source so future work does not
  depend on the Godot Asset Library or an ambient installation.
- Prove all new infrastructure with focused, offline-after-setup checks.

**Non-Goals:**

- Create a sidecar API, SQLite schema, world model, gameplay loop, player UI,
  assets, export preset, or packaged application.
- Change `requirements.txt`, `scripts/run_world.py`, legacy JSONL persistence,
  or existing template/director contracts.
- Migrate the repository to `pyproject.toml`, a uv-managed project, or a new
  Python distribution layout.
- Verify the Godot addon or game test runner on Windows x86_64.

## Decisions

### Keep requirements inputs and add a uv-generated lock

The existing `requirements.txt` and `requirements-dev.txt` remain declarative
inputs for the legacy project. F0.3 SHALL generate a checked-in exact
requirements-format lock from both inputs with uv, using the F0.1 CPython
baseline. A focused test will verify that direct requirements are represented
by exact pins in the lock and that the documented generation command is
recorded in its header.

This uses uv's pip-compatible compile workflow rather than introducing
`pyproject.toml` and `uv.lock`. A project migration is a broader dependency and
packaging decision than F0.3 requires; a requirements-format lock is readable
by uv and pip-compatible tooling while preserving the old runner contract.

**Alternatives considered:**

- Use `pyproject.toml` with `uv.lock`: rejected for this slice because it
  changes the repository's package-management model before the sidecar exists.
- Keep only lower-bounded requirements: rejected because it cannot reproduce
  the transitive environment.
- Add pip-tools: rejected because uv is already the declared setup tool and
  provides the required compatible compiler without another dependency.

### Vendor the official GdUnit4 release with provenance metadata

The change SHALL retrieve the official GdUnit4 6.2.0 release archive once,
extract its addon at the release-defined path under `godot/addons/`, and commit
the addon files. A small tracked provenance file beside the Godot project SHALL
record the release URL, version, and archive SHA-256. This makes headless test
execution independent of AssetLib interaction and repeatable after checkout.

The addon is development/test infrastructure only. Future export work SHALL
exclude it from game artifacts; F0.3 does not create exports.

**Alternatives considered:**

- Install through the Godot Asset Library: rejected because it requires a GUI,
  mutable editor state, and an unpinned download workflow.
- Use a Git submodule: rejected because checkout becomes network-dependent and
  a tag alone is weaker provenance than a release archive digest.
- Defer the addon again: rejected because F0.1 explicitly deferred validation
  until a Godot project exists, which F0.3 now supplies.

### Keep the Godot project deliberately inert

`godot/project.godot` SHALL select a bootstrap scene whose root is a single
plain `Node` with one attached GDScript. The script SHALL not access files,
network services, model credentials, SQLite, the Python sidecar, or legacy run
data. The sole GdUnit4 suite SHALL instantiate that scene and assert its
expected root/script identity.

This is the smallest end-to-end proof that the chosen editor, addon, GDScript,
and project layout cooperate. It is not a prototype UI or a playable vertical
slice.

### Use focused checks before broad suites

A Python-focused test SHALL validate the directory contract, lock metadata, and
imports. The GdUnit4 runner bundled with the addon SHALL run the GDScript suite
in headless mode on the declared macOS host. The existing Python suite runs
after the focused checks. Generated Godot cache and test-report directories
remain ignored.

## Risks / Trade-offs

- [The GdUnit4 release layout differs from documentation casing] → Preserve
  the archive's addon path and assert the expected plugin manifest and runner
  rather than inventing a renamed layout.
- [Dependency resolution changes as registries publish new releases] → Commit
  the exact generated lock and require deliberate regeneration for upgrades.
- [A release archive or dependency cannot resolve for CPython 3.14.6] → Stop
  the change before marking the roadmap item complete and surface the concrete
  incompatible dependency to the user.
- [Vendoring the addon enlarges the repository] → Keep the scope to the
  official release contents and document provenance; do not vendor assets or
  unrelated tools.
- [Windows runner behavior differs] → Leave it explicitly unverified until a
  later desktop-platform slice rather than imply cross-platform support.

## Migration Plan

The change is additive. Create the failing focused tests first, add the Python
and Godot skeletons, generate the lock, vendor the verified addon, then run the
focused checks and the complete existing Python suite. No data migration or
runtime cutover is needed.

Rollback removes the new directories, lock, provenance metadata, focused test,
and this OpenSpec change. Existing legacy requirements and simulation behavior
remain intact.

## Open Questions

- None for F0.3. A later platform-validation change will decide whether Windows
  runner invocation is normalized behind a cross-platform wrapper.
