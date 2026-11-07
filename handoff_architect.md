# Architect Session Handoff — Tomorrow's Reply

Read this first, then `handoff.md` (general state and environment), `GAME_DEVELOPMENT_PLAN.md` (roadmap), and `AGENTS.md` (rules). This file is for a session whose job is to decide architecture, not to write features.

## Your job

Decide how the playable game's runtime should be built, and in what order, using what already exists. Nothing here is decided except the items under "Fixed". Bring recommendations with evidence; the user decides.

## State at handoff

- `develop` is at `6798c4e`. PR #7 (director wiring, four prototype fixes, refactor review) and PR #8 (archive of the director change) are merged. CI passes on `develop`.
- One local commit is not pushed: `f70c1f9` on `chore/archive-playable-time-and-ids`, which archives `add-playable-time-and-ids` and creates the main spec `playable-time-and-identity`. No PR yet.
- 120 tests pass on Python 3.14.7. The prototype tests also pass on 3.13.5. `openspec validate --all --strict` passes for 8 specs. No OpenSpec change is active.
- Roadmap progress: F0, G0, and D1.1 are done. D1.2 `WorldBlueprintV1` is the next unchecked step. The prototype ticked nothing, because no acceptance criterion was verified against it.
- Never run: any real model call, the legacy runner smoke test (needs `config.json`), the Godot client beyond its bootstrap scene.
- Uncommitted in the working tree: this file (untracked) and edits to `handoff.md`, `prototype/README.md`, and `docs/refactor_review.md` that correct statements an independent review showed to be wrong. Nothing has been pushed since `develop` moved to `6798c4e`.
- This handoff was itself reviewed by an independent read-only session (Opus). Its findings are in "Review of this handoff" below. The wrong statements it found are already corrected here; the recommendations are the reviewer's, not the user's decisions.

## The three code bases

| Track | Where | What it is | Relation to the game |
|---|---|---|---|
| Legacy simulation | `src/`, `scripts/run_world.py` | Upstream Agentopia: weekly loop, God Model, life reward, JSONL persistence | Research runner. AGENTS.md says keep its behavior and file contracts. Not the game runtime. |
| Director layer | `src/world/director*.py`, `template_world.py`, `visualization.py`, `data/world_templates/` | Template packs, player-authored events, character entry, client snapshots | Built on the legacy engine. Now consumed by its weekly loop. Specified in `openspec/specs/director-events`, `dynamic-character-entry`, `visualization-state`, `world-templates`. |
| Playable runtime | `server/domain/`, `prototype/`, `godot/` | Plan: SQLite authority, Python sidecar, thin Godot client. Reality: value objects, a working spike, and an empty Godot scene | The product. |

The playable runtime shares no code with the other two. That is deliberate (`openspec/specs/playable-runtime-skeleton`).

## What exists in the playable track

**`server/domain/`** has `WorldDay`, `TimeSlot` (fixed four slots), `WorldTime`, `EventId` (UUIDv7; only `EventId.new()` needs Python 3.14), and `Version`. No runtime code imports them yet; only their tests do.

**`prototype/`** is a stdlib-only spike of the whole first slice. Read `prototype/README.md` first.
- `engine.py` holds `Game`: commands (`send_message`, `advance_slot`, `open_session`, `simulate_absence`, `read_letter`, `new_world`), output validation, rule-based fallbacks, the `snapshot` read model, and catch-up.
- `boundary.py` screens narrator output for undiscovered secrets.
- `store.py` is SQLite: `worlds` (blueprint JSON, state JSON blob, version), append-only `events`, `messages` (deduplicated by `client_id`), `letters`.
- `llm.py` has Anthropic and OpenAI-compatible providers, a deterministic fake, and `complete_json` (one repair call, optional salvage).
- `server.py` is a threading HTTP server with one write lock; `static/` is the web client.

