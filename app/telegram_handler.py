# app/telegram_handler.py

import os
import json
import httpx
from dotenv import load_dotenv
from datetime import datetime

from .agent import run_langgraph_agent


load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

SAVE_DIR = "telegram_image"
os.makedirs(SAVE_DIR, exist_ok=True)


async def download_telegram_image(file_id: str):
    async with httpx.AsyncClient() as client:
        # STEP 1: get file path
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
        res = await client.get(url, params={"file_id": file_id})
        data = res.json()

        if not data.get("ok"):
            print("Failed to get file info")
            return None

        file_path = data["result"]["file_path"]

        # STEP 2: download actual file
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        file_data = await client.get(file_url)

        # STEP 3: save file
        filename = f"{datetime.now().timestamp()}.jpg"
        full_path = os.path.join(SAVE_DIR, filename)

        with open(full_path, "wb") as f:
            f.write(file_data.content)

        print("IMAGE SAVED:", full_path)

        return full_path


async def answer_callback_query(callback_query_id: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"

    payload = {
        "callback_query_id": callback_query_id
    }

    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)


async def send_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(url, json=payload)
        print("MESSAGE SENT:", res.json())


async def send_image(chat_id: int, image_path: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    async with httpx.AsyncClient() as client:
        with open(image_path, "rb") as f:
            files = {
                "photo": f
            }

            data = {
                "chat_id": chat_id
            }

            res = await client.post(url, data=data, files=files)

            print("IMAGE SENT:", res.json())


async def send_poster_for_approval(chat_id: int, image_path: str, caption: str):
    """
    Sends generated poster with caption and inline approval buttons.
    """

    if not os.path.exists(image_path):
        await send_message(chat_id, f"Poster image not found: {image_path}")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    # Telegram photo caption limit is 1024 chars
    safe_caption = caption[:950]

    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Approve",
                    "callback_data": "approve"
                },
                {
                    "text": "❌ Reject",
                    "callback_data": "reject"
                }
            ]
        ]
    }

    async with httpx.AsyncClient(timeout=60) as client:
        with open(image_path, "rb") as f:
            files = {
                "photo": f
            }

            data = {
                "chat_id": chat_id,
                "caption": safe_caption,
                "reply_markup": json.dumps(reply_markup)
            }

            res = await client.post(url, data=data, files=files)

            print("POSTER APPROVAL SENT:", res.json())


async def handle_agent_response(chat_id: int, response: dict):
    """
    Decides whether to send normal text or poster approval message.
    """

    response_type = response.get("type")
    text = response.get("text") or "Workflow completed."
    image_path = response.get("image_path")
    needs_approval = response.get("needs_approval", False)

    if response_type == "approval" and image_path and needs_approval:
        await send_poster_for_approval(
            chat_id=chat_id,
            image_path=image_path,
            caption=text,
        )
        return

    await send_message(chat_id, text)


async def process_update(update: dict):
    # ======================
    # 🔵 CALLBACK HANDLING
    # ======================
    callback_query = update.get("callback_query")

    if callback_query:
        callback_query_id = callback_query["id"]
        callback_data = callback_query.get("data")
        message = callback_query.get("message", {})
        chat_id = message.get("chat", {}).get("id")

        print("CALLBACK RECEIVED:", callback_data)
        print("FROM CHAT ID:", chat_id)

        await answer_callback_query(callback_query_id)

        if not chat_id:
            return

        if callback_data not in ["approve", "reject"]:
            await send_message(chat_id, "Unknown action.")
            return

        response = await run_langgraph_agent(
            user_text="",
            chat_id=str(chat_id),
            callback_action=callback_data,
        )

        await handle_agent_response(chat_id, response)

        return

    # ======================
    # 🟡 MESSAGE HANDLING
    # ======================
    message = update.get("message")

    if not message:
        return

    chat_id = message["chat"]["id"]

    # ======================
    # 🟢 IMAGE HANDLING
    # ======================
    if "photo" in message:
        photos = message["photo"]
        file_id = photos[-1]["file_id"]  # highest resolution

        print("IMAGE RECEIVED:", file_id)

        saved_path = await download_telegram_image(file_id)

        print("SAVED TO:", saved_path)

        return

    # ======================
    # 🟡 TEXT HANDLING
    # ======================
    user_text = message.get("text")

    if not user_text:
        return

    print("TEXT RECEIVED:", user_text)
    print("FROM CHAT ID:", chat_id)

    response = await run_langgraph_agent(
        user_text=user_text,
        chat_id=str(chat_id),
    )

    await handle_agent_response(chat_id, response)