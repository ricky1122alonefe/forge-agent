"""Tests for TavilySearch backend."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge_agent.search.tavily import TavilySearch, TavilySearcher


def test_tavily_search_requires_package() -> None:
    """TavilySearch should raise ImportError when tavily-python is not installed."""
    # Force the tavily import inside __init__ to fail.
    with (
        patch.dict("sys.modules", {"tavily": None}),
        pytest.raises(ImportError, match="TavilySearch requires"),
    ):
        TavilySearch(api_key="fake")


def test_alias() -> None:
    """TavilySearcher should be an alias for TavilySearch."""
    assert TavilySearcher is TavilySearch


@pytest.mark.anyio()
async def test_search_normalizes_results() -> None:
    """Results from Tavily client should be normalized to the standard schema."""
    fake_client = MagicMock()
    fake_client.search = AsyncMock(
        return_value={
            "answer": "Arsenal won.",
            "results": [
                {
                    "title": "Match Report",
                    "url": "https://example.com/report",
                    "source": "example",
                    "content": "Arsenal beat Liverpool 2-1.",
                    "published_date": "2026-06-28",
                    "score": 0.95,
                },
            ],
        }
    )

    searcher = TavilySearch.__new__(TavilySearch)
    searcher._client = fake_client
    searcher._search_depth = "basic"
    searcher._include_answer = True
    searcher._include_raw_content = False

    results = await searcher.search("Arsenal vs Liverpool", max_results=5)

    assert len(results) == 2
    assert results[0]["title"] == "Tavily Answer"
    assert results[0]["snippet"] == "Arsenal won."
    assert results[1]["title"] == "Match Report"
    assert results[1]["url"] == "https://example.com/report"
    assert results[1]["snippet"] == "Arsenal beat Liverpool 2-1."
    assert results[1]["score"] == 0.95
