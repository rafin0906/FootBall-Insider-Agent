# web_scraper/save_session.py
"""
Run this script ONCE before using the scraper.

It opens a real (non-headless) browser window so you can log in manually.
After you press Enter, it saves the session (cookies + localStorage) so
the main scraper can reuse it in headless mode — no credentials needed.

Usage:
    python -m app.web_scraper.save_session
    (or just: python save_session.py  from inside the web_scraper folder)
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

SESSION_DIR = Path(__file__).parent / "sessions"
SESSION_DIR.mkdir(exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


async def save_session(platform: str, start_url: str, save_path: Path) -> None:
    print(f"\n{'─'*55}")
    print(f"  Saving session for: {platform}")
    print(f"{'─'*55}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=USER_AGENT,
        )
        page = await context.new_page()
        await page.goto(start_url)

        print(f"\n  ✋ Browser opened at {start_url}")
        print("  → Log in completely (pass 2FA if needed).")
        print("  → Once your feed / home page is visible, come back here.")
        input("\n  Press ENTER when you're fully logged in... ")

        await context.storage_state(path=str(save_path))
        await browser.close()

    print(f"  ✅ Session saved → {save_path}\n")


async def main() -> None:
    print("\n╔══════════════════════════════════════════╗")
    print("║        FB-AGENT  Session Saver           ║")
    print("╚══════════════════════════════════════════╝")
    print("\nWhich platform do you want to save a session for?")
    print("  1 → Facebook")
    print("  2 → X (Twitter)")
    print("  3 → Both")

    choice = input("\nEnter choice (1 / 2 / 3): ").strip()

    if choice not in ("1", "2", "3"):
        print("Invalid choice. Exiting.")
        return

    if choice in ("1", "3"):
        await save_session(
            "Facebook",
            "https://www.facebook.com",
            SESSION_DIR / "facebook_session.json",
        )

    if choice in ("2", "3"):
        await save_session(
            "X (Twitter)",
            "https://x.com",
            SESSION_DIR / "twitter_session.json",
        )

    print("🎉 All done! You can now run the scraper in headless mode.")


if __name__ == "__main__":
    asyncio.run(main())
