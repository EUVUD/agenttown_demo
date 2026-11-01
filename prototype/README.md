# Tomorrow's Reply — fast prototype

A playable, deliberately rough version of the first vertical slice in
`GAME_DEVELOPMENT_PLAN.md`: one protagonist (林夏) and four NPCs in a fixed school
world, four slots per day, real-time chat, indirect influence, letters, and
offline catch-up. It exists to feel the play loop before the event-sourced runtime
is built. Expect to refactor it, not extend it.

## Run

```bash
python3 -m prototype            # then open http://127.0.0.1:8765
python3 -m prototype --llm fake # force the offline fake model
python3 -m prototype --dev      # also allow the developer view (?debug=1)
```

Standard library only (tested on Python 3.13 and 3.14). No install step and no change to
`requirements.lock`. World state lives in `prototype/.data/world.db` (git-ignored);
use `--db PATH` to keep separate saves.

## Models

`AGENTTOWN_LLM` selects the provider; the default `auto` uses Anthropic when
`ANTHROPIC_API_KEY` is set, otherwise an OpenAI-compatible endpoint when
`OPENAI_API_KEY` is set, otherwise the offline fake.

| Variable | Used for |
|---|---|
| `AGENTTOWN_LLM` | `auto`, `anthropic`, `openai`, or `fake` |
| `ANTHROPIC_API_KEY` | Anthropic Messages API |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | Any OpenAI-compatible endpoint (vLLM, Ollama, hosted APIs) |
| `AGENTTOWN_MODEL` | Model name; required for `openai`, defaults to `claude-opus-5-5` for `anthropic` |

The fake model is deterministic and rule-based. It is enough to click through
every feature and is what the tests use, but its writing is canned.

## The loop

- **Chat** (`chat` call): she replies in character. If you suggest something, the
  reply carries an *influence* that is stored as pending. Chat output cannot touch
  relationships, location, or any other state; extra fields are dropped.
- **Advance a slot** (`slot` call): a narrator decides what she does. Pending
  influences are adopted, declined, or deferred by *her*, with a reason, and the
  scene event records which influences caused it.
- **End of day** (`review` call after slot 4): summary, diary, tomorrow's focus,
  and sometimes a letter to you.
- **Offline catch-up**: on page load, each real day missed becomes one summarized
  game day (`offscreen_day` call), capped at 7; longer absences put the world to
  sleep. One `letter` call then writes to you. Use "模拟离开…" to test it. The plan
  is stored before the first model call and updated with every committed day, so a
  provider error part way through is finished by the next page load instead of
  simulating the absence again.
- **Knowledge boundary**: NPC secrets (`hidden` in `world.json`) only appear in
  narrator prompts. Chat, letters, and reviews see what she experienced or
  discovered. Narrator output is also screened before it is stored: her memory,
  mood, diary, focus, reasons, and letters, and the scene text fed to the day review,
  are dropped or blanked when they carry text of a secret she has not been told, and
  the event records `meta.leak_blocked`. A secret counts as told once a fact she
  knows carries it, so an unrelated discovery about the same person changes nothing,
  and a discovery that carries someone else's secret is dropped. Her chat reply, mood,
  and influence text are screened the same way. A blocked absence letter is replaced
  by a plain one without a record. The screen matches copied or lightly edited text
  (ten consecutive characters, ignoring punctuation); a paraphrase can still pass, so
  the narrator prompt rule remains the first defence. The timeline shows the
  narrator's scene text to the player as written and is not screened.
- **Developer view**: snapshots carry no `debug` payload by default. `?debug=1` adds
  NPC secrets, her memories, and diaries, and only a server started with `--dev`
  honours it.
- **Worlds keep their blueprint**: each world stores the blueprint it was created
  from. Editing `world.json` changes new worlds only; a world whose stored blueprint
  version this build cannot read reports that instead of failing.
- **Model failures**: invalid JSON gets one repair call, then a rule-based
  fallback flagged in the timeline. Network or auth errors surface in the UI.

Model calls per game day: 4 slots + 1 review online; 1 per day plus 1 letter for
catch-up.

## API

| Method | Path | Body |
|---|---|---|
| GET | `/api/state` | — (add `?debug=1` on a `--dev` server for the developer view) |
| POST | `/api/session` | — (runs catch-up) |
| POST | `/api/message` | `{"text", "client_id"}` (retries with the same `client_id` are deduplicated) |
| POST | `/api/advance` | — |
| POST | `/api/letters/<id>/read` | — |
| POST | `/api/dev/away` | `{"days"}` |
| POST | `/api/world/new` | — |

POST responses are `{"result": ..., "state": <snapshot>}`. A Godot client can use
the same API in place of `static/`.

## Shortcuts to pay back when refactoring

- State is a JSON blob rewritten per command; events are append-only but are not
  yet the source of truth (no reducer or replay; D1.5/D1.6).
- IDs are random `prefix-hex`, and time is plain ints, instead of `server.domain`
  `EventId`/`WorldTime` (those require Python 3.14).
- One active world (the latest); no world selection.
- The leak screen is a text guard, not a proof; separating "what happened" from
  "what she perceived" in the narrator output is the real fix (M9.1).
- Slots advance on a button press rather than the wall clock (O8.1).
- Keys come from environment variables, not the OS keyring (L5.2).
- No OpenSpec change was written for this spike, and no roadmap checkbox is ticked:
  none of the acceptance criteria were verified.

Tests: `python -m pytest tests/test_prototype.py -q` (offline, deterministic).
