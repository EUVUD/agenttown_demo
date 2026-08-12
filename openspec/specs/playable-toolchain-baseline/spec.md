## Purpose

Defines the exact, version-controlled toolchain baseline for the playable Godot runtime and its isolated Python tests.

## Requirements

### Requirement: The playable toolchain baseline is declared exactly

The system SHALL declare the playable-runtime toolchain in a version-controlled machine-readable manifest. The manifest MUST specify CPython 3.14.6 using the standard GIL build, pytest 9.1.1, Godot Standard 4.7.1 using GDScript, matching Godot 4.7.1 export templates, and GdUnit4 6.2.0. It MUST identify macOS Apple Silicon as the F0.1 verification target and identify Windows x86_64 as a later target that is not verified by this change.

#### Scenario: A developer inspects the declared baseline

- **WHEN** a developer reads the playable toolchain manifest
- **THEN** the exact required versions, runtime variants, scripting language, export-template version, GdUnit4 version, and verification scope are available without relying on an ambient local installation

#### Scenario: A free-threaded Python build is proposed for the baseline

- **WHEN** a change proposes a free-threaded CPython build for playable-runtime work
- **THEN** the baseline treats it as unsupported and identifies the standard GIL build as required

### Requirement: The Python test environment is isolated and exact

The repository SHALL provide an English-language procedure to create a project-local `.venv` using CPython 3.14.6 with the standard GIL build and to install `pytest==9.1.1` into that environment. The procedure MUST NOT require replacing or modifying a host Python installation. The exact Python test dependency MUST be version-controlled separately from the legacy runtime dependency list.

#### Scenario: A developer creates the supported test environment

- **WHEN** a developer follows the documented setup on macOS Apple Silicon
- **THEN** the project has a local virtual environment using CPython 3.14.6 and pytest 9.1.1, while the host Python installation remains unchanged

#### Scenario: A developer runs the isolated tests

- **WHEN** a developer invokes pytest through the project-local virtual environment
- **THEN** the focused baseline tests and existing legacy tests use the interpreter and pytest installed in that environment

### Requirement: Godot is documented for manual verification

The repository SHALL document Godot Standard 4.7.1 with GDScript and matching 4.7.1 export templates as the supported engine setup. It SHALL document a manual, non-interactive engine-version check and the editor action for confirming export-template installation. It MUST NOT add a custom preflight command in F0.1.

#### Scenario: A developer validates the local engine installation

- **WHEN** a developer runs the documented headless version command against their local Godot executable
- **THEN** they can confirm whether it reports Godot 4.7.1 without opening an interactive editor session

#### Scenario: A developer prepares for future export work

- **WHEN** a developer opens a Godot project in the editor and checks export templates
- **THEN** the documentation directs them to install or confirm the matching Standard 4.7.1 export templates before packaging a build

### Requirement: Baseline verification is scoped and upgrades are explicit

The focused baseline and legacy test verification run in F0.1 MUST NOT contact a network service, load model credentials, invoke a real LLM, or require a Godot GUI after the local environment has been set up. A baseline version change MUST update the manifest, relevant focused validation, and documentation before the new version is treated as supported. GdUnit4 addon validation and Windows x86_64 verification are deferred until later playable-runtime work supplies their project and test infrastructure.

#### Scenario: F0.1 verification completes on the declared host target

- **WHEN** a developer runs the documented focused baseline and legacy Python tests on macOS Apple Silicon after creating the local environment
- **THEN** the checks complete using local files and tools without a network service, model credentials, real LLM, or Godot GUI

#### Scenario: A baseline version changes

- **WHEN** a proposed change updates any declared Python, pytest, Godot, GdUnit4, or export-template version
- **THEN** the change includes an updated manifest, relevant validation, and documentation before the new version is treated as supported
