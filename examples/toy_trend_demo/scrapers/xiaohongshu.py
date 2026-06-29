"""Xiaohongshu search scraper using a headless browser."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from .base import TrendScraper
from .mock import MockScraper

log = logging.getLogger(__name__)


class XiaohongshuSearchScraper(TrendScraper):
    """Scrape Xiaohongshu web search results for a keyword.

    XHS aggressively blocks anonymous scraping; this implementation tries a few
    common selectors and falls back to mock data if the page is gated.
    """

    platform = "xiaohongshu"

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
            log.warning("Xiaohongshu scrape failed (%s), returning mock data", exc)
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
                "playwright is required for the Xiaohongshu scraper. "
                "Install it with: pip install playwright && playwright install chromium"
            )
            raise RuntimeError(msg) from exc

        if not keyword:
            keyword = "潮玩"

        query = quote(keyword)
        url = f"https://www.xiaohongshu.com/search_result?keyword={query}&source=web"

        items: list[dict[str, Any]] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout * 1000,
            )

            # XHS often requires login; detect that early.
            login_text = await page.locator("text=/登录/").count()
            if login_text > 0:
                log.warning("Xiaohongshu is requesting login; using mock data")
                await browser.close()
                raise RuntimeError("Login wall detected")

            # Wait for dynamic content; scroll to trigger lazy loading.
            try:
                await page.wait_for_selector(
                    "a[href*='/explore/'], div[class], section[class]",
                    timeout=min(10000, self.timeout * 1000),
                )
            except Exception:
                log.warning("XHS initial selector not found, continuing anyway")
            await page.evaluate("window.scrollBy(0, 800)")
            await page.wait_for_timeout(2000)

            # Common selectors for note cards in XHS web search results.
            selectors = [
                "a[href*='/explore/']",
                "section.note-item a",
                "div.note-item a",
                "div.card a",
                "a.cover",
                "div[class*='note'] a",
            ]
            seen: set[str] = set()
            for selector in selectors:
                cards = await page.query_selector_all(selector)
                for card in cards:
                    if len(items) >= 20:
                        break
                    href = await card.get_attribute("href") or ""
                    if not href or href in seen:
                        continue
                    seen.add(href)

                    title = await card.inner_text()
                    title = title.strip().replace("\n", " ")[:200]

                    # Try to find a like count near the card.
                    likes = 0
                    parent = await card.evaluate("el => el.closest('div')")
                    if parent:
                        like_text = await page.locator("text=/\\d+/").first.inner_text()
                        likes = self._parse_count(like_text)

                    if title:
                        items.append(
                            {
                                "title": title,
                                "url": href
                                if href.startswith("http")
                                else f"https://www.xiaohongshu.com{href}",
                                "likes": likes,
                                "keyword_matched": self._matches_keyword(title, keyword),
                            }
                        )
                if len(items) >= 10:
                    break

            await browser.close()

        if not items:
            raise RuntimeError("No XHS search results extracted")

        return items

    @staticmethod
    def _parse_count(text: str) -> int:
        cleaned = text.strip().replace(",", "").replace("万", "0000")
        try:
            return int(cleaned)
        except ValueError:
            return 0

    @staticmethod
    def _matches_keyword(title: str, keyword: str | None) -> bool:
        if not keyword:
            return False
        return keyword.lower() in title.lower()
