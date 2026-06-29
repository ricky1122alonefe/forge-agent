"""Tests for DataSource fetchers."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge_agent.data.source import DataSource, DataSourceConfig


@pytest.fixture
def mock_httpx():
    """Patch httpx.AsyncClient so network calls are never made."""
    response = MagicMock()
    response.raise_for_status = MagicMock()

    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=client):
        yield response


@pytest.mark.anyio
async def test_fetch_json(mock_httpx: AsyncMock) -> None:
    """JSON API source should return parsed JSON."""
    mock_httpx.json.return_value = {"home": "Arsenal", "away": "Liverpool"}

    config = DataSourceConfig(
        source_id="test.json",
        source_type="json_api",
        urls=["https://api.example.com/match"],
    )
    source = DataSource(config)
    result = await source.fetch()

    assert result["home"] == "Arsenal"
    assert result["away"] == "Liverpool"


@pytest.mark.anyio
async def test_fetch_html(mock_httpx: AsyncMock) -> None:
    """HTML source should extract fields via CSS selectors."""
    pytest.importorskip("bs4", reason="beautifulsoup4 not installed")

    mock_httpx.text = """
    <html>
        <body>
            <h1 class="title">Arsenal vs Liverpool</h1>
            <span class="odds">1.95</span>
            <a class="link" href="/match/123">Details</a>
        </body>
    </html>
    """

    config = DataSourceConfig(
        source_id="test.html",
        source_type="html",
        urls=["https://example.com/match"],
        fields=[
            {"name": "title", "selector": "h1.title"},
            {"name": "odds", "selector": "span.odds", "transform": "float"},
            {"name": "link", "selector": "a.link", "attr": "href"},
            {"name": "missing", "selector": "span.missing", "default": "n/a"},
        ],
    )
    source = DataSource(config)
    result = await source.fetch()

    assert result["fields"]["title"] == "Arsenal vs Liverpool"
    assert result["fields"]["odds"] == 1.95
    assert result["fields"]["link"] == "/match/123"
    assert result["fields"]["missing"] == "n/a"


@pytest.mark.anyio
async def test_fetch_rss(mock_httpx: AsyncMock) -> None:
    """RSS source should parse feed items."""
    mock_httpx.text = """<?xml version="1.0"?>
    <rss version="2.0">
        <channel>
            <title>Football News</title>
            <link>https://example.com</link>
            <item>
                <title>Arsenal injury update</title>
                <link>https://example.com/1</link>
                <description>Saka is fit.</description>
                <pubDate>Mon, 29 Jun 2026 10:00:00 GMT</pubDate>
            </item>
            <item>
                <title>Liverpool lineup</title>
                <link>https://example.com/2</link>
                <description>Salah starts.</description>
            </item>
        </channel>
    </rss>
    """

    config = DataSourceConfig(
        source_id="test.rss",
        source_type="rss",
        urls=["https://example.com/feed.xml"],
    )
    source = DataSource(config)
    result = await source.fetch()

    assert result["title"] == "Football News"
    assert result["link"] == "https://example.com"
    assert result["count"] == 2
    assert result["items"][0]["title"] == "Arsenal injury update"
    assert result["items"][1]["title"] == "Liverpool lineup"


@pytest.mark.anyio
async def test_fetch_custom() -> None:
    """Custom source should call the provided fetcher."""

    async def fetcher(url: str, config: DataSourceConfig) -> dict[str, Any]:
        return {"url": url, "source_id": config.source_id}

    config = DataSourceConfig(
        source_id="test.custom",
        source_type="custom",
        urls=["https://example.com/custom"],
        mock_payload={"fetcher": fetcher},
    )
    source = DataSource(config)
    result = await source.fetch()

    assert result["url"] == "https://example.com/custom"
    assert result["source_id"] == "test.custom"


@pytest.mark.anyio
async def test_fetch_mock() -> None:
    """Mock source should return the configured payload."""
    config = DataSourceConfig(
        source_id="test.mock",
        source_type="mock",
        mock_payload={"data": "hello"},
    )
    source = DataSource(config)
    result = await source.fetch()
    assert result["data"] == "hello"


@pytest.mark.anyio
async def test_fetch_no_urls() -> None:
    """Fetching a non-mock source with no URLs should report an error."""
    config = DataSourceConfig(source_id="test.empty", source_type="json_api")
    source = DataSource(config)
    result = await source.fetch()
    assert result["error"] == "no urls configured"
