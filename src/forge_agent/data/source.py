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
        """Fetch raw data according to source_type."""
        if self.config.source_type == "mock":
            return self.config.mock_payload or {}

        if not self.config.urls:
            return {"error": "no urls configured"}

        url = self.config.urls[0]

        if self.config.source_type == "json_api":
            return await self._fetch_json(url)

        if self.config.source_type == "html":
            return await self._fetch_html(url)

        if self.config.source_type == "rss":
            return await self._fetch_rss(url)

        if self.config.source_type == "custom":
            return await self._fetch_custom(url)

        msg = f"source_type {self.config.source_type!r} not implemented for {self.config.source_id}"
        raise NotImplementedError(msg)

    async def _fetch_json(self, url: str) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient(headers=self.config.headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def _fetch_html(self, url: str) -> dict[str, Any]:
        """Fetch HTML and extract fields via CSS selectors."""
        try:
            from bs4 import BeautifulSoup  # type: ignore[import-not-found]
        except ImportError as exc:
            msg = (
                "HTML DataSource requires 'beautifulsoup4'. "
                "Install with: pip install forge-agent[scraper]"
            )
            raise ImportError(msg) from exc

        import httpx

        async with httpx.AsyncClient(headers=self.config.headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "html.parser")
        extracted: dict[str, Any] = {"url": url, "fields": {}}

        for field_def in self.config.fields:
            name = field_def.get("name")
            selector = field_def.get("selector")
            if not name or not selector:
                continue

            elements = soup.select(selector)
            if not elements:
                extracted["fields"][name] = field_def.get("default")
                continue

            attr = field_def.get("attr")
            transform = field_def.get("transform")
            multiple = field_def.get("multiple", False)

            def _extract(el, attr=attr, transform=transform):
                value = el.get(attr) if attr else el.get_text(strip=True)
                return self._apply_transform(value, transform)

            if multiple:
                extracted["fields"][name] = [_extract(el) for el in elements]
            else:
                extracted["fields"][name] = _extract(elements[0])

        return extracted

    async def _fetch_rss(self, url: str) -> dict[str, Any]:
        """Fetch RSS/Atom feed and parse entries."""
        import httpx

        async with httpx.AsyncClient(headers=self.config.headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            xml = response.text

        try:
            from defusedxml import ElementTree as ElementTree  # type: ignore[import-not-found]
        except ImportError:
            import xml.etree.ElementTree as ElementTree

        root = ElementTree.fromstring(xml)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # Determine root tag and channel
        if root.tag == "rss":
            channel = root.find("channel")
            entries = channel.findall("item") if channel is not None else []
            title = channel.findtext("title", default="") if channel is not None else ""
            link = channel.findtext("link", default="") if channel is not None else ""
        elif root.tag.endswith("feed"):
            title = root.findtext("atom:title", default="", namespaces=ns)
            link_elem = root.find("atom:link", namespaces=ns)
            link = link_elem.get("href", "") if link_elem is not None else ""
            entries = root.findall("atom:entry", namespaces=ns)
        else:
            return {"error": "unsupported feed format", "url": url}

        items = []
        for entry in entries:
            if root.tag == "rss":
                item = {
                    "title": entry.findtext("title", default=""),
                    "link": entry.findtext("link", default=""),
                    "description": entry.findtext("description", default=""),
                    "published": entry.findtext("pubDate", default=""),
                }
            else:
                item = {
                    "title": entry.findtext("atom:title", default="", namespaces=ns),
                    "link": entry.findtext("atom:link", default="", namespaces=ns),
                    "description": entry.findtext("atom:summary", default="", namespaces=ns),
                    "published": entry.findtext("atom:published", default="", namespaces=ns),
                }
            items.append(item)

        return {
            "url": url,
            "title": title,
            "link": link,
            "items": items,
            "count": len(items),
        }

    async def _fetch_custom(self, url: str) -> dict[str, Any]:
        """Call a user-provided async fetcher."""
        fetcher = self.config.mock_payload.get("fetcher") if self.config.mock_payload else None
        if fetcher is None:
            msg = "custom DataSource requires a 'fetcher' callable in mock_payload"
            raise ValueError(msg)
        if not callable(fetcher):
            msg = "custom DataSource 'fetcher' must be callable"
            raise TypeError(msg)
        return await fetcher(url, self.config)

    @staticmethod
    def _apply_transform(value: Any, transform: str | None) -> Any:
        """Apply a simple transform to an extracted value."""
        if value is None or transform is None:
            return value
        try:
            if transform == "strip":
                return str(value).strip()
            if transform == "lower":
                return str(value).lower()
            if transform == "upper":
                return str(value).upper()
            if transform == "int":
                return int(value)
            if transform == "float":
                return float(value)
        except Exception:
            return value
        return value

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
