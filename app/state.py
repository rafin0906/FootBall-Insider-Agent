# app/state.py

from typing import TypedDict, Optional, List, Dict, Any, Literal


class AgentState(TypedDict):
    # =========================
    # ENTRY DATA
    # =========================
    user_text: str
    chat_id: str

    # =========================
    # ROUTER OUTPUT
    # =========================
    intent: Optional[Literal[
        "order_post"
    ]]

    # =========================
    # NEWS QUERY
    # =========================
    news_query: Optional[str]
    news_query_entity: Optional[str]
    news_query_keywords: Optional[List[str]]

    # =========================
    # NEWS DATA LAYER
    # =========================
    raw_news: Optional[List[Dict[str, Any]]]
    structured_news: Optional[Dict[str, Any]]

    # =========================
    # CONTENT GENERATION
    # =========================
    caption: Optional[str]

    # =========================
    # IMAGE LAYER
    # general image fields
    # =========================
    image_url: Optional[str]
    image_file_id: Optional[str]
    image_path: Optional[str]

    image_verified: Optional[bool]
    image_verification_feedback: Optional[str]

    # =========================
    # POSTER IMAGE SELECTION
    # =========================
    poster_image_query: Optional[str]

    # new / cleaner fields for poster image pipeline
    image_candidates: Optional[List[Dict[str, Any]]]
    selected_image_url: Optional[str]
    selected_image_local_path: Optional[str]

    # POSTER GENERATION
    poster_image_dir: Optional[str]
    poster_image_candidates: Optional[List[Dict[str, Any]]]
    selected_poster_image: Optional[Dict[str, Any]]

    poster_design: Optional[Dict[str, Any]]

    poster_headline_big: Optional[str]
    poster_headline_small: Optional[str]

    poster_html: Optional[str]
    poster_image_path: Optional[str]
    poster_generation_dir: Optional[str]
    poster_css: Optional[str]
    poster_html_path: Optional[str]
    poster_css_path: Optional[str]
    
    rejected_poster_image_urls: Optional[List[str]]
    # =========================
    # HUMAN APPROVAL FLOW
    # =========================
    approval_action: Optional[Literal[
        "approve",
        "reject",
        "feedback",
        "unknown"
    ]]

    entry_action: Optional[Literal[
        "new_post",
        "approve",
        "reject",
        "feedback",
        "unknown"
    ]]

    callback_action: Optional[Literal[
        "approve",
        "reject"
    ]]

    feedback_text: Optional[str]
    feedback_type: Optional[Literal[
        "caption",
        "image",
        "poster",
        "general"
    ]]

    # =========================
    # FINAL OUTPUT
    # =========================
    final_caption: Optional[str]
    final_poster_path: Optional[str]

    # =========================
    # DEBUG / CONTROL
    # =========================
    current_step: Optional[str]

    workflow_stage: Optional[Literal[
        "idle",
        "creating_post",
        "awaiting_approval",
        "processing_feedback",
        "completed"
    ]]


    facebook_publish_result: Optional[Dict[str, Any]]
    facebook_photo_id: Optional[str]
    facebook_post_id: Optional[str]
    error: Optional[str]