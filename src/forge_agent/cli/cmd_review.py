"""`forge-agent review` — post-match feedback & agent evolution.

Record the actual outcome of a past prediction and optionally trigger
prompt evolution for the agent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "review",
        help="Post-match feedback: record outcome and optionally evolve an agent",
    )
    p.add_argument("--agent-id", required=True, help="Agent identifier")
    p.add_argument("--run-id", required=True, help="Run identifier for the prediction")
    p.add_argument(
        "--winner",
        required=True,
        choices=["home", "away", "draw"],
        help="Actual winner",
    )
    p.add_argument("--home-score", type=float, default=None, help="Actual home score")
    p.add_argument("--away-score", type=float, default=None, help="Actual away score")
    p.add_argument(
        "--note",
        action="append",
        default=[],
        help="Free-form note (can be given multiple times)",
    )
    p.add_argument(
        "--evolve",
        action="store_true",
        help="Trigger prompt evolution if reflection score is low",
    )
    p.add_argument(
        "--report-db",
        type=Path,
        default=None,
        help="Path to the SQLite reports database (default: ~/.forge_agent/agent_reports.db)",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from forge_agent.core.capabilities import InMemoryPromptManager
    from forge_agent.core.report_store import SQLiteReportStore
    from forge_agent.learning import MatchOutcome, PostMatchFeedback

    outcome = MatchOutcome(
        actual_winner=args.winner,
        home_score=args.home_score,
        away_score=args.away_score,
        notes=list(args.note),
    )

    report_store = SQLiteReportStore(db_path=args.report_db)
    feedback = PostMatchFeedback(report_store=report_store)

    async def _main() -> dict:
        await feedback.record_outcome(args.run_id, outcome, agent_id=args.agent_id)
        if args.evolve:
            prompt_manager = InMemoryPromptManager()
            # Seed the prompt manager with the agent's current prompt if known.
            try:
                from forge_agent.cli._helpers import get_store

                store = get_store(Path.cwd())
                source = store.load_source(args.agent_id)
                if source:
                    prompt_manager.register(args.agent_id, "v1", source)
            except Exception:
                pass
            return await feedback.review_and_evolve(
                args.agent_id,
                args.run_id,
                prompt_manager=prompt_manager,
            )
        return await feedback.review(args.agent_id, args.run_id)

    result = asyncio.run(_main())
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("reflected", False) else 1
