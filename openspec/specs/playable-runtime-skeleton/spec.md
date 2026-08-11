## Purpose

Defines the isolated, reproducible project and test skeleton required before
playable-runtime behavior is implemented.

## Requirements

### Requirement: Playable-runtime areas are isolated from the legacy simulation

The repository SHALL provide an importable `server` Python package, importable
`tests.playable` and `tests.e2e` Python packages, and a `godot` project root.
The initial `server` package and Godot bootstrap code MUST NOT import or mutate
legacy simulation modules, legacy run directories, JSONL data, model
credentials, or world-template fixtures.

#### Scenario: A developer imports the Python skeleton

- **WHEN** a developer imports `server`, `tests.playable`, and `tests.e2e`
- **THEN** all imports succeed without starting a simulation, contacting a
  service, or loading model credentials

#### Scenario: The legacy runner remains independent

- **WHEN** the playable-runtime skeleton exists in the repository
- **THEN** `scripts/run_world.py` retains its existing file contracts and does
  not depend on the new Python or Godot project areas

### Requirement: Python dependencies have an exact, reproducible lock

The repository SHALL retain the existing requirements-format declaration files
and SHALL include a checked-in, uv-generated exact lock resolving both runtime
and development-test requirements for the F0.1 Python baseline. The lock MUST
identify its generation command and MUST pin every direct requirement to an
exact version.

#### Scenario: A developer inspects the dependency lock

- **WHEN** a developer reads the tracked lock file
- **THEN** it identifies uv compilation from the repository's requirements
  inputs and contains exact versions for every direct runtime and test
  requirement

#### Scenario: A developer prepares a reproducible environment

- **WHEN** a developer follows the documented lock installation command after
  setup
- **THEN** uv can synchronize the declared environment without changing the
  legacy requirements declaration files

### Requirement: The Godot bootstrap project loads without game services

The repository SHALL contain a version-controlled GDScript Godot project whose
configured main scene is a bootstrap scene with a single plain `Node` root and
an attached bootstrap script. The project MUST load in Godot headless mode and
the bootstrap script MUST NOT access a network service, model provider,
database, Python sidecar, legacy run data, or player-facing assets.

#### Scenario: Godot loads the bootstrap project headlessly

- **WHEN** the declared Godot executable opens the `godot` project in headless
  mode
- **THEN** it loads the configured bootstrap scene without a parser, resource,
  or project-configuration error

#### Scenario: The bootstrap scene remains inert

- **WHEN** the bootstrap scene is instantiated
- **THEN** it creates only its root node and attached script without invoking
  gameplay, persistence, provider, or sidecar behavior

### Requirement: GdUnit4 is pinned and validates the bootstrap scene

The repository SHALL vendor the official GdUnit4 6.2.0 addon under the Godot
project and SHALL record the release URL, version, and SHA-256 digest in tracked
provenance metadata. The project SHALL include a GDScript GdUnit4 test that
instantiates the bootstrap scene and verifies its expected root and script. The
test MUST run headlessly on the declared macOS Apple Silicon host.

#### Scenario: A developer verifies addon provenance

- **WHEN** a developer inspects the Godot test infrastructure
- **THEN** they can identify the exact official GdUnit4 release and archive
  digest that supplied the vendored addon

#### Scenario: The bootstrap test runs headlessly

- **WHEN** a developer invokes the vendored GdUnit4 command-line runner against
  the bootstrap test suite with the declared Godot binary
- **THEN** the test completes successfully without opening an interactive
  Godot editor or requiring a real model, network service, or player data
