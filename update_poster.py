import os
import io

code = """import os
import json
import base64
import shutil
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

import requests
from PIL import Image
from pydantic import BaseModel, Field
from groq import Groq

from langchain_groq import ChatGroq


# =========================================================
# PATHS
# =========================================================

APP_DIR = Path(__file__).resolve().parents[1]
POSTER_IMAGES_DIR = APP_DIR / "poster_images"
POSTER_GENERATION_DIR = APP_DIR / "poster_generation"
ASSETS_DIR = APP_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"


# =========================================================
# FIXED CONFIG
# Only API key comes from .env
# =========================================================

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"
POSTER_MAX_IMAGE_CANDIDATES = 10


#=========================================================
# PYDANTIC SCHEMAS
# =========================================================

class VisionPosterDecision(BaseModel):
    selected: bool = Field(
        description="Select the image for poster generation based on relevance and if it doesnot have any watermark or visible text. If false, the image will be rejected and the next ranked image will be checked."
    )

    rejection_reason: Optional[str] = Field(
        default=None,
        description="Reject the image if it has visible text, watermark. Also reject if it appears irrelevant to the news context. This field explains the reason for rejection if selected=false."
    )

    overlay_color: str
    headline_big_color: str
    headline_small_color: str
    font_family: Literal["League Spartan", "Oswald", "Bebas Neue", "Montserrat"]

    headline_big_font_size: Optional[int] = None
    headline_smal_font_size: Optional[int] = None


class PosterHeadlineOutput(BaseModel):
    headline_big: str = Field(
        description="Main bigger first line of headline"
    )

    headline_small: str = Field(
        description="Second line of headline, smaller than the first"
    )

# =========================================================
# FILE / IMAGE HELPERS
# =========================================================

def ensure_poster_image_dir() -> str:
    POSTER_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    return str(POSTER_IMAGES_DIR)

def encode_image_to_data_url(image_path: str) -> str:
    \"\"\"
    Converts local image to compressed JPEG data URL.
    This reduces image size before sending to Groq Vision.
    \"\"\"
    image_path = Path(image_path)

    img = Image.open(image_path).convert("RGB")

    max_side = 1280
    width, height = img.size

    if max(width, height) > max_side:
        scale = max_side / max(width, height)
        new_size = (
            int(width * scale),
            int(height * scale),
        )
        img = img.resize(new_size)

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=85)

    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return f"data:image/jpeg;base64,{b64}"


def _looks_like_image_url(url: str) -> bool:
    if not isinstance(url, str):
        return False

    if not url.startswith(("http://", "https://")):
        return False

    lowered = url.lower()

    image_markers = [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        "image",
        "photo",
        "media",
        "cdn",
    ]

    return any(marker in lowered for marker in image_markers)


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    output = []

    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)

    return output

# =========================================================
# RETRIEVAL -> IMAGE URL EXTRACTION
# =========================================================

def _extract_image_urls_from_value(value: Any, found: List[str]) -> None:
    if value is None:
        return

    if isinstance(value, str):
        if _looks_like_image_url(value):
            found.append(value)
        return

    if isinstance(value, dict):
        for key, val in value.items():
            key = str(key).lower()

            if key in {
                "image", "image_url", "image_urls", "img", "img_url",
                "img_src", "img_srcs", "src", "thumbnail", "thumbnail_url",
                "photo", "photo_url", "poster_image", "poster_image_url",
                "images", "media"
            }:
                _extract_image_urls_from_value(val, found)
            elif isinstance(val, (dict, list, str)):
                _extract_image_urls_from_value(val, found)
        return

    if isinstance(value, list):
        for item in value:
            _extract_image_urls_from_value(item, found)


def _get_retrieved_items_from_state(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    structured_news = state.get("structured_news")
    if isinstance(structured_news, dict):
        for key in ["news_items", "items", "results", "chunks", "retrieved_chunks", "poster_image_candidates"]:
            value = structured_news.get(key)
            if isinstance(value, list) and value:
                return value

    raw_news = state.get("raw_news")
    if isinstance(raw_news, list) and raw_news:
        return raw_news

    image_candidates = state.get("image_candidates")
    if isinstance(image_candidates, list) and image_candidates:
        return image_candidates

    poster_image_candidates = state.get("poster_image_candidates")
    if isinstance(poster_image_candidates, list) and poster_image_candidates:
        return poster_image_candidates

    return []

def extract_ranked_image_candidates(
    state: Dict[str, Any],
    max_images: int = 10
) -> List[Dict[str, Any]]:
    items = _get_retrieved_items_from_state(state)
    rejected_urls = set(state.get("rejected_poster_image_urls") or [])

    ranked = []
    seen_urls = set()

    for item in items:
        found_in_item: List[str] = []
        _extract_image_urls_from_value(item, found_in_item)
        found_in_item = _dedupe_preserve_order(found_in_item)

        candidate_context = str(item)

        for url in found_in_item:
            if url in seen_urls: continue
            if url in rejected_urls:
                print(f"[poster_generation] skipping rejected image: {url}")
                continue

            seen_urls.add(url)
            rank = len(ranked) + 1
            ranked.append({
                "rank": rank,
                "url": url,
                "file_name": f"rank{rank}.jpg",
                "candidate_context": candidate_context,
            })
            if len(ranked) >= max_images:
                return ranked
    return ranked

# =========================================================
# DOWNLOAD IMAGES
# =========================================================

def download_ranked_images(
    ranked_candidates: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    ensure_poster_image_dir()
    headers = {"User-Agent": "Mozilla/5.0"}
    downloaded = []

    for item in ranked_candidates:
        rank = item["rank"]
        url = item["url"]
        save_path = POSTER_IMAGES_DIR / f"rank{rank}.jpg"

        try:
            response = requests.get(url, headers=headers, timeout=25)
            response.raise_for_status()

            img = Image.open(BytesIO(response.content)).convert("RGB")
            img.save(save_path, format="JPEG", quality=95)

            downloaded.append({
                "rank": rank,
                "url": url,
                "local_path": str(save_path),
                "file_name": save_path.name,
                "candidate_context": item.get("candidate_context", ""),
            })

            print(f"[poster_generation] downloaded rank{rank}: {save_path}")

        except Exception as e:
            print(f"[poster_generation] failed to download rank{rank}: {url} | {e}")

    return downloaded

# =========================================================
# GROQ VISION SELECTION + DESIGN DECISION
# =========================================================

def analyze_image_with_groq(
    image_path: str,
    news_query: Optional[str] = None,
    caption: Optional[str] = None,
    candidate_context: Optional[str] = None,
) -> VisionPosterDecision:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    image_data_url = encode_image_to_data_url(image_path)

    prompt = f\"\"\"
You are a visual evaluator and design planner for an automated football news poster system.

News context:
News query: {news_query or ""}
Generated caption: {caption or ""}
Retrieved chunk context connected to this image: {candidate_context or ""}

Your job has 3 parts:

PART 1 — NEWS RELEVANCE CHECK
Check whether the image is visually relevant to the news context.
Reject the image if:
- it appears unrelated to the player, team, match, country, club, or event in the news context
- it is a generic football photo with no clear relation to the news
- it shows a different team/player/event than the news context

Accept only if:
- it appears relevant to the main football subject, team, player, country, match, or event
- or the retrieved chunk context strongly suggests the image belongs to the same news item

PART 2 — IMAGE SELECTION
Check whether the image should be selected for poster generation.
Selection criteria:
- reject if the image has visible text
- reject if the image looks pre-edited, posterized, or already designed for social media
- cropped or collage images are allowed if there is no visible text
- prefer raw football editorial photos suitable as a background image

PART 3 — DESIGN DECISION
In terms of design, provide output strictly adhering to the schema VisionPosterDecision:
1. Provide overlay_color, headline_big_color, headline_small_color as valid CSS color strings (hex or rgba).
2. Choose font_family from: 'League Spartan', 'Oswald', 'Bebas Neue', or 'Montserrat'.
3. Set headline_big_font_size and headline_smal_font_size.
If there's no selection, then keep other fields as default values, but write the rejection reason clearly.
\"\"\"
    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url,
                        },
                    },
                ],
            }
        ],
        response_format={"type": "json_object"}
    )
    
    content = response.choices[0].message.content
    data = json.loads(content)

    return VisionPosterDecision(**data)


def _default_poster_decision() -> Dict[str, Any]:
    return {
        "selected": True,
        "rejection_reason": None,
        "overlay_color": "#071225",
        "headline_big_color": "#ffffff",
        "headline_small_color": "#57d8ff",
        "font_family": "Montserrat",
        "headline_big_font_size": 84,
        "headline_smal_font_size": 56
    }


def select_best_image_sequentially(
    downloaded_images: List[Dict[str, Any]],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    decisions_log = []
    sorted_images = sorted(downloaded_images, key=lambda x: x["rank"])

    for item in sorted_images:
        print(f"[poster_generation] checking image rank{item['rank']} with Groq Vision")
        try:
            decision = analyze_image_with_groq(
                image_path=item["local_path"],
                news_query=state.get("news_query"),
                caption=state.get("caption"),
                candidate_context=item.get("candidate_context", ""),
            )
            decision_dict = decision.model_dump()
        except Exception as e:
            decision_dict = {
                **_default_poster_decision(),
                "rejection_reason": f"Vision analysis failed: {str(e)}",
                "selected": False
            }

        decisions_log.append({
            "rank": item["rank"],
            "url": item["url"],
            "local_path": item["local_path"],
            "decision": decision_dict,
        })

        if decision_dict.get("selected") is True:
            selected = {**item, "decision": decision_dict}
            return {
                "selected_image": selected,
                "poster_design": decision_dict,
                "decisions_log": decisions_log,
            }

    if sorted_images:
        fallback = sorted_images[0]
        fallback_decision = {
            **_default_poster_decision(),
            "rejection_reason": "All images were rejected. Fallback to rank1.",
            "selected": True
        }

        selected = {**fallback, "decision": fallback_decision, "fallback_used": True}
        return {
            "selected_image": selected,
            "poster_design": fallback_decision,
            "decisions_log": decisions_log,
        }

    raise ValueError("No images were successfully downloaded.")


# =========================================================
# GROQ HEADLINE GENERATION
# =========================================================

def generate_split_headlines(
    caption: str,
    news_query: Optional[str] = None,
    poster_design: Optional[Dict[str, Any]] = None,
    human_feedback: Optional[str] = None
) -> Dict[str, str]:
    llm = ChatGroq(model=GROQ_TEXT_MODEL, api_key=os.getenv("GROQ_API_KEY"))
    structured_llm = llm.with_structured_output(PosterHeadlineOutput)

    feedback_prompt = f"\\nHuman Feedback for Headline adjustments: {human_feedback}\\nPlease adjust the headlines accordingly to satisfy the human feedback." if human_feedback else ""

    prompt = f\"\"\"
You are a football editorial headline writer.

Generate a professional 2-line poster headline from the given caption.

Requirements:
- line 1 = bigger and stronger
- line 2 = smaller and supportive
- make it professional and editorial
- suitable for a football social media news card
- no emojis
- short and punchy
- avoid long sentences
- line 1 should ideally be 2 to 5 words
- line 2 should ideally be 3 to 8 words
- write in clear English

Context:
News query: {news_query or ""}
Caption: {caption}
{feedback_prompt}

Return structured output only.
\"\"\"

    result = structured_llm.invoke(prompt)

    return {
        "headline_big": result.headline_big.strip(),
        "headline_small": result.headline_small.strip(),
    }

# =========================================================
# POSTER HTML/CSS GENERATION + RENDERING
# =========================================================

def prepare_poster_assets(selected_image_path: str) -> Dict[str, str]:
    POSTER_GENERATION_DIR.mkdir(parents=True, exist_ok=True)
    background_path = POSTER_GENERATION_DIR / "background.jpg"
    logo_output_path = POSTER_GENERATION_DIR / "logo.png"

    shutil.copyfile(selected_image_path, background_path)
    logo_exists = LOGO_PATH.exists()

    if logo_exists:
        shutil.copyfile(LOGO_PATH, logo_output_path)

    return {
        "background_file": "background.jpg",
        "background_path": str(background_path),
        "logo_file": "logo.png" if logo_exists else "",
        "logo_path": str(logo_output_path) if logo_exists else "",
        "logo_exists": str(logo_exists),
    }

def generate_category_label() -> str:
    return "INSIDER UPDATE"

def generate_poster_html_css(
    poster_design: Dict[str, Any],
    headline_big: str,
    headline_small: str,
    background_file: str,
    logo_file: str,
    category_label: str,
) -> Dict[str, str]:
    panel_dark = poster_design.get("overlay_color", "#071225")
    headline_big_color = poster_design.get("headline_big_color", "#ffffff")
    headline_small_color = poster_design.get("headline_small_color", "#57d8ff")
    font_family = poster_design.get("font_family", "Montserrat")
    headline_big_font_size = poster_design.get("headline_big_font_size", 84)
    headline_small_font_size = poster_design.get("headline_smal_font_size", 56)
    
    badge_blue = "#2d61ff"

    html = f\"\"\"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Football Poster</title>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;700;800;900&family=Bebas+Neue&family=League+Spartan:wght@700;800;900&family=Montserrat:wght@700;800;900&family=Oswald:wght@500;600;700&display=swap" rel="stylesheet">

    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="card">
        <div class="image-container">
            <img src="{background_file}" class="bg" alt="Background Image" />
            {"<div class='logo-wrap'><img src='" + logo_file + "' class='logo' alt='Logo' /></div>" if logo_file else ""}
            <div class="news-panel">
                <div class="category">{category_label}</div>
                <h1>{headline_big}</h1>
                <h2>{headline_small}</h2>
            </div>
        </div>
    </div>
</body>
</html>
\"\"\"
    css = f\"\"\"*{{
    margin:0;
    padding:0;
    box-sizing:border-box;
}}
html, body{{
    width:100%;
    height:100%;
}}
body{{
    min-height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
    background:#111;
    font-family:'Inter', sans-serif;
}}
.card{{
    width:1080px;
    height:1350px;
    overflow:hidden;
    border-radius:34px;
    background:{panel_dark};
    display:flex;
    flex-direction:column;
    position:relative;
    box-shadow:0 28px 80px rgba(0,0,0,.45);
}}
.image-container{{
    flex:1;
    position:relative;
    overflow:hidden;
    isolation:isolate;
}}
.bg{{
    width:100%;
    height:100%;
    object-fit:cover;
    display:block;
    transform:scale(1.01);
}}
.image-container::after{{
    content:"";
    position:absolute;
    left:0;
    right:0;
    bottom:0;
    height:560px;
    background:
        linear-gradient(
            180deg,
            rgba(7,18,37,0) 0%,
            rgba(7,18,37,.05) 10%,
            rgba(7,18,37,.14) 22%,
            rgba(7,18,37,.30) 36%,
            rgba(7,18,37,.55) 52%,
            rgba(7,18,37,.78) 68%,
            rgba(7,18,37,.93) 84%,
            {panel_dark} 100%
        );
    z-index:2;
}}
.image-container::before{{
    content:"";
    position:absolute;
    inset:0;
    background:
        radial-gradient(
            circle at center,
            rgba(0,0,0,0) 45%,
            rgba(0,0,0,.10) 68%,
            rgba(0,0,0,.22) 100%
        );
    z-index:1;
    pointer-events:none;
}}
.logo-wrap{{
    position:absolute;
    top:42px;
    left:42px;
    z-index:5;
    width:84px;
    height:84px;
    border-radius:18px;
    background:rgba(255,255,255,.14);
    backdrop-filter:blur(12px);
    display:flex;
    justify-content:center;
    align-items:center;
    box-shadow:0 8px 20px rgba(0,0,0,.18);
}}
.logo{{
    width:54px;
    height:54px;
    object-fit:contain;
    display:block;
}}
.news-panel{{
    position:absolute;
    left:54px;
    right:54px;
    bottom:58px;
    z-index:5;
}}
.category{{
    display:inline-block;
    padding:15px 26px;
    border-radius:999px;
    background:{badge_blue};
    color:#fff;
    font-size:28px;
    font-weight:800;
    font-family:'Inter', sans-serif;
    letter-spacing:.3px;
    margin-bottom:28px;
    box-shadow:0 10px 24px rgba(0,0,0,.18);
}}
h1{{
    color:{headline_big_color};
    font-family:'{font_family}', sans-serif;
    font-size:{headline_big_font_size}px;
    font-weight:900;
    line-height:.95;
    letter-spacing:-2.2px;
    text-transform:uppercase;
    margin-bottom:18px;
    text-shadow:0 6px 18px rgba(0,0,0,.25);
}}
h2{{
    color:{headline_small_color};
    font-family:'{font_family}', sans-serif;
    font-size:{headline_small_font_size}px;
    font-weight:800;
    line-height:1.02;
    letter-spacing:-1px;
    text-transform:uppercase;
    text-shadow:0 4px 14px rgba(0,0,0,.22);
    max-width:88%;
}}
\"\"\"
    return {
        "html": html,
        "css": css,
    }

def save_poster_files(html: str, css: str) -> Dict[str, str]:
    POSTER_GENERATION_DIR.mkdir(parents=True, exist_ok=True)
    html_path = POSTER_GENERATION_DIR / "index.html"
    css_path = POSTER_GENERATION_DIR / "styles.css"

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(css_path, "w", encoding="utf-8") as f:
        f.write(css)

    return {
        "poster_html_path": str(html_path),
        "poster_css_path": str(css_path),
    }

def render_poster_image(html_path: str) -> str:
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from playwright.async_api import async_playwright

    output_path = POSTER_GENERATION_DIR / "poster.png"
    html_file_url = Path(html_path).resolve().as_uri()

    async def _render():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                viewport={"width": 1080, "height": 1350},
                device_scale_factor=1,
            )
            await page.goto(html_file_url, wait_until="networkidle")
            await page.screenshot(path=str(output_path), full_page=False)
            await browser.close()
        return str(output_path)

    def _run_async_renderer():
        return asyncio.run(_render())

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_async_renderer)
        return future.result()

# =========================================================
# MAIN ORCHESTRATION HELPER
# =========================================================

def run_poster_image_pipeline(
    state: Dict[str, Any]
) -> Dict[str, Any]:
    max_images = POSTER_MAX_IMAGE_CANDIDATES
    
    ranked_candidates = extract_ranked_image_candidates(state, max_images)
    downloaded_images = download_ranked_images(ranked_candidates)
    
    selection_result = select_best_image_sequentially(downloaded_images, state)
    selected_image = selection_result["selected_image"]
    poster_design = selection_result["poster_design"]
    
    headlines = generate_split_headlines(
        state.get("caption", ""),
        news_query=state.get("news_query"),
        poster_design=poster_design,
        human_feedback=state.get("human_feedback")
    )
    
    saved_assets = prepare_poster_assets(selected_image["local_path"])
    category_label = generate_category_label()
    
    poster_code = generate_poster_html_css(
        poster_design=poster_design,
        headline_big=headlines["headline_big"],
        headline_small=headlines["headline_small"],
        background_file=saved_assets["background_file"],
        logo_file=saved_assets["logo_file"],
        category_label=category_label,
    )
    
    saved_files = save_poster_files(poster_code["html"], poster_code["css"])
    poster_image_path = render_poster_image(saved_files["poster_html_path"])
    
    return {
        "poster_image_dir": str(POSTER_IMAGES_DIR),
        "poster_generation_dir": str(POSTER_GENERATION_DIR),

        "poster_image_candidates": downloaded_images,
        "selected_poster_image": selected_image,

        "poster_design": poster_design,

        "poster_headline_big": headlines["headline_big"],
        "poster_headline_small": headlines["headline_small"],

        "poster_html": poster_code["html"],
        "poster_css": poster_code["css"],

        "poster_html_path": saved_files["poster_html_path"],
        "poster_css_path": saved_files["poster_css_path"],

        "poster_image_path": poster_image_path,
        "final_poster_path": poster_image_path,
    }
"""

with open(r"c:\FB Agent\app\services\poster_generation_service.py", "w", encoding="utf-8") as f:
    f.write(code)

