"""`forge-agent manifest` — show the project manifest."""

from __future__ import annotations

import argparse
import json


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("manifest", help="Show the project manifest")
    p.add_argument("--raw", action="store_true", help="Print raw JSON")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from forge_agent.cli._helpers import get_store

    try:
        store = get_store(args.project)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    if args.raw:
        print(json.dumps(store.manifest.to_dict(), indent=2, ensure_ascii=False))
    else:
        m = store.manifest
        print(f"Project: {m.project}")
        print(f"Updated: {m.updated_at}")
        print(f"Agents:  {len(m.agents)}")
        for aid, e in m.agents.items():
            print(f"  - {aid}: active={e.active_version}, {len(e.versions)} version(s)")
    return 0