Rules the prototype already enforces and tests: the player never edits state; chat output cannot change relationships or location (it can set her mood); the protagonist adopts, declines, or defers each influence with a reason and the scene event records its causes; each world keeps the blueprint it was created with; catch-up is resumable; the `debug` payload with NPC secrets is only returned by a `--dev` server. The timeline shows the narrator's scene text as written and is not screened, so a narrator that writes a secret into a scene shows it to the player.

## Fixed (do not reopen without the user)

- MVP boundary table in `GAME_DEVELOPMENT_PLAN.md` section 2: one protagonist, 6–8 NPCs, 5–8 locations, fixed school world, exactly four slots per day (the accepted `playable-time-and-identity` spec requires four too), at most 7 catch-up days, local single-writer, SQLite authoritative, player's own API key.
- The influence contract: the player only injects context; the protagonist decides. Roadmap C4.4, C4.5, gate G4.
- The initial `server` package must not import the legacy runtime or load model credentials (skeleton spec, an import-time rule). Whether the future sidecar holds credentials is open: the roadmap gives model calls and the keyring to the sidecar.
- Director events add context and timeline entries. They never mutate state, relationships, profiles, or scratchpads.
- Clients read snapshots, never prompts, scratchpads, or traces.
- New documentation is English. OpenSpec artifacts are called proposal, design, spec, tasks.

## Decisions waiting for you

Each item says what is known and what I would do. Evidence is in `docs/refactor_review.md`.

1. **Real-model play before more design.** Nothing has run against a real model. Prompt quality, valid-JSON rate, latency, cost, and the leak screen's real-world recall are unknown. I would play a few game days first (`python -m prototype`, with an API key), because it decides how much of the prototype is worth keeping. The reviewer's view: D1.2 and D1.3 do not depend on it, D1.4 does. Add a call recorder first (about half a day): `complete_json` returns only `{"repaired"}`, `{"salvaged"}`, or an error in its meta, so a play session today would not record tokens, latency, or stop reason, which are the unknowns listed above.
2. **Event model (D1.4, D1.5, D1.6).** Prototype events are lossy: state cannot be rebuilt from them, and chat, influence, and letter-read changes emit no event. Replay cannot start until event payload equals reducer input. I would define the payload schema from the validated narrator output, move the reducer rules out of `Game`, and test that replay equals the stored state. The reviewer agrees with the goal (payload is sufficient reducer input; replay reproduces the stored state) with two changes. First, the payload should be a closed set of typed effects, not the validated narrator output itself. Second, session data such as `last_seen_at` and the catch-up plan lives in the world state blob today; move it out, or D1.6's byte-for-byte replay cannot pass. The reviewer also judged the gap smaller than "lossy" suggests: a few fields the state update consumes (it counted four; I did not recount) plus events for chat, influence, and letter-read.
3. **Slots: decided, four fixed.** The MVP table and the accepted spec require exactly four. The prototype is inconsistent with that: the engine reads the slot count from the blueprint and the fake model hard-codes four. `WorldBlueprintV1` should carry exactly four slot descriptors and reject any other count. Reopen only if the user wants other shapes of day.
4. **Python version and IDs.** `EventId.new()` needs `uuid.uuid7` (3.14). The prototype claims 3.13 and uses random hex IDs. Either drop 3.13 or vendor an RFC 9562 fallback. CI is pinned to 3.14.6.
5. **Blueprint shape.** `tests/fixtures/f0_school.json` (1 protagonist, 6 NPCs, 5 locations, `fixture_version`) and `prototype/world.json` (1, 4, 6, `blueprint_version`, richer fields) disagree. D1.3 requires 6–8 NPCs, so the prototype blueprint fails it today.
6. **Knowledge boundary design (M9.1).** The current screen only catches copied text. The real fix is to split narrator output into what happened and what she perceived, with memories typed as canonical facts, beliefs, and episodes. This changes the event schema, so it belongs before D1.4, not after.
7. **Persistence and concurrency (S2).** The state is a JSON blob rewritten per command. There is no expected-version check (S2.2), idempotency exists only for chat messages (S2.3), and catch-up progress lives inside the blob. The write lock lives in the HTTP server.
8. **Package boundaries.** Where do the provider adapters and the keyring live, and where does the sidecar API (A6) live? The skeleton rule only covers the initial package, so a modified requirement can allow credential loading in the sidecar. Any move out of the prototype needs an OpenSpec change.
9. **The legacy and director track.** `scripts/run_world.py` still cannot start a template-created run directly (`ensure_run_world_data` needs a base world directory). Decide whether that adapter is worth building, or whether the director track is frozen while the game is built.

