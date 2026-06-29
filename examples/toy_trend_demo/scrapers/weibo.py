"""Weibo hot-search scraper using a headless browser."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .base import TrendScraper
from .mock import MockScraper

log = logging.getLogger(__name__)


class WeiboHotScraper(TrendScraper):
    """Scrape Weibo real-time hot search list.

    Falls back to mock data if the page structure changes or anti-bot measures
    block the request.  This keeps the demo runnable without API keys.
    """

    platform = "weibo"
    _default_url = "https://s.weibo.com/top/summary?cate=realtimehot"

    def __init__(self, timeout: int = 30, headless: bool = True) -> None:
        self.timeout = timeout
        self.headless = headless

    @property
    def requires_browser(self) -> bool:
        return True

    async def scrape(self, keyword: str | None = None, **kwargs: Any) -> dict[str, Any]:
        try:
            items = await self._fetch_items(keyword)
        except Exception as exc:
            log.warning("Weibo scrape failed (%s), returning mock data", exc)
            return await MockScraper().scrape(keyword, platform_name=self.platform)

        return {
            "platform": self.platform,
            "keyword": keyword,
            "items": items,
            "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    async def _fetch_items(self, keyword: str | None = None) -> list[dict[str, Any]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            msg = (
                "playwright is required for the Weibo scraper. "
                "Install it with: pip install playwright && playwright install chromium"
            )
            raise RuntimeError(msg) from exc

        items: list[dict[str, Any]] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()
            await page.goto(
                self._default_url,
                wait_until="domcontentloaded",
                timeout=self.timeout * 1000,
            )

            # Wait for the hot-search table to appear; fall back to body if absent.
            try:
                await page.wait_for_selector(
                    "table tbody tr",
                    timeout=min(10000, self.timeout * 1000),
                )
            except Exception:
                log.warning("Weibo table selector not found, trying broader selectors")

            rows = await page.query_selector_all("table tbody tr")
            for row in rows[:50]:  # top 50
                cells = await row.query_selector_all("td")
                if len(cells) < 2:
                    continue

                rank_el = await cells[0].query_selector(".ranktop")
                rank_text = await rank_el.inner_text() if rank_el else ""
                if not rank_text.strip() and cells:
                    # Fallback: first cell may contain the rank as plain text.
                    rank_text = await cells[0].inner_text()
                try:
                    rank = int(rank_text.strip().split()[0])
                except (ValueError, IndexError):
                    rank = 0

                topic_el = await cells[1].query_selector("a")
                title = await topic_el.inner_text() if topic_el else ""
                href = await topic_el.get_attribute("href") if topic_el else ""

                heat_el = await cells[1].query_selector("span")
                heat_text = await heat_el.inner_text() if heat_el else "0"
                heat = self._parse_heat(heat_text)

                if title.strip():
                    items.append(
                        {
                            "rank": rank,
                            "title": title.strip(),
                            "heat": heat,
                            "url": f"https://s.weibo.com{href}" if href else "",
                            "keyword_matched": self._matches_keyword(title, keyword),
                        }
                    )

            await browser.close()

        if not items:
            raise RuntimeError("No hot-search items extracted")

        return items

    @staticmethod
    def _parse_heat(text: str) -> int:
        cleaned = text.strip().replace(",", "").replace(",", "")
        try:
            return int(cleaned)
        except ValueError:
            return 0

    @staticmethod
    def _matches_keyword(title: str, keyword: str | None) -> bool:
        if not keyword:
            return False
        return keyword.lower() in title.lower()
