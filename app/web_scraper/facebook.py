# web_scraper/facebook.py
"""
Facebook profile / page scraper — v6

Fixes vs v5:
  1. "See more" clicking now uses Playwright's get_by_text() which is
     encoding-aware and handles unicode/bold chars in surrounding text.
     Runs up to 3 rounds per scroll to catch nested expansions.
  2. Deduplication is now by text-prefix (first 80 chars, normalised),
     not by hash of text — so if a truncated post was already stored,
     the expanded version REPLACES it instead of being dropped.
  3. Strips trailing "See less" / "… See more" from final text output.
"""

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import Page, ElementHandle

DEBUG = False

_TEXT_SELECTORS = [
    'div[data-ad-comet-preview="message"]',
    'div[data-testid="post_message"]',
    '[data-ad-preview="message"]',
    'div[dir="auto"]',
]

_TS_SELECTORS = [
    "abbr[data-utime]",
    "a[role='link'] abbr",
    "span[data-utime]",
    "a[aria-label] span > span",
]

# Normalise text for dedup key (strip whitespace/punctuation, lowercase)
def _dedup_key(text: str) -> str:
    return re.sub(r'\s+', ' ', text[:80]).strip().lower()


async def scrape_facebook_profile(
    page: Page,
    url: str,
    scroll_iterations: int = 10,
    scroll_delay: float = 3.0,
    page_load_wait: float = 4.0,
) -> list[dict]:
    # Use dict keyed by text-prefix so expanded version overwrites truncated one
    posts: dict[str, dict] = {}   # dedup_key → post dict

    posts_url = url.rstrip("/") + "?sk=posts"
    print(f"    → Navigating: {posts_url}")
    await page.goto(posts_url, wait_until="domcontentloaded", timeout=45_000)
    await asyncio.sleep(page_load_wait)
    await _dismiss_popups(page)

    if DEBUG:
        first = await page.query_selector('div[role="article"]')
        if first:
            html = await first.inner_html()
            print("\n[DEBUG] First article HTML (first 3000 chars):")
            print(html[:3000])
            print("[DEBUG END]\n")

    for i in range(scroll_iterations):
        # Expand ALL "See more" buttons — multiple rounds until none left
        await _expand_all_see_more(page)

        articles = await page.query_selector_all('div[role="article"]')
        for article in articles:
            try:
                if not await _is_real_post(article):
                    continue
                post = await _extract_post(article)
            except Exception:
                continue
            if post:
                key = _dedup_key(post["text"])
                existing = posts.get(key)
                # Always prefer the longer (more complete) text
                if not existing or len(post["text"]) > len(existing["text"]):
                    posts[key] = post

        print(f"    → Scroll {i + 1}/{scroll_iterations}  "
              f"(collected so far: {len(posts)})")

        scrolled = await page.evaluate("""() => {
            const articles = document.querySelectorAll('div[role="article"]');
            if (!articles.length) return false;
            articles[articles.length - 1].scrollIntoView({
                behavior: 'smooth', block: 'end'
            });
            return true;
        }""")
        if not scrolled:
            await page.evaluate("window.scrollBy(0, window.innerHeight * 3)")

        await asyncio.sleep(scroll_delay)
        await _wait_for_spinner(page)

    result = sorted(posts.values(), key=lambda p: p.get("timestamp") or 0, reverse=True)

    print(f"    ✅ Facebook: {len(result)} posts extracted")
    ts_posts = [p for p in result if p.get("posted_at")]
    if ts_posts:
        print(f"       Latest : {ts_posts[0]['posted_at']}")
        print(f"       Oldest : {ts_posts[-1]['posted_at']}")

    return result


# ── Expand "See more" ─────────────────────────────────────────────────────────

