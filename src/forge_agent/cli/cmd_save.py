"""`forge-agent save` — push generated_agents/ to a git repository.

Lightweight git integration: just shells out to `git` commands. This is
intentionally simple; advanced users can manage this manually.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("save", help="Commit and optionally push generated_agents/")
    p.add_argument("--message", "-m", default="forge-agent: save generated agents", help="Commit message")
    p.add_argument("--push", action="store_true", help="Push to remote after commit")
    p.add_argument("--init", action="store_true", help="git init the directory first")
    p.add_argument("--remote", help="Git remote URL (for --init)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    gen_dir = args.project / "generated_agents"
    if not gen_dir.is_dir():
        print(f"No generated_agents/ at {gen_dir}")
        return 1

    if args.init and not (gen_dir / ".git").exists():
        if not shutil.which("git"):
            print("Error: git not installed")
            return 1
        subprocess.run(["git", "init"], cwd=gen_dir, check=True)
        if args.remote:
            subprocess.run(["git", "remote", "add", "origin", args.remote], cwd=gen_dir, check=True)
        print(f"✓ Initialized git in {gen_dir}")

    if not (gen_dir / ".git").exists():
        print("Not a git repo. Use --init to create one, or run 'git init' manually in generated_agents/")
        return 1

    # Commit
    subprocess.run(["git", "add", "-A"], cwd=gen_dir, check=True)
    result = subprocess.run(
        ["git", "commit", "-m", args.message],
        cwd=gen_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and "nothing to commit" not in result.stdout:
        print(f"git commit failed: {result.stderr}")
        return 1
    print(f"✓ Committed: {args.message}")

    if args.push:
        push = subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=gen_dir, capture_output=True, text=True,
        )
        if push.returncode != 0:
            print(f"git push failed: {push.stderr}")
            return 1
        print("✓ Pushed to origin/main")
    return 0
