"""`forge-agent rollback` — roll back to the previous version."""

from __future__ import annotations

import argparse


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("rollback", help="Roll back an agent to its previous version")
    p.add_argument("agent_id", help="The agent_id")
    p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from forge_agent.cli._helpers import get_store

    try:
        store = get_store(args.project)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    entry = store.manifest.agents.get(args.agent_id)
    if not entry:
        print(f"Agent {args.agent_id!r} not found.")
        return 1

    if not args.yes:
        print(f"Current active: {entry.active_version}")
        confirm = input("Roll back to previous version? (y/N): ")
        if confirm.strip().lower() != "y":
            print("Cancelled.")
            return 0

    try:
        new_active = store.rollback(args.agent_id)
    except ValueError as exc:
        print(f"Cannot rollback: {exc}")
        return 1
    print(f"✓ Rolled back. Now running: {new_active}")
    return 0
