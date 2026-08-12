## 1. Declarative baseline

- [x] 1.1 Add a version-controlled TOML manifest declaring the exact CPython, pytest, Godot, export-template, GdUnit4, scripting-language, and macOS Apple Silicon verification baseline.
- [x] 1.2 Add a focused baseline loader and tests that validate the manifest and reject incomplete or unsupported runtime variants.
- [x] 1.3 Add an exact development-test dependency file for pytest and ensure the project-local `.venv` is not tracked.

## 2. Setup and policy documentation

- [x] 2.1 Document the macOS Apple Silicon setup using a project-local `.venv` and CPython 3.14.6 without modifying host Python.
- [x] 2.2 Document manual Godot Standard 4.7.1 and matching export-template verification, the deferred GdUnit4/Windows scope, test isolation, and the explicit upgrade policy.

## 3. Verification and roadmap alignment

- [x] 3.1 Create the project-local CPython 3.14.6 environment, install pytest 9.1.1, and run the focused baseline tests plus the existing legacy Python test suite without network, model credentials, or a Godot GUI.
- [x] 3.2 Validate the local macOS Godot Standard 4.7.1 installation and matching export-template availability without introducing a Godot project.
- [x] 3.3 Validate the OpenSpec change strictly and update the F0.1 roadmap checkpoint only after all in-scope acceptance checks pass; leave Windows and GdUnit4 addon validation for later playable-runtime work.
