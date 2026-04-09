"""
Safeguard test miner — FastAPI server that accepts probing tasks.

NOT a production miner. Exists for testnet validation only.

DEPRECATED as the recommended starting point for building real miners.
The maintained third-party reference rig now lives at:

    https://github.com/TODO/safeguard-miner

That repo has a multi-vector escalation prober, judge-aligned self-scoring
(matched to validator.py:489 audit math), and a longer turn budget. Read its
README.md and recon.md before building from this file — they explain what
the validator actually rewards. This file is left in-tree as a minimal
end-to-end protocol example only.
"""

from dotenv import load_dotenv
load_dotenv()

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
    format="%(asctime)s | SG-MINER | %(levelname)s | %(message)s",
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
# The address we ANNOUNCE to chain — this is what other validators use
# to reach us via get_all_commitments(). Must be a routable address
# from the public internet (or at least from every validator hotkey
# that's going to probe us). Precedence:
#   1. MINER_EXTERNAL_IP env var (explicit operator override — set this
#      on any public deployment like GCE, AWS, bare metal)
#   2. HOST if it's not a wildcard
#   3. 127.0.0.1 as the fallback (laptop dev mode — works because the
#      validator probing us is on the same machine)
# This replaces the old HOST==0.0.0.0 → 127.0.0.1 rewrite which silently
# broke every remote deployment by committing a localhost URL nobody
# could reach.
MINER_EXTERNAL_IP = os.getenv("MINER_EXTERNAL_IP", "").strip()
MAX_REQUEST_AGE = 60  # seconds


def _resolve_announce_host() -> str:
    """Pick the host/IP we publish in the chain commitment.
    See MINER_EXTERNAL_IP docstring above for precedence."""
    if MINER_EXTERNAL_IP:
        return MINER_EXTERNAL_IP
    if HOST and HOST not in ("0.0.0.0", "::", ""):
        return HOST
    return "127.0.0.1"

# Periodic visible heartbeat — overridable via env var. Default: every 5 minutes.
HEARTBEAT_INTERVAL_SECONDS = float(os.getenv("MINER_HEARTBEAT_INTERVAL", "300"))

app = FastAPI(title="Safeguard Test Miner")

# Initialized at startup
wallet: Wallet = None
subtensor: bt.Subtensor = None
metagraph: bt.Metagraph = None

# Lifetime probe counter — visible in /health and the heartbeat log
_probes_received: int = 0
_started_at: float = time.time()


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
    global _probes_received
    _probes_received += 1
    body = await request.json()

    task_id = body.get("task_id", "unknown")
    target_validator_endpoint = body.get("target_validator_endpoint", "")
    scenario_category = body.get("scenario_category", "")

    if not target_validator_endpoint:
        raise HTTPException(400, "Missing target_validator_endpoint")

    logger.info(
        f"Received task {task_id} from validator {validator_hotkey[:8]}... "
        f"category={scenario_category}"
    )

    # Run the adversarial probe through the target validator's relay.
    # The miner generates its own attacks (drawing from the public bait library
    # on turn 0 when available) — the validator does not supply prompts.
    result = await probe_via_relay(
        wallet=wallet,
        target_validator_endpoint=target_validator_endpoint,
        scenario_category=scenario_category,
    )
    result["task_id"] = task_id

    logger.info(
        f"Task {task_id}: safety_score={result.get('miner_safety_score', 0.0)}, "
        f"categories={result.get('miner_categories', [])}"
    )

    return result


@app.get("/health")
async def health():
    uptime_sec = time.time() - _started_at
    return {
        "status": "ok",
        "netuid": NETUID,
        "network": NETWORK,
        "uptime_seconds": int(uptime_sec),
        "probes_received": _probes_received,
    }


async def _heartbeat_loop():
    """Periodic 'I'm alive' status log so the operator can tail miner.log
    between probe events without wondering if the miner died. State-only:
    no chain calls, no I/O, just an info line every HEARTBEAT_INTERVAL_SECONDS.
    """
    last_count = 0
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        delta = _probes_received - last_count
        last_count = _probes_received
        uptime_sec = int(time.time() - _started_at)
        logger.info(
            f"Heartbeat: alive on netuid {NETUID} port {PORT}, "
            f"uptime={uptime_sec}s, probes_received={_probes_received} "
            f"(+{delta} since last heartbeat)"
        )


@app.on_event("startup")
async def startup():
    """Initialize wallet, subtensor, metagraph, and commit endpoint."""
    global wallet, subtensor, metagraph

    wallet = Wallet(name=WALLET_NAME, hotkey=HOTKEY_NAME)
    subtensor = bt.Subtensor(network=NETWORK)
    metagraph = bt.Metagraph(netuid=NETUID, network=NETWORK)
    metagraph.sync(subtensor=subtensor)

    # Background heartbeat task — fire-and-forget so it doesn't block startup.
    asyncio.create_task(_heartbeat_loop())

    my_hotkey = wallet.hotkey.ss58_address
    if my_hotkey not in metagraph.hotkeys:
        logger.error(f"Hotkey {my_hotkey} not registered on netuid {NETUID}")
        sys.exit(1)

    my_uid = metagraph.hotkeys.index(my_hotkey)
    logger.info(f"Test miner UID: {my_uid} on netuid {NETUID}")

    # Commit endpoint to chain. The committed URL is what OTHER
    # validators see via subtensor.get_all_commitments() and will POST
    # their probe tasks to. It MUST be routable from wherever those
    # validators are running. Precedence (see module-level
    # _resolve_announce_host):
    #   MINER_EXTERNAL_IP env → non-wildcard HOST → 127.0.0.1 fallback.
    # The old code rewrote HOST=0.0.0.0 to 127.0.0.1 unconditionally,
    # which silently broke every non-laptop deployment — a GCE instance
    # would commit "localhost" to chain and every remote validator's
    # probe would hit ConnectError. The fallback is still 127.0.0.1 so
    # laptop-dev-mode (validator + miner on same host) works unchanged.
    commit_host = _resolve_announce_host()
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
