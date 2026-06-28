"""DataSource — declarative configuration for a single raw data source.

A DataSource describes:
    - where to fetch data from (or a mock payload)
    - how to parse it (source_type + fields)
    - what normalizer to apply

The actual fetching/parsing is intentionally thin here; it delegates to the
existing scraper module or a user-provided fetcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DataSourceConfig:
    """Configuration for one external data source."""

    source_id: str
    name: str = ""
    source_type: str = "mock"  # "mock" | "json_api" | "html" | "rss" | "custom"
    urls: list[str] = field(default_factory=list)
    fields: list[dict[str, Any]] = field(default_factory=list)
    normalizer: str = "odds"  # normalizer template id
    field_map: dict[str, str] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    transforms: dict[str, str] = field(default_factory=dict)
    mock_payload: dict[str, Any] | None = None
    headers: dict[str, str] = field(default_factory=dict)
    interval_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name or self.source_id,
            "source_type": self.source_type,
            "urls": list(self.urls),
            "fields": list(self.fields),
            "normalizer": self.normalizer,
            "field_map": dict(self.field_map),
            "defaults": dict(self.defaults),
            "transforms": dict(self.transforms),
            "mock_payload": self.mock_payload,
            "headers": dict(self.headers),
            "interval_seconds": self.interval_seconds,
        }


class DataSource:
    """Runtime handle for a configured data source."""

    def __init__(self, config: DataSourceConfig) -> None:
        self.config = config

    async def fetch(self) -> dict[str, Any]:
        """Fetch raw data according to source_type.

        For now supports ``mock`` directly; other types delegate to scraper.
        """
        if self.config.source_type == "mock":
            return self.config.mock_payload or {}

        if self.config.source_type == "json_api" and self.config.urls:
            return await self._fetch_json(self.config.urls[0])

        msg = f"source_type {self.config.source_type!r} not implemented for {self.config.source_id}"
        raise NotImplementedError(msg)

    async def _fetch_json(self, url: str) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient(headers=self.config.headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
