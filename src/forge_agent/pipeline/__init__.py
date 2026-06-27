"""Pipeline: DAG-based orchestration of Agents."""

from __future__ import annotations

from forge_agent.pipeline.pipeline import Pipeline, PipelineNode, NodeType
from forge_agent.pipeline.engine import PipelineEngine
from forge_agent.pipeline.aggregator import Aggregator

__all__ = [
    "Pipeline",
    "PipelineNode",
    "NodeType",
    "PipelineEngine",
    "Aggregator",
]
