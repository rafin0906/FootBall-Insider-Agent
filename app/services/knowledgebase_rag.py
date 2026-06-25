# app/services/knowledgebase_rag.py

import json
from typing import Any

from langchain_core.tools import tool
from sqlalchemy import select

from app.web_scraper.db import ScrapedPost, get_db_session
from app.web_scraper.embedding import create_embedding


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


@tool
def search_football_knowledge_base(query: str, top_k: int = 8) -> str:
    """
    Search the football news knowledge base using pgvector similarity.

    Input:
        query: football news search query
        top_k: number of retrieved posts

    Output:
        JSON string containing retrieved posts.
    """

    query = _safe_text(query)

    if not query:
        return json.dumps(
            {
                "query": query,
                "results": [],
                "error": "Empty query",
            },
            ensure_ascii=False,
        )

    query_embedding = create_embedding(query)

    distance = ScrapedPost.embedding.cosine_distance(query_embedding).label("distance")

    stmt = (
        select(
            ScrapedPost.post_id.label("post_id"),
            ScrapedPost.post_content.label("post_content"),
            ScrapedPost.post_img_url.label("post_img_url"),
            ScrapedPost.metadata_.label("metadata"),
            distance,
        )
        .where(ScrapedPost.embedding.is_not(None))
        .order_by(distance)
        .limit(top_k)
    )

    results: list[dict] = []

    with get_db_session() as db:
        rows = db.execute(stmt).all()

        for row in rows:
            item = row._mapping

            distance_value = float(item["distance"])

            results.append(
                {
                    "post_id": item["post_id"],
                    "post_content": item["post_content"],
                    "post_img_url": item["post_img_url"] or [],
                    "metadata": item["metadata"] or {},
                    "distance": distance_value,
                    "similarity_score": 1 - distance_value,
                }
            )

    return json.dumps(
        {
            "query": query,
            "top_k": top_k,
            "results": results,
        },
        ensure_ascii=False,
    )