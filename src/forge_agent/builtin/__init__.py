"""Built-in agents and adapters shipped with forge-agent.

These serve two purposes:
    1. Show canonical implementations of BaseAgent for the docs.
    2. Provide drop-in functionality for common needs (logging, monitoring,
       chief aggregation).

For domain-specific agents (football, stock, etc.), prefer:
    - Putting them under `forge_agent.contrib.<domain>` in separate packages
    - Or generating them via the Code Generator (v0.2+)
"""

from __future__ import annotations

from forge_agent.builtin.chief_agent import ChiefAgent
from forge_agent.builtin.logging_agent import LoggingAgent
from forge_agent.builtin.monitoring_agent import MonitoringAgent

__all__ = ["ChiefAgent", "LoggingAgent", "MonitoringAgent"]
