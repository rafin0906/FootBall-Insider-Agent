# web_scraper/config.py
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ─── Add / remove your target URLs here ───────────────────────────────────────
TARGET_URLS = [
    "https://www.facebook.com/fabrizioromanoherewego",
    "https://www.facebook.com/ESPNFC",
    "https://www.facebook.com/BleacherReportFootball",
    "https://www.facebook.com/AFASeleccionEN",
    "https://x.com/WorldCupXtraa",
]

# ─── Scraper behaviour ─────────────────────────────────────────────────────────
HEADLESS         = True   # set False to watch the browser while debugging
SCROLL_ITERATIONS = 2    # how many times to scroll down per page
SCROLL_DELAY      = 2.5   # seconds between each scroll
PAGE_LOAD_WAIT    = 3.0   # seconds to wait after initial page load

# ─── Paths ─────────────────────────────────────────────────────────────────────
SESSION_DIR = BASE_DIR / "sessions"
OUTPUT_DIR  = BASE_DIR / "output"

SESSION_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Playwright storage_state files — one per platform
SESSION_FILES = {
    "facebook.com": SESSION_DIR / "facebook_session.json",
    "x.com":        SESSION_DIR / "twitter_session.json",
    "twitter.com":  SESSION_DIR / "twitter_session.json",
}

OUTPUT_FILE = OUTPUT_DIR / "scraped_posts.json"

# ─── Browser fingerprint ───────────────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1280, "height": 800}
