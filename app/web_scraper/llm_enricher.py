# app/web_scraper/llm_enricher.py

import os
import time

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

load_dotenv()


class EnrichedContextOutput(BaseModel):
    enriched_context: str = Field(
        description="RAG-friendly enriched context generated from the raw social media post text only."
    )


GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_ENRICHMENT_MODEL = "llama-3.3-70b-versatile"

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing from .env")


llm = ChatGroq(
    model=GROQ_ENRICHMENT_MODEL,
    temperature=0,
    api_key=GROQ_API_KEY,
)

structured_llm = llm.with_structured_output(EnrichedContextOutput)


SYSTEM_PROMPT = """
You are a football news RAG enrichment engine.

You will receive ONLY one raw social media post text.

Your job:
- Rewrite the information into a retrieval-friendly context.
- Identify important football entities: players, clubs, managers, competitions, countries, transfer terms, match events.
- Add useful search keywords and alternate names only when clearly implied.
- Keep the meaning faithful to the raw post.
- Do not invent facts, scores, dates, fees, clubs, or claims not present in the post.
- Do not create a Facebook caption.
- Do not add hashtags.
- Do not mention that you are an AI.

Return only the enriched context.
"""


def enrich_post_text(post_text: str, max_retries: int = 2) -> str:
    """
    Sends only the raw post text to the LLM and returns enriched context.
    """

    post_text = (post_text or "").strip()

    if not post_text:
        return ""

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            result = structured_llm.invoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=post_text),
                ]
            )

            return result.enriched_context.strip()

        except Exception as e:
            last_error = e
            time.sleep(1.5)

    raise RuntimeError(f"Failed to enrich post text: {last_error}")