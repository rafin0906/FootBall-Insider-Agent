# app/nodes/caption_generator.py

import os
import json
from typing import Any

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from app.state import AgentState

load_dotenv()


GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing from .env")


llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.6,
    api_key=GROQ_API_KEY,
)


SYSTEM_PROMPT = """
You are a professional football Facebook caption writer.

You will receive:
1. Original user request.
2. Generated RAG search query.
3. Retrieved posts from the football knowledge base.

Critical rules:
- Use ONLY retrieved posts that are clearly relevant to the user's request and generated query.
- If a retrieved post is unrelated, ignore it completely.
- Do not mix different unrelated news stories.
- Do not invent facts.
- Do not add scores, clubs, injuries, transfers, or dates unless present in the retrieved data.
- If no retrieved post is clearly relevant, return exactly:
  NOT_ENOUGH_RELEVANT_NEWS
- Caption must be in English.
- Caption should be suitable for a football Facebook page.
- Keep it in engaging, and news-style.
- Do not mention RAG, database, retrieved data, or AI.
"""


def _format_retrieved_posts(posts: list[dict[str, Any]]) -> str:
    formatted = []

    for index, post in enumerate(posts, start=1):
        metadata = post.get("metadata", {}) or {}

        formatted.append(
            {
                "index": index,
                "post_id": post.get("post_id"),
                "similarity_score": post.get("similarity_score"),
                "source_url": metadata.get("source_url"),
                "platform": metadata.get("platform"),
                "post_content": post.get("post_content"),
            }
        )

    return json.dumps(formatted, ensure_ascii=False, indent=2)


def caption_generator(state: AgentState) -> AgentState:
    user_text = state["user_text"]
    news_query = state.get("news_query") or user_text
    retrieved_posts = state.get("raw_news") or []

    print("\n========== CAPTION GENERATOR ==========")
    print("USER TEXT:", user_text)
    print("NEWS QUERY:", news_query)
    print("RETRIEVED COUNT:", len(retrieved_posts))

    if not retrieved_posts:
        return {
            **state,
            "caption": "NOT_ENOUGH_RELEVANT_NEWS",
            "current_step": "caption_generator",
        }

    retrieved_context = _format_retrieved_posts(retrieved_posts)

    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=f"""
Original user request:
{user_text}

Generated RAG search query:
{news_query}

Retrieved knowledge base posts:
{retrieved_context}

Now write the final Facebook caption.
"""
            ),
        ]
    )

    caption = (response.content or "").strip()

    return {
        **state,
        "caption": caption,
        "current_step": "caption_generator",
        "workflow_stage": "awaiting_approval",
    }