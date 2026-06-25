#main.py
from fastapi import FastAPI, Request
from .telegram_handler import process_update

app = FastAPI()


@app.get("/")
async def health():
    return {"status": "running"}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):

    update = await request.json()

    await process_update(update)

    return {"ok": True}