# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Marginalia is a playable AI life-simulation game: the player talks with one
protagonist, cannot change the world directly, and the world keeps running while
the player is away. The repository is a fork of Agentopia (`Neph0s/Agentopia`).

Also follow `AGENTS.md`. It holds the base rules (scope, layout, data contracts,
change rules), and this file does not repeat them. This file holds stable rules
only. Current state, open decisions, and next steps live in the handoff files
described below, not here.

Reply to the user in the language they write in (usually Chinese). Write
repository documentation in English, as `AGENTS.md` requires.

## Session workflow: architect, executor, reviewer

The user runs the project through three roles, each in its own session, and
names the role when opening a session. Sessions share nothing but the
repository, so every hand-off is a file. If the user names no role, work as an
ordinary session and leave the handoff files alone unless asked.

The cycle is: architect → executor → reviewer → back to the executor for fixes,
or the user merges → architect.

### Handoff files

They live at the repository root and are tracked. Each one is named for its
reader and rewritten, not appended to, by whoever hands off to that reader. Git
history keeps the earlier versions.

| File | Reader | Written by |
|---|---|---|
| `handoff.md` | every role | any role that changes project state: a decision, a PR, a merge, an archive |
| `handoff_architect.md` | architect | the reviewer after a verdict; the executor when a task needs a design decision |
| `handoff_executor.md` | executor | the architect when a change is approved; the reviewer when changes are requested |
| `handoff_reviewer.md` | reviewer | the executor when a branch is ready for review |

Rules for every handoff:

- Start with the date and the branch or PR.
- Separate what was verified, with the command that verified it, from what was
  not verified.
- Separate the user's decisions from recommendations, and say whose each
  recommendation is.
- Name PRs and branches, never `develop` commit hashes: rebase merges rewrite them.
- Use absolute dates.

### Architect

Reads first: `handoff_architect.md`, `handoff.md`, `GAME_DEVELOPMENT_PLAN.md`,
the relevant `openspec/specs/`, and `docs/refactor_review.md`.

1. Archive changes that have been merged (`openspec archive <change-id>`, then
   fill in any `TBD` Purpose by hand) on a `chore/` branch.
2. Bring the user recommendations with evidence. The user decides. Record each
   decision with its date: project-wide ones under "Fixed" in
   `handoff_architect.md`, change-level ones in the change's `design.md`.
3. Turn one approved roadmap step into one OpenSpec change under
   `openspec/changes/<change-id>/`: `proposal.md`, `design.md`, `tasks.md`, and
   spec deltas in `specs/<capability>/spec.md`. A step is one observable
   behaviour, 0.5–2 days of work (`GAME_DEVELOPMENT_PLAN.md` section 3). Order
   `tasks.md` so that every task names the failing test it starts with.
4. Create `feature/<change-id>` from `develop`, commit the change there, and run
   `openspec validate --all --strict --no-interactive`.
5. Write `handoff_executor.md`: the change id, the branch, decisions that bind
   the work, what is out of scope, and the exact acceptance commands.

The architect does not write implementation code or tests. It does not start a
change the user has not approved, and does not reopen a "Fixed" decision without
the user.

### Executor

Reads first: `handoff_executor.md`, then the change's proposal, design, tasks,
and spec deltas.

1. Work on the branch named in the handoff.
2. For each task in order: write the test, watch it fail, write the minimal
   code, then tick the task in `tasks.md`.
3. Run the narrowest test, then the full suite and spec validation. If
   `prototype/` changed, also run its tests on Python 3.13.
4. Tick the roadmap step in `GAME_DEVELOPMENT_PLAN.md` only when its acceptance
   criteria pass.
5. Commit on the feature branch. Push and open the PR only after the user says
   so in that session.
6. Write `handoff_reviewer.md`: what was done, the commands run and their
   results, what was not verified, any deviation from the design, and where to
   look first.

The executor does not change the design, the spec, or the scope on its own. If a
spec is wrong or ambiguous, or would break a "Fixed" decision, it stops that
task, writes the question into `handoff_architect.md`, and tells the user.

### Reviewer

Reads first: the change's spec deltas and `tasks.md`, then
`git diff develop...<branch>`. Read `handoff_reviewer.md` only after that, to
check its claims, so the review is not anchored on the executor's summary.

