"""
Mock target subnet validator implementing the /relay protocol.

For local testing only. Forwards prompts to a mock chat service,
simulating what a real target subnet validator would do.

Usage:
    # Start the mock chat service first:
    python mock_chat_service.py  # runs on port 8000

    # Then start this relay:
    python mock_target_validator.py  # runs on port 9000
"""

import os
import json
import logging
import uuid

import uvicorn
import httpx
from fastapi import FastAPI, Request, HTTPException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "9000"))
CHAT_SERVICE_URL = os.getenv("CHAT_SERVICE_URL", "http://localhost:8000")

app = FastAPI(title="Mock Target Validator (Relay)")

# Injectable chat client — set this for testing to use ASGI transport
# instead of hitting a real network endpoint.
_chat_client: httpx.AsyncClient | None = None


def set_chat_client(client: httpx.AsyncClient | None):
    """Inject a chat service client (for testing with ASGI transport)."""
    global _chat_client
    _chat_client = client


async def _get_chat_client() -> httpx.AsyncClient:
    """Get the chat client — injected or default."""
    if _chat_client is not None:
        return _chat_client
    return httpx.AsyncClient(timeout=15.0)


@app.post("/relay")
async def relay(request: Request):
    """
    Relay endpoint per RELAY_PROTOCOL.md.
    Forwards prompt to mock chat service, returns response.
    """
    body = await request.json()
    prompt = body.get("prompt", "")
    session_id = body.get("session_id", str(uuid.uuid4()))

    if not prompt:
        raise HTTPException(400, "Missing prompt")

    logger.info(f"Relay session={session_id[:8]}... prompt={prompt[:50]}...")

    # Forward to chat service
    client = await _get_chat_client()
    try:
        resp = await client.post(
            f"{CHAT_SERVICE_URL}/chat",
            json={"prompt": prompt, "session_id": session_id},
        )
        resp.raise_for_status()
        data = resp.json()
        reply = data.get("response", "")
    except httpx.HTTPError as e:
        logger.error(f"Chat service error: {e}")
        raise HTTPException(502, f"Target miner failed: {e}")
    finally:
        # Only close if we created it (not injected)
        if _chat_client is None:
            await client.aclose()

    logger.info(f"Relay session={session_id[:8]}... response={reply[:50]}...")

    return {"response": reply, "session_id": session_id}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock-target-validator-relay"}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
