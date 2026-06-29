"""Dewu search scraper using a headless browser."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from .base import TrendScraper
from .mock import MockScraper

log = logging.getLogger(__name__)


class DewuSearchScraper(TrendScraper):
    """Scrape Dewu (Poizon) web search results for a keyword.

    Dewu product listings include price and sale info; the page structure changes
    frequently, so this implementation falls back to mock data on any failure.
    """

    platform = "dewu"

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
            log.warning("Dewu scrape failed (%s), returning mock data", exc)
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
                "playwright is required for the Dewu scraper. "
                "Install it with: pip install playwright && playwright install chromium"
            )
            raise RuntimeError(msg) from exc

        if not keyword:
            keyword = "潮玩"

        query = quote(keyword)
        url = f"https://www.dewu.com/search?keyword={query}"

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

            # Wait for dynamic search results to render; common class patterns.
            try:
                await page.wait_for_selector(
                    "div[class], section[class]",
                    timeout=min(10000, self.timeout * 1000),
                )
            except Exception:
                log.warning("Dewu initial selector not found, continuing anyway")

            # Scroll a bit to trigger lazy loading.
            await page.evaluate("window.scrollBy(0, 800)")
            await page.wait_for_timeout(2000)

            # Try a broad set of selectors for product links.
            selectors = [
                "a[href*='/product/']",
                "a[href*='/router/']",
                "a[href^='/product/']",
                "a[href^='/router/']",
                "div[class*='product'] a",
                "div[class*='item'] a",
                "div[class*='card'] a",
                "section a",
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

                    # Extract numeric price from the card text if possible.
                    price = self._extract_price(title)
                    sales = self._extract_sales(title)

                    if title and price > 0:
                        items.append(
                            {
                                "title": title,
                                "url": href
                                if href.startswith("http")
                                else f"https://www.dewu.com{href}",
                                "price": price,
                                "sales": sales,
                                "keyword_matched": self._matches_keyword(title, keyword),
                            }
                        )
                if len(items) >= 10:
                    break

            await browser.close()

        if not items:
            raise RuntimeError("No Dewu search results extracted")

        return items

    @staticmethod
    def _extract_price(text: str) -> int:
        matches = re.findall(r"[¥￥](\d{1,6}(?:\.\d{1,2})?)", text)
        if not matches:
            return 0
        return int(float(matches[0]))

    @staticmethod
    def _extract_sales(text: str) -> int:
        # Common patterns: "已售 1.2万", "销量 999", " sold 1k+"
        match = re.search(r"(?:已售|销量|sold)[\s:：]*(\d+(?:\.\d+)?)\s*万?", text, re.IGNORECASE)
        if not match:
            return 0
        value = float(match.group(1))
        if "万" in text[match.start() : match.end() + 5]:
            value *= 10000
        return int(value)

    @staticmethod
    def _matches_keyword(title: str, keyword: str | None) -> bool:
        if not keyword:
            return False
        return keyword.lower() in title.lower()
