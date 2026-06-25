from app.state import AgentState
from app.services.poster_generation_service import run_poster_image_pipeline


def poster_generator(state: AgentState) -> AgentState:
    print("\n========== POSTER GENERATOR ==========")

    try:
        result = run_poster_image_pipeline(state)

        print("POSTER IMAGE DIR:", result["poster_image_dir"])
        print("SELECTED POSTER IMAGE:", result["selected_poster_image"])
        print("POSTER DESIGN:", result["poster_design"])
        print("HEADLINE BIG:", result["poster_headline_big"])
        print("HEADLINE SMALL:", result["poster_headline_small"])
        print("POSTER HTML PATH:", result["poster_html_path"])
        print("POSTER CSS PATH:", result["poster_css_path"])
        print("FINAL POSTER PATH:", result["poster_image_path"])

        return {
            **state,

            "poster_image_dir": result["poster_image_dir"],
            "poster_generation_dir": result["poster_generation_dir"],

            "poster_image_candidates": result["poster_image_candidates"],
            "selected_poster_image": result["selected_poster_image"],

            "poster_design": result["poster_design"],

            "poster_headline_big": result["poster_headline_big"],
            "poster_headline_small": result["poster_headline_small"],

            "poster_html": result["poster_html"],
            "poster_css": result["poster_css"],

            "poster_html_path": result["poster_html_path"],
            "poster_css_path": result["poster_css_path"],

            "poster_image_path": result["poster_image_path"],
            "final_poster_path": result["final_poster_path"],

            "current_step": "poster_generator",
            "workflow_stage": "awaiting_approval",

            # IMPORTANT: clear previous checkpoint error
            "error": None,
        }

    except Exception as e:
        print("POSTER GENERATOR ERROR:", str(e))

        return {
            **state,
            "current_step": "poster_generator",
            "error": f"poster_generator failed: {str(e)}"
        }