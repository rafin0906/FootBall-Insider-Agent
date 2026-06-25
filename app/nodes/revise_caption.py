# app/nodes/revise_caption.py

from typing import Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq

from app.state import AgentState


GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"


class RevisedCaptionOutput(BaseModel):
    caption: str = Field(description="Updated Facebook caption")


def revise_caption(state: AgentState) -> AgentState:
    print("\n========== REVISE CAPTION ==========")

    old_caption = state.get("caption") or ""
    feedback_text = state.get("feedback_text") or state.get("user_text") or ""
    news_query = state.get("news_query") or ""
    structured_news = state.get("structured_news") or {}
    raw_news = state.get("raw_news") or []

    llm = ChatGroq(
        model=GROQ_TEXT_MODEL,
        temperature=0.4,
    )

    structured_llm = llm.with_structured_output(RevisedCaptionOutput)

    prompt = f"""
You are a football Facebook caption editor.

Your task:
Revise ONLY the Facebook caption based on the user's feedback.

Important:
- Do NOT change poster image.
- Do NOT ask for a new image.
- Do NOT regenerate poster design.
- Keep the caption factual.
- Use the given news context only.
- Write in clean English.
- Make it suitable for a football Facebook page.
- No markdown.

News query:
{news_query}

Old caption:
{old_caption}

User feedback:
{feedback_text}

Retrieved news context:
{raw_news}

Structured news:
{structured_news}

Return structured output only.
"""

    result = structured_llm.invoke(prompt)

    print("UPDATED CAPTION:", result.caption)

    return {
        **state,
        "caption": result.caption,
        "workflow_stage": "awaiting_approval",
        "current_step": "revise_caption",
        "callback_action": None,
        "approval_action": None,
        "error": None,
    }