# app/nodes/entry_router.py

from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

from app.state import AgentState

load_dotenv()


class EntryRouterOutput(BaseModel):
    action: Literal["feedback", "new_post"] = Field(
        description="""
        Decide whether the user's text is feedback/modification for the existing post,
        or a completely new post request.
        """
    )

    feedback_type: Optional[Literal[
        "caption",
        "image",
        "poster",
        "general"
    ]] = Field(
        default=None,
        description="""
        If action is feedback, classify the feedback type.
        caption = user wants caption text changed
        image = user rejects current background image / wants another image
        poster = user wants poster design changed: colors, fonts, sizes, overlay
        general = vague feedback
        """
    )


llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0
)

entry_router_llm = llm.with_structured_output(EntryRouterOutput)


# =========================================================
# SIMPLE RULE HELPERS
# =========================================================

def _normalize(text: str) -> str:
    return " ".join((text or "").lower().strip().split())


def _contains_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _detect_feedback_type(user_text: str) -> Optional[str]:
    """
    Strong rule-based feedback detector.
    This prevents the LLM from misclassifying obvious feedback.
    """

    text = _normalize(user_text)

    image_phrases = [
        "change image",
        "change the image",
        "change poster image",
        "change background",
        "change bg",
        "use another image",
        "use different image",
        "use another photo",
        "use different photo",
        "select another image",
        "select another photo",
        "choose another image",
        "choose another photo",
        "don't use this image",
        "do not use this image",
        "dont use this image",
        "not this image",
        "remove this image",
        "image is bad",
        "image not good",
        "photo is bad",
        "photo not good",
        "background is bad",
        "bg is bad",
        "poster image is bad",
        "poster image not good",
        "current image is bad",
        "current photo is bad",
    ]

    caption_phrases = [
        "change caption",
        "change the caption",
        "rewrite caption",
        "rewrite the caption",
        "edit caption",
        "edit the caption",
        "fix caption",
        "fix the caption",
        "improve caption",
        "improve the caption",
        "update caption",
        "update the caption",
        "make caption shorter",
        "make the caption shorter",
        "caption shorter",
        "shorter caption",
        "make caption longer",
        "make the caption longer",
        "caption longer",
        "longer caption",
        "caption is bad",
        "caption not good",
        "make it shorter",
        "make it longer",
        "rewrite it",
        "make it professional",
        "make it emotional",
        "add more emotion",
    ]

    poster_phrases = [
        "change poster",
        "change the poster",
        "poster design",
        "design is bad",
        "layout is bad",
        "change layout",
        "change font",
        "font is bad",
        "change color",
        "color is bad",
        "overlay is bad",
        "change overlay",
        "headline is bad",
        "change headline",
        "text position",
        "move text",
        "make poster better",
    ]

    info_phrases = [
        "wrong score",
        "score is wrong",
        "wrong info",
        "information is wrong",
        "fix the score",
        "fix score",
        "wrong player",
        "wrong team",
        "wrong match",
        "incorrect info",
        "incorrect information",
    ]

    poster_phrases = [
        "change color",
        "change the color",
        "change text color",
        "change the text color",
        "text color",
        "color combination",
        "change font",
        "font size",
        "text size",
        "make text bigger",
        "make text smaller",
        "increase text size",
        "decrease text size",
        "overlay",
        "make overlay stronger",
        "text not visible",
        "headline color",
        "headline size",
        "poster design",
    ]

    if _contains_any(text, image_phrases):
        return "image"

    if _contains_any(text, caption_phrases):
        return "caption"

    if _contains_any(text, poster_phrases):
        return "poster"

    if _contains_any(text, info_phrases):
        return "info"

    return None


def _looks_like_new_post_request(user_text: str) -> bool:
    """
    Detects when user is ignoring old approval and asking for a new post topic.
    Example:
    - messi scored against austria arg wins...post
    - make a post about Brazil probable XI
    """

    text = _normalize(user_text)

    feedback_anchor_words = [
        "this image",
        "this photo",
        "current image",
        "current photo",
        "caption",
        "poster design",
        "change",
        "rewrite",
        "shorter",
        "longer",
        "fix",
        "improve",
        "another image",
        "another photo",
    ]

    if _contains_any(text, feedback_anchor_words):
        return False

    football_topic_words = [
        "scored",
        "score",
        "scores",
        "goal",
        "goals",
        "win",
        "wins",
        "won",
        "against",
        "vs",
        "match",
        "hattrick",
        "hat trick",
        "transfer",
        "deal",
        "signing",
        "lineup",
        "xi",
        "preview",
        "reaction",
        "performance",
        "argentina",
        "brazil",
        "messi",
        "ronaldo",
        "barcelona",
        "real madrid",
        "liverpool",
        "chelsea",
        "man city",
        "psg",
    ]

    new_post_phrases = [
        "post about",
        "make a post",
        "create a post",
        "write a post",
        "write about",
        "make post",
        "create post",
    ]

    if _contains_any(text, new_post_phrases):
        return True

    if "post" in text and _contains_any(text, football_topic_words):
        return True

    return False


