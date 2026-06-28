"""Normalizer — turn raw source data into a standardized SchemaRecord.

Each normalizer knows:
    - which SchemaRecord subclass to produce
    - how to map source-specific field names to schema field names
    - how to coerce types
    - how to produce evidence strings for agents
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar

from forge_agent.data.schema import OddsRecord, SchemaRecord
from forge_agent.data.source import DataSource

log = logging.getLogger(__name__)


@dataclass
class NormalizerConfig:
    """Configuration for a normalizer.

    field_map:  {schema_field: raw_field_path}
                Path can be a simple key or dot-separated ("data.home_team").
    defaults:   Fallback values for missing fields.
    transforms: Optional per-field transform functions (registered by name).
    """

    schema: str = "odds"
    field_map: dict[str, str] = None  # type: ignore[assignment]
    defaults: dict[str, Any] = None  # type: ignore[assignment]
    transforms: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.field_map is None:
            self.field_map = {}
        if self.defaults is None:
            self.defaults = {}
        if self.transforms is None:
            self.transforms = {}


class Normalizer:
    """Convert raw data from a DataSource into a SchemaRecord."""

    # schema name -> record class
    _schemas: ClassVar[dict[str, type[SchemaRecord]]] = {
        "odds": OddsRecord,
    }

    # transform name -> callable
    _transforms: ClassVar[dict[str, Callable[[Any], Any]]] = {
        "float": lambda v: float(v) if v is not None else None,
        "int": lambda v: int(v) if v is not None else None,
        "strip": lambda v: str(v).strip() if v is not None else None,
    }

    def __init__(self, config: NormalizerConfig) -> None:
        self.config = config

    @classmethod
    def register_schema(cls, name: str, record_cls: type[SchemaRecord]) -> None:
        cls._schemas[name] = record_cls

    @classmethod
    def register_transform(cls, name: str, fn: Callable[[Any], Any]) -> None:
        cls._transforms[name] = fn

    def normalize(
        self,
        source: DataSource,
        raw: dict[str, Any],
        timestamp: str | None = None,
    ) -> SchemaRecord:
        """Normalize raw data into the configured schema."""
        record_cls = self._schemas.get(self.config.schema)
        if record_cls is None:
            raise ValueError(f"Unknown schema: {self.config.schema!r}")

        kwargs: dict[str, Any] = {
            "source": source.config.source_id,
            "timestamp": timestamp or source.now_iso(),
            "raw": dict(raw),
        }

        for schema_field, raw_path in self.config.field_map.items():
            value = self._resolve_path(raw, raw_path)
            if value is None and schema_field in self.config.defaults:
                value = self.config.defaults[schema_field]

            transform_name = self.config.transforms.get(schema_field)
            if transform_name and value is not None:
                value = self._apply_transform(transform_name, value)

            kwargs[schema_field] = value

        return record_cls(**kwargs)

    @staticmethod
    def _resolve_path(data: dict[str, Any], path: str) -> Any:
        """Resolve a dot-separated path in a nested dict."""
        current: Any = data
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _apply_transform(self, name: str, value: Any) -> Any:
        fn = self._transforms.get(name)
        if fn is None:
            log.warning("Unknown transform %r, returning value as-is", name)
            return value
        try:
            return fn(value)
        except Exception as exc:
            log.warning("Transform %r failed for value %r: %s", name, value, exc)
            return value
