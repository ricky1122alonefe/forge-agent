"""Mock scraper for platforms without a real implementation yet."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import TrendScraper


class MockScraper(TrendScraper):
    """Return synthetic trend data so the pipeline can run end-to-end."""

    platform = "mock"

    async def scrape(self, keyword: str | None = None, **kwargs: Any) -> dict[str, Any]:
        platform = kwargs.get("platform_name", self.platform)
        seed = keyword or "潮玩"
        return {
            "platform": platform,
            "keyword": seed,
            "items": [
                {
                    "title": f"{platform}: {seed} 热度持续上升",
                    "heat": 1_200_000,
                    "rank": 1,
                    "url": f"https://example.com/{platform}/{seed}",
                },
                {
                    "title": f"{platform}: 二手市场 {seed} 溢价明显",
                    "heat": 980_000,
                    "rank": 2,
                    "url": f"https://example.com/{platform}/{seed}/resale",
                },
                {
                    "title": f"{platform}: 用户对 {seed} 设计评价两极",
                    "heat": 650_000,
                    "rank": 3,
                    "url": f"https://example.com/{platform}/{seed}/review",
                },
            ],
            "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
            "note": "mock data",
        }
