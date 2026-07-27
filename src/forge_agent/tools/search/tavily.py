"""Tavily-backed web search implementation.

This is an optional capability; install with ``pip install forge-agent[search]``
or ``pip install tavily-python httpx``.
"""

from __future__ import annotations

import os
from typing import Any

from forge_agent.core.capabilities import SearcherProtocol


class TavilySearch(SearcherProtocol):
    """Tavily web search backend.

    Usage::

        searcher = TavilySearch(api_key=os.getenv("TAVILY_API_KEY"))
        results = await searcher.search("Arsenal vs Liverpool news", max_results=5)
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        search_depth: str = "basic",
        include_answer: bool = True,
        include_raw_content: bool = False,
    ) -> None:
        self._api_key = api_key or os.getenv("TAVILY_API_KEY")
        self._search_depth = search_depth
        self._include_answer = include_answer
        self._include_raw_content = include_raw_content

        try:
            from tavily import AsyncTavilyClient  # type: ignore[import-not-found]
        except ImportError as exc:
            msg = (
                "TavilySearch requires 'tavily-python'. "
                "Install with: pip install forge-agent[search]"
            )
            raise ImportError(msg) from exc
        self._client: Any = AsyncTavilyClient(api_key=self._api_key or "")

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Execute a Tavily search and normalize results."""
        max_results = kwargs.get("max_results", 5)
        response = await self._client.search(
            query=query,
            max_results=max_results,
            search_depth=self._search_depth,
            include_answer=self._include_answer,
            include_raw_content=self._include_raw_content,
        )

        answer = response.get("answer", "")
        raw_results = response.get("results", [])
        normalized: list[dict[str, Any]] = []
        for item in raw_results:
            normalized.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", "tavily"),
                    "snippet": item.get("content", ""),
                    "published_at": item.get("published_date", ""),
                    "score": item.get("score", 0.0),
                    "raw": item,
                }
            )

        if answer and not any(r.get("snippet") == answer for r in normalized):
            normalized.insert(
                0,
                {
                    "title": "Tavily Answer",
                    "url": "",
                    "source": "tavily",
                    "snippet": answer,
                    "published_at": "",
                    "score": 1.0,
                },
            )

        return normalized


# Backwards-compatible alias for code that imports the class with a
# slightly different name (older generator templates / docs).
TavilySearcher = TavilySearch
