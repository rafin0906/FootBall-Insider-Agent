from app.state import AgentState

def revise_post(state: AgentState) -> AgentState:
    print("\n========== REVISE POST ==========")
    print("FEEDBACK TEXT:", state.get("feedback_text"))
    print("FEEDBACK TYPE:", state.get("feedback_type"))

    feedback_type = state.get("feedback_type")

    rejected_urls = list(state.get("rejected_poster_image_urls") or [])

    if feedback_type == "image":
        selected_image = state.get("selected_poster_image") or {}
        selected_url = selected_image.get("url")

        print("CURRENT SELECTED IMAGE URL:", selected_url)

        if selected_url and selected_url not in rejected_urls:
            rejected_urls.append(selected_url)

        print("REJECTED IMAGE URLS:", rejected_urls)

        return {
            **state,
            "rejected_poster_image_urls": rejected_urls,
            "workflow_stage": "processing_feedback",
            "current_step": "revise_post",
            "callback_action": None,
            "approval_action": None,
            "error": None,
        }

    return {
        **state,
        "workflow_stage": "processing_feedback",
        "current_step": "revise_post",
        "callback_action": None,
        "approval_action": None,
        "error": None,
    }


def route_after_revise_post(state: AgentState) -> str:
    feedback_type = state.get("feedback_type")

    if feedback_type == "caption":
        return "revise_caption"

    if feedback_type == "image":
        return "poster_generator"

    if feedback_type == "poster":
        return "revise_poster"

    # general feedback fallback
    return "revise_caption"