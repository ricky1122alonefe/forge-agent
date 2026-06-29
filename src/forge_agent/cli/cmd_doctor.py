"""`forge-agent doctor` — environment health check.

Checks:
    1. Python version >= 3.10
    2. forge-agent package importable
    3. Optional dependencies (mcp, search, otel)
    4. LLM config file exists and is valid
    5. API keys set in environment
    6. generated_agents/ directory exists
    7. SQLite available
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("doctor", help="Check environment health")
    p.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to auto-fix common issues",
    )
    p.set_defaults(func=run)


# ---------------------------------------------------------------------------
# Check helpers
# ---------------------------------------------------------------------------


class CheckResult:
    """Result of a single health check."""

    def __init__(self, name: str, ok: bool, message: str, hint: str = "") -> None:
        self.name = name
        self.ok = ok
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        icon = "✓" if self.ok else "✗"
        line = f"  {icon} {self.name}: {self.message}"
        if not self.ok and self.hint:
            line += f"\n    → {self.hint}"
        return line


def _check_python_version() -> CheckResult:
    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    ok = v >= (3, 10)
    return CheckResult(
        "Python version",
        ok,
        ver,
        hint="Install Python 3.10+ from https://python.org" if not ok else "",
    )


def _check_forge_agent() -> CheckResult:
    try:
        from forge_agent.__version__ import __version__

        return CheckResult("forge-agent", True, f"v{__version__}")
    except ImportError:
        return CheckResult("forge-agent", False, "not installed", hint="pip install forge-agent")


def _check_optional_dep(package: str, extra: str) -> CheckResult:
    try:
        mod = importlib.import_module(package)
        ver = getattr(mod, "__version__", "installed")
        return CheckResult(f"{extra} SDK", True, str(ver))
    except ImportError:
        return CheckResult(
            f"{extra} SDK",
            False,
            "not installed",
            hint=f"pip install 'forge-agent[{extra}]'",
        )


def _check_llm_config(project: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # Find config file
    config_path: Path | None = None
    env_path = os.environ.get("FORGE_LLM_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            config_path = p

    if config_path is None:
        for name in ("llm_providers.json", "llm_providers.example.json"):
            p = project / name
            if p.is_file():
                config_path = p
                break

    if config_path is None:
        results.append(
            CheckResult(
                "LLM config file",
                False,
                "not found",
                hint="Create llm_providers.json or set FORGE_LLM_CONFIG env var",
            )
        )
        return results

    results.append(CheckResult("LLM config file", True, str(config_path)))

    # Validate JSON
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        results.append(
            CheckResult(
                "LLM config JSON",
                False,
                f"invalid: {exc}",
                hint="Fix the JSON syntax in your config file",
            )
        )
        return results

    results.append(CheckResult("LLM config JSON", True, "valid"))

    # Check providers and API keys
    providers = data.get("providers", {})
    for _pid, pdata in providers.items():
        if not isinstance(pdata, dict):
            continue
        if not pdata.get("enabled", True):
            continue
        api_key_env = pdata.get("api_key_env")
        if api_key_env:
            key_val = os.environ.get(api_key_env)
            if key_val:
                masked = key_val[:4] + "..." + key_val[-4:] if len(key_val) > 8 else "***"
                results.append(CheckResult(f"API key: {api_key_env}", True, masked))
            else:
                results.append(
                    CheckResult(
                        f"API key: {api_key_env}",
                        False,
                        "not set",
                        hint=f"export {api_key_env}=your-key-here",
                    )
                )

    return results


def _check_generated_dir(project: Path) -> CheckResult:
    d = project / "generated_agents"
    if d.is_dir():
        # Count agents
        manifest = d / "MANIFEST.json"
        if manifest.is_file():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                count = len(data.get("agents", {}))
                return CheckResult("generated_agents/", True, f"{count} agent(s)")
            except Exception:
                return CheckResult("generated_agents/", True, "exists (manifest unreadable)")
        return CheckResult("generated_agents/", True, "exists (no manifest)")
    return CheckResult(
        "generated_agents/",
        False,
        "not found",
        hint="Run 'forge-agent generate \"...\"' to create your first agent",
    )


def _check_sqlite() -> CheckResult:
    try:
        import sqlite3

        ver = sqlite3.sqlite_version
        return CheckResult("SQLite", True, ver)
    except ImportError:
        return CheckResult("SQLite", False, "not available", hint="Install sqlite3 for your Python")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    project: Path = args.project

    print("forge-agent doctor")
    print("=" * 50)

    checks: list[CheckResult] = []

    # 1. Core
    checks.append(_check_python_version())
    checks.append(_check_forge_agent())

    # 2. Optional dependencies
    checks.append(_check_optional_dep("mcp", "mcp"))
    checks.append(_check_optional_dep("opentelemetry", "otel"))

    # 3. SQLite
    checks.append(_check_sqlite())

    # 4. LLM config
    checks.extend(_check_llm_config(project))

    # 5. Generated agents directory
    checks.append(_check_generated_dir(project))

    # Print results
    passed = 0
    failed = 0
    for c in checks:
        print(c)
        if c.ok:
            passed += 1
        else:
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed, {len(checks)} total")

    if failed == 0:
        print("\nAll checks passed! Your environment is healthy.")
        return 0
    else:
        print(f"\n{failed} issue(s) found. See hints above for fixes.")
        return 1
