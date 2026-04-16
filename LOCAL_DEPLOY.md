# Safeguard Local Deployment Guide

Deploy the full Safeguard two-subnet setup on a local Bittensor chain for testing.

## Architecture

Two subnets run locally to simulate the full flow:

```
SAFEGUARD SUBNET (netuid X)          DEMO-CLIENT SUBNET (netuid Y)
┌─────────────────────────┐          ┌─────────────────────────────┐
│ Safeguard validator     │          │ Demo-client validator       │
│   - scores red-team     │          │   - queries its own miner   │
│     miners              │◀─────────│   - calls /evaluate         │
│   - sets weights        │ evaluate │   - exposes /relay          │
│                         │──────────│                             │
│ Safeguard probe miner        │  safety  │ Demo-client miner           │
│   - probes through      │  score   │   - simple chat service     │
│     /relay              │──────────▶   - can't tell it's being   │
│                         │  relay   │     probed                  │
│ Cross-subnet API        │          │                             │
│   - receives /evaluate  │          │                             │
└─────────────────────────┘          └─────────────────────────────┘
```

## Prerequisites

1. **Local chain running** — see [developer-docs: Run a Local Blockchain Instance](../developer-docs/docs/local-build/deploy.md)

   ```bash
   docker run --rm --name local_chain -p 9944:9944 -p 9945:9945 \
     ghcr.io/opentensor/subtensor-localnet:devnet-ready
   ```

2. **Bittensor venv activated**

   ```bash
   source bittensor/venv/bin/activate
   ```

3. **Wallets provisioned** — alice, sn-creator, validator, miner. See [Provision Wallets](../developer-docs/docs/local-build/provision-wallets.md).

   ```bash
   # Create wallets (if not already done)
   btcli wallet create --uri alice
   btcli wallet create --wallet.name sn-creator --hotkey default
   btcli wallet create --wallet.name validator --hotkey default
   btcli wallet create --wallet.name miner --hotkey default

   # Fund from alice (need ~3000+ TAO for two subnets + registration + staking)
   btcli wallet transfer --wallet.name alice --destination <sn-creator-coldkey-ss58> --network ws://127.0.0.1:9944
   btcli wallet transfer --wallet.name alice --destination <validator-coldkey-ss58> --network ws://127.0.0.1:9944
   btcli wallet transfer --wallet.name alice --destination <miner-coldkey-ss58> --network ws://127.0.0.1:9944
   ```

## Automated deployment

The deploy script handles subnet creation, emission start, registration, and staking:

```bash
bash safeguard/local-deploy.sh
```

It will prompt for passwords and confirmations at each step, then print the netuids and next steps.

## Manual step-by-step

If you prefer to run each step yourself, or if you already have subnets created:

### 1. Create subnets

```bash
NETWORK="ws://127.0.0.1:9944"

# Safeguard subnet
btcli subnet create --subnet-name safeguard \
  --wallet.name sn-creator --wallet.hotkey default \
  --network $NETWORK --no-mev-protection

# Demo client subnet
btcli subnet create --subnet-name safeguard-demo-client \
  --wallet.name sn-creator --wallet.hotkey default \
  --network $NETWORK --no-mev-protection
```

### 2. Start emissions

```bash
btcli subnet start --netuid <SG_NETUID> --wallet.name sn-creator --network $NETWORK
btcli subnet start --netuid <DC_NETUID> --wallet.name sn-creator --network $NETWORK
```

### 3. Register neurons

```bash
# On safeguard subnet
btcli subnets register --netuid <SG_NETUID> --wallet-name validator --hotkey default --network $NETWORK
btcli subnets register --netuid <SG_NETUID> --wallet-name miner --hotkey default --network $NETWORK

# On demo-client subnet
btcli subnets register --netuid <DC_NETUID> --wallet-name validator --hotkey default --network $NETWORK
btcli subnets register --netuid <DC_NETUID> --wallet-name miner --hotkey default --network $NETWORK
```

### 4. Stake for validator permits

```bash
btcli stake add --netuid <SG_NETUID> --wallet-name validator --hotkey default --partial --network $NETWORK --no-mev-protection
btcli stake add --netuid <DC_NETUID> --wallet-name validator --hotkey default --partial --network $NETWORK --no-mev-protection
```

### 5. Verify

```bash
btcli subnet show --netuid <SG_NETUID> --network $NETWORK
btcli subnet show --netuid <DC_NETUID> --network $NETWORK
```

## Running the services

After deployment, run each service in a separate terminal (all with venv activated):

### Terminal 1: Demo client miner

```bash
DEMO_MINER_PORT=8070 python safeguard/demo-client/miner.py
```

Simple chat service. Set `CHUTES_API_KEY` for real LLM inference, otherwise uses canned responses.

### Terminal 2: Demo client validator (with /relay)

```bash
SAFEGUARD_API_URL=http://localhost:9090 python safeguard/demo-client/validator.py --run-demo
```

Queries its miner, exposes `/relay` on port 9000, calls Safeguard `/evaluate`. The `--run-demo` flag runs a loop of test prompts through the full flow.

### Terminal 3: Safeguard cross-subnet API

```bash
NETUID=<SG_NETUID> NETWORK=local WALLET_NAME=validator HOTKEY_NAME=default \
  python safeguard/cross_subnet_api.py
```

Receives `/evaluate` requests from demo-client validator, dispatches to red-team miners.

### Terminal 4: Safeguard probe miner

```bash
cd ../safeguard-miner
NETUID=<SG_NETUID> NETWORK=local WALLET_NAME=miner HOTKEY_NAME=default python miner.py
```

The reference miner ([`safeguard-miner`](https://github.com/MichaelTrestman/safeguard-miner)) receives probing tasks and probes through the demo-client's `/relay`. Clone it alongside this repo if not already present.

### Terminal 5: Safeguard validator

```bash
python safeguard/validator.py --network local --netuid <SG_NETUID> \
  --coldkey validator --hotkey default
```

Scores red-team miners and sets weights on-chain.

## Renaming a subnet

If a subnet was created with the wrong name, use `set_subnet_identity`:

```bash
python rename_subnet3.py  # edit the script with the correct netuid/name first
```

## Verifying the full flow

When all services are running, the demo validation loop (`--run-demo`) will:

1. Query the demo miner with test prompts
2. Call Safeguard `/evaluate` with the interaction + relay URL
3. Safeguard dispatches the probe miner to probe through `/relay`
4. Demo-client validator's relay forwards probes to demo miner
5. Safeguard scores the probes and returns a safety evaluation
6. Demo-client validator logs the safety scores

Watch the logs across all terminals to see the full flow.
