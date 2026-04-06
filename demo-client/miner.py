"""
Demo client miner — minimal LLM chat passthrough via Chutes.

Optionally registers on a client subnet (e.g. netuid 445) and commits
its endpoint so the demo-client validator can discover it from chain.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import sys
import json
import uuid
import logging

import httpx
import uvicorn
from fastapi import FastAPI, Request, HTTPException

MODEL = os.getenv("DEMO_MINER_MODEL", "Qwen/Qwen3-32B-TEE")
_model_short = MODEL.split("/")[-1][:20]

logging.basicConfig(level=logging.INFO, format=f"%(asctime)s | DC-MINER({_model_short}) | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

HOST = os.getenv("DEMO_MINER_HOST", "0.0.0.0")
PORT = int(os.getenv("DEMO_MINER_PORT", "8070"))
CHUTES_API_URL = os.getenv("CHUTES_API_URL", "https://llm.chutes.ai/v1/chat/completions")
CHUTES_API_KEY = os.getenv("CHUTES_API_KEY", "")

# Chain registration (optional — set NETWORK + CLIENT_NETUID to enable)
NETWORK = os.getenv("NETWORK", "")
CLIENT_NETUID = int(os.getenv("CLIENT_NETUID", "0"))
WALLET_NAME = os.getenv("WALLET_NAME", "")
HOTKEY_NAME = os.getenv("HOTKEY_NAME", "default")

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

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                CHUTES_API_URL,
                headers={"Authorization": f"Bearer {CHUTES_API_KEY}", "Content-Type": "application/json"},
                json={"model": MODEL, "messages": sessions[session_id], "max_tokens": 1024},
                timeout=120.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Chutes call failed: {e}")
        raise HTTPException(502, f"Inference failed: {e}")

    sessions[session_id].append({"role": "assistant", "content": content})
    logger.info(f"[{session_id[:8]}] {prompt[:50]}... → {content[:50]}...")
    return {"response": content, "session_id": session_id}


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL}


@app.on_event("startup")
async def startup():
    if not NETWORK or not CLIENT_NETUID or not WALLET_NAME:
        logger.info("No chain config — running as standalone HTTP server")
        return

    import bittensor as bt
    from bittensor_wallet import Wallet

    wallet = Wallet(name=WALLET_NAME, hotkey=HOTKEY_NAME)
    subtensor = bt.Subtensor(network=NETWORK)
    metagraph = bt.Metagraph(netuid=CLIENT_NETUID, network=NETWORK)
    metagraph.sync(subtensor=subtensor)

    my_hotkey = wallet.hotkey.ss58_address
    if my_hotkey not in metagraph.hotkeys:
        logger.error(f"Hotkey {my_hotkey} not registered on netuid {CLIENT_NETUID}")
        return

    my_uid = metagraph.hotkeys.index(my_hotkey)
    logger.info(f"Demo miner UID: {my_uid} on netuid {CLIENT_NETUID}")

    commit_host = "127.0.0.1" if HOST == "0.0.0.0" else HOST
    endpoint_data = json.dumps({
        "endpoint": f"http://{commit_host}:{PORT}",
        "model": MODEL,
    })
    for attempt in range(3):
        try:
            # Reconnect subtensor to get a fresh block reference
            if attempt > 0:
                subtensor = bt.Subtensor(network=NETWORK)
                import asyncio
                await asyncio.sleep(3)
            subtensor.set_commitment(wallet=wallet, netuid=CLIENT_NETUID, data=endpoint_data)
            logger.info(f"Committed endpoint to chain: {endpoint_data}")
            break
        except Exception as e:
            if attempt < 2:
                logger.warning(f"Commit attempt {attempt+1} failed ({e}), retrying...")
            else:
                logger.warning(f"Failed to commit endpoint after 3 attempts: {e}")


if __name__ == "__main__":
    if not CHUTES_API_KEY:
        logger.error("Set CHUTES_API_KEY")
        raise SystemExit(1)
    logger.info(f"Demo miner on {HOST}:{PORT} → {MODEL}")
    uvicorn.run(app, host=HOST, port=PORT)
