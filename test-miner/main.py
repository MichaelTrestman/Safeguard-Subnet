"""
Safeguard test miner — FastAPI server that accepts probing tasks.

NOT a production miner. Exists for testnet validation only.
"""

import os
import sys
import json
import time
import hashlib
import logging
import asyncio

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from bittensor_wallet.keypair import Keypair
import bittensor as bt
from bittensor_wallet import Wallet

from prober import probe_via_relay

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Config
NETWORK = os.getenv("NETWORK", "test")
NETUID = int(os.getenv("NETUID", "1"))
WALLET_NAME = os.getenv("WALLET_NAME", "miner")
HOTKEY_NAME = os.getenv("HOTKEY_NAME", "default")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
MAX_REQUEST_AGE = 60  # seconds

app = FastAPI(title="Safeguard Test Miner")

# Initialized at startup
wallet: Wallet = None
subtensor: bt.Subtensor = None
metagraph: bt.Metagraph = None


def verify_epistula(timestamp: str, signature: str, hotkey: str, body: bytes) -> str:
    """Verify Epistula authentication headers."""
    request_time = int(timestamp) / 1e9
    if abs(time.time() - request_time) > MAX_REQUEST_AGE:
        raise ValueError("Request timestamp too old")

    body_hash = hashlib.sha256(body).hexdigest()
    message = f"{timestamp}.{body_hash}"

    keypair = Keypair(ss58_address=hotkey)
    if not keypair.verify(message.encode(), bytes.fromhex(signature)):
        raise ValueError("Invalid signature")

    return hotkey


async def get_body(request: Request) -> bytes:
    return await request.body()


async def verify_validator(request: Request, body: bytes = Depends(get_body)) -> str:
    """Verify the caller is a registered validator on this subnet."""
    try:
        hotkey = verify_epistula(
            timestamp=request.headers["X-Epistula-Timestamp"],
            signature=request.headers["X-Epistula-Signature"],
            hotkey=request.headers["X-Epistula-Hotkey"],
            body=body,
        )
    except KeyError as e:
        raise HTTPException(400, f"Missing header: {e}")
    except ValueError as e:
        raise HTTPException(401, str(e))

    # Verify caller is a validator on this subnet
    if hotkey not in metagraph.hotkeys:
        raise HTTPException(403, "Not registered on subnet")

    uid = metagraph.hotkeys.index(hotkey)
    if not metagraph.validator_permit[uid]:
        raise HTTPException(403, "Not a validator")

    return hotkey


@app.post("/probe")
async def handle_probe(
    request: Request,
    validator_hotkey: str = Depends(verify_validator),
):
    """Accept a probing task and return results."""
    body = await request.json()

    task_id = body.get("task_id", "unknown")
    target_validator_endpoint = body.get("target_validator_endpoint", "")
    scenario_category = body.get("scenario_category", "")
    prompt = body.get("prompt", "")

    if not target_validator_endpoint:
        raise HTTPException(400, "Missing target_validator_endpoint")

    logger.info(
        f"Received task {task_id} from validator {validator_hotkey[:8]}... "
        f"category={scenario_category}"
    )

    # Run the adversarial probe through the target validator's relay
    result = await probe_via_relay(
        wallet=wallet,
        target_validator_endpoint=target_validator_endpoint,
        initial_prompt=prompt,
        scenario_category=scenario_category,
    )
    result["task_id"] = task_id

    logger.info(
        f"Task {task_id}: verdict={result['miner_safety_verdict']}, "
        f"severity={result['miner_severity']}"
    )

    return result


@app.get("/health")
async def health():
    return {"status": "ok", "netuid": NETUID, "network": NETWORK}


@app.on_event("startup")
async def startup():
    """Initialize wallet, subtensor, metagraph, and commit endpoint."""
    global wallet, subtensor, metagraph

    wallet = Wallet(name=WALLET_NAME, hotkey=HOTKEY_NAME)
    subtensor = bt.Subtensor(network=NETWORK)
    metagraph = bt.Metagraph(netuid=NETUID, network=NETWORK)
    metagraph.sync(subtensor=subtensor)

    my_hotkey = wallet.hotkey.ss58_address
    if my_hotkey not in metagraph.hotkeys:
        logger.error(f"Hotkey {my_hotkey} not registered on netuid {NETUID}")
        sys.exit(1)

    my_uid = metagraph.hotkeys.index(my_hotkey)
    logger.info(f"Test miner UID: {my_uid} on netuid {NETUID}")

    # Commit endpoint to chain — use 127.0.0.1 for local, not 0.0.0.0
    commit_host = "127.0.0.1" if HOST == "0.0.0.0" else HOST
    endpoint_data = json.dumps({"endpoint": f"http://{commit_host}:{PORT}"})
    try:
        subtensor.set_commitment(
            wallet=wallet,
            netuid=NETUID,
            data=endpoint_data,
        )
        logger.info(f"Committed endpoint to chain: {endpoint_data}")
    except Exception as e:
        logger.warning(f"Failed to commit endpoint (may already be committed): {e}")


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
