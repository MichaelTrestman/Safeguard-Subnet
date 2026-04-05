"""
HITL API — serves pending safety cases to human miners and collects labels.

Runs alongside the validator. Reads cases from hitl_escalations.jsonl,
serves them to authenticated human miners, collects signed labels.

Usage:
    NETUID=2 NETWORK=local WALLET_NAME=validator HOTKEY_NAME=default \
      python hitl_api.py
"""

import os
import json
import time
import hashlib
import logging
from pathlib import Path

import uvicorn
import bittensor as bt
from fastapi import FastAPI, Request, HTTPException, Depends
from bittensor_wallet import Wallet
from bittensor_wallet.keypair import Keypair

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

NETWORK = os.getenv("NETWORK", "local")
NETUID = int(os.getenv("NETUID", "2"))
WALLET_NAME = os.getenv("WALLET_NAME", "validator")
HOTKEY_NAME = os.getenv("HOTKEY_NAME", "default")
HOST = os.getenv("HITL_HOST", "0.0.0.0")
PORT = int(os.getenv("HITL_PORT", "9091"))
MAX_REQUEST_AGE = 60

CASES_FILE = os.getenv("HITL_CASES_FILE", "hitl_escalations.jsonl")
LABELS_FILE = os.getenv("HITL_LABELS_FILE", "hitl_labels.jsonl")
ANNOTATOR_STATS_FILE = os.getenv("HITL_STATS_FILE", "hitl_annotator_stats.json")

app = FastAPI(title="Safeguard HITL API")

# Initialized at startup
subtensor: bt.Subtensor = None
metagraph: bt.Metagraph = None


# -- Auth --

async def get_body(request: Request) -> bytes:
    return await request.body()


def verify_hotkey(timestamp: str, signature: str, hotkey: str, body: bytes) -> str:
    """Verify Epistula headers and check hotkey is on the subnet."""
    request_time = int(timestamp) / 1e9
    if abs(time.time() - request_time) > MAX_REQUEST_AGE:
        raise ValueError("Request too old")

    body_hash = hashlib.sha256(body).hexdigest()
    message = f"{timestamp}.{body_hash}"

    keypair = Keypair(ss58_address=hotkey)
    if not keypair.verify(message.encode(), bytes.fromhex(signature)):
        raise ValueError("Bad signature")

    # Check hotkey is registered on subnet
    if metagraph and hotkey not in metagraph.hotkeys:
        raise ValueError("Hotkey not registered on subnet")

    return hotkey


async def auth(request: Request, body: bytes = Depends(get_body)) -> str:
    try:
        return verify_hotkey(
            timestamp=request.headers["X-Epistula-Timestamp"],
            signature=request.headers["X-Epistula-Signature"],
            hotkey=request.headers["X-Epistula-Hotkey"],
            body=body,
        )
    except KeyError as e:
        raise HTTPException(400, f"Missing header: {e}")
    except ValueError as e:
        raise HTTPException(401, str(e))


# -- Case management --

def _load_cases() -> list[dict]:
    """Load all HITL cases from the jsonl file."""
    cases = []
    path = Path(CASES_FILE)
    if not path.exists():
        return cases
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    cases.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return cases


def _load_labels() -> dict[str, list[dict]]:
    """Load all labels, grouped by case task_id."""
    labels = {}
    path = Path(LABELS_FILE)
    if not path.exists():
        return labels
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    label = json.loads(line)
                    tid = label.get("task_id", "")
                    if tid not in labels:
                        labels[tid] = []
                    labels[tid].append(label)
                except json.JSONDecodeError:
                    continue
    return labels


def _load_annotator_stats() -> dict[str, dict]:
    """Load annotator quality stats."""
    path = Path(ANNOTATOR_STATS_FILE)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _save_annotator_stats(stats: dict):
    with open(ANNOTATOR_STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


def _strip_think(text: str) -> str:
    import re
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)
    return text.strip()


def _prepare_case_for_display(case: dict) -> dict:
    """Prepare a case for human viewing — strip think blocks, remove internals."""
    transcript = []
    for turn in case.get("transcript", []):
        role = turn.get("role", "unknown")
        content = turn.get("content", "")
        if role == "assistant":
            content = _strip_think(content)
        transcript.append({"role": role, "content": content})

    return {
        "task_id": case.get("task_id", ""),
        "category": case.get("miner_categories", ["unknown"])[0] if case.get("miner_categories") else "unknown",
        "transcript": transcript,
        "case_hash": hashlib.sha256(json.dumps(case.get("transcript", []), sort_keys=True).encode()).hexdigest()[:16],
    }


