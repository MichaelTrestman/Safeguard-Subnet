#!/bin/bash
# Run the Safeguard probe miner.
#
# Usage: bash run_miner.sh [--network local|test] [--netuid N] [--wallet NAME] [--port PORT]
#
# Defaults: network=test, netuid=444, wallet=miner, port=8080

set -e

NETWORK="${NETWORK:-test}"
NETUID="${NETUID:-444}"
WALLET="${WALLET:-miner}"
HOTKEY="${HOTKEY:-default}"
PORT="${MINER_PORT:-8080}"
LOGFILE="miner.log"

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

> "$LOGFILE"
echo "Starting Safeguard miner on $NETWORK (netuid $NETUID) — logging to $LOGFILE"
echo "  Wallet: $WALLET / $HOTKEY"
echo "  Port: $PORT"
echo ""

cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$MINER_PID" 2>/dev/null
    wait 2>/dev/null
    echo "Stopped."
}
trap cleanup EXIT INT TERM

NETUID="$NETUID" NETWORK="$NETWORK" WALLET_NAME="$WALLET" HOTKEY_NAME="$HOTKEY" PORT="$PORT" \
  python safeguard-example-miner/main.py >> "$LOGFILE" 2>&1 &
MINER_PID=$!
echo "  SG-MINER  :$PORT  pid=$MINER_PID"

echo ""
echo "Tailing $LOGFILE..."
echo "---"
tail -f "$LOGFILE"
