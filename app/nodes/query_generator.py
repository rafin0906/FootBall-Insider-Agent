# app/nodes/query_generator.py

import os
from typing import List

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.state import AgentState

load_dotenv()


class NewsQueryOutput(BaseModel):
    search_query: str = Field(
        description="A clean football news search query for RAG retrieval."
    )
    main_entity: str = Field(
        description="Main player, club, country, manager, competition, or event."
    )
    keywords: List[str] = Field(
        description="Important football keywords for filtering."
    )


GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing from .env")


llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    api_key=GROQ_API_KEY,
)

structured_llm = llm.with_structured_output(NewsQueryOutput)


SYSTEM_PROMPT = """
You are a football news query generator for a RAG knowledge base.

Input:
- User's raw request.

Your job:
- Create a clean search query that can retrieve the most relevant football news.
- Keep the query specific.
- Include the main entity and event.
- Do not add unrelated details.
- Do not create a caption.
- Do not answer the user.

Examples:

User:
"messi hattrick niye post dao"

Output:
search_query: "Lionel Messi hat trick latest match news"
main_entity: "Lionel Messi"
keywords: ["Messi", "hat trick", "match"]

User:
"brazil probable xi for tomorrow haiti match post"

Output:
search_query: "Brazil probable lineup Haiti match"
main_entity: "Brazil"
keywords: ["Brazil", "Haiti", "probable lineup"]
"""


def query_generator(state: AgentState) -> AgentState:
    user_text = state["user_text"]

    try:
        result = structured_llm.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_text),
            ]
        )

        return {
            **state,
            "news_query": result.search_query,
            "news_query_entity": result.main_entity,
            "news_query_keywords": result.keywords,
            "current_step": "query_generator",
        }

    except Exception as e:
        # fallback so workflow does not crash
        return {
            **state,
            "news_query": user_text,
            "news_query_entity": "",
            "news_query_keywords": [],
            "current_step": "query_generator",
            "error": f"query_generator fallback used: {e}",
        }