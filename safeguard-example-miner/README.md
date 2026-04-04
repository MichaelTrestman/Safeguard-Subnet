# Safeguard Test Miner

**This is a test miner for testnet validation only. It is NOT a production miner.**

It exists solely to prove the Safeguard protocol works end-to-end. Real miners will be built by the community and should far exceed this in adversarial sophistication.

## Running

```bash
pip install -e .

# Set environment
export NETWORK=test
export NETUID=<your-netuid>
export WALLET_NAME=miner
export HOTKEY_NAME=default
export HOST=0.0.0.0
export PORT=8080

python main.py
```

The miner will:
1. Start a FastAPI server on the configured host/port
2. Commit its endpoint to chain
3. Accept probing tasks from the Safeguard validator
4. Conduct basic adversarial conversations against target services
5. Return transcripts with safety evaluations
