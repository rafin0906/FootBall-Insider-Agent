# app/agent.py

import os

from langgraph.graph import StateGraph, START, END

from dotenv import load_dotenv
from .state import AgentState

# Nodes
from .nodes.entry_router import entry_router, route_after_entry_router
from .nodes.reset_for_new_request import reset_for_new_request
from .nodes.approval_feedback import approval_feedback, route_after_approval_feedback
from .nodes.clear_current_post import clear_current_post
from .nodes.intent_router import intent_router, route_after_intent

from .nodes.query_generator import query_generator
from .nodes.retrieve_rag_news import retrieve_rag_news
from .nodes.caption_generator import caption_generator
from .nodes.poster_generator import poster_generator
from .nodes.revise_caption import revise_caption
from .nodes.revise_poster import revise_poster
from .nodes.revise_post import revise_post, route_after_revise_post
from .nodes.publish_post import publish_post

# Checkpointer
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection


load_dotenv()


# =====================================
# CHECKPOINTER
# =====================================

DB_URI = os.getenv("DATABASE_URL")

if not DB_URI:
    raise RuntimeError("DATABASE_URL is missing from .env")


conn = Connection.connect(
    DB_URI,
    autocommit=True,
)

checkpointer = PostgresSaver(conn)

# Run this once when DB/checkpoint tables are not created yet.
# If tables already exist, you can keep it or remove it.
checkpointer.setup()


# =====================================
# GRAPH
# =====================================

builder = StateGraph(AgentState)

builder.add_node("entry_router", entry_router)
builder.add_node("reset_for_new_request", reset_for_new_request)
builder.add_node("intent_router", intent_router)

builder.add_node("approval_feedback", approval_feedback)
builder.add_node("clear_current_post", clear_current_post)
builder.add_node("publish_post", publish_post)
builder.add_node("revise_post", revise_post)

builder.add_node("query_generator", query_generator)
builder.add_node("retrieve_rag_news", retrieve_rag_news)
builder.add_node("caption_generator", caption_generator)
builder.add_node("poster_generator", poster_generator)
builder.add_node("revise_caption", revise_caption)
builder.add_node("revise_poster", revise_poster)

builder.add_edge(START, "entry_router")

builder.add_conditional_edges(
    "entry_router",
    route_after_entry_router,
    {
        "reset_for_new_request": "reset_for_new_request",
        "approval_feedback": "approval_feedback",
    }
)

# New post flow
builder.add_edge("reset_for_new_request", "intent_router")

builder.add_conditional_edges(
    "intent_router",
    route_after_intent,
    {
        "order_post": "query_generator",
    }
)

builder.add_edge("query_generator", "retrieve_rag_news")
builder.add_edge("retrieve_rag_news", "caption_generator")
builder.add_edge("caption_generator", "poster_generator")
builder.add_edge("poster_generator", END)

# Approval / feedback flow
builder.add_conditional_edges(
    "approval_feedback",
    route_after_approval_feedback,
    {
        "publish_post": "publish_post",
        "clear_current_post": "clear_current_post",
        "revise_post": "revise_post",
        "end": END,
    }
)

builder.add_edge("publish_post", END)
builder.add_edge("clear_current_post", END)

builder.add_conditional_edges(
    "revise_post",
    route_after_revise_post,
    {
        "revise_caption": "revise_caption",
        "poster_generator": "poster_generator",
        "revise_poster": "revise_poster",
    }
)

builder.add_edge("revise_caption", END)
builder.add_edge("revise_poster", END)



graph = builder.compile(checkpointer=checkpointer)


# =====================================
# TELEGRAM CALLER
# =====================================

async def run_langgraph_agent(
    user_text: str,
    chat_id: str,
    callback_action: str | None = None,
) -> dict:
    config = {
        "configurable": {
            "thread_id": str(chat_id),
        }
    }

    result = graph.invoke(
        {
            "user_text": user_text,
            "chat_id": str(chat_id),
            "callback_action": callback_action,
        },
        config=config,
    )

    print("USER TEXT:", user_text)
    print("CALLBACK ACTION:", callback_action)
    print("ENTRY ACTION:", result.get("entry_action"))
    print("APPROVAL ACTION:", result.get("approval_action"))
    print("INTENT:", result.get("intent"))
    print("CURRENT STEP:", result.get("current_step"))
    print("WORKFLOW STAGE:", result.get("workflow_stage"))
    print("NEWS QUERY:", result.get("news_query"))
    print("RETRIEVED COUNT:", len(result.get("raw_news") or []))

    if result.get("error"):
        return {
            "type": "message",
            "text": f"Workflow error: {result['error']}",
            "image_path": None,
            "needs_approval": False,
        }

    if result.get("workflow_stage") == "completed":
        fb_post_id = result.get("facebook_post_id")
        fb_photo_id = result.get("facebook_photo_id")

        text = "Post published successfully."

        if fb_post_id:
            text += f"\nFacebook post ID: {fb_post_id}"
        elif fb_photo_id:
            text += f"\nFacebook photo ID: {fb_photo_id}"

        return {
            "type": "message",
            "text": text,
            "image_path": None,
            "needs_approval": False,
        }

    if result.get("workflow_stage") == "idle":
        return {
            "type": "message",
            "text": "Post cancelled.",
            "image_path": None,
            "needs_approval": False,
        }

    poster_path = result.get("final_poster_path") or result.get("poster_image_path")
    caption = result.get("caption")

    if poster_path and caption:
        return {
            "type": "approval",
            "text": caption,
            "image_path": poster_path,
            "needs_approval": True,
        }

    if caption:
        return {
            "type": "message",
            "text": caption,
            "image_path": None,
            "needs_approval": False,
        }

    return {
        "type": "message",
        "text": "Workflow completed.",
        "image_path": None,
        "needs_approval": False,
    }