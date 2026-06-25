# app/nodes/revise_poster.py

from typing import Dict, Any, Optional, Literal
import os
import json
from groq import Groq
from pydantic import BaseModel, Field

from app.state import AgentState

from app.services.poster_generation_service import (
    VISION_MODEL,
    encode_image_to_data_url,
    prepare_poster_assets,
    generate_poster_html_css,
    save_poster_files,
    render_poster_image,
    generate_category_label,
    _default_poster_decision,
)


class PosterRevisionOutput(BaseModel):
    selected: bool = Field(default=True)
    rejection_reason: Optional[str] = None

    overlay_color: str = Field(default="#071225")
    headline_big_color: str = Field(default="#ffffff")
    headline_small_color: str = Field(default="#57d8ff")

    font_family: Literal[
        "League Spartan",
        "Oswald",
        "Bebas Neue",
        "Montserrat"
    ] = "Montserrat"

    headline_big_font_size: int = Field(default=86)
    headline_small_font_size: int = Field(default=56)

    headline_big: str = Field(
        description="Updated big headline line"
    )

    headline_small: str = Field(
        description="Updated smaller headline line"
    )


def _clean_headline(text: str) -> str:
    text = (text or "").strip()

    # Fix common Cyrillic lookalike issue
    text = text.replace("М", "M")
    text = text.replace("е", "e")
    text = text.replace("і", "i")
    text = text.replace("а", "a")
    text = text.replace("о", "o")

    return text


def revise_poster_design_with_groq(
    current_poster_path: str,
    current_design: Dict[str, Any],
    feedback_text: str,
    news_query: Optional[str],
    caption: Optional[str],
    headline_big: Optional[str],
    headline_small: Optional[str],
    candidate_context: Optional[str],
) -> Dict[str, Any]:
    """
    Uses Groq Vision to look at the CURRENT GENERATED POSTER
    and revise poster design + poster headline text.

    It does not change:
    - background image
    - caption
    - news meaning
    """

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing from .env")

    client = Groq(api_key=api_key)

    image_data_url = encode_image_to_data_url(current_poster_path)

    prompt = f"""
You are a visual poster design reviewer for an automated football news card system.

You are looking at the CURRENT GENERATED POSTER IMAGE.

Your task:
Revise the poster based on the user's feedback.

You may update:
- overlay_color
- headline_big_color
- headline_small_color
- font_family
- headline_big_font_size
- headline_small_font_size
- headline_big
- headline_small

Do NOT change:
- background image
- caption
- news meaning
- player/team/event

News context:
News query: {news_query or ""}
Caption: {caption or ""}
Retrieved raw chunk connected to the selected image:
{candidate_context or ""}

Current poster headline:
Big headline: {headline_big or ""}
Small headline: {headline_small or ""}

Current poster design:
{json.dumps(current_design, ensure_ascii=False, indent=2)}

User feedback:
{feedback_text or ""}

Design goal:
- professional sports editorial card
- high contrast
- strong readable text
- modern football poster
- visible cinematic bottom overlay
- big headline must stand out
- small headline must contrast clearly
- avoid weak/washed-out colors
- avoid tiny text
- headline must look sharp and premium

Headline rules:
- If user asks to change headline/text/title, rewrite headline_big and headline_small.
- If user asks to make headline stronger, make it more punchy.
- If user only asks color/font/size, keep headline meaning mostly same.
- headline_big should be short, ideally 2 to 5 words.
- headline_small should be supportive, ideally 3 to 8 words.
- Use clean English only.
- No emojis.
- No hashtags.
- No markdown.
- Use ASCII English letters only. No Cyrillic or lookalike characters.
- Keep it factual based on caption/news context.

Design rules:
- If user asks to change text color, update headline_big_color and/or headline_small_color.
- If user asks to change color combination, update overlay_color and headline colors.
- If user asks text is not visible, use white big headline and bright cyan/yellow small headline.
- If user asks bigger text, increase font sizes.
- If user asks smaller text, decrease font sizes.
- If user asks better font, choose a stronger sports font.
- Use only these fonts:
  League Spartan, Oswald, Bebas Neue, Montserrat

Return ONLY valid JSON with this exact structure:
{{
  "selected": true,
  "rejection_reason": null,
  "overlay_color": "#071225",
  "headline_big_color": "#ffffff",
  "headline_small_color": "#57d8ff",
  "font_family": "Montserrat",
  "headline_big_font_size": 86,
  "headline_small_font_size": 56,
  "headline_big": "MESSI TURNS 39",
  "headline_small": "Defying age and inspiring fans"
}}
"""

    response = client.chat.completions.create(
        model=VISION_MODEL,
        temperature=0,
        response_format={
            "type": "json_object"
        },
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url,
                        },
                    },
                ],
            }
        ],
    )

    content = response.choices[0].message.content
    data = json.loads(content)

    revised = PosterRevisionOutput(**data).model_dump()

    revised["selected"] = True
    revised["rejection_reason"] = None

    revised["headline_big"] = _clean_headline(revised["headline_big"])
    revised["headline_small"] = _clean_headline(revised["headline_small"])

    return revised


