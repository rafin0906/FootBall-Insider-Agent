# app/nodes/reset_for_new_request.py

from app.state import AgentState


def reset_for_new_request(state: AgentState) -> AgentState:
    """
    Clears all old post-related state.

    Used when:
    - user starts a new post request
    - user ignores previous approval and sends a new post request

    Important:
    Do NOT use this for feedback.
    Feedback must keep previous news/caption/poster state.
    """

    return {
        **state,

        # fixed intent
        "intent": "order_post",

        # news query
        "news_query": None,
        "news_query_entity": None,
        "news_query_keywords": None,

        # news data
        "raw_news": None,
        "structured_news": None,

        # content
        "caption": None,

        # image layer
        "image_url": None,
        "image_file_id": None,
        "image_path": None,
        "image_verified": None,
        "image_verification_feedback": None,

        # poster
        "poster_image_query": None,
        "poster_image_candidates": None,
        "selected_poster_image": None,
        "poster_design": None,
        "poster_html": None,
        "poster_image_path": None,
        "rejected_poster_image_urls": [],

        # approval / feedback
        "approval_action": None,
        "feedback_text": None,
        "feedback_type": None,

        # final
        "final_caption": None,
        "final_poster_path": None,

        # entry control
        "entry_action": None,
        "callback_action": None,

        # control
        "workflow_stage": "creating_post",
        "current_step": "reset_for_new_request",
        "error": None,
    }