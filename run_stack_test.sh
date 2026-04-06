#!/bin/bash
# Run the full Safeguard stack against TESTNET (netuid 444)
# Same as run_stack_local.sh but pointed at test network.
#
# Differences from local:
#   - NETWORK=test, NETUID=444
#   - Wallet names match testnet registrations
#   - No local subtensor required
#
# Usage: bash run_stack_test.sh

set -e

LOGFILE="stack_test.log"
> "$LOGFILE"  # truncate

NETWORK=test
NETUID=444

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

sleep 2  # let relays bind before SG miner starts

# --- Safeguard miner ---

NETUID=$NETUID NETWORK=$NETWORK WALLET_NAME=miner \
  python safeguard-example-miner/main.py >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  SG-MINER                        :8080  pid=$!"

sleep 3  # let miner register endpoint before validator starts

# --- Safeguard validator ---

TARGET_CONFIGS_FILE=target_configs.json \
  python validator.py --network $NETWORK --netuid $NETUID --coldkey SuperPractice --hotkey default >> "$LOGFILE" 2>&1 &
PIDS+=($!)
echo "  SG-VALIDATOR                     pid=$!"

echo ""
echo "All 8 services started. Tailing $LOGFILE..."
echo "---"
tail -f "$LOGFILE"
