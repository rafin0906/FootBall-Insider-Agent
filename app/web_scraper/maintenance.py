# app/web_scraper/maintenance.py

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.web_scraper.db import ScrapedPost, get_db_session


def delete_old_scraped_posts(hours: int = 7) -> int:
    """
    Delete only scraped posts whose created_at is older than `hours`.

    Example:
    - created 1 hour ago  -> keep
    - created 6 hours ago -> keep
    - created 7+ hours ago -> delete
    """

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    with get_db_session() as db:
        result = db.execute(
            delete(ScrapedPost).where(
                ScrapedPost.created_at < cutoff_time
            )
        )

        deleted_count = result.rowcount or 0

    print(
        f"🧹 Deleted scraped_posts older than {hours} hours: {deleted_count}"
    )

    return deleted_count