### Gaps the first version of this handoff missed

These came from the independent review. I checked the call counts in 10 against the roadmap and `prototype/engine.py`; 11 to 13 are the reviewer's reading and were not reproduced.

10. **Model-call budget and the shape of a day.** The roadmap (`GAME_DEVELOPMENT_PLAN.md` line 199) allows at most 3 backend model calls on a normal day and at most 6 for a 7-day catch-up, and plans `PlanDay` (R3.2) to produce candidate actions for the four slots before rules resolve each scene. The prototype calls the narrator once per slot plus one day review, so 5 calls on a normal day, and up to 7 offscreen days plus one letter, so 8 for a full catch-up, before any repair call. The D1.4 command list (`CreateWorld`, `PlanDay`, `AdvanceSlot`, `SendMessage`, `SendLetter`) matches neither. Decide the budget and whether a day is planned once or narrated per slot before D1.4, because it changes the commands and the event types.
11. **Who the timeline is for.** The timeline shows scene text unscreened (see above). Decide whether it is the player's omniscient log or the protagonist's perspective. The screen, the schema split in item 6, and the snapshot contract all depend on the answer.
12. **Two incompatible fakes.** `tests/support/fakes.py` has `FakeLLM`, which is keyed by the exact prompt string. The prototype has `FakeProvider` (keyed by task, takes an `LLMRequest`) and the tests add a `ScriptedProvider`. Gates G8 and O8.3 need one deterministic substitute that both the roadmap tests and the prototype can use.
13. **Discovery integrity.** The narrator's output can declare that she discovered an NPC's secret, and the player's chat and influence text enter the prompts. The reviewer's concern is that a player can steer the narrator into declaring a discovery that unlocks a secret. The validator (`prototype/engine.py`, near line 938) only requires a known NPC id and a non-empty fact text, and `boundary.Screen.for_output` only drops a discovery whose fact carries another NPC's secret. Nothing checks a discovery against what happened in the scene. Not reproduced; worth a test with a scripted provider before relying on the boundary.

Open product questions from `handoff.md` are not decided: measure early (move the M9.6 evaluation forward and defer Temporal, Postgres, outbox, WebSocket), the project's uniqueness (parked by the user; raise only if asked), and how to credit upstream work versus this fork.

## Review of this handoff

An independent read-only Opus session read the first version of this file and the code it points to, without the conversation that produced it. What it changed and proposed:

