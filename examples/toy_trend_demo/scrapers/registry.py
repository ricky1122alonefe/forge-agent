"""Scraper registry: map platform names to scraper instances."""

from __future__ import annotations

from typing import Any, ClassVar

from .base import TrendScraper
from .dewu import DewuSearchScraper
from .mock import MockScraper
from .weibo import WeiboHotScraper
from .xiaohongshu import XiaohongshuSearchScraper


class ScraperRegistry:
    """Central registry for trend scrapers.

    New platforms are registered here once; agents reference them by name.
    """

    _scrapers: ClassVar[dict[str, type[TrendScraper]]] = {
        DewuSearchScraper.platform: DewuSearchScraper,
        WeiboHotScraper.platform: WeiboHotScraper,
        XiaohongshuSearchScraper.platform: XiaohongshuSearchScraper,
        MockScraper.platform: MockScraper,
    }

    @classmethod
    def register(cls, scraper_class: type[TrendScraper]) -> None:
        cls._scrapers[scraper_class.platform] = scraper_class

    @classmethod
    def get(cls, platform: str) -> TrendScraper:
        scraper_class = cls._scrapers.get(platform)
        if scraper_class is None:
            # Graceful fallback to mock so the pipeline never breaks.
            return MockScraper()
        return scraper_class()

    @classmethod
    def list_platforms(cls) -> list[str]:
        return list(cls._scrapers)

    @classmethod
    async def scrape(
        cls, platform: str, keyword: str | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        scraper = cls.get(platform)
        return await scraper.scrape(keyword, **kwargs)
