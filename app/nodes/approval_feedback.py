# app/nodes/approval_feedback.py

from app.state import AgentState


def approval_feedback(state: AgentState) -> AgentState:
    """
    Handles approve / reject / feedback entry action.

    approve:
        publish existing post

    reject:
        clear existing post state

    feedback:
        keep previous state and revise the existing post
    """

    approval_action = state.get("approval_action")

    print("\n========== APPROVAL FEEDBACK ==========")
    print("APPROVAL_ACTION:", approval_action)

    if approval_action == "approve":
        return {
            **state,
            "workflow_stage": "completed",
            "current_step": "approval_feedback",
        }

    if approval_action == "reject":
        return {
            **state,
            "workflow_stage": "idle",
            "current_step": "approval_feedback",
        }

    if approval_action == "feedback":
        return {
            **state,
            "workflow_stage": "processing_feedback",
            "current_step": "approval_feedback",
        }

    return {
        **state,
        "error": "Unknown approval action",
        "current_step": "approval_feedback",
    }


def route_after_approval_feedback(state: AgentState) -> str:
    approval_action = state.get("approval_action")

    if approval_action == "approve":
        return "publish_post"

    if approval_action == "reject":
        return "clear_current_post"

    if approval_action == "feedback":
        return "revise_post"

    return "end"# app/nodes/approval_feedback.py

from app.state import AgentState


def approval_feedback(state: AgentState) -> AgentState:
    """
    Handles approve / reject / feedback entry action.

    approve:
        publish existing post

    reject:
        clear existing post state

    feedback:
        keep previous state and revise the existing post
    """

    approval_action = state.get("approval_action")

    print("\n========== APPROVAL FEEDBACK ==========")
    print("APPROVAL_ACTION:", approval_action)

    if approval_action == "approve":
        return {
            **state,
            "workflow_stage": "completed",
            "current_step": "approval_feedback",
        }

    if approval_action == "reject":
        return {
            **state,
            "workflow_stage": "idle",
            "current_step": "approval_feedback",
        }

    if approval_action == "feedback":
        return {
            **state,
            "workflow_stage": "processing_feedback",
            "current_step": "approval_feedback",
        }

    return {
        **state,
        "error": "Unknown approval action",
        "current_step": "approval_feedback",
    }


def route_after_approval_feedback(state: AgentState) -> str:
    approval_action = state.get("approval_action")

    if approval_action == "approve":
        return "publish_post"

    if approval_action == "reject":
        return "clear_current_post"

    if approval_action == "feedback":
        return "revise_post"

    return "end"