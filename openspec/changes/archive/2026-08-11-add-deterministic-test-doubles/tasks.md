## 1. Contract Tests

- [x] 1.1 Add and run a focused failing pytest contract for deterministic fakes, fixture isolation, temporary SQLite, and repeatable persisted output.

## 2. Deterministic Test Support

- [x] 2.1 Implement test-only `FakeClock` and scripted `FakeLLM` helpers with explicit failure for unexpected prompts.
- [x] 2.2 Add the checked-in fixed school JSON fixture and an independently decoding loader.
- [x] 2.3 Add the file-backed temporary SQLite pytest fixture with foreign-key enforcement and teardown cleanup.

## 3. Verification

- [x] 3.1 Make the focused deterministic-support contract test pass and refactor only as needed for clarity.
- [x] 3.2 Run the relevant playable tests, the full Python suite, and strict OpenSpec validation.
