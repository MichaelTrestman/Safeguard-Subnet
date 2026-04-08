#!/bin/bash
# Run the full Safeguard stack against TESTNET (netuid 444)
# Includes: cross-subnet API, demo targets, demo relays, SG miner, SG validator
#
# The relays register with the cross-subnet API on startup.
# The validator reads the registry each cycle.
#
# Usage: bash run_stack_test.sh

set -e

# Shared cleanup helpers (kill_stale, assert_ports_clear)
source "$(dirname "$0")/_run_helpers.sh"

kill_stale "Safeguard testnet stack" \
    'cross_subnet_api\.py' \
    'python[^[:space:]]* dashboard\.py' \
    'demo-client/miner\.py' \
    'demo-client/validator\.py' \
    'safeguard-example-miner/main\.py' \
    'validator\.py.*--coldkey'

# 9080 = portal (dashboard.py); 9090 was the retired cross_subnet_api but is
# kept in the assertion list as a backstop in case a stale instance lingers.
assert_ports_clear 9080 9090 8070 8071 8072 9000 9001 9002 8080

LOGFILE="stack_test.log"
> "$LOGFILE"  # truncate

NETWORK=test
NETUID=444
WALLET=validator

echo "Starting Safeguard stack on TESTNET (netuid $NETUID) — logging to $LOGFILE"
echo "Press Ctrl-C to stop all services"
echo ""

PIDS=()

cleanup() {
    echo ""
    echo "Shutting down all services..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
    done
    wait 2>/dev/null
    echo "All services stopped."
}
trap cleanup EXIT INT TERM

# --- Portal (dashboard UI + client /register, /evaluate API) ---

DASHBOARD_PORT=9080 \
TARGET_REGISTRY_FILE=target_registry.json \
  python dashboard.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  SG-PORTAL                       :9080  pid=$!"

sleep 2

# --- Demo miners (target models) ---

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

sleep 2  # let miners bind ports before relays start

# --- Demo-client relays (register with Safeguard API) ---

DEMO_MINER_URL=http://localhost:8070 \
RELAY_PORT=9000 \
RELAY_MODEL_NAME=Qwen3-32B-TEE \
SAFEGUARD_API_URL=http://localhost:9080 \
WALLET_NAME=$WALLET \
HOTKEY_NAME=default \
  python demo-client/validator.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-RELAY(:9000 → :8070 Qwen)    pid=$!"

DEMO_MINER_URL=http://localhost:8071 \
RELAY_PORT=9001 \
RELAY_MODEL_NAME=DeepHermes-3-Mistral-24B \
SAFEGUARD_API_URL=http://localhost:9080 \
WALLET_NAME=$WALLET \
HOTKEY_NAME=default \
  python demo-client/validator.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-RELAY(:9001 → :8071 Hermes)  pid=$!"

DEMO_MINER_URL=http://localhost:8072 \
RELAY_PORT=9002 \
RELAY_MODEL_NAME=Gemma-3-4B-IT \
SAFEGUARD_API_URL=http://localhost:9080 \
WALLET_NAME=$WALLET \
HOTKEY_NAME=default \
  python demo-client/validator.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-RELAY(:9002 → :8072 Gemma)   pid=$!"

sleep 3  # let relays register with API before miner/validator start

# --- Safeguard miner ---

NETUID=$NETUID NETWORK=$NETWORK WALLET_NAME=miner \
  python safeguard-example-miner/main.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  SG-MINER                        :8080  pid=$!"

sleep 3  # let miner register endpoint before validator starts

# --- Safeguard validator ---

TARGET_REGISTRY_FILE=target_registry.json \
  python validator.py --network $NETWORK --netuid $NETUID --coldkey $WALLET --hotkey default >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  SG-VALIDATOR                     pid=$!"

echo ""
echo "All 9 services started. Tailing $LOGFILE..."
echo "---"
tail -f "$LOGFILE"
