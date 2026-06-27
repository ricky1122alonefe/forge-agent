"""CLI: `forge-agent` command.

Commands:
    generate    Generate an Agent from a natural-language description
    list        List all generated agents
    history     Show version history for an agent
    use         Switch the active version of an agent
    rollback    Roll back to the previous version
    diff        Show diff between two versions
    manifest    Show the project manifest
    save        Push generated_agents/ to a git repository
    restore     Restore generated_agents/ from a git repository
    archive     Archive an agent (mark deprecated)
    delete      Delete a specific version (DANGEROUS)
    llm         LLM management: list / test / config
    new         Create a new project from a template
    logs        Show recent structured log entries
    dashboard   Start the local observability dashboard (web UI)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="forge-agent",
        description="forge-agent CLI: scaffold, generate, manage, and deploy AI agents.",
    )
    parser.add_argument(
        "--project", "-p",
        type=Path,
        default=Path.cwd(),
        help="Project root (default: cwd)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose logging",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    # Top-level commands — lazily import to avoid heavy deps at startup
    from forge_agent.cli import cmd_generate, cmd_list, cmd_history, cmd_use
    from forge_agent.cli import cmd_rollback, cmd_diff, cmd_manifest
    from forge_agent.cli import cmd_save, cmd_restore, cmd_archive, cmd_delete
    from forge_agent.cli import cmd_llm, cmd_new, cmd_logs, cmd_datasets, cmd_mcp, cmd_doctor
    from forge_agent.cli import cmd_dashboard

    cmd_generate.add(sub)
    cmd_list.add(sub)
    cmd_history.add(sub)
    cmd_use.add(sub)
    cmd_rollback.add(sub)
    cmd_diff.add(sub)
    cmd_manifest.add(sub)
    cmd_save.add(sub)
    cmd_restore.add(sub)
    cmd_archive.add(sub)
    cmd_delete.add(sub)
    cmd_llm.add(sub)
    cmd_new.add(sub)
    cmd_logs.add(sub)
    cmd_datasets.add(sub)
    cmd_mcp.add(sub)
    cmd_doctor.add(sub)
    cmd_dashboard.add(sub)

    args = parser.parse_args(argv)

    # Configure the unified logger BEFORE dispatching the subcommand,
    # so the chosen command's logs already go through the right renderer.
    from forge_agent.observability.logger import configure_logging

    configure_logging(level="DEBUG" if args.verbose else None)

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        if args.verbose:
            raise
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
