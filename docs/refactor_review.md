# Codebase Refactoring Review

This review covers the whole repository at `46d2c49` plus the director-input change that follows it. Four independent read-only reviews split the code as follows:

| Area | Files |
|---|---|
| Legacy role agents and utilities | `src/agents/*`, `src/utils.py`, `src/config.py` |
| Legacy world engine and director layer | `src/world/*` |
| Prototype and playable-runtime skeleton | `prototype/`, `server/`, `godot/`, `tests/playable`, `tests/support` |
| Scripts, tests, CI, docs, OpenSpec | `scripts/`, `tests/`, `.github/`, `docs/`, `openspec/` |

A second pass then tried to reproduce every bug listed in section 1 against copies of the code, and four reviewers attacked the director change. Every claim is tagged with how it was established.

- **reproduced**: a script was run against a copy of the code and showed the failure.
- **read**: established by reading or grep/AST analysis, not executed.

Items under "Already fixed" are changed on the `feature/update-prototype-handoff` branch.

## Already fixed

| Problem | Where |
|---|---|
| Director results were never consumed by the weekly simulation | `src/world/director.py`, `src/world/world.py`, `src/agents/data_manager.py` |
| Characters added through the director service never joined a running roster | `src/world/world.py` (`_sync_director_roster`), `src/world/template_world.py` |
| Every snapshot overwrote one file named after a fixed time | `src/world/visualization.py` |
| Importing `src.world.clock` required `config.json` | `src/world/clock.py` |
| A template run with any director data crashed legacy resume cleanup | `src/world/cleanup.py` |
| Template worldview and state files lacked the keys and row shape the engine reads | `src/world/template_world.py` |
| `requires_home` was true for every join mode if any mode set it | `src/world/template_world.py` |
| The two "server must not import `src.world`" tests could never fail in a full run | `tests/support/fresh_interpreter.py` |
| Generated paths (`logs/`, `rft_data/`, run directories, `config.json`) were not ignored | `.gitignore` |
| A character added in a later year crashed the world because the profile was always written as `year=2020.json` | `src/world/template_world.py` |
| Resume deleted a newcomer's state and memories because they were stamped at the joining week | `src/world/template_world.py` |
| Starting a template run again failed on characters added since the last start | `src/world/world.py` |
| The year-end position season would assert on a newcomer whose role was not in the position store | `src/world/world.py` |
| One stored event with an unreadable timing would stop every week | `src/world/director.py` |
| Prototype catch-up repeated the absence after a provider error | `prototype/engine.py` |
| Every prototype snapshot carried all NPC secrets | `prototype/engine.py`, `prototype/server.py` |
| Narrator text could carry an undiscovered secret into protagonist prompts | `prototype/boundary.py`, `prototype/engine.py` |
| A prototype world broke when `world.json` changed after it was created | `prototype/engine.py`, `prototype/store.py` |
| Week-end snapshots would have published the full body of private relationship notes | `src/world/visualization.py` |

The behavior change was specified in `openspec/changes/archive/2026-11-06-wire-director-inputs-into-simulation/` and now lives in the main specs.

## 1. Bugs, ranked

All of these exist at `46d2c49`. None is caused by the director change. Bugs 1 to 4 are fixed on this branch.