1. Check every requirement and scenario against the code. Each one needs a test
   that fails without the code. Mutation-check new validators and rules: break
   one, and confirm that a test fails.
2. Rerun the full suite and spec validation yourself.
3. Check the `AGENTS.md` contracts and the invariants below. Check every ticked
   task and roadmap box against its acceptance criteria.
4. Reproduce each finding before reporting it, and mark any you could not
   reproduce.
5. Give one verdict: approve, changes requested, or needs an architect
   decision. For each finding, give the file and line, the failure scenario, and
   the severity.
6. Write the findings to `handoff_executor.md` (changes requested) or to
   `handoff_architect.md` (approved, or a design question), and update
   `handoff.md`.

The reviewer does not edit code, tests, or specs, and does not post to GitHub
unless the user asks. Merging is the user's decision.

## Commands

`AGENTS.md` lists the legacy-runner commands. The playable track uses these:

| Task | Command |
|---|---|
| Recreate the venv (local 3.14.7; CI pins 3.14.6) | `uv venv --python 3.14.7 .venv && uv pip sync --python .venv/bin/python --require-hashes requirements.lock` |
| Full Python suite | `.venv/bin/python -m pytest -q -p no:cacheprovider` |
| One test | `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_prototype.py::<test_name>` |
| Prototype tests on Python 3.13 | `uv run --no-project --with pytest -- python -m pytest -q -p no:cacheprovider tests/test_prototype.py tests/test_prototype_boundary.py` |
| Spec validation (OpenSpec 1.5.0) | `openspec validate --all --strict --no-interactive` |
| Run the prototype | `python3 -m prototype`, then open <http://127.0.0.1:8765>; `--llm fake` forces the offline model, `--dev` allows `?debug=1`, `--db PATH` keeps a separate save |
| Godot tests (macOS) | `cd godot && GODOT_BIN=/Applications/Godot.app/Contents/MacOS/Godot ./addons/gdUnit4/runtest.sh -a tests/test_bootstrap_scene.gd` |
| Regenerate the lock after changing requirements | `uv pip compile --python .venv/bin/python --generate-hashes requirements.txt requirements-dev.txt --output-file requirements.lock` |

CI (`.github/workflows/verify.yml`) runs three gates on every PR to `develop`:
the Python suite, OpenSpec validation, and GdUnit4 on Godot 4.7.1. The WSL clone
has no Godot install, so Godot tests run in CI only. No linter or formatter is
configured.

