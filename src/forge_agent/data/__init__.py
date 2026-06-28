"""Data layer — normalize heterogeneous sources into domain schemas.

This module bridges raw scraped data and forge-agent's analysis layer:

    DataSource (config) -> fetch -> Normalizer -> SchemaRecord -> Evidence

The goal is to make upstream agents independent of specific websites or APIs.
"""

from __future__ import annotations

from forge_agent.data.normalizer import Normalizer, NormalizerConfig
from forge_agent.data.schema import OddsRecord, SchemaRecord
from forge_agent.data.source import DataSource, DataSourceConfig

__all__ = [
    "DataSource",
    "DataSourceConfig",
    "Normalizer",
    "NormalizerConfig",
    "OddsRecord",
    "SchemaRecord",
]
