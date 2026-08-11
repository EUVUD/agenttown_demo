## 1. Contract-First Test Skeleton

- [x] 1.1 Add a focused failing Python test for the required package paths,
  import isolation, dependency-lock metadata, and Godot project contract.
- [x] 1.2 Add the failing GDScript GdUnit4 bootstrap-scene test before adding
  the bootstrap scene and script it exercises.

## 2. Reproducible Dependencies

- [x] 2.1 Generate and check in the exact uv requirements-format lock from the
  existing runtime and development-test inputs, including its generation
  command and hashes.
- [x] 2.2 Download the official GdUnit4 6.2.0 release, verify its SHA-256,
  vendor its addon under `godot/addons/`, and record provenance metadata.

## 3. Isolated Runtime Skeleton

- [x] 3.1 Create the inert `server`, `tests/playable`, and `tests/e2e` Python
  package boundaries without importing legacy simulation code.
- [x] 3.2 Create the minimal GDScript Godot project, bootstrap scene, and
  bootstrap script with no gameplay or external-service behavior.
- [x] 3.3 Add ignore rules for generated Godot cache and GdUnit4 reports
  without ignoring source, provenance, or test files.

## 4. Verification and Roadmap Alignment

- [x] 4.1 Run the focused Python contract test, headless Godot bootstrap load,
  and the vendored GdUnit4 bootstrap test on macOS Apple Silicon.
- [x] 4.2 Run the complete existing Python suite and confirm the legacy runner
  remains independent of the new skeleton.
- [x] 4.3 Strictly validate the OpenSpec change, update F0.3 only after all
  in-scope checks pass, and record Windows validation as deferred.