| # | Bug | Status | Fix size |
|---|---|---|---|
| 1 | Prototype catch-up is not resumable. A provider error in the absence-letter call, after offscreen days are committed, leaves `last_seen_at` unchanged, so the retry simulates the absence again. A 10-day absence ends at world day 15 with two sleep events. Fixed: the plan is stored before the first model call and updated with every committed day. | reproduced, then fixed | done |
| 2 | Every prototype snapshot contains all NPC secrets, and the HTTP responses carry them. The `?debug=1` view only toggles CSS. Fixed: `debug` needs a server started with `--dev` and a request with `?debug=1`. | reproduced, then fixed | done |
| 3 | Narrator `memory` text is stored and later placed verbatim in protagonist prompts. A secret the narrator writes, without a discovery, appears in the next chat prompt. The README lists the output check as not done, but the test suite gives no warning. Fixed: narrator output is screened before it is stored. Only copied or lightly edited secret text is caught, so a paraphrase can still pass, and the timeline still shows scene text to the player. | reproduced, then fixed | done |
| 4 | The prototype applies today's `world.json` to a world created from an older one. Renaming, adding, or dropping an NPC, or renaming the current location, turns every state request into a 500. The stored blueprint is never read. Fixed: each world uses the blueprint stored with it. | reproduced, then fixed | done |
| 5 | `World.position_store` and the year-end season use different `PositionStore` objects. At the next year start the stale one rewrites `positions.json` and drops the season's occupancy changes. Needs two or more years. Fix: `self.position_store = get_position_store(self.data_dir)` after the season. | reproduced | S |
| 6 | `generate_with_fc` returns the string `"NO_RESPONSE"` when retries run out, but `get_response`, `get_response_json`, the validator, and `_compact_response` index the result as a list. A provider outage ends in `TypeError`, which also defeats the retry and fallback loop that wraps them. Fix: raise one error type, or return a list. | reproduced | S |
| 7 | When response validation exhausts its retries, the saved generation trace holds the first rejected answer while the agent says the last retry. Applies to the contact, solo, and social-ranking paths, and only when validation is enabled. | reproduced | S |
| 8 | `scripts/build_rft_data.py --output` can make the god-sample path equal the roleplay path, so one overwrites the other. Without a `.jsonl` suffix the report overwrites the samples, and `--top 0` is ignored. The script also reads the repository `config.json` instead of the run's own. | reproduced (config source: read) | S |
| 9 | `scripts/time_analysis.py` shifts every timestamp by a hard-coded 15 hours. | read | S |
| 10 | Logger registries and a `loggerDict` scan are not thread-safe while agents run in a thread pool. Latent. | read | S to M |
| 11 | When a solo activity evaluation exhausts its retries, `evaluate_solo_activity` raises `UnboundLocalError` because a function-local `get_logger` import shadows the module-level name. If that is fixed, `activity.py` then slices `None` and raises `TypeError`. | partly reproduced: the stub run shows the `TypeError`; the live path fails earlier | S |

### Independent check of the director change

Four reviewers attacked the change from different angles, and a skeptic tried to refute each finding. Eighteen findings held, and the most serious was a crash when a character joins after the first year. All were fixed or covered by tests. The same pass confirmed that legacy prompts are byte-identical, that `clock.py` behaves as before once configuration is loaded, and that no director path writes character state. The new tests were then mutation-tested in a copy: 36 deliberate breakages of the new code, and every one now turns the suite red.

At `46d2c49` a template run was also unusable by the engine for three separate reasons, all reproduced: resume cleanup rejected the director files, the worldview lacked `world_setting`, and the first state row had the wrong shape. A fourth mismatch, `assets.money` against `assets.deposit`, was found on the way.

The two tests that claim `server` must not import `src.world` could not catch a violation. At `46d2c49` a planted import either broke test collection (no `config.json`, because the clock loaded configuration on import) or went unnoticed (`config.json` present). They now run in a fresh interpreter.

## 2. Contract gaps

- **Events cannot rebuild state.** Prototype events omit fields the state update consumes, and chat, influence, and letter-read changes emit no event at all. D1.5 and D1.6 need event payloads that are sufficient reducer input.
- **Idempotency only exists for chat.** Advance, session, and world-reset requests have no command id, and `save_state` has no expected-version check (S2.2, S2.3, A6.3).
- **Directors still skip two spec items.** Targets and locations are not validated when an event is created (they are checked when applied), only `applied` and `skipped` outcomes exist, and `DirectorEvent.status` stays `pending` forever while results say `applied`.
- **Snapshot location is always empty.** No engine file stores a character location, so `last_known_location` is null for engine runs.
- **`server.domain` and the prototype disagree.** `EventId.new()` needs Python 3.14 while the prototype claims 3.13, and `TimeSlot` fixes four slots while the blueprint declares its own.
- **Template runs still cannot be started by `scripts/run_world.py`.** It requires a base world directory next to the run. A short adapter is the missing piece.

## 3. Structural refactors

Ordered by value for the roadmap. Each can land as an additive change behind re-exports.

