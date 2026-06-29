"""`forge-agent dashboard` — start the local observability dashboard."""

from __future__ import annotations

import argparse
import contextlib
import sys


def add(sub: argparse._SubParsersAction) -> None:
    """Add the dashboard command to the CLI."""
    p = sub.add_parser(
        "dashboard",
        help="Start the local observability dashboard (web UI)",
    )
    p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host (default: 127.0.0.1, local only)",
    )
    p.add_argument(
        "--port",
        "-p",
        type=int,
        default=8765,
        help="Bind port (default: 8765)",
    )
    p.add_argument(
        "--reload",
        action="store_true",
        help="Enable hot reload (development only)",
    )
    p.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't auto-open browser",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Start the dashboard server."""
    try:
        import uvicorn
    except ImportError:
        print(
            "Error: uvicorn not installed.\nInstall with: pip install 'forge-agent[dashboard]'",
            file=sys.stderr,
        )
        return 1

    from forge_agent.dashboard.app import create_app

    project_root = args.project.resolve()
    app = create_app(
        project_root=project_root,
        host=args.host,
        port=args.port,
    )

    print("⚡ forge-agent Dashboard")
    print(f"  → URL:       http://{args.host}:{args.port}")
    print(f"  → Project:   {project_root}")
    print(f"  → Hot reload: {'ON' if args.reload else 'OFF'}")
    print("  → Press Ctrl+C to stop")
    print()

    # Auto-open browser (best-effort)
    if not args.no_browser:
        import threading
        import time
        import webbrowser

        def _open_browser() -> None:
            time.sleep(1.0)  # wait for server to start
            url = f"http://{args.host}:{args.port}"
            with contextlib.suppress(Exception):
                webbrowser.open(url)

        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0
