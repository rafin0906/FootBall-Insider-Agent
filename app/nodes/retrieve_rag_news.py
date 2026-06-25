# app/nodes/retrieve_rag_news.py

import json

from app.state import AgentState
from app.services.knowledgebase_rag import search_football_knowledge_base


def retrieve_rag_news(state: AgentState) -> AgentState:
    query = state.get("news_query") or state["user_text"]

    print("\n========== RAG RETRIEVAL ==========")
    print("QUERY:", query)

    try:
        tool_result = search_football_knowledge_base.invoke(
            {
                "query": query,
                "top_k": 8,
            }
        )

        parsed = json.loads(tool_result)

        retrieved_posts = parsed.get("results", [])

        print("RETRIEVED POSTS:", len(retrieved_posts))

        return {
            **state,
            "raw_news": retrieved_posts,
            "structured_news": {
                "retrieval_query": query,
                "retrieved_count": len(retrieved_posts),
                "retrieved_posts": retrieved_posts,
            },
            "current_step": "retrieve_rag_news",
        }

    except Exception as e:
        print("RAG RETRIEVAL ERROR:", e)

        return {
            **state,
            "raw_news": [],
            "structured_news": {
                "retrieval_query": query,
                "retrieved_count": 0,
                "retrieved_posts": [],
            },
            "current_step": "retrieve_rag_news",
            "error": str(e),
        }