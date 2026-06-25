# app/nodes/clear_current_post.py

from app.state import AgentState


def clear_current_post(state: AgentState) -> AgentState:
    """
    Clears the currently pending post after user rejects/declines it.
    Does not start a new workflow.
    """

    return {
        **state,

        "intent": "order_post",

        "news_query": None,
        "news_query_entity": None,
        "news_query_keywords": None,

        "raw_news": None,
        "structured_news": None,

        "caption": None,

        "image_url": None,
        "image_file_id": None,
        "image_path": None,
        "image_verified": None,
        "image_verification_feedback": None,

        "poster_image_query": None,
        "poster_image_candidates": None,
        "selected_poster_image": None,
        "poster_design": None,
        "poster_html": None,
        "poster_image_path": None,

        "approval_action": None,
        "feedback_text": None,
        "feedback_type": None,

        "final_caption": None,
        "final_poster_path": None,

        "entry_action": None,
        "callback_action": None,

        "workflow_stage": "idle",
        "current_step": "clear_current_post",
        "error": None,
    }