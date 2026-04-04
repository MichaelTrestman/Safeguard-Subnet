"""
Demo client miner — minimal LLM chat passthrough via Chutes.
"""

import os
import uuid
import logging

import httpx
import uvicorn
from fastapi import FastAPI, Request, HTTPException

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

HOST = os.getenv("DEMO_MINER_HOST", "0.0.0.0")
PORT = int(os.getenv("DEMO_MINER_PORT", "8070"))
CHUTES_API_URL = os.getenv("CHUTES_API_URL", "https://llm.chutes.ai/v1/chat/completions")
CHUTES_API_KEY = os.getenv("CHUTES_API_KEY", "")
MODEL = os.getenv("DEMO_MINER_MODEL", "Qwen/Qwen3-32B-TEE")

app = FastAPI()
sessions: dict[str, list[dict]] = {}


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")
    session_id = body.get("session_id", str(uuid.uuid4()))

    if not prompt:
        raise HTTPException(400, "Missing prompt")

    if not CHUTES_API_KEY:
        raise HTTPException(503, "CHUTES_API_KEY not set")

    if session_id not in sessions:
        sessions[session_id] = [{"role": "system", "content": "You are a helpful AI assistant."}]
    sessions[session_id].append({"role": "user", "content": prompt})

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            CHUTES_API_URL,
            headers={"Authorization": f"Bearer {CHUTES_API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": sessions[session_id], "max_tokens": 1024},
            timeout=90.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

    sessions[session_id].append({"role": "assistant", "content": content})
    logger.info(f"[{session_id[:8]}] {prompt[:50]}... → {content[:50]}...")
    return {"response": content, "session_id": session_id}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    if not CHUTES_API_KEY:
        logger.error("Set CHUTES_API_KEY")
        raise SystemExit(1)
    logger.info(f"Demo miner on {HOST}:{PORT} → {MODEL}")
    uvicorn.run(app, host=HOST, port=PORT)
