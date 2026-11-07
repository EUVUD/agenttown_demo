# Marginalia — Handoff

## Current State

On 2026-11-06 the project was renamed **Marginalia**. Its earlier names were
`agenttown_demo` (the repository), `AGENTTOWN_*` (environment variables), and the
working title 明日回信 / Tomorrow's Reply. The GitHub repository is now
`EUVUD/marginalia`; GitHub redirects the old URL. Agentopia is named only as the
upstream project. The local WSL folder is still `~/agenttown_demo`.

`CLAUDE.md` defines how the work runs from now on: the user opens separate
architect, executor, and reviewer sessions that hand off through
`handoff_architect.md`, `handoff_executor.md`, and `handoff_reviewer.md`.

As of 2026-11-06 `develop` contains PRs #1 to #9, and nothing is unpushed.
[PR #5](https://github.com/EUVUD/marginalia/pull/5)
added a stdlib-only fast prototype of the first vertical slice under
`prototype/`. PR #6 updated this handoff. [PR #7](https://github.com/EUVUD/marginalia/pull/7)
wired director events into the weekly loop, fixed four prototype bugs, and added
`docs/refactor_review.md`. PR #8 archived the director OpenSpec change. PR #9
archived the D1.1 OpenSpec change (`add-playable-time-and-ids`), added
`handoff_architect.md` for a session that decides the runtime architecture, and
corrected statements in the handoffs that an independent review showed to be
wrong. Earlier merges (PR #1–#4) delivered the F0 foundation, CI/CD, and the D1.1
time and identity value objects. CI passes on `develop`. No OpenSpec change is
active.

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
- `--dev` allows the developer view: `?debug=1` then shows NPC secrets and her memories.
  Without `--dev` no response carries the `debug` payload. The narrator's scene
  text in the timeline is shown as written and is not screened, so it can carry a
  secret the narrator wrote.

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

1. Chat may leave a pending influence. Chat output cannot change relationships
   or location; it can set her mood. Extra fields are dropped.
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

- `MARGINALIA_LLM`: `auto`, `anthropic`, `openai`, or `fake`.
- `ANTHROPIC_API_KEY`.
- `OPENAI_API_KEY` and `OPENAI_BASE_URL`.
- `MARGINALIA_MODEL`: defaults to `claude-opus-5-5` for Anthropic and is
  required for `openai`.

The old names `AGENTTOWN_LLM` and `AGENTTOWN_MODEL` are still read when the new
ones are unset.

## Decisions That Matter Next

- The prototype lives outside `server/` because the playable-runtime skeleton
  spec says the initial `server` package must not import model credentials. That
  rule is about the skeleton; the roadmap gives model calls and the keyring to the
  future sidecar. When refactoring, move pieces into `server/` deliberately, with
  OpenSpec changes, not by moving the folder.
- It uses only the standard library, so `requirements.lock` is untouched and it
  runs on Python 3.13 and 3.14.
- The influence contract is the core rule to preserve: the player never edits
  state, and the protagonist decides. This maps to C4.4, C4.5, and gate G4.
- The knowledge boundary is enforced when prompts are built and, since PR #7,
  by a screen on narrator output (`prototype/boundary.py`). The screen only
  catches copied or lightly edited secret text; the real fix is M9.1.
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

- When the prototype was added (PR #5), its 10 tests passed on Python 3.13.5 and
  3.14.7 and the full suite of 43 passed. Today the prototype has 56 tests
  (`test_prototype.py` and `test_prototype_boundary.py`) and the full suite has
  120, all passing on Python 3.14.7. These tests run offline and are
  deterministic.
- CI passes all three jobs on `develop`: Python tests, OpenSpec validation, and
  Godot GdUnit4.
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
4. Follow-ups:
   - Both OpenSpec changes that were waiting for approval
     (`add-playable-time-and-ids` and `wire-director-inputs-into-simulation`)
     were archived on 2026-11-06 (PRs #8 and #9). Both are merged into `develop`.
   - Add the small adapter that lets `scripts/run_world.py` start a
     template-created run (`ensure_run_world_data` requires a base world
     directory). See `docs/director_world.md`.
   - Confirm branch protection for `develop` and `main` (see
     `docs/ci_cd.md`).
5. Cleanup: the remote branches of PRs #1 to #9 were deleted on 2026-11-06, so
   `origin` has only `main` and `develop`. See "Working Tree and Git" for the local
   branches that remain in the WSL clone.

## Open Product Questions

**Name.** Decided on 2026-11-06: Marginalia. The player's words are notes in the
margin of the protagonist's day; the protagonist reads them and decides. Still
open:

- The English store title needs a formal trademark search before release (P11),
  in USPTO classes 9 and 41 and at CNIPA. Steam already lists two games called
  Marginalia (apps 889280 and 4559530). A web search found no "MARGINALIA" mark
  for games, but found a 2021 USPTO filing for "MARGINAL" that covers game
  software.
- No Chinese name is chosen. 旁批 was proposed.

The questions below were discussed on 2026-10-31. None of them is decided.

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

The three issues listed here earlier were fixed in
[PR #7](https://github.com/EUVUD/marginalia/pull/7), merged into `develop`:

- Director results are consumed by the weekly loop of template-created runs
  (prompt context, public events, arranged encounters, application log).
- Characters added through the director service join the running roster at the
  next week start, using their arrival event.
- Visualization snapshots are labelled with the latest recorded simulation time
  and refreshed at the end of every week.

The change was specified in `openspec/changes/archive/2026-11-06-wire-director-inputs-into-simulation/`;
its requirements now live in `openspec/specs/director-events`, `dynamic-character-entry`,
and `visualization-state`. It is documented in `docs/director_world.md`. `scripts/run_world.py`
still cannot start a template-created run directly; that adapter is the next gap.

`docs/refactor_review.md` holds the full codebase review: reproduced bugs, contract
gaps, and ranked refactors. The four prototype bugs found there are fixed in PR #7:
catch-up is resumable, the `debug` payload with NPC secrets is only returned by a
server started with `--dev`, narrator output is screened for undiscovered secrets,
and each world keeps the blueprint it was created with. The leak screen only catches
copied or lightly edited text, and the timeline shows scene text unscreened, so check
real-model output for paraphrased secrets when you first play.

## Environment Notes

This session ran in a WSL Ubuntu clone at `~/agenttown_demo` (the folder kept
its old name after the rename; its `origin` points to `EUVUD/marginalia`). The `.venv` and
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

PRs #7, #8, and #9 were rebase-merged into `develop`. PR #7 added the director-input
wiring, the four prototype fixes, and `docs/refactor_review.md`. PR #8 and PR #9
archived the two OpenSpec changes. PR #9 also added `handoff_architect.md` and
corrected this handoff. Each PR used one feature or chore branch and `develop` as its base.

Verified for PR #7: 120 tests pass on Python 3.14.7 and the prototype tests pass on
3.13.5; `openspec validate --all --strict` passes; CI passed on the pull request
and on `develop` after the merge. After PR #9, which changed documentation and the
archived OpenSpec change only, 120 tests still pass on 3.14.7 and CI passed on
`develop`; the prototype tests were not rerun on 3.13.5. Not run: the legacy runner
smoke test (it needs `config.json` and a model) and any real-model play.

Branches: on 2026-11-06 the remote branches of PRs #1 to #9 were deleted, after
`git cherry origin/develop origin/<branch>` showed that every patch was already in
`develop`. `origin` has only `main` and `develop`. In the WSL clone five local branches
remain whose remote copies are gone: `chore/archive-playable-time-and-ids`,
`chore/archive-wire-director-inputs`, `feature/director-inputs-and-prototype-fixes`,
`feature/fast-prototype`, and `feature/update-prototype-handoff`. Rebase merges change
commit hashes, so `git branch -d` refuses to delete them; use `git branch -D` after
`git cherry origin/develop <branch>` shows no `+` line. The tip of the local
`feature/update-prototype-handoff` is an earlier draft of the `docs: add the codebase
refactor review` commit that is in `develop`, so `git cherry` shows one `+` line for
it; that content is superseded.

## Suggested Skills

- `git-feature-develop-workflow` and `caveman-commit` for commits, pushes, PRs,
  and post-merge cleanup.
- `openspec-explore`, `openspec-propose`, and `openspec-apply-change` when the
  prototype is refactored into roadmap slices, starting with D1.2.
- `openspec-archive-change` (both existing changes are already archived).
- The `.claude/skills/` analysis skills target legacy simulation runs only.
