#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.world.director_service import DirectorWorldService


def main() -> None:
    parser = argparse.ArgumentParser(description="Opt-in director-world backend tools")
    sub = parser.add_subparsers(dest="command", required=True)

    schema = sub.add_parser("schema", help="Print a template creator schema")
    schema.add_argument("template_id")

    create = sub.add_parser("create", help="Create a run from a template payload")
    create.add_argument("template_id")
    create.add_argument("payload_json")
    create.add_argument("--run-id", default=None)

    args = parser.parse_args()
    service = DirectorWorldService()
    if args.command == "schema":
        print(json.dumps(service.get_template_schema(args.template_id), ensure_ascii=False, indent=2))
    elif args.command == "create":
        payload = json.loads(Path(args.payload_json).read_text(encoding="utf-8"))
        run_dir = service.create_world(args.template_id, payload, run_id=args.run_id)
        print(run_dir.as_posix())


if __name__ == "__main__":
    main()
