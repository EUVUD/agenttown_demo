# Tomorrow's Reply — Handoff

## Current State

`develop` is at `46d2c49` after [PR #5](https://github.com/EUVUD/agenttown_demo/pull/5)
was squash-merged on 2026-10-31. PR #5 added a stdlib-only fast prototype of
the first vertical slice under `prototype/`. Earlier merges (PR #1–#4)
delivered the F0 foundation, CI/CD, and the D1.1 time and identity value
objects. CI passed on the PR and on the merged `develop` commit.

`GAME_DEVELOPMENT_PLAN.md` is unchanged. F0.1–F0.5, the F0 gate, G0, and D1.1
are checked, and D1.2 `WorldBlueprintV1` is the next unchecked item. The
prototype ticked nothing, because its acceptance criteria were not verified.

`main` is still at `8d534f0`. Its README leads with upstream Agentopia, and
none of the playable work is visible there.

## What the Prototype Does

Run `python3 -m prototype` from the repository root, then open
<http://127.0.0.1:8765>.

- `--llm fake` forces the offline model.
- `--db PATH` keeps a separate save.
- Saves default to `prototype/.data/`, which is git-ignored.
- `?debug=1` opens the developer view, which shows NPC secrets and her memories.

`prototype/README.md` is the reference. Summary:

- `world.json` is a fixed school blueprint: 林夏, four NPCs that each carry a
  `hidden` secret, six locations, and four slot labels.
- `engine.py` holds `Game`. Its commands are `send_message`, `advance_slot`,
  `open_session` (offline catch-up), `simulate_absence`, `read_letter`, and
  `new_world`. It also holds output validation, rule-based fallbacks, and the
  `snapshot` read model.
- `prompts.py` builds two kinds of prompt. Narrator prompts (slot, offscreen
  day) see NPC secrets; protagonist prompts (chat, letter, review) never do.
- `llm.py` holds:
  - Anthropic and OpenAI-compatible providers over `urllib`;
  - a deterministic `FakeProvider`;
  - `complete_json`, which makes one repair call and has an optional salvage
    path for plain-text chat replies.
- `store.py` is SQLite with these tables:
  - `worlds`, holding a JSON state blob and a version;
  - append-only `events`;
  - `messages`, deduplicated by `client_id`;
  - `letters`.
- `server.py` is a `ThreadingHTTPServer` with one write lock, a JSON API, and
  the static client in `static/`.

The loop:

1. Chat may leave a pending influence. Chat output cannot change any state:
   extra fields are dropped.
2. Each slot is resolved by the narrator. The protagonist adopts, declines, or
   defers each pending influence with a reason, and the scene event's `causes`
   records which influences it considered.
3. Slot 4 triggers a `review` call that produces a summary, a diary entry,
   tomorrow's focus, and sometimes a letter.
4. Opening a session turns each missed real day into one `offscreen_day` call,
   up to 7. A longer absence adds a `sleep` event. One absence `letter` follows.

Model calls are 5 per online game day (4 slots and 1 review). Catch-up costs 1
per missed day plus 1 letter.

Environment variables:

- `AGENTTOWN_LLM`: `auto`, `anthropic`, `openai`, or `fake`.
- `ANTHROPIC_API_KEY`.
- `OPENAI_API_KEY` and `OPENAI_BASE_URL`.
- `AGENTTOWN_MODEL`: defaults to `claude-opus-5-5` for Anthropic and is
  required for `openai`.

## Decisions That Matter Next

- The prototype lives outside `server/` because the playable-runtime skeleton
  spec says `server` must not load model credentials. When refactoring, move
  pieces into `server/` deliberately, with OpenSpec changes, not by moving the
  folder.
- It uses only the standard library, so `requirements.lock` is untouched and it
  runs on Python 3.13 and 3.14.
- The influence contract is the core rule to preserve: the player never edits
  state, and the protagonist decides. This maps to C4.4, C4.5, and gate G4.
- The knowledge boundary is enforced only when prompts are built. Checking
  model output for leaks is still to do (M9).
- `prototype/README.md` ends with "Shortcuts to pay back when refactoring".
  Treat that list as the refactor backlog. Mapping to the roadmap:

  | Prototype part | Roadmap step |
  |---|---|
  | `world.json` | D1.2 / D1.3 |
  | engine commands | D1.4 |
  | state blob | D1.5 reducer and D1.6 replay |
  | `store.py` | S2 |
  | `llm.py` | L5.1 / L5.4 |
  | `server.py` | A6 |
  | `static/` | G7 (Godot) |

## Verification Already Performed

- `tests/test_prototype.py` passed 10 tests on Python 3.13.5 and 3.14.7. These
  tests run offline and are deterministic.
- The full suite passed 43 tests on Python 3.14.7, in a venv synced from
  `requirements.lock`.
- PR #5 CI passed all three jobs: Python tests, OpenSpec validation, and Godot
  GdUnit4. The post-merge `develop` run for `46d2c49` also passed.
- A manual run with the fake model worked end to end through the HTTP API:
  chat, four slots, a simulated three-day absence, and the absence letter.
  Headless Chrome screenshots at 1440px wide confirmed the UI renders.

## Not Verified

- No real model call has been made. The Anthropic and OpenAI-compatible code
  paths are untested. Prompt quality, the valid-JSON rate, latency, and cost are
  unknown.
- The mobile layout has not been checked, and there is no Godot client.

## Next Steps

1. Play with a real model. Watch for:
   - the `规则兜底` (fallback) badge in the timeline;
   - the character's voice;
   - whether influence decisions look reasonable;
   - any NPC secret appearing in her chat or letters before she discovers it.

   Tune `prompts.py` based on what you see.
2. Ask the user whether to keep iterating on gameplay in the prototype or to
   start refactoring it into roadmap slices.
3. If refactoring, start with D1.2: formalize `prototype/world.json` as
   `WorldBlueprintV1`, with legal and illegal fixtures.
4. Older follow-ups are still open:
   - Archive `openspec/changes/add-playable-time-and-ids` when the user
     approves.
   - Confirm branch protection for `develop` and `main` (see
     `docs/ci_cd.md`).
5. Cleanup: the squash-merged `feature/fast-prototype` branch still exists
   locally and on `origin`.

## Open Product Questions

These were discussed on 2026-10-31. None of them is decided.

- **Depth.** One suggestion: close one loop and measure it, by moving the
  M9.6/G9 evaluation earlier. The metrics would be:
  - contradiction rate;
  - knowledge leakage;
  - how often player influence is adopted;
  - cost per game day.

  The same suggestion was to defer Temporal, Postgres/RLS, the outbox, and
  WebSocket.
- **Uniqueness.** The user feels the project resembles other AI-town projects.
  One candidate was researched: a time-loop or counterfactual town where the
  player can only inject information, and deterministic replay re-simulates
  only the intervention's causal reach. The user explicitly parked this. Raise
  it only if asked.
- **Attribution.** When describing the project, keep two kinds of work
  separate:
  - upstream Agentopia work, from initial commit `c04e36f`: the weekly loop,
    the God Model, and the life reward;
  - work done in this fork: the director layer, the playable runtime, and the
    prototype.

## Known Issues in Older Code

These are on legacy paths. The prototype does not use them.

- `src/world/director.py`: `_resolve_one` records `produced_inputs`, but
  nothing reads them, so director events do not affect the simulation.
- `World.add_agent_from_data` runs only when `add_character_to_world` receives
  `active_world`, and no caller passes it.
- `src/world/visualization.py` defaults `time` to `Y2020-W00-begin`, and
  `DirectorWorldService` never passes a time. Every snapshot therefore
  overwrites the same file.

## Environment Notes

This session ran in a WSL Ubuntu clone at `~/agenttown_demo`. The `.venv` and
stashes mentioned in the previous handoff are on the macOS machine and were not
touched.

- System Python is 3.13.5, `uv` is installed, and a uv-managed 3.14.7 exists.
  `pytest` is not installed globally. To run the prototype tests:
  `uv run --no-project --with pytest -- python -m pytest -q tests/test_prototype.py`.
  For the full suite, follow `docs/playable_toolchain.md`.
- No git identity is configured. The PR #5 commit passed `-c user.name` and
  `-c user.email` with the identity used by earlier commits.
- The Windows Chrome executable can take headless screenshots of the WSL server
  at `http://localhost:8765`. The output path must be a Windows path.

## Working Tree and Git

This handoff was written on `feature/update-prototype-handoff`, created from
`origin/develop` at `46d2c49`.

## Suggested Skills

- `git-feature-develop-workflow` and `caveman-commit` for commits, pushes, PRs,
  and post-merge cleanup.
- `openspec-explore`, `openspec-propose`, and `openspec-apply-change` when the
  prototype is refactored into roadmap slices, starting with D1.2.
- `openspec-archive-change` for D1.1 once the user approves.
- The `.claude/skills/` analysis skills target legacy simulation runs only.
