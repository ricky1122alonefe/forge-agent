"""`forge-agent diff` — show diff between two versions."""

from __future__ import annotations

import argparse
import difflib


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("diff", help="Show diff between two versions")
    p.add_argument("agent_id", help="The agent_id")
    p.add_argument("from_version", help="From version (e.g. v1)")
    p.add_argument("to_version", help="To version (e.g. v2)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from forge_agent.cli._helpers import get_store

    try:
        store = get_store(args.project)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    from_src = store.load(args.agent_id, args.from_version)
    to_src = store.load(args.agent_id, args.to_version)
    if not from_src or not to_src:
        print("One or both versions not found.")
        return 1

    from_lines = from_src.splitlines(keepends=True)
    to_lines = to_src.splitlines(keepends=True)
    diff = difflib.unified_diff(
        from_lines, to_lines,
        fromfile=f"{args.agent_id}@{args.from_version}",
        tofile=f"{args.agent_id}@{args.to_version}",
    )
    print("".join(diff), end="")
    return 0