async def _expand_all_see_more(page: Page) -> None:
    """
    Click every 'See more' button using Playwright's native text locator
    (encoding-aware, handles bold unicode in surrounding elements).
    Loops up to 3 times to catch any buttons that appear after earlier ones expand.
    """
    for _round in range(3):
        clicked = 0

        # Primary: Playwright get_by_text — exact match, case-insensitive via regex
        try:
            locator = page.get_by_text(re.compile(r'^See more$'))
            n = await locator.count()
            for idx in range(n):
                try:
                    btn = locator.nth(idx)
                    # Only click if it looks like a button/interactive element
                    tag = await btn.evaluate("el => el.tagName.toLowerCase()")
                    role = await btn.evaluate("el => el.getAttribute('role') || ''")
                    if tag in ('div', 'span', 'a') or role == 'button':
                        await btn.click(timeout=1500, force=True)
                        clicked += 1
                        await asyncio.sleep(0.15)
                except Exception:
                    continue
        except Exception:
            pass

        # Fallback: JS textContent scan (catches any missed by Playwright locator)
        js_clicked = await page.evaluate("""() => {
            let n = 0;
            document.querySelectorAll('[role="button"], span, div').forEach(el => {
                if (el.children.length === 0) {
                    const t = (el.textContent || '').trim();
                    if (t === 'See more' || t === 'See More') {
                        el.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                        n++;
                    }
                }
            });
            return n;
        }""")
        clicked += js_clicked

        if clicked == 0:
            break  # no more buttons found — done
        await asyncio.sleep(0.6)  # let DOM re-render after expansion


# ── Other helpers ─────────────────────────────────────────────────────────────

async def _is_real_post(article: ElementHandle) -> bool:
    """
    Returns True only for actual page posts, not comments/replies.
    Real posts always contain a Like/Comment/Share action bar.
    Comments are nested inside posts and never have that bar.
    """
    try:
        result = await article.evaluate("""el => {
            // Action bar is present on real posts only
            const hasLike    = !!el.querySelector('[aria-label="Like"]');
            const hasComment = !!el.querySelector('[aria-label="Leave a comment"]');
            const hasShare   = !!el.querySelector('[aria-label="Send this to friends or post it on your profile."]');
            // Also check generic like/comment button by data-testid
            const hasActions = !!el.querySelector('[data-testid="UFI2ReactionsCount/root"]')
                             || !!el.querySelector('div[aria-label*="Comment"]')
                             || !!el.querySelector('div[aria-label*="Like"]');
            return hasLike || hasComment || hasShare || hasActions;
        }""")
        return bool(result)
    except Exception:
        return False


async def _dismiss_popups(page: Page) -> None:
    for sel in [
        '[data-testid="cookie-policy-manage-dialog-decline-button"]',
        '[aria-label="Decline optional cookies"]',
        'div[role="dialog"] [aria-label="Close"]',
    ]:
        try:
            btn = page.locator(sel)
            if await btn.count() > 0:
                await btn.first.click()
                await asyncio.sleep(0.8)
        except Exception:
            pass


async def _wait_for_spinner(page: Page, timeout_ms: int = 2000) -> None:
    try:
        await page.wait_for_selector(
            '[role="progressbar"]', state="detached", timeout=timeout_ms
        )
    except Exception:
        pass


async def _extract_post(article: ElementHandle) -> Optional[dict]:
    text = await _extract_text(article)
    if not text:
        return None

    # Clean up FB artifacts
    text = re.sub(r'\s*See less\s*$', '', text).strip()
    text = re.sub(r'[\u2026…]\s*See more\s*$', '', text).strip()
    text = re.sub(r'\.\.\.\s*See more\s*$', '', text).strip()

    images: list[str] = []
    try:
        for img in await article.query_selector_all('img[src*="scontent"]'):
            src = await img.get_attribute("src")
            if src and len(src) > 150 and "emoji" not in src and "static" not in src:
                images.append(src)
    except Exception:
        pass
    images = list(dict.fromkeys(images))

    timestamp, posted_at = await _extract_timestamp(article)
    post_id = hashlib.sha256(f"{timestamp or ''}:{text[:150]}".encode()).hexdigest()[:16]

    return {
        "id": post_id,
        "text": text,
        "images": images,
        "timestamp": timestamp,
        "posted_at": posted_at,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


async def _extract_text(article: ElementHandle) -> str:
    for sel in _TEXT_SELECTORS:
        try:
            el = await article.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text and len(text) > 5:
                    return text
        except Exception:
            continue
    return ""


async def _extract_timestamp(article: ElementHandle) -> tuple[Optional[int], Optional[str]]:
    for sel in _TS_SELECTORS:
        try:
            el = await article.query_selector(sel)
            if not el:
                continue
            val = await el.get_attribute("data-utime")
            if val and val.isdigit():
                utime = int(val)
                return utime, datetime.fromtimestamp(utime, tz=timezone.utc).isoformat()
        except Exception:
            continue
    return None, None
