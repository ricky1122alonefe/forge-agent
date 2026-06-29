"""Pipeline: DAG-based orchestration of Agents."""

from __future__ import annotations

from forge_agent.pipeline.aggregator import Aggregator
from forge_agent.pipeline.engine import PipelineEngine
from forge_agent.pipeline.pipeline import NodeType, Pipeline, PipelineNode

__all__ = [
    "Aggregator",
    "NodeType",
    "Pipeline",
    "PipelineEngine",
    "PipelineNode",
]
