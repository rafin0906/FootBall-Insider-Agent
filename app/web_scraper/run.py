# web_scraper/run.py
"""
Entry point.

From the project root:
    python -m app.web_scraper.run

Or directly (if you're inside the web_scraper folder):
    python run.py
"""

import asyncio
import sys
from pathlib import Path

# Allow running as a standalone script too
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.web_scraper.scraper import scrape_all

if __name__ == "__main__":
    asyncio.run(scrape_all())
