"""Allow `python -m forge_agent.cli` to invoke the CLI."""
from __future__ import annotations

from forge_agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