def revise_current_poster(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Revises poster design and poster headline only.

    Does not change:
    - selected image
    - caption
    """

    feedback_text = state.get("feedback_text") or ""

    selected_image = state.get("selected_poster_image") or {}
    selected_image_path = selected_image.get("local_path")

    if not selected_image_path:
        raise ValueError("No selected poster image found for poster revision.")

    current_poster_path = (
        state.get("final_poster_path")
        or state.get("poster_image_path")
    )

    if not current_poster_path:
        raise ValueError("No current poster image path found for poster revision.")

    current_design = dict(
        state.get("poster_design")
        or _default_poster_decision()
    )

    old_headline_big = state.get("poster_headline_big") or "FOOTBALL UPDATE"
    old_headline_small = state.get("poster_headline_small") or "LATEST STORY"

    candidate_context = selected_image.get("candidate_context", "")

    revision = revise_poster_design_with_groq(
        current_poster_path=current_poster_path,
        current_design=current_design,
        feedback_text=feedback_text,
        news_query=state.get("news_query"),
        caption=state.get("caption"),
        headline_big=old_headline_big,
        headline_small=old_headline_small,
        candidate_context=candidate_context,
    )

    revised_design = {
        "selected": True,
        "rejection_reason": None,
        "overlay_color": revision["overlay_color"],
        "headline_big_color": revision["headline_big_color"],
        "headline_small_color": revision["headline_small_color"],
        "font_family": revision["font_family"],
        "headline_big_font_size": revision["headline_big_font_size"],
        "headline_small_font_size": revision["headline_small_font_size"],
    }

    revised_headline_big = revision["headline_big"]
    revised_headline_small = revision["headline_small"]

    assets = prepare_poster_assets(
        selected_image_path=selected_image_path
    )

    poster_code = generate_poster_html_css(
        poster_design=revised_design,
        headline_big=revised_headline_big,
        headline_small=revised_headline_small,
        background_file=assets["background_file"],
        logo_file=assets["logo_file"],
        category_label=generate_category_label(),
    )

    saved_files = save_poster_files(
        html=poster_code["html"],
        css=poster_code["css"],
    )

    poster_image_path = render_poster_image(
        html_path=saved_files["poster_html_path"]
    )

    return {
        "poster_design": revised_design,

        "poster_headline_big": revised_headline_big,
        "poster_headline_small": revised_headline_small,

        "poster_html": poster_code["html"],
        "poster_css": poster_code["css"],

        "poster_html_path": saved_files["poster_html_path"],
        "poster_css_path": saved_files["poster_css_path"],

        "poster_image_path": poster_image_path,
        "final_poster_path": poster_image_path,
    }


def revise_poster(state: AgentState) -> AgentState:
    print("\n========== REVISE POSTER ==========")
    print("FEEDBACK TEXT:", state.get("feedback_text"))

    try:
        result = revise_current_poster(state)

        print("UPDATED POSTER DESIGN:", result["poster_design"])
        print("UPDATED HEADLINE BIG:", result["poster_headline_big"])
        print("UPDATED HEADLINE SMALL:", result["poster_headline_small"])
        print("POSTER HTML PATH:", result["poster_html_path"])
        print("POSTER CSS PATH:", result["poster_css_path"])
        print("FINAL POSTER PATH:", result["poster_image_path"])

        return {
            **state,

            "poster_design": result["poster_design"],

            "poster_headline_big": result["poster_headline_big"],
            "poster_headline_small": result["poster_headline_small"],

            "poster_html": result["poster_html"],
            "poster_css": result["poster_css"],

            "poster_html_path": result["poster_html_path"],
            "poster_css_path": result["poster_css_path"],

            "poster_image_path": result["poster_image_path"],
            "final_poster_path": result["final_poster_path"],

            "workflow_stage": "awaiting_approval",
            "current_step": "revise_poster",
            "callback_action": None,
            "approval_action": None,
            "error": None,
        }

    except Exception as e:
        print("REVISE POSTER ERROR:", str(e))

        return {
            **state,
            "workflow_stage": "awaiting_approval",
            "current_step": "revise_poster",
            "error": f"revise_poster failed: {str(e)}",
        }