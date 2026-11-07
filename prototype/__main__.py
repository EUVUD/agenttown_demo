"""Run the prototype: `python -m prototype` from the repository root."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from prototype.engine import Game, load_blueprint
from prototype.llm import LLMError, provider_from_env
from prototype.server import serve

DEFAULT_DB = Path(__file__).with_name(".data") / "world.db"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m prototype", description="Run the Marginalia fast prototype."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite file for world state")
    parser.add_argument(
        "--llm",
        choices=["auto", "anthropic", "openai", "fake"],
        help="model provider; overrides MARGINALIA_LLM (default: auto)",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="allow the developer view (?debug=1), whose responses include every NPC's hidden secret",
    )
    args = parser.parse_args(argv)
    try:
        provider = provider_from_env(args.llm)
    except LLMError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    serve(Game(args.db, provider, load_blueprint()), args.host, args.port, dev=args.dev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
