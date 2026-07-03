"""`forge-agent up` — start the self-hosted web UI."""

from __future__ import annotations

import argparse
import contextlib
import sys
import threading
import time
import webbrowser


def add(sub: argparse._SubParsersAction) -> None:
    """Add the `up` command to the CLI."""
    p = sub.add_parser(
        "up",
        help="启动 forge-agent 并打开 Web UI（自动初始化默认租户/项目）",
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
        default=8787,
        help="Bind port (default: 8787)",
    )
    p.add_argument(
        "--tenant-id",
        default="default",
        help="Tenant id to use (default: default)",
    )
    p.add_argument(
        "--project-id",
        default="default",
        help="Project id to use (default: default)",
    )
    p.add_argument(
        "--data-dir",
        default=None,
        help="Data directory (default: FORGE_AGENT_DATA_DIR or ~/.forge-agent)",
    )
    p.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't auto-open browser",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Start the self-hosted web UI."""
    try:
        import uvicorn
    except ImportError:
        print(
            "Error: uvicorn not installed.\nInstall with: pip install 'forge-agent[dashboard]'",
            file=sys.stderr,
        )
        return 1

    from pathlib import Path

    from forge_agent.platform import LocalTenant
    from forge_agent.web.app import create_app
    from forge_agent.web.context import project_url, resolve_data_root

    data_root = resolve_data_root(Path(args.data_dir) if args.data_dir else None)
    tenant = LocalTenant(args.tenant_id, root_dir=data_root)
    tenant.ensure_project(args.project_id)

    app = create_app(
        data_root=data_root,
        default_tenant_id=args.tenant_id,
        default_project_id=args.project_id,
    )

    workspace_url = project_url(args.tenant_id, args.project_id, "/")

    print("⚡ forge-agent is up")
    print(f"  → URL:     http://{args.host}:{args.port}{workspace_url}")
    print(f"  → Data:    {data_root}")
    print(f"  → Tenant:  {args.tenant_id}")
    print(f"  → Project: {args.project_id}")
    print("  → Press Ctrl+C to stop")
    print()

    if not args.no_browser:

        def _open_browser() -> None:
            time.sleep(1.0)
            url = f"http://{args.host}:{args.port}{workspace_url}"
            with contextlib.suppress(Exception):
                webbrowser.open(url)

        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
    )
    return 0
