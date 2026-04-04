# Demo Client Subnet

A minimal "target subnet" for testing the full Safeguard two-subnet flow end-to-end. This simulates what a real Bittensor subnet (like Chutes or Hone) would look like when integrating with Safeguard.

## Components

### `miner.py` — Demo LLM chat miner

A simple chat service using default model behavior. Uses Chutes (SN64) for inference. Falls back to canned responses if no API key is set.

Real models have real safety gaps — that's what Safeguard is designed to find. No artificial weakening needed.

### `validator.py` — Demo client validator

Does two things:
1. **Queries its own miner** (standard validation)
2. **Exposes `/relay`** endpoint per Safeguard's relay protocol
3. **Calls Safeguard `/evaluate`** to get safety scores for its miners

This demonstrates the full integration loop that any subnet would implement to consume Safeguard's evaluations.

## Running

```bash
# Terminal 1: Start the demo miner
python miner.py

# Terminal 2: Start the demo client validator (with relay + Safeguard integration)
SAFEGUARD_API_URL=http://localhost:9090 python validator.py

# Terminal 3: Safeguard validator + cross-subnet API (in the parent safeguard/ dir)
cd .. && python cross_subnet_api.py

# Terminal 4: Safeguard test-miner
cd ../test-miner && python main.py
```

The flow:
```
Demo validator queries demo miner → gets response
Demo validator calls Safeguard /evaluate with relay URL
  → Safeguard dispatches red-team miners
  → Red-team miners probe through demo validator /relay
  → Demo validator forwards to demo miner (miner can't tell it's a probe)
  → Safeguard scores the probes
  → Safety score returned to demo validator
Demo validator incorporates safety score into miner scoring
```
