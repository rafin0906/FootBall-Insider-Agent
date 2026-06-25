# web_scraper/twitter.py
"""
X / Twitter profile scraper.

Strategy:
  - Navigate to the profile page with a saved Playwright session.
  - Scroll down N times; Twitter renders tweets progressively.
  - For each `article[data-testid="tweet"]`: extract text + pbs.twimg.com images.
  - Upgrade image URLs to `name=large` quality automatically.
  - Deduplicate by SHA-256 of the first 200 chars of tweet text.
"""

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import Page, ElementHandle


async def scrape_twitter_profile(
    page: Page,
    url: str,
    scroll_iterations: int = 10,
    scroll_delay: float = 2.0,
    page_load_wait: float = 3.0,
) -> list[dict]:
    """
    Scrape tweets from an X/Twitter profile URL.
    Returns a list of post dicts  {id, text, images, scraped_at}.
    """
    posts: list[dict] = []
    seen_ids: set[str] = set()

    print(f"    → Navigating: {url}")
    await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    await asyncio.sleep(page_load_wait)

    for i in range(scroll_iterations):
        print(f"    → Scroll {i + 1}/{scroll_iterations}  "
              f"(collected so far: {len(posts)})")

        tweet_els = await page.query_selector_all('article[data-testid="tweet"]')

        for tweet_el in tweet_els:
            try:
                post = await _extract_tweet(tweet_el)
            except Exception:
                continue

            if post and post["id"] not in seen_ids:
                seen_ids.add(post["id"])
                posts.append(post)

        await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        await asyncio.sleep(scroll_delay)

    print(f"    ✅ Twitter: {len(posts)} tweets extracted from {url}")
    return posts


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _extract_tweet(tweet_el: ElementHandle) -> Optional[dict]:
    """Pull text + image URLs out of one tweet article element."""

    # 1. Text
    text = ""
    try:
        text_el = await tweet_el.query_selector('div[data-testid="tweetText"]')
        if text_el:
            text = (await text_el.inner_text()).strip()
    except Exception:
        pass

    if not text:
        return None

    # 2. Images  (Twitter media CDN = pbs.twimg.com/media/...)
    images: list[str] = []
    try:
        img_els = await tweet_el.query_selector_all(
            'img[src*="pbs.twimg.com/media"]'
        )
        for img in img_els:
            src = await img.get_attribute("src")
            if src:
                # Strip existing query params and request large-size JPEG
                base = src.split("?")[0]
                images.append(f"{base}?format=jpg&name=large")
    except Exception:
        pass

    images = list(dict.fromkeys(images))  # deduplicate

    post_id = hashlib.sha256(text[:200].encode()).hexdigest()[:16]

    return {
        "id": post_id,
        "text": text,
        "images": images,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