def entry_router(state: AgentState) -> AgentState:
    workflow_stage = state.get("workflow_stage")
    user_text = state.get("user_text") or ""
    callback_action = state.get("callback_action")

    print("\n========== ENTRY ROUTER ==========")
    print("WORKFLOW_STAGE:", workflow_stage)
    print("USER_TEXT:", user_text)
    print("CALLBACK_ACTION:", callback_action)

    # =========================
    # INLINE KEYBOARD CALLBACK
    # =========================

    if workflow_stage == "awaiting_approval" and callback_action == "approve":
        print("ENTRY ACTION: approve")

        return {
            **state,
            "entry_action": "approve",
            "approval_action": "approve",
            "feedback_text": None,
            "feedback_type": None,
            "current_step": "entry_router",
            "error": None,
        }

    if workflow_stage == "awaiting_approval" and callback_action == "reject":
        print("ENTRY ACTION: reject")

        return {
            **state,
            "entry_action": "reject",
            "approval_action": "reject",
            "feedback_text": None,
            "feedback_type": None,
            "current_step": "entry_router",
            "error": None,
        }

    # =========================
    # NOT WAITING FOR APPROVAL
    # =========================

    if workflow_stage != "awaiting_approval":
        print("ENTRY ACTION: new_post")

        return {
            **state,
            "entry_action": "new_post",
            "approval_action": None,
            "feedback_text": None,
            "feedback_type": None,
            "current_step": "entry_router",
            "error": None,
        }

    # =========================
    # AWAITING APPROVAL + TEXT MESSAGE
    # =========================
    # First use strict rule-based detection.
    # Then use LLM only for ambiguous cases.

    detected_feedback_type = _detect_feedback_type(user_text)

    if detected_feedback_type:
        print("ENTRY ACTION: feedback")
        print("FEEDBACK_TYPE:", detected_feedback_type)

        return {
            **state,
            "entry_action": "feedback",
            "approval_action": "feedback",
            "feedback_text": user_text,
            "feedback_type": detected_feedback_type,
            "workflow_stage": "processing_feedback",
            "current_step": "entry_router",
            "error": None,
        }

    if _looks_like_new_post_request(user_text):
        print("ENTRY ACTION: new_post")

        return {
            **state,
            "entry_action": "new_post",
            "approval_action": None,
            "feedback_text": None,
            "feedback_type": None,
            "current_step": "entry_router",
            "error": None,
        }

    # =========================
    # LLM FALLBACK
    # =========================

    result = entry_router_llm.invoke(
        [
            HumanMessage(
                content=f"""
You are routing a Telegram message for a Facebook football post agent.

The agent has already generated a post and is waiting for user approval.

Now classify the user's new text message.

There are only two possible actions:

1. feedback
Use this only if the user wants to modify the existing generated post.

Feedback examples:
- make the caption shorter
- rewrite the caption
- change the poster image
- don't use this image
- use another image
- change the background photo
- make the headline stronger
- fix the score
- improve the design
- change the font
- move the text

Feedback type rules:
- image: user wants a different image/photo/background
- caption: user wants caption/text rewritten, shorter, longer, emotional, professional
- poster: user wants visual design/layout/font/color/overlay/headline placement changed
- info: user says factual details are wrong
- general: feedback is vague

2. new_post
Use this if the user is asking for a new football post topic, even if the previous post is waiting for approval.

New post examples:
- create a post about Brazil probable XI
- make a post about Messi hattrick
- leo messi scored against austria arg wins...post
- Ronaldo transfer update post
- write about Argentina vs Spain
- today's France match preview

Important:
Do NOT classify a new football topic as feedback just because the workflow is awaiting approval.
If the user mentions a player/team/match/event and asks for a post, it is usually new_post.

Previous generated caption:
{state.get("caption")}

Previous news query:
{state.get("news_query")}

User message:
{user_text}

Return only structured output.
"""
            )
        ]
    )

    if result.action == "feedback":
        feedback_type = result.feedback_type or "general"

        if feedback_type == "none":
            feedback_type = "general"

        print("ENTRY ACTION: feedback")
        print("FEEDBACK_TYPE:", feedback_type)

        return {
            **state,
            "entry_action": "feedback",
            "approval_action": "feedback",
            "feedback_text": user_text,
            "feedback_type": feedback_type,
            "workflow_stage": "processing_feedback",
            "current_step": "entry_router",
            "error": None,
        }

    print("ENTRY ACTION: new_post")

    return {
        **state,
        "entry_action": "new_post",
        "approval_action": None,
        "feedback_text": None,
        "feedback_type": None,
        "current_step": "entry_router",
        "error": None,
    }


def route_after_entry_router(state: AgentState) -> str:
    entry_action = state.get("entry_action")

    if entry_action == "approve":
        return "approval_feedback"

    if entry_action == "reject":
        return "approval_feedback"

    if entry_action == "feedback":
        return "approval_feedback"

    return "reset_for_new_request"