**Recommended order of decisions** (the reviewer's): blueprint shape (item 5) → secret ids → location → call budget and `PlanDay` (item 10) → everything else. Blueprint shape comes first because D1.2 cannot start without it, and the next three feed it. The reviewer gave only the names "secret ids" and "location"; my reading is that secret ids means giving each hidden fact an id so a discovery can reference it instead of free text (item 13), and location means whether a character's location is stored at all (the snapshot's `last_known_location` is null for engine runs today). Confirm that reading with the user.

**Proposed first slice:** D1.2 as an OpenSpec change `add-world-blueprint-v1`. Pure parsing and validation in `server/domain/blueprint.py` (no I/O, no model, no `prototype` import), one valid fixture and about eight invalid ones (for example: wrong slot count, fewer than 6 NPCs, unknown location reference, duplicate id, unsupported version; the list is mine, the count is the reviewer's), tests written first. I would also mutation-check it, as the earlier slices were. The reviewer's estimate is 1 to 1.5 days. It requires the user's answer on item 5, and ideally on the secret-id and location questions above. Do not start it before then.

**Statements in the first handoffs the review showed to be wrong** (already corrected in `handoff.md`, `prototype/README.md`, `docs/refactor_review.md`, and above; listed so you do not rely on an old copy):
- Snapshots carry no secrets. Only the `debug` payload is gated by `--dev`; the timeline's scene text is unscreened.
- Chat changes no state. It can set her mood.
- `server/` may never load credentials. That is an import-time rule of the initial skeleton; the roadmap gives model calls and the keyring to the sidecar.
- `EventId` needs Python 3.14. Only `EventId.new()` does.
- Slot count is an open decision. It is decided: four.
- Stale PR numbers, test counts, branch names, and archive status in `handoff.md`.

**Not verified by me.** The reviewer read the Claude API reference and reported that Opus 5.5's extended thinking cannot be switched off and may share `max_tokens` with the visible answer (the prototype caps are 800, 1800, and 1200, which would then risk truncated JSON), and that one Sonnet model is scheduled for retirement on 2026-11-30. I did not confirm either against a real call or the live documentation. Treat them as leads for the real-model play in item 1, and check the model IDs against the current docs before choosing a default.

## Suggested first hour

1. Read `prototype/README.md` and skim `prototype/engine.py` and `prototype/store.py`.
2. Read `docs/refactor_review.md`, sections 1 to 3 and the extraction order.
3. Read `openspec/specs/playable-runtime-skeleton/spec.md` and `playable-time-and-identity/spec.md`.
4. Run the prototype with the fake model and click through one day, a chat, and "模拟离开…".
5. Read "Review of this handoff" and items 10 to 13, then bring the user a short recommendation on items 1 to 3 and 5 and 10. Do not start D1.2 before they answer.

## Commands

```bash
# full suite (the repo venv is Python 3.14.7; recreate it from the lock if missing)
.venv/bin/python -m pytest -q -p no:cacheprovider

# prototype tests on system Python 3.13
uv run --no-project --with pytest -- python -m pytest -q -p no:cacheprovider tests/test_prototype.py tests/test_prototype_boundary.py

# run the prototype (add --llm fake to force the offline model, --dev for the developer view)
python3 -m prototype

# spec validation
openspec validate --all --strict --no-interactive
```

Recreate the venv: `uv venv --python 3.14.7 .venv && uv pip sync --python .venv/bin/python --require-hashes requirements.lock`.

## Traps

- Importing `src.world.world` or `src.utils` creates `logs/` next to the code and, until a config is loaded, needs `config.json`. Run such experiments in a copy. `logs/` is git-ignored now.
- The legacy code resolves `data/...` relative to the current directory, so it only works from the repository root.
- `EUVUD/agenttown_demo` is a fork of `Neph0s/Agentopia`. Run every `gh pr` command with `--repo EUVUD/agenttown_demo`, or `gh` targets the upstream repository.
- Opening a PR or pushing is an outward write. The permission system blocked one `gh pr create` until the user said so explicitly. Ask first.
- No git identity is configured. Earlier commits passed `-c user.name` and `-c user.email` on the command line; reuse the author of the latest `develop` commit (`git log -1 --format='%an %ae' origin/develop`).
- `docs/ci_cd.md` asks for rebase-and-merge into `develop`, with one feature branch per change. Branch protection for `develop` and `main` is still unconfirmed.
- `openspec archive` leaves a `TBD` Purpose in a main spec it creates from a delta without a Purpose. Fill it in by hand.
- Branches of merged PRs that can be deleted on `origin`: `feature/add-ci-cd-pipeline`, `feature/d1-time-and-id`, `feature/f0-playable-foundation`, `feature/update-d1-handoff`, `feature/fast-prototype`, `feature/update-prototype-handoff`, `feature/director-inputs-and-prototype-fixes`, `chore/archive-wire-director-inputs`. The local `feature/update-prototype-handoff` is three commits ahead of its origin copy but its content is already in `develop`.
