"""End-to-end pipeline demo.

Loads ``examples/configs/sports_pipeline.yaml``:
    - match context (home/away/city/date)
    - multiple odds sources (different raw formats)
    - config-driven expert agents
    - a Team with a Chief agent

Then runs everything through ``PipelineLoader`` and prints the final report.

Run with:

    cd /path/to/forge-agent
    python -m examples.run_pipeline
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from forge_agent.config.pipeline import PipelineLoader


async def main() -> None:
    config_path = Path(__file__).with_suffix("").parent / "configs" / "sports_pipeline.yaml"
    loader = PipelineLoader.from_yaml(config_path)

    print("=" * 60)
    print("End-to-End Sports Pipeline")
    print("=" * 60)

    board = await loader.run()

    print("\n--- Member Reports ---")
    for report in board.agents:
        print(
            f"\n[{report.name}] "
            f"verdict={report.verdict.value} "
            f"confidence={report.confidence:.0%} "
            f"risk={report.risk:.0%}"
        )
        for ev in report.evidence:
            print(f"  - {ev}")

        search_meta = report.raw.get("search")
        if search_meta:
            print(
                f"  [search] query={search_meta.get('query')!r} backend={search_meta.get('backend')}"
            )
            for idx, result in enumerate(search_meta.get("results", []), 1):
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                print(f"    {idx}. {title}: {snippet}")

    print("\n--- Chief Briefing ---")
    chief_report = board.summary.get("chief_report")
    if chief_report:
        print(f"verdict: {chief_report.get('verdict')}")
        print(f"confidence: {chief_report.get('confidence')}")
        print(f"risk: {chief_report.get('risk')}")
        print(f"action: {chief_report.get('recommended_action')}")
        print(f"summary: {chief_report.get('evidence', [''])[0]}")
        if len(chief_report.get("evidence", [])) > 1:
            for ev in chief_report["evidence"][1:]:
                print(f"  - {ev}")
    else:
        print("No chief report produced.")

    print("\n--- Board Summary ---")
    print(f"ok: {board.ok}")
    print(f"hard_guards: {board.hard_guards}")
    for key, value in board.summary.items():
        if key == "chief_report":
            continue
        print(f"{key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
