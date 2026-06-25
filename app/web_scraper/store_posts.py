# app/web_scraper/store_posts.py

import hashlib
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.web_scraper.db import ScrapedPost, get_db_session
from app.web_scraper.embedding import create_embedding
from app.web_scraper.llm_enricher import enrich_post_text


def _make_stable_post_id(
    platform: str,
    source_url: str,
    raw_post_id: str,
    raw_text: str,
) -> str:
    """
    Creates stable DB post_id for deduplication across scraper runs.
    """

    raw_key = f"{platform}:{source_url}:{raw_post_id}:{raw_text[:300]}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:32]


def _build_structured_post_content(
    raw_news: str,
    ai_enriched_context: str,
) -> str:
    return f"""RAW NEWS:
{raw_news}

AI_ENRICHED_CONTEXT:
{ai_enriched_context}
""".strip()


def _clean_images(images: Any) -> list[str]:
    if not images:
        return []

    if not isinstance(images, list):
        return []

    cleaned = []

    for img in images:
        if isinstance(img, str) and img.strip():
            cleaned.append(img.strip())

    return list(dict.fromkeys(cleaned))


def save_scraped_output_to_supabase(scraped_output: dict) -> int:
    """
    Takes the exact scraper output dict.

    For every post:
    1. Send only post["text"] to Groq.
    2. Build post_content:
       RAW NEWS: ...
       AI_ENRICHED_CONTEXT: ...
    3. Create embedding from full post_content.
    4. Save post_content, images list, metadata, and embedding to Supabase.

    Important:
    created_at is NOT updated on conflict.
    So created_at means the time when the row was first created.
    Cleanup deletes only rows whose created_at crossed 7 hours.
    """

    saved_count = 0
    sources = scraped_output.get("sources", [])

    with get_db_session() as db:
        for source in sources:
            source_url = source.get("source_url", "")
            platform = source.get("platform", "")
            source_scraped_at = source.get("scraped_at", "")

            posts = source.get("posts", [])

            for post in posts:
                raw_text = (post.get("text") or "").strip()

                if not raw_text:
                    continue

                raw_post_id = post.get("id", "")
                images = _clean_images(post.get("images", []))

                post_id = _make_stable_post_id(
                    platform=platform,
                    source_url=source_url,
                    raw_post_id=raw_post_id,
                    raw_text=raw_text,
                )

                print(f"    → Enriching post: {post_id}")

                enriched_context = enrich_post_text(raw_text)

                structured_content = _build_structured_post_content(
                    raw_news=raw_text,
                    ai_enriched_context=enriched_context,
                )

                print(f"    → Creating embedding: {post_id}")

                embedding = create_embedding(structured_content)

                metadata = {
                    "source_url": source_url,
                    "platform": platform,
                    "source_scraped_at": source_scraped_at,
                    "post_scraped_at": post.get("scraped_at"),
                    "posted_at": post.get("posted_at"),
                    "timestamp": post.get("timestamp"),
                    "raw_post_id": raw_post_id,
                    "knowledgebase_version": "v2_enriched_context_with_pgvector_embedding",
                    "embedding_provider": "huggingface_api",
                    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                    "embedding_dimension": 384,
                }

                table = ScrapedPost.__table__

                stmt = pg_insert(table).values(
                    post_id=post_id,
                    post_content=structured_content,
                    post_img_url=images,
                    metadata=metadata,
                    embedding=embedding,
                )

                stmt = stmt.on_conflict_do_update(
                    index_elements=["post_id"],
                    set_={
                        "post_content": stmt.excluded.post_content,
                        "post_img_url": stmt.excluded.post_img_url,
                        "metadata": stmt.excluded["metadata"],
                        "embedding": stmt.excluded.embedding,
                    },
                )

                db.execute(stmt)
                saved_count += 1

    print(f"    ✅ Supabase saved/upserted posts: {saved_count}")
    return saved_count