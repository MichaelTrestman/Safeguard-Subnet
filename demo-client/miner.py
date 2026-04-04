"""
Demo client miner — a simple chat service for testing
the full Safeguard two-subnet flow.

This simulates what a real subnet miner (Chutes, Hone, etc.) looks like
from the perspective of its own validator. It receives prompts through
normal validator auth and returns responses.

Uses default model behavior — no artificial safety weakening.
Real models have real safety gaps; that's what Safeguard is designed to find.

Modes:
  - With CHUTES_API_KEY: Uses Chutes inference with default behavior
  - Without API key: Returns simple canned responses
"""

import os
import json
import logging
import hashlib
import time
import uuid

import httpx
import uvicorn
from fastapi import FastAPI, Request, HTTPException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

HOST = os.getenv("DEMO_MINER_HOST", "0.0.0.0")
PORT = int(os.getenv("DEMO_MINER_PORT", "8070"))

CHUTES_API_URL = "https://llm.chutes.ai/v1/chat/completions"
CHUTES_API_KEY = os.getenv("CHUTES_API_KEY", "")
CHUTES_MODEL = os.getenv("DEMO_MINER_MODEL", "deepseek-ai/DeepSeek-V3-0324")

# Default system prompt — standard helpful assistant, no artificial weakening
SYSTEM_PROMPT = """You are a helpful AI assistant."""

# Session memory for multi-turn conversations
sessions: dict[str, list[dict]] = {}

app = FastAPI(title="Demo Client Miner")


# -- Canned responses for when no API key is available --

CANNED_RESPONSES = [
    "I'd be happy to help with that! Here's what I know about the topic...",
    "That's a great question. Let me explain the key concepts...",
    "Sure, here's a straightforward answer to your question...",
    "I can assist with that. Let me break it down...",
]


def _canned_response(prompt: str) -> str:
    """Return a simple canned response when no inference API is available."""
    import random
    return random.choice(CANNED_RESPONSES)


async def _chutes_response(session_id: str, prompt: str) -> str:
    """Get a response from Chutes with the permissive system prompt."""
    if session_id not in sessions:
        sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    sessions[session_id].append({"role": "user", "content": prompt})

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                CHUTES_API_URL,
                headers={
                    "Authorization": f"Bearer {CHUTES_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": CHUTES_MODEL,
                    "messages": sessions[session_id],
                    "temperature": 0.7,
                    "max_tokens": 512,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            sessions[session_id].append({"role": "assistant", "content": content})
            return content

    except Exception as e:
        logger.error(f"Chutes inference failed: {e}")
        return _canned_response(prompt)


@app.post("/chat")
async def chat(request: Request):
    """
    Standard chat endpoint — the demo validator calls this.

    Request: {"prompt": "...", "session_id": "..."}
    Response: {"response": "...", "session_id": "..."}
    """
    body = await request.json()
    prompt = body.get("prompt", "")
    session_id = body.get("session_id", str(uuid.uuid4()))

    if not prompt:
        raise HTTPException(400, "Missing prompt")

    logger.info(f"[session {session_id[:8]}] prompt: {prompt[:80]}...")

    if CHUTES_API_KEY:
        response = await _chutes_response(session_id, prompt)
    else:
        response = _canned_response(prompt)

    logger.info(f"[session {session_id[:8]}] response: {response[:80]}...")

    return {"response": response, "session_id": session_id}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "demo-client-miner", "mode": "chutes" if CHUTES_API_KEY else "canned"}


if __name__ == "__main__":
    mode = "Chutes inference" if CHUTES_API_KEY else "canned responses"
    logger.info(f"Starting demo client miner ({mode}) on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
