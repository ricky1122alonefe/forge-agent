"""`forge-agent delete` — delete a specific version (DANGEROUS)."""

from __future__ import annotations

import argparse


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("delete", help="Delete a specific version (DANGEROUS)")
    p.add_argument("agent_id", help="The agent_id")
    p.add_argument("version", help="Version to delete (e.g. v1)")
    p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from forge_agent.cli._helpers import get_store

    try:
        store = get_store(args.project)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    if not args.yes:
        print(f"PERMANENTLY delete {args.agent_id}@{args.version}?")
        print("This cannot be undone (unless you have a git backup).")
        confirm = input("Type 'delete' to confirm: ")
        if confirm.strip() != "delete":
            print("Cancelled.")
            return 0

    try:
        store.delete_version(args.agent_id, args.version)
    except ValueError as exc:
        print(f"Cannot delete: {exc}")
        return 1
    print(f"✓ Deleted {args.agent_id}@{args.version}")
    return 0
