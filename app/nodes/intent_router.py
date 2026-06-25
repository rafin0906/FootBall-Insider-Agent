# app/nodes/intent_router.py

from app.state import AgentState


def intent_router(state: AgentState) -> AgentState:
    """
    For now there is only one workflow:

        order_post

    This file is kept for future scaling.
    Later you can add:
        - find_viral_post
        - meme_post
        - match_preview
        - transfer_post
    """

    print("\n========== INTENT ROUTER ==========")
    print("FIXED INTENT: order_post")

    return {
        **state,
        "intent": "order_post",
        "current_step": "intent_router",
    }


def route_after_intent(state: AgentState) -> str:
    return "order_post"