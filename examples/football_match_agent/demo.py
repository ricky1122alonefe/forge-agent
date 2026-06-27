"""End-to-end demo: run the football pipeline on a sample match.

Usage:
    python -m examples.football_match_agent.demo
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

# Make `forge_agent` importable when running this file directly.
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from forge_agent.core.context import AgentContext
from forge_agent.registry.discovery import discover_filesystem
from forge_agent.registry.registry import get_registry

# Side-effect import: triggers @register_agent decorators.
from examples.football_match_agent import agents  # noqa: F401
from examples.football_match_agent.pipeline import run_pipeline
from forge_agent.builtin import chief_agent  # noqa: F401  (registers generic.chief)


SAMPLE_FIXTURE = {
    "scope_id": "wc_2026_group_a_001",
    "scope_name": "Qatar vs Indonesia",
    "payload": {
        "match": "Qatar vs Indonesia",
        "competition": "World Cup 2026 — Group A",
        "kickoff": "2026-06-15T18:00:00+03:00",
        "home_team": "Qatar",
        "away_team": "Indonesia",
        "odds_snapshot": {"home": 1.45, "draw": 4.2, "away": 6.5},
        "news": {
            "home_injuries": 0,
            "away_injuries": 2,
        },
        "form": {"home_last5": "WWDWL", "away_last5": "LDLLW"},
    },
}


async def main() -> None:
    print("=" * 70)
    print("forge-agent :: football pipeline demo")
    print("=" * 70)

    # 1. Show registered agents
    registry = get_registry()
    print(f"\nRegistered agents ({len(registry)}):")
    for aid in registry.list():
        meta = registry.get_metadata(aid)
        print(f"  - {aid}  [domain={meta.get('domain')}, tags={meta.get('tags')}]")

    # 2. Build context
    ctx = AgentContext(
        scope_id=SAMPLE_FIXTURE["scope_id"],
        scope_name=SAMPLE_FIXTURE["scope_name"],
        domain="football",
        payload=SAMPLE_FIXTURE["payload"],
    )
    print(f"\nRunning pipeline for: {ctx.scope_name} ({ctx.scope_id})")

    # 3. Run the pipeline
    state = await run_pipeline(ctx)

    # 4. Show the results
    print("\n--- Agent Reports ---")
    for node_id, report in state["reports"].items():
        d = report.to_dict()
        print(f"\n[{node_id}] {d['name']}")
        print(f"  verdict:        {d['verdict']}")
        print(f"  confidence:     {d['confidence']}")
        print(f"  risk:           {d['risk']}")
        print(f"  action:         {d['recommended_action']}")
        print(f"  evidence:       {d['evidence']}")
        if d["warnings"]:
            print(f"  warnings:       {d['warnings']}")

    print("\n--- Final Board ---")
    if "board" in state and state["board"] is not None:
        board_dict = state["board"].to_dict()
        print(json.dumps(board_dict, indent=2, ensure_ascii=False))
    else:
        print("(no board produced)")

    # 5. Cleanup
    await registry.shutdown_all()
    print("\nDemo done.")


if __name__ == "__main__":
    asyncio.run(main())
