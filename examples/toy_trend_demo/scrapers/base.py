"""Base scraper interface for toy trend intelligence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TrendScraper(ABC):
    """Abstract scraper for a social/commerce platform."""

    platform: str = "base"

    @abstractmethod
    async def scrape(self, keyword: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Return structured trend data for the given keyword.

        The returned dict should be JSON-serializable and contain at least:
            - platform: str
            - keyword: str | None
            - items: list[dict]
            - scraped_at: str (ISO timestamp)
        """

    @property
    def requires_browser(self) -> bool:
        """Whether this scraper needs a headless browser."""
        return False
