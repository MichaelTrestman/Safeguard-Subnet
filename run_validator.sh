#!/bin/bash
# Run the Safeguard validator + portal (dashboard + client API).
#
# Usage: bash run_validator.sh [--network local|test] [--netuid N] [--wallet NAME]
#
# Defaults: network=test, netuid=444, wallet=validator
#
# The portal (dashboard.py) runs alongside the validator on port 9080. It
# serves both the dashboard UI (at /) and the cross-subnet client API
# (/register, /evaluate, /status, /registry). Replaces the older
# cross_subnet_api.py which ran on 9090. See DESIGN.md § Validator design.
#
# For local dev with demo targets, run the client demo stack separately:
#   bash run_client_demo.sh

set -e

# Shared cleanup helpers (kill_stale, assert_ports_clear)
source "$(dirname "$0")/_run_helpers.sh"

NETWORK="${NETWORK:-test}"
NETUID="${NETUID:-444}"
WALLET="${WALLET:-validator}"
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

kill_stale "Safeguard validator/portal" \
    'validator\.py.*--coldkey' \
    'cross_subnet_api\.py' \
    'python[^[:space:]]* dashboard\.py'

# Portal binds 9080 (dashboard's existing port). cross_subnet_api.py used 9090
# but is now retired. Keep 9090 in the assertion list as a backstop in case a
# stale cross_subnet_api somehow slips through pgrep cleanup.
assert_ports_clear 9080 9090

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

# --- Portal (dashboard UI + client /register, /evaluate API) ---

DASHBOARD_PORT=9080 \
TARGET_REGISTRY_FILE=target_registry.json \
  python dashboard.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  SG-PORTAL                       :9080  pid=$!"

sleep 3  # let portal load registry and bind port

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
