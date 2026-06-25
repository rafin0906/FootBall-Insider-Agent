# app/web_scraper/run.py

"""
Entry point.

From the project root:
    python -m app.web_scraper.run

Or directly:
    python run.py
"""

import asyncio
import sys
from pathlib import Path

# Allow running as a standalone script too
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.web_scraper.scraper import scrape_all
from app.web_scraper.maintenance import delete_old_scraped_posts
from app.web_scraper.telegram_notify import send_scrape_report


async def main() -> None:
    print("\n========== SCRAPER JOB STARTED ==========")

    print("========== CLEANUP BEFORE SCRAPING ==========")
    delete_old_scraped_posts(hours=7)

    print("========== RUNNING SCRAPER ==========")
    scraped_output = await scrape_all()

    print("========== SENDING TELEGRAM SCRAPE REPORT ==========")
    if scraped_output:
        send_scrape_report(scraped_output)
    else:
        print("⚠️ scrape_all() returned nothing. Telegram report skipped.")

    print("========== CLEANUP AFTER SCRAPING ==========")
    delete_old_scraped_posts(hours=7)

    print("========== SCRAPER JOB FINISHED ==========\n")


if __name__ == "__main__":
    asyncio.run(main())