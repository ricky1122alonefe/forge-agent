"""Web searcher (HTTP-based, pluggable backend).

Default backend: a no-op stub. Replace with Tavily / Bing / SerpAPI / etc.
by subclassing or by injecting a `search_fn`.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from forge_agent.core.capabilities import SearcherProtocol

log = logging.getLogger(__name__)


class WebSearcher(SearcherProtocol):
    """Web searcher with a pluggable async `search_fn`.

    Usage::
        async def my_search(query: str, **kw): ...


        searcher = WebSearcher(search_fn=my_search, name="tavily")
    """

    def __init__(
        self,
        *,
        search_fn: Callable[[str], Awaitable[list[dict[str, Any]]]] | None = None,
        name: str = "noop-web",
    ) -> None:
        self.name = name
        self._fn = search_fn or self._noop

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        return await self._fn(query, **kwargs)

    async def _noop(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        log.debug("WebSearcher[%s]: noop for query=%r", self.name, query)
        return []
