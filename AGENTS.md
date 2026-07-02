# Repository Guidelines

## Project Structure & Module Organization

Agentopia is a Python project for long-term multi-agent life simulation. Core source lives in `src/`: `src/world/` contains simulation orchestration, scheduling, activities, locations, rewards, and run management; `src/agents/` contains role-agent behavior, prompts, context, validation, and data access. Entry points and analysis utilities live in `scripts/`. Scenario assets and generated run data live under `data/`, with base worlds such as `data/school/` and `data/apartment/`. OpenSpec planning artifacts live in `openspec/`.

Create and keep track of the interview.md documents in the project. Every time you made some important changes and improvements, include it in the interview.md. Structure interview.md as what you have done, the highlights, and the diffculties encountered in the project.

## Build, Test, and Development Commands

- `pip install -r requirements.txt`: install runtime dependencies.
- `cp config.example.json config.json`: create local model/world configuration. Do not commit secrets in `config.json`.
- `python scripts/run_world.py --world school --max-agents 5 --years 1 --weeks 1`: run a small local simulation smoke test.
- `python scripts/run_world.py --resume data/<run_dir>`: resume an existing run.
- `python scripts/compute_metrics.py --data-dir <run_dir>`: compute quantitative run metrics.
- `python scripts/build_rft_data.py --data-dir <run_dir> --top 0.25`: build RFT samples from a completed run.

## Coding Style & Naming Conventions

Use Python 3 style with 4-space indentation and type hints where practical. Prefer small, explicit functions and data structures over hidden global state. Keep module names lowercase with underscores, class names in `PascalCase`, and functions/variables in `snake_case`. Follow the existing file-backed JSON/JSONL patterns for simulation state, memory, logs, and generated records.

## Testing Guidelines

There is currently no formal test suite or coverage target. For changes, add focused tests when introducing reusable logic, validators, parsers, or data transformations. Prefer `tests/test_<module>.py` naming if a test suite is added, and include small fixtures rather than full 100-agent runs. At minimum, run a small smoke simulation with `--max-agents`, `--years`, and `--weeks` before submitting simulation changes.

## Commit & Pull Request Guidelines

Recent commits use concise Conventional Commit-style subjects, such as `docs: add Chinese, Japanese and Korean README translations`. Use a short imperative subject with an optional scope prefix (`docs:`, `feat:`, `fix:`). Pull requests should include a summary, affected modules or data paths, commands run, and notes about model/API configuration assumptions. Include screenshots or sample output only when changing reports, visual artifacts, or generated documentation.

## Security & Configuration Tips

Keep API keys, endpoints, credentials files, and generated run outputs out of commits unless intentionally adding sanitized fixtures. Treat `data/<world>_<runid>/`, `logs/`, and `rft_data/` as potentially large and sensitive generated artifacts.