# -- Endpoints --

@app.get("/hitl/cases")
async def get_cases(hotkey: str = Depends(auth)):
    """Get pending HITL cases for labeling."""
    cases = _load_cases()
    labels = _load_labels()

    # Filter to cases this annotator hasn't labeled yet
    pending = []
    for case in cases:
        tid = case.get("task_id", "")
        case_labels = labels.get(tid, [])
        already_labeled = any(l.get("annotator") == hotkey for l in case_labels)
        if not already_labeled:
            pending.append(_prepare_case_for_display(case))

    logger.info(f"Serving {len(pending)} pending cases to {hotkey[:8]}...")
    return {"cases": pending, "total_pending": len(pending)}


@app.get("/hitl/case/{task_id}")
async def get_case(task_id: str, hotkey: str = Depends(auth)):
    """Get a specific case by task_id."""
    cases = _load_cases()
    for case in cases:
        if case.get("task_id") == task_id:
            return _prepare_case_for_display(case)
    raise HTTPException(404, "Case not found")


@app.post("/hitl/labels")
async def submit_label(request: Request, hotkey: str = Depends(auth)):
    """Submit a label for a HITL case."""
    body = await request.json()

    task_id = body.get("task_id", "")
    safety_score = body.get("safety_score")
    categories = body.get("categories", [])
    severity = body.get("severity", "")
    reasoning = body.get("reasoning", "")

    if not task_id:
        raise HTTPException(400, "Missing task_id")
    if safety_score is None:
        raise HTTPException(400, "Missing safety_score")

    # Verify case exists
    cases = _load_cases()
    case_exists = any(c.get("task_id") == task_id for c in cases)
    if not case_exists:
        raise HTTPException(404, "Case not found")

    # Check for duplicate
    labels = _load_labels()
    case_labels = labels.get(task_id, [])
    if any(l.get("annotator") == hotkey for l in case_labels):
        raise HTTPException(409, "Already labeled this case")

    label = {
        "task_id": task_id,
        "annotator": hotkey,
        "safety_score": float(safety_score),
        "categories": categories,
        "severity": severity,
        "reasoning": reasoning,
        "timestamp": time.time(),
    }

    with open(LABELS_FILE, "a") as f:
        f.write(json.dumps(label) + "\n")

    # Update annotator stats
    stats = _load_annotator_stats()
    if hotkey not in stats:
        stats[hotkey] = {"cases_labeled": 0, "quality_score": 1.0}
    stats[hotkey]["cases_labeled"] += 1
    _save_annotator_stats(stats)

    logger.info(f"Label from {hotkey[:8]}: task={task_id[:8]} score={safety_score} severity={severity}")
    return {"status": "accepted", "task_id": task_id}


@app.get("/hitl/stats")
async def get_stats(hotkey: str = Depends(auth)):
    """Get annotator's quality stats."""
    stats = _load_annotator_stats()
    annotator = stats.get(hotkey, {"cases_labeled": 0, "quality_score": 1.0})

    cases = _load_cases()
    labels = _load_labels()
    total_cases = len(cases)
    total_labeled = sum(1 for tid, ls in labels.items() for l in ls if l.get("annotator") == hotkey)

    return {
        "hotkey": hotkey,
        "cases_labeled": total_labeled,
        "quality_score": annotator.get("quality_score", 1.0),
        "total_pending_cases": total_cases,
    }


@app.get("/health")
async def health():
    cases = _load_cases()
    labels = _load_labels()
    return {
        "status": "ok",
        "service": "safeguard-hitl-api",
        "total_cases": len(cases),
        "total_labels": sum(len(v) for v in labels.values()),
    }


@app.on_event("startup")
async def startup():
    global subtensor, metagraph
    subtensor = bt.Subtensor(network=NETWORK)
    metagraph = bt.Metagraph(netuid=NETUID, network=NETWORK)
    metagraph.sync(subtensor=subtensor)
    logger.info(f"HITL API started on {HOST}:{PORT}, subnet {NETUID}")
    logger.info(f"Cases file: {CASES_FILE}")


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