Prototype model settings come from `MARGINALIA_LLM` (`auto`, `anthropic`,
`openai`, or `fake`), `MARGINALIA_MODEL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
and `OPENAI_BASE_URL`. The old `AGENTTOWN_*` names still work.

## Architecture

Three code bases share the repository. The playable runtime shares no code with
the other two on purpose (`openspec/specs/playable-runtime-skeleton`).

| Track | Where | Role |
|---|---|---|
| Legacy simulation | `src/`, `scripts/run_world.py` | Upstream Agentopia research runner. Not the game runtime. |
| Director layer | `src/world/director*.py`, `template_world.py`, `visualization.py`, `data/world_templates/` | This fork's player-authored events and client snapshots, built on the legacy loop |
| Playable runtime | `server/`, `prototype/`, `godot/` | The game |

**Legacy simulation.** Agents live a weekly cycle (Plan → Contact → Activity →
Review), and an environment model ("God Model") verifies their actions and
schedules events. At each year end, profiles update and a life reward is
computed. Each run copies a base world (`data/school/`, `data/apartment/`) into
`data/<world>_<MMDDHHMM>/` and appends JSONL there.

**Director layer.** A template pack in `data/world_templates/<id>/` defines a
world. `template_world.py` instantiates it as a run. `director.py` validates
player events into `DirectorEvent` JSONL. The weekly loop consumes those events
as prompt context, public events, and arranged encounters. `visualization.py`
writes `visualization/current.json` for clients. The contract is in
`docs/director_world.md`. `scripts/run_world.py` cannot yet start a
template-created run.

**Playable runtime (target).** SQLite is the authority. A Python sidecar owns
simulation, persistence, model calls, and the API. Godot is a thin client that
only presents and takes input. State is event-sourced: commands produce events,
a reducer builds projections, and replay must reproduce them (roadmap D1, S2).
Today `server/domain/` holds only value objects (`WorldDay`, `TimeSlot`,
`WorldTime`, `EventId`, `Version`), and `godot/` is a bootstrap scene.

**Prototype (`prototype/`).** A stdlib-only spike of the first slice, to be
refactored into roadmap slices rather than extended. `Game` in `engine.py` runs
the commands. `prompts.py` builds narrator prompts, which see NPC secrets, and
protagonist prompts, which never do. `llm.complete_json` makes one repair call,
then `engine.py` falls back to rules. `boundary.py` screens output for
undiscovered secrets. `store.py` keeps a per-world state blob, append-only
events, messages, and letters in SQLite. `server.py` serves a JSON API under one
write lock, plus `static/`. Its events are not yet enough to rebuild state;
`docs/refactor_review.md` lists this and the other gaps.

## Development guidelines

These add to `AGENTS.md`.

**Product invariants.** Change these only with the user's decision.
- The player only injects context, and the protagonist decides: each influence
  is adopted, declined, or deferred, with a reason. Player input never edits
  state, relationships, or NPCs (roadmap C4.4, C4.5, gate G4).
- The MVP is bounded by the table in `GAME_DEVELOPMENT_PLAN.md` section 2: one
  protagonist, 6–8 NPCs, 5–8 locations, exactly four slots per day, at most 7
  catch-up days, local single writer, SQLite authoritative, and the player's own
  API key.
- Knowledge boundary: NPC secrets reach only narrator prompts. Anything the
  protagonist says or writes must not reveal a secret the protagonist has not
  discovered.

**Boundaries between tracks.**
- The initial `server` package and the Godot bootstrap must not import the
  legacy simulation, run data, templates, or model credentials.
- Move prototype code into `server/` one roadmap slice at a time, each through
  an OpenSpec change. Never move the folder wholesale.
- Keep `prototype/` stdlib-only and runnable on Python 3.13 and 3.14.
  `EventId.new()` needs Python 3.14 (`uuid.uuid7`).

**Tests** (`GAME_DEVELOPMENT_PLAN.md` section 3).
- Write the failing test first.
- Default tests run without a real model, the network, or the Godot GUI. Use
  the doubles in `tests/support/` (`FakeClock`, `FakeLLM`, the school fixture,
  temporary SQLite). The plan marks real-model tests `integration`; none exist yet.
- Acceptance checks state, events, idempotency, or a user-visible result.
  "It starts" does not count.
- Tests for `server/` go in `tests/playable/`, and end-to-end tests go in
  `tests/e2e/`. Prototype tests stay in `tests/test_prototype*.py`.

**Git and GitHub.**
- Use one branch per change from `develop`: `feature/`, `fix/`, `chore/`, or
  `docs/`.
- Commit subjects follow the existing style, for example
  `feat(domain): ...`, `fix(prototype): ...`, `chore(openspec): ...`, `docs: ...`.
- PRs are rebase-merged into `develop`. A release PR takes `develop` to `main`,
  and a `v*` tag on `main` creates a GitHub Release (`docs/ci_cd.md`).
- Run every `gh` command with `--repo EUVUD/marginalia`. Otherwise `gh` targets
  the upstream repository.
- No git identity is configured. Pass
  `-c user.name=... -c user.email=...` using the author of the latest
  `develop` commit (`git log -1 --format='%an %ae' origin/develop`).
- Before deleting a rebase-merged local branch, run `git cherry origin/develop <branch>`. Delete it with
  `git branch -D` only when that shows no `+` line.
- When describing the project, keep upstream Agentopia work (the weekly loop,
  the God Model, and the life reward) separate from this fork's work (the
  director layer, the playable runtime, and the prototype). Keep the MIT
  copyright notice in `LICENSE`.

**Traps.**
- Importing `src.world.world` or `src.utils` creates `logs/` and needs
  `config.json`. Legacy code resolves `data/...` from the current directory, so
  run it from the repository root.
- Toolchain versions are pinned in `toolchain.toml`. Don't treat an ambient
  Python, pytest, or Godot version as supported. Upgrades follow
  `docs/playable_toolchain.md`.
