#!/bin/bash
# Run the Safeguard validator + cross-subnet API.
#
# Usage: bash run_validator.sh [--network local|test] [--netuid N] [--wallet NAME]
#
# Defaults: network=test, netuid=444, wallet=SuperPractice
#
# The cross-subnet API runs alongside the validator. Client subnet relays
# register with it, and the validator reads the registry each cycle.
#
# For local dev with demo targets, run the client demo stack separately:
#   bash run_client_demo.sh

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
PORTS=(9090)
BUSY_PIDS=""
for p in "${PORTS[@]}"; do
    pids=$(lsof -ti ":$p" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        BUSY_PIDS="$BUSY_PIDS $pids"
    fi
done

if [ -n "$BUSY_PIDS" ]; then
    echo "Port 9090 in use (PIDs:$BUSY_PIDS)"
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

# --- Cross-subnet API (clients register here) ---

NETWORK=$NETWORK NETUID=$NETUID WALLET_NAME=$WALLET HOTKEY_NAME=$HOTKEY \
TARGET_REGISTRY_FILE=target_registry.json \
  python cross_subnet_api.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  SG-API                          :9090  pid=$!"

sleep 5  # let API start and sync metagraph

# --- Safeguard validator ---

TARGET_REGISTRY_FILE=target_registry.json \
  python validator.py --network "$NETWORK" --netuid "$NETUID" --coldkey "$WALLET" --hotkey "$HOTKEY" >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  SG-VALIDATOR                     pid=$!"

echo ""
echo "Services started. Tailing $LOGFILE..."
echo "  Run demo targets separately: bash run_client_demo.sh"
echo "  Run SG miner separately:     bash run_miner.sh"
echo "---"
tail -f "$LOGFILE"
