# app/web_scraper/telegram_notify.py

import os
from datetime import datetime, timezone
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_NOTIFY_CHAT_ID = os.getenv("TELEGRAM_NOTIFY_CHAT_ID")


MAX_TELEGRAM_MESSAGE_LENGTH = 3900


def _shorten(text: str, limit: int = 220) -> str:
    text = " ".join((text or "").split())

    if len(text) <= limit:
        return text

    return text[: limit - 3] + "..."


def _split_message(text: str, limit: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> list[str]:
    chunks = []

    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)

        if split_at == -1:
            split_at = limit

        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()

    if text:
        chunks.append(text)

    return chunks


def send_telegram_message(text: str) -> None:
    """
    Sends a plain Telegram message to your notify chat.
    """

    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ TELEGRAM_BOT_TOKEN missing. Notification skipped.")
        return

    if not TELEGRAM_NOTIFY_CHAT_ID:
        print("⚠️ TELEGRAM_NOTIFY_CHAT_ID missing. Notification skipped.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    for chunk in _split_message(text):
        response = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_NOTIFY_CHAT_ID,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )

        if not response.ok:
            print("❌ Telegram notify failed:", response.text)
        else:
            print("✅ Telegram notification sent.")


def format_scrape_report(scraped_output: dict[str, Any], max_posts: int = 12) -> str:
    """
    Creates a Telegram-friendly report from scraper output.

    Expected structure:
    {
        "sources": [
            {
                "source_url": "...",
                "platform": "facebook/x",
                "posts": [
                    {
                        "text": "...",
                        "images": [...]
                    }
                ]
            }
        ]
    }
    """

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    sources = scraped_output.get("sources", []) if scraped_output else []

    total_sources = len(sources)
    total_posts = 0

    lines = [
        "📰 <b>FB Agent Scraper Report</b>",
        f"⏰ <b>Time:</b> {now}",
        "",
    ]

    collected_posts = []

    for source in sources:
        platform = source.get("platform", "unknown")
        source_url = source.get("source_url", "")
        posts = source.get("posts", []) or []

        total_posts += len(posts)

        for post in posts:
            collected_posts.append(
                {
                    "platform": platform,
                    "source_url": source_url,
                    "text": post.get("text", ""),
                    "images": post.get("images", []) or [],
                    "posted_at": post.get("posted_at"),
                    "timestamp": post.get("timestamp"),
                }
            )

    lines.extend(
        [
            f"📌 <b>Sources scraped:</b> {total_sources}",
            f"🧾 <b>Total posts found:</b> {total_posts}",
            "",
        ]
    )

    if not collected_posts:
        lines.append("No posts found in this scraper run.")
        return "\n".join(lines)

    lines.append(f"🔥 <b>Latest scraped posts</b> — showing top {min(max_posts, len(collected_posts))}")
    lines.append("")

    for idx, post in enumerate(collected_posts[:max_posts], start=1):
        text = _shorten(post["text"], limit=260)
        platform = post["platform"]
        image_count = len(post["images"])
        source_url = post["source_url"]

        lines.append(f"<b>{idx}. [{platform}]</b>")
        lines.append(text)

        if image_count:
            lines.append(f"🖼 Images: {image_count}")

        if source_url:
            lines.append(f"🔗 Source: {source_url}")

        lines.append("")

    if len(collected_posts) > max_posts:
        lines.append(f"Plus {len(collected_posts) - max_posts} more posts saved to Supabase.")

    return "\n".join(lines)


def send_scrape_report(scraped_output: dict[str, Any]) -> None:
    report = format_scrape_report(scraped_output)
    send_telegram_message(report)