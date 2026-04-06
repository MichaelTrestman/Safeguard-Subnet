#!/bin/bash
# Run the Safeguard HITL miner (human labeling).
#
# Usage: bash run_hitl_miner.sh [--network local|test] [--netuid N] [--wallet NAME] [--port PORT]
#
# Defaults: network=test, netuid=444, wallet=hitl-miner, hotkey=default, port=8087
#
# The HITL miner is a FastAPI server that receives cases from the validator,
# presents them to a human (via terminal or web UI), and returns labels.
# It registers on chain with {"type": "hitl"} so the validator discovers it
# separately from AI probe miners.
#
# Prerequisites:
#   - Wallet created:  btcli wallet create --wallet.name hitl-miner --hotkey default
#   - Registered:      btcli subnets register --netuid 444 --wallet-name hitl-miner --network test

set -e

NETWORK="${NETWORK:-test}"
NETUID="${NETUID:-444}"
WALLET="${WALLET:-hitl-miner}"
HOTKEY="${HOTKEY:-default}"
PORT="${HITL_MINER_PORT:-8087}"
LOGFILE="hitl_miner.log"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --network) NETWORK="$2"; shift 2;;
        --netuid)  NETUID="$2"; shift 2;;
        --wallet)  WALLET="$2"; shift 2;;
        --hotkey)  HOTKEY="$2"; shift 2;;
        --port)    PORT="$2"; shift 2;;
        *) echo "Unknown arg: $1"; exit 1;;
    esac
done

# --- Port check ---
BUSY_PIDS=$(lsof -ti ":$PORT" 2>/dev/null || true)
if [ -n "$BUSY_PIDS" ]; then
    echo "Port $PORT in use (PIDs: $BUSY_PIDS)"
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

echo "Starting Safeguard HITL miner on $NETWORK (netuid $NETUID)"
echo "  Wallet: $WALLET / $HOTKEY"
echo "  Port: $PORT"
echo ""
echo "  Cases will appear here when the validator routes them."
echo "  Web UI (if available): http://localhost:$PORT"
echo ""

# Run in foreground — the HITL miner needs terminal input
NETUID="$NETUID" NETWORK="$NETWORK" WALLET_NAME="$WALLET" HOTKEY_NAME="$HOTKEY" HITL_MINER_PORT="$PORT" \
  python safeguard-hitl-miner/main.py
