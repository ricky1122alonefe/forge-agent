"""`forge-agent restore` — restore generated_agents/ from a git repository."""

from __future__ import annotations

import argparse
import shutil
import subprocess


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("restore", help="Restore generated_agents/ from a git repo")
    p.add_argument("--from", dest="source", help="Git URL to clone from")
    p.add_argument("--branch", default="main", help="Branch to checkout")
    p.add_argument("--force", action="store_true", help="Overwrite existing generated_agents/")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    if not shutil.which("git"):
        print("Error: git not installed")
        return 1

    gen_dir = args.project / "generated_agents"
    if gen_dir.exists() and not args.force:
        print(f"{gen_dir} already exists. Use --force to overwrite.")
        return 1

    if gen_dir.exists():
        shutil.rmtree(gen_dir)

    if args.source:
        # Clone
        subprocess.run(["git", "clone", args.source, str(gen_dir)], check=True)
        if args.branch != "main":
            subprocess.run(["git", "checkout", args.branch], cwd=gen_dir, check=True)
        print(f"✓ Cloned to {gen_dir}")
    else:
        # Pull from existing remote
        if not (gen_dir / ".git").exists():
            print("No git history found. Use --from <url> to clone.")
            return 1
        subprocess.run(["git", "pull"], cwd=gen_dir, check=True)
        print("✓ Pulled latest")

    # Verify manifest
    manifest_path = gen_dir / "MANIFEST.json"
    if manifest_path.is_file():
        print(f"✓ Manifest valid: {manifest_path}")
    else:
        print(f"⚠️  No MANIFEST.json found at {manifest_path}")
    return 0
