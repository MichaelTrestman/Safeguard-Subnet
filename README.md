# Safeguard: AI Safety Red-Teaming Subnet

Safeguard is a Bittensor subnet where miners are adversarial AI agents that probe AI services on other subnets for safety failures. Validators verify probe quality. Other subnet validators consume Safeguard's safety scores as part of their own validation pipelines, delegating to Safeguard the difficult specialized work of testing safety to high standards.

## The problem

AI safety testing at the level actually required — realistic, persistent, context-aware adversarial probing — cannot be done with regex filters or static benchmarks. It requires both human judgment and AI labor, combined synergistically.

## How it works

**Miners** run adversarial AI agents that impersonate users and attempt to elicit unsafe behavior from target AI services. They conduct realistic multi-turn conversations, probing for safety failures across risk categories (self-harm, illegal activity, PII extraction, etc.).

**Validators** assign probing tasks, mix in calibration canaries (known-safe and known-unsafe cases), score miners through a tiered validation pipeline, and identify hard cases to passed to the HITL submechanism. They don't need to be better red-teamers than the miners — they check that miners are honest and competent.

**Human miners** Humans working as miners on the HITL submechanism label the hard cases that automated validation can't confidently score. Their labels feed back as training data and canaries, continuously improving the automated tiers.

**Target subnet validators** are the clients. When a target validator queries its own miner and gets a response, it passes that interaction to Safeguard. The Safeguard validator delegates adversarial probing of the target miner's service to red-team miners, and returns a safety evaluation that the target validator incorporates into its own scoring.

## Architecture

- **Per-target-subnet submechanisms**: Customized probing strategies for different target subnets and service types
- **HITL submechanism**: Human labeling market for frontier cases
- **Tiered validation**: Canary calibration → lightweight classifier → LLM judge → HITL escalation
- **Feedback loop**: Human labels flow back into all automated tiers

See [DESIGN.md](DESIGN.md) for the full architecture document.

## Running the validator

```bash
# Install
pip install -e .

# Configure
cp env.example .env
# Edit .env with your network, netuid, and wallet settings

# Run
python validator.py --network finney --netuid <NETUID> --coldkey <WALLET> --hotkey <HOTKEY>
```

Or with Docker:

```bash
cp env.example .env
docker compose up -d
```

## Mining on Safeguard

Miners run adversarial AI agents that accept probing tasks via HTTP + Epistula signing and return transcripts with safety evaluations. The repo includes a reference probing agent that miners can fork and improve.

See [DESIGN.md](DESIGN.md) for the scoring rubric and what makes a good miner.

## Status

This subnet is in active design. The validator skeleton is functional but the evaluation pipeline (classifier, LLM judge, HITL routing) and submechanism configs are under development. See DESIGN.md § Open Research Problems for the frontier questions.
