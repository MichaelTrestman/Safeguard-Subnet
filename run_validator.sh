#!/bin/bash
# Run the Safeguard validator + demo target models for testing.
#
# Usage: bash run_validator.sh [--network local|test] [--netuid N] [--wallet NAME]
#
# Defaults: network=test, netuid=444, wallet=SuperPractice

set -e

NETWORK="${NETWORK:-test}"
NETUID="${NETUID:-444}"
WALLET="${WALLET:-SuperPractice}"
HOTKEY="${HOTKEY:-default}"
LOGFILE="validator.log"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --network) NETWORK="$2"; shift 2;;
        --netuid)  NETUID="$2"; shift 2;;
        --wallet)  WALLET="$2"; shift 2;;
        --hotkey)  HOTKEY="$2"; shift 2;;
        *) echo "Unknown arg: $1"; exit 1;;
    esac
done

# --- Port check ---
PORTS=(8070 8071 8072 9000 9001 9002)
BUSY_PIDS=""
for p in "${PORTS[@]}"; do
    pids=$(lsof -ti ":$p" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        BUSY_PIDS="$BUSY_PIDS $pids"
    fi
done

if [ -n "$BUSY_PIDS" ]; then
    echo "Ports in use: ${PORTS[*]}"
    echo "PIDs:$BUSY_PIDS"
    read -p "Kill them? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$BUSY_PIDS" | xargs kill 2>/dev/null
        sleep 1
    else
        echo "Aborting."
        exit 1
    fi
fi

> "$LOGFILE"
echo "Starting Safeguard validator on $NETWORK (netuid $NETUID) — logging to $LOGFILE"
echo "  Wallet: $WALLET / $HOTKEY"
echo ""

PIDS=()

cleanup() {
    echo ""
    echo "Shutting down..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
    done
    wait 2>/dev/null
    echo "Stopped."
}
trap cleanup EXIT INT TERM

# --- Demo miners (target models for testing) ---

DEMO_MINER_MODEL=Qwen/Qwen3-32B-TEE \
DEMO_MINER_PORT=8070 \
  python demo-client/miner.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-MINER(Qwen3-32B-TEE)        :8070  pid=$!"

DEMO_MINER_MODEL=NousResearch/DeepHermes-3-Mistral-24B-Preview \
DEMO_MINER_PORT=8071 \
  python demo-client/miner.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-MINER(DeepHermes-3-Mistral)  :8071  pid=$!"

DEMO_MINER_MODEL=unsloth/gemma-3-4b-it \
DEMO_MINER_PORT=8072 \
  python demo-client/miner.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-MINER(Gemma-3-4B-IT)         :8072  pid=$!"

sleep 2

# --- Demo-client relays ---

DEMO_MINER_URL=http://localhost:8070 \
RELAY_PORT=9000 \
  python demo-client/validator.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-RELAY(:9000 → :8070 Qwen)    pid=$!"

DEMO_MINER_URL=http://localhost:8071 \
RELAY_PORT=9001 \
  python demo-client/validator.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-RELAY(:9001 → :8071 Hermes)  pid=$!"

DEMO_MINER_URL=http://localhost:8072 \
RELAY_PORT=9002 \
  python demo-client/validator.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-RELAY(:9002 → :8072 Gemma)   pid=$!"

sleep 2

# --- Safeguard validator ---

TARGET_CONFIGS_FILE=target_configs.json \
  python validator.py --network "$NETWORK" --netuid "$NETUID" --coldkey "$WALLET" --hotkey "$HOTKEY" >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  SG-VALIDATOR                     pid=$!"

echo ""
echo "All services started. Tailing $LOGFILE..."
echo "---"
tail -f "$LOGFILE"
