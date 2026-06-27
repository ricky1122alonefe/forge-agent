"""Sample football pipeline using forge-agent.

DAG:
    football.intel  ──┐
                      ├──► chief ──► aggregator
    football.factors ──┘
"""

from __future__ import annotations

from forge_agent.pipeline.aggregator import Aggregator
from forge_agent.pipeline.engine import PipelineEngine
from forge_agent.pipeline.pipeline import NodeType, Pipeline, PipelineNode


def build_football_pipeline() -> Pipeline:
    p = Pipeline(pipeline_id="football.match.v1")
    p.add_node(
        PipelineNode(
            node_id="intel",
            node_type=NodeType.AGENT,
            agent_id="football.intel",
            next_nodes=["chief"],
        )
    )
    p.add_node(
        PipelineNode(
            node_id="chief",
            node_type=NodeType.AGENT,
            agent_id="generic.chief",
            next_nodes=["aggregate"],
        )
    )
    p.add_node(
        PipelineNode(
            node_id="aggregate",
            node_type=NodeType.AGGREGATOR,
        )
    )
    return p


async def run_pipeline(ctx) -> dict:
    pipeline = build_football_pipeline()
    engine = PipelineEngine(aggregator=Aggregator(hard_risk_threshold=0.7))
    return await engine.run(pipeline, ctx)
