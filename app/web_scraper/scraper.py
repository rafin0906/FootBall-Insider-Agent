# web_scraper/scraper.py
"""
Main scraper orchestrator.

- Groups TARGET_URLS by platform.
- Loads the matching Playwright session file.
- Runs the platform-specific extractor.
- Merges all results into a single JSON output file.
- After JSON save, enriches scraped post text with LLM.
- Saves enriched posts into Supabase knowledge base.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright, Browser, BrowserContext

from .config import (
    TARGET_URLS,
    HEADLESS,
    SCROLL_ITERATIONS,
    SCROLL_DELAY,
    PAGE_LOAD_WAIT,
    SESSION_FILES,
    OUTPUT_FILE,
    USER_AGENT,
    VIEWPORT,
)
from .facebook import scrape_facebook_profile
from .twitter import scrape_twitter_profile
from .store_posts import save_scraped_output_to_supabase


# ── Platform detection ────────────────────────────────────────────────────────

def _detect_platform(url: str) -> str:
    if "facebook.com" in url:
        return "facebook"
    if "x.com" in url or "twitter.com" in url:
        return "twitter"
    return "unknown"


def _session_file(url: str) -> Path | None:
    for domain, path in SESSION_FILES.items():
        if domain in url:
            return path
    return None


# ── Browser context factory ───────────────────────────────────────────────────

async def _make_context(browser: Browser, session_path: Path) -> BrowserContext:
    return await browser.new_context(
        storage_state=str(session_path),
        viewport=VIEWPORT,
        user_agent=USER_AGENT,
        java_script_enabled=True,
    )


# ── Core scrape loop ──────────────────────────────────────────────────────────

async def scrape_all() -> dict:
    """
    Scrape every URL in TARGET_URLS.

    Step 1:
        Scrape posts exactly like before.

    Step 2:
        Save raw scraper output into JSON exactly like before.

    Step 3:
        Pass only each post text/content to Groq LLM for enrichment.

    Step 4:
        Store this structure into Supabase:

        post_content:
            RAW NEWS:
            {actual post text}

            AI_ENRICHED_CONTEXT:
            {LLM enriched context}

        post_img_url:
            list of image URLs

        metadata:
            source_url, platform, scraped_at, posted_at, timestamp, raw_post_id
    """

    fb_urls = [u for u in TARGET_URLS if _detect_platform(u) == "facebook"]
    tw_urls = [u for u in TARGET_URLS if _detect_platform(u) == "twitter"]
    unknown = [u for u in TARGET_URLS if _detect_platform(u) == "unknown"]

    if unknown:
        print(f"⚠️  Skipping unsupported URLs: {unknown}")

    all_results: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        # ── Facebook ─────────────────────────────────────────────────────────
        if fb_urls:
            fb_session = _session_file(fb_urls[0])

            if not fb_session or not fb_session.exists():
                print("⚠️  Facebook session not found — run save_session.py first.")

            else:
                print("\n📘  Starting Facebook scrape...")

                ctx = await _make_context(browser, fb_session)
                page = await ctx.new_page()

                for url in fb_urls:
                    print(f"\n  🔗 {url}")

                    try:
                        posts = await scrape_facebook_profile(
                            page,
                            url,
                            scroll_iterations=SCROLL_ITERATIONS,
                            scroll_delay=SCROLL_DELAY,
                            page_load_wait=PAGE_LOAD_WAIT,
                        )

                        all_results.append(
                            _make_source_entry(
                                url=url,
                                platform="facebook",
                                posts=posts,
                            )
                        )

                    except Exception as e:
                        print(f"  ❌ Error scraping {url}: {e}")

                await ctx.close()

        # ── X / Twitter ───────────────────────────────────────────────────────
        if tw_urls:
            tw_session = _session_file(tw_urls[0])

            if not tw_session or not tw_session.exists():
                print("⚠️  Twitter/X session not found — run save_session.py first.")

            else:
                print("\n🐦  Starting X/Twitter scrape...")

                ctx = await _make_context(browser, tw_session)
                page = await ctx.new_page()

                for url in tw_urls:
                    print(f"\n  🔗 {url}")

                    try:
                        posts = await scrape_twitter_profile(
                            page,
                            url,
                            scroll_iterations=SCROLL_ITERATIONS,
                            scroll_delay=SCROLL_DELAY,
                            page_load_wait=PAGE_LOAD_WAIT,
                        )

                        all_results.append(
                            _make_source_entry(
                                url=url,
                                platform="twitter",
                                posts=posts,
                            )
                        )

                    except Exception as e:
                        print(f"  ❌ Error scraping {url}: {e}")

                await ctx.close()

        await browser.close()

    # ── Build output exactly like before ───────────────────────────────────────
    output = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total_sources": len(all_results),
        "total_posts": sum(r["post_count"] for r in all_results),
        "sources": all_results,
    }

    # ── Initial scrape summary ────────────────────────────────────────────────
    print(f"\n{'─' * 55}")
    print("✅  Scraping complete!")
    print(f"   Posts collected : {output['total_posts']}")
    print(f"{'─' * 55}\n")

    # ── LLM enrichment + Supabase save ────────────────────────────────────────
    print("\n🧠  Starting LLM enrichment + Supabase save...")

    saved_count = save_scraped_output_to_supabase(output)

    output["saved_to_supabase"] = saved_count

    # ── Save final JSON after DB save info is added ───────────────────────────
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'─' * 55}")
    print("✅  Knowledge base update complete!")
    print(f"   Posts collected : {output['total_posts']}")
    print(f"   Saved/upserted DB rows : {saved_count}")
    print(f"   Output file     : {OUTPUT_FILE}")
    print(f"{'─' * 55}\n")

    return output

# ── Util ──────────────────────────────────────────────────────────────────────

def _make_source_entry(url: str, platform: str, posts: list[dict]) -> dict:
    return {
        "source_url": url,
        "platform": platform,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "post_count": len(posts),
        "posts": posts,
    }