| # | Refactor | Why | Size |
|---|---|---|---|
| 1 | Add focused tests for pure legacy logic: `TimeState`, `Clock`, `cleanup._cutoff_index`, `scheduling` (`make_activity_id`, `PublicEvent`, `confirm_schedule`), `reward`, `parse_kv_args`, `extract_json`, validators | Nothing in the engine has a unit test, so no later split is safe | M |
| 2 | Delete dead code verified by AST and grep: about 900 lines in `src/utils.py`, `src/agents/context.py`, commented tool specs in `functions.py`, six `DataManager` methods, the commented `World._build_today_activities`, unused constants and imports | Pure deletion that makes the next steps readable | S |
| 3 | Remove import-time config loading from `utils`, `prompts`, `data_manager`, `role_agent`. Provide builders that return the same strings | Blocks tests, a second world in one process, and the adapter | M |
| 4 | Introduce one JSONL helper and one data-root helper. Nine JSONL implementations and 25 hard-coded `Path("data")` exist | The runner only works from the repository root | M |
| 5 | Split `src/utils.py` into client, cache, logging, and parsing modules with `src/utils.py` re-exporting every name | A 3,475-line module mixes the two riskiest subsystems with dead helpers | M |
| 6 | Decompose `DataManager` (2,635 lines, nine responsibilities) by composition | It is the persistence contract AGENTS.md protects | L |
| 7 | Split the 250 to 500 line functions `SoloActivity.run`, `JointActivity.run`, `PublicActivity.run`, `MessageCenter.confirm_schedule` without changing call order | Their deterministic parts have no tests | M to L |
| 8 | Share the god-prompt scaffolding and delta clipping in `prompts.py` and `god.py`; replace regex JSON extraction with `extract_json`; split `god.py` into a package | Triplicated code drifts | M |
| 9 | `World`: one fan-out helper instead of ten copies, and move resume cleanup out of `__init__` | Building a `World` for a test currently rewrites run data | S to M |

### Prototype toward the roadmap

1. Done: the knowledge boundary now has a server-side debug gate and a screen for narrator output. The proper fix is to separate what happened from what she perceived in the narrator schema (M9.1).
2. Move validators into a pure `contracts` module with legal and illegal fixtures (D1.4 payload draft).
3. Make events complete and catch-up resumable (D1.4, R3.7).
4. Extract a reducer and a replay function and test replay equals the stored state (D1.5, D1.6).
5. Read the stored blueprint per world and reconcile `world.json` with `tests/fixtures/f0_school.json` (D1.2, D1.3).
6. Add expected-version saves, a command table, and one transaction per command (S2.2, S2.3).
7. Fold the repair, salvage, and fallback logic of `llm.py` and `engine.py` into one structured-task runner (L5.1, L5.4).
8. Move routes into `server/` only through an OpenSpec change, keeping credential loading outside it.

## 4. Tests, CI, docs, repository hygiene

- **Version pins live in about ten places.** `toolchain.toml` is not the single source: the loader, tests, workflow, and docs repeat the numbers. Cross-check them from the manifest instead.
- **Script helpers have no tests.** `build_rft_data`, `compute_metrics`, `time_analysis`, and `extract_activity_dialogues` all contain pure transformations.
- **Documentation drift.** The README tree omits `prototype/`, `server/`, `godot/`, and `openspec/`. The README test command uses `unittest` while AGENTS.md uses pytest. The roadmap lists `scripts/test_game.sh`, which does not exist, and an empty `tests/e2e`. `docs/ci_cd.md` prescribes rebase merges while the last PR was squashed. `prototype/README.md` omits one environment variable and the host and port flags.
- **No pytest configuration.** `pytest -q` walks `data/` and the vendored Godot addon while collecting.
- **Tracked tool state.** Three files under `.superpowers/` are committed, including a server pid.
- **Duplicate doubles.** The prototype tests define their own clock and provider instead of using `tests/support/fakes.py`.

## 5. Suggested order

1. The small `run_manager` adapter and its document, to finish the director track.
2. Refactor 1 (tests for pure logic), then 2 (dead code), then 3 and 4.
3. The remaining structural splits, one module per change.
4. Prototype extraction in the order above, starting with D1.2.
