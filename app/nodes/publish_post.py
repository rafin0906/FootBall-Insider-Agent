# app/nodes/publish_post.py

import os
from pathlib import Path
from typing import Dict, Any

import requests
from dotenv import load_dotenv

from app.state import AgentState

load_dotenv()


def _get_facebook_config() -> Dict[str, str]:
    page_id = os.getenv("FACEBOOK_PAGE_ID")
    page_access_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
    graph_version = os.getenv("FACEBOOK_GRAPH_VERSION", "v23.0")

    if not page_id:
        raise ValueError("FACEBOOK_PAGE_ID is missing from .env")

    if not page_access_token:
        raise ValueError("FACEBOOK_PAGE_ACCESS_TOKEN is missing from .env")

    return {
        "page_id": page_id,
        "page_access_token": page_access_token,
        "graph_version": graph_version,
    }


def publish_photo_to_facebook_page(
    image_path: str,
    caption: str,
) -> Dict[str, Any]:
    """
    Publishes the final poster image + caption to a Facebook Page.

    Uses:
    POST /{PAGE_ID}/photos

    This creates a photo post on the Page.
    """

    config = _get_facebook_config()

    page_id = config["page_id"]
    page_access_token = config["page_access_token"]
    graph_version = config["graph_version"]

    image_file = Path(image_path)

    if not image_file.exists():
        raise FileNotFoundError(f"Poster image not found: {image_path}")

    url = f"https://graph.facebook.com/{graph_version}/{page_id}/photos"

    data = {
        "caption": caption or "",
        "published": "true",
        "access_token": page_access_token,
    }

    with open(image_file, "rb") as f:
        files = {
            "source": (
                image_file.name,
                f,
                "image/png",
            )
        }

        response = requests.post(
            url,
            data=data,
            files=files,
            timeout=60,
        )

    try:
        result = response.json()
    except Exception:
        result = {
            "raw_response": response.text,
        }

    if not response.ok:
        raise RuntimeError(
            f"Facebook publish failed. "
            f"Status: {response.status_code}. Response: {result}"
        )

    return result


def publish_post(state: AgentState) -> AgentState:
    print("\n========== PUBLISH POST ==========")

    caption = state.get("caption") or ""
    poster_path = (
        state.get("final_poster_path")
        or state.get("poster_image_path")
    )

    print("POSTER PATH:", poster_path)
    print("CAPTION:", caption)

    if not poster_path:
        return {
            **state,
            "workflow_stage": "awaiting_approval",
            "current_step": "publish_post",
            "error": "No poster image path found for publishing.",
        }

    if not caption:
        return {
            **state,
            "workflow_stage": "awaiting_approval",
            "current_step": "publish_post",
            "error": "No caption found for publishing.",
        }

    try:
        fb_result = publish_photo_to_facebook_page(
            image_path=poster_path,
            caption=caption,
        )

        print("FACEBOOK PUBLISH RESULT:", fb_result)

        return {
            **state,

            "facebook_publish_result": fb_result,
            "facebook_photo_id": fb_result.get("id"),
            "facebook_post_id": fb_result.get("post_id"),

            "workflow_stage": "completed",
            "current_step": "publish_post",

            "approval_action": None,
            "entry_action": None,
            "callback_action": None,
            "feedback_text": None,
            "feedback_type": None,

            "error": None,
        }

    except Exception as e:
        print("FACEBOOK PUBLISH ERROR:", str(e))

        return {
            **state,
            "workflow_stage": "awaiting_approval",
            "current_step": "publish_post",
            "error": f"publish_post failed: {str(e)}",
        }