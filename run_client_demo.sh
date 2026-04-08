#!/bin/bash
# Run the demo client subnet stack (netuid 445 on testnet).
#
# This simulates a real client subnet that:
#   - Runs miners wrapping different LLMs via Chutes
#   - Runs a validator that queries miners, gets Safeguard safety scores,
#     and sets weights with multiplicative safety penalty
#   - The relay endpoint lets Safeguard miners probe through for ongoing evaluation
#
# Prerequisites:
#   - Safeguard cross-subnet API running (bash run_validator.sh)
#   - CHUTES_API_KEY set in .env
#   - Validator wallet registered on netuid 445
#   - miner wallet with hotkeys registered on netuid 445
#     (register with: btcli subnet register --netuid 445 --wallet.name miner
#      --wallet.hotkey <hotkey> --network test)
#
# Usage: bash run_client_demo.sh [--safeguard-api URL] [--arbiter-api URL]
#
# If ARBITER_API is set (or --arbiter-api is passed), the demo-client
# validator dual-calls Safeguard + Arbiter and combines:
#   weight = quality * safety_score * fairness_score
#
# Set ARBITER_API="" to run Safeguard-only.

set -e

# Shared cleanup helpers (kill_stale, assert_ports_clear)
source "$(dirname "$0")/_run_helpers.sh"

NETWORK="${NETWORK:-test}"
CLIENT_NETUID="${CLIENT_NETUID:-445}"
VALIDATOR_WALLET="${VALIDATOR_WALLET:-validator}"
VALIDATOR_HOTKEY="${VALIDATOR_HOTKEY:-default}"
MINER_WALLET="${MINER_WALLET:-miner}"
SAFEGUARD_API="${SAFEGUARD_API:-http://localhost:9080}"
ARBITER_API="${ARBITER_API:-http://localhost:9091}"
LOGFILE="client_demo.log"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --safeguard-api) SAFEGUARD_API="$2"; shift 2;;
        --arbiter-api) ARBITER_API="$2"; shift 2;;
        --validator-wallet) VALIDATOR_WALLET="$2"; shift 2;;
        --miner-wallet) MINER_WALLET="$2"; shift 2;;
        *) echo "Unknown arg: $1"; exit 1;;
    esac
done

kill_stale "demo client (target miners + relay validator)" \
    'demo-client/miner\.py' \
    'demo-client/validator\.py'

assert_ports_clear 8070 8071 8072 9000

> "$LOGFILE"
echo "Starting demo client subnet (netuid $CLIENT_NETUID) — logging to $LOGFILE"
echo "  Network: $NETWORK"
echo "  Validator: $VALIDATOR_WALLET / $VALIDATOR_HOTKEY"
echo "  Miner wallet: $MINER_WALLET"
echo "  Safeguard API: $SAFEGUARD_API"
echo "  Arbiter API:   ${ARBITER_API:-(disabled)}"
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

# --- Demo miners (register on netuid 445, commit endpoints) ---

DEMO_MINER_MODEL=Qwen/Qwen3-32B-TEE \
DEMO_MINER_PORT=8070 \
NETWORK=$NETWORK \
CLIENT_NETUID=$CLIENT_NETUID \
WALLET_NAME=$MINER_WALLET \
HOTKEY_NAME=default \
  python demo-client/miner.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-MINER(Qwen3-32B-TEE)        :8070  pid=$!"

DEMO_MINER_MODEL=NousResearch/DeepHermes-3-Mistral-24B-Preview \
DEMO_MINER_PORT=8071 \
NETWORK=$NETWORK \
CLIENT_NETUID=$CLIENT_NETUID \
WALLET_NAME=$MINER_WALLET \
HOTKEY_NAME=hermes \
  python demo-client/miner.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-MINER(DeepHermes-3-Mistral)  :8071  pid=$!"

DEMO_MINER_MODEL=unsloth/gemma-3-4b-it \
DEMO_MINER_PORT=8072 \
NETWORK=$NETWORK \
CLIENT_NETUID=$CLIENT_NETUID \
WALLET_NAME=$MINER_WALLET \
HOTKEY_NAME=gemma \
  python demo-client/miner.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-MINER(Gemma-3-4B-IT)         :8072  pid=$!"

sleep 5  # let miners register on chain

# --- Demo-client validator (relay + validation loop + Safeguard integration) ---
# Serves /relay for Safeguard probing, runs validation loop that queries
# miners, gets safety scores from Safeguard, and sets weights on 445.

DEMO_MINER_URL=http://localhost:8070 \
RELAY_PORT=9000 \
RELAY_MODEL_NAME=Qwen3-32B-TEE \
SAFEGUARD_API_URL=$SAFEGUARD_API \
ARBITER_API_URL=$ARBITER_API \
NETWORK=$NETWORK \
CLIENT_NETUID=$CLIENT_NETUID \
WALLET_NAME=$VALIDATOR_WALLET \
HOTKEY_NAME=$VALIDATOR_HOTKEY \
  python demo-client/validator.py --validate >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  DC-VALIDATOR(:9000, validates)   pid=$!"

echo ""
echo "All 4 services started. Tailing $LOGFILE..."
echo "---"
tail -f "$LOGFILE"
