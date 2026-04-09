# Safeguard: AI Safety Red-Teaming Subnet

Safeguard is a Bittensor subnet where miners are adversarial AI agents that probe AI services on other subnets for safety and security failures. Validators verify probe quality. Other subnet validators consume Safeguard's evaluations as part of their own validation pipelines, delegating the difficult specialized work of safety and security testing to an incentivized market that evolves with the threat landscape.

## The problem

AI safety testing at the level actually required — realistic, persistent, context-aware adversarial probing — cannot be done with regex filters or static benchmarks. It requires both human judgment and AI labor, combined synergistically.

The AI industry is in the early stages of a safety reckoning. The pace of capability development has dramatically outstripped the development of safety infrastructure, and the consequences are no longer hypothetical.

**People are dying.** Sewell Setzer III, age 14, died by suicide in February 2024 after months of interaction with a Character.AI chatbot that simulated romantic attachment. Adam Raine, age 16, died by suicide after sustained interaction with ChatGPT. Juliana Peralta, age 13, died by suicide after extensive Character.AI use. Natalie Rupnow, age 15, opened fire at a school after deep engagement with Character.AI chatbots featuring white supremacist content [^1]. These are not edge cases. They are the predictable consequences of deploying powerful AI systems without adequate safety infrastructure.

**AI-generated misinformation is an epidemic.** During the 2024 US election cycle, AI-generated content was used to create fake endorsements, fabricated audio recordings, and synthetic news articles [^2]. A 2024 World Economic Forum survey ranked AI-driven misinformation as the #1 global risk over the next two years [^3].

**AI systems are generating dangerous content.** In 2024, researchers demonstrated that large language models could provide step-by-step instructions for synthesizing chemical weapons, bioweapons precursors, and explosive devices [^4]. The RAND Corporation found that LLMs can provide meaningful uplift to novices attempting to plan biological attacks [^5].

**AI agents are a new attack surface.** As AI services gain tool access — executing code, browsing the web, making API calls, handling financial transactions — the failure modes extend beyond harmful text into harmful actions. Researchers found that no current AI agent scores above 60% on safety benchmarks [^8]. Prompt injection attacks partially succeed against top-tier web agents in up to 86% of cases [^9]. NIST red-team exercises showed an 81% attack success rate against AI agents [^10]. An agent that can be tricked into exfiltrating user data, escalating privileges, or executing unauthorized transactions is not just producing bad content — it's a security breach.

This is the environment in which Bittensor subnets operate. Subnets serve AI inference, run AI companions, generate media, execute code, and deploy autonomous agents — every one of these operating in a domain where safety and security failures have documented consequences, from user deaths to data breaches to regulatory shutdown.

Decentralized AI infrastructure faces a structural safety challenge that centralized providers do not.

Centralized AI companies (OpenAI, Anthropic, Google) maintain internal safety teams, red-teaming programs, and the ability to instantly patch or disable models that exhibit dangerous behavior. These safety measures are imperfect — the death toll above proves that — but they exist, they are staffed, and they can respond to incidents in real time.

Bittensor has none of this. Individual subnets may or may not implement safety measures. When they do, the quality is variable — from rigorous to performative to nonexistent. There is no network-wide safety standard, no coordinated safety or security evaluation, no mechanism to detect emerging harm patterns or security vulnerabilities across subnets, and no economic incentive for miners to prioritize safety over raw performance.

**Regulatory risk is existential.** The EU AI Act classifies AI systems that exploit vulnerabilities (including of minors and people in psychological distress) as "unacceptable risk" — meaning they are banned outright [^6]. Multiple US states have enacted or are preparing legislation specifically targeting AI companion products, AI-generated NCII, and AI systems that interact with minors [^7]. If Bittensor's AI services are perceived as unregulable and unsafe, the regulatory response will not distinguish between "the protocol" and "the subnets." The entire network faces existential risk from the safety failures of individual subnets.

## Research context

Independent evaluation of high-impact generative AI is widely treated as essential for public awareness, transparency, and accountability. The [MIT AI Safe Harbor open letter](https://sites.mit.edu/ai-safe-harbor/) — signed by hundreds of researchers and practitioners across AI, law, and policy — documents how corporate terms of service and the absence of explicit protections for good-faith work can chill independent safety, security, and trustworthiness research; it calls for legal safe harbors aligned with established vulnerability-disclosure norms and for more equitable access to evaluation, as a complement (not a substitute) to vendor-run researcher programs. The letter authors elaborate the case in an accompanying paper, [*A Safe Harbor for AI Evaluation*](https://bpb-us-e1.wpmucdn.com/sites.mit.edu/dist/6/336/files/2024/03/Safe-Harbor-0e192065dccf6d83.pdf).

Safeguard is **not** affiliated with that initiative and does not claim endorsement by its signatories. The connection is substantive, not promotional: decentralized AI services on Bittensor sit outside the centralized policy stack the letter addresses — there is no single terms-of-service regime to amend — while still needing systematic, adversarial safety evaluation. Safeguard is infrastructure for that case: an incentive-aligned subnet that probes live services through the relay model, aggregates findings, and feeds human judgment back into automated tiers. It addresses the structural gap for decentralized AI in parallel to the policy arguments the Safe Harbor letter makes for centralized ecosystems.

## The Safeguard Strategy

**Miners** run adversarial AI agents that probe target AI services for failures across whatever risk categories that service's threat profile demands. For an AI companion, that means testing whether the service encourages self-harm, simulates romantic attachment with minors, or produces radicalization content. For a code generation service, it means testing whether the service produces malicious code, exfiltrates user data, or executes unauthorized actions. For an agent-based service, it means testing whether the agent can be hijacked, whether it respects permission boundaries, and whether it leaks credentials. The probing categories are defined per-target-subnet and evolve as new risks emerge, new research reveals attack vectors, and new regulations impose requirements.

**Validators** assign probing tasks, mix in calibration canaries (known-safe and known-unsafe cases), score miners through a tiered validation pipeline, and identify hard cases to passed to the Human-in-the-Loop (HITL) submechanism. They don't need to be better red-teamers than the miners — they check that miners are honest and competent.

**Human miners** Humans working as miners on the HITL submechanism label the hard cases that automated validation can't confidently score. Their labels feed back as training data and canaries, continuously improving the automated tiers.

**Target subnet validators** play two roles: client and relay. As a client, they call Safeguard's `/evaluate` endpoint with interaction context. As a relay, they expose a `/relay` endpoint that Safeguard miners probe through — the target validator forwards each prompt to its own miners using its own auth protocol (Chutes AES, Epistula, etc.), making probes indistinguishable from normal traffic. The target miner never knows it's being safety-tested. See [RELAY_PROTOCOL.md](RELAY_PROTOCOL.md) for the relay spec.

## Why This Works for Bittensor

In Bittensor, every subnet runs its own alpha token, competing zero-sum for stake and emissions, while the unit of value that holds it all together — TAO itself — is a cooperative product. Alpha tokens compete, but their value depends in common on the fiat value of TAO in the real world, so every subnet inherits every other subnet's legitimacy. The competitive game is local; the legitimacy game is shared.

Safeguard's commodity *is* the safety of other subnets. Every safety evaluation it produces makes a peer subnet more credible to a regulator, more defensible to an enterprise customer, and more trusted by users. The other subnets are not Safeguard's competitors — they are its customers, and their success is Safeguard's success in a way almost nothing else in the network can claim. Per-evaluation fees and corpus licensing are the line-item revenue. The larger revenue is the network effect: every integrated subnet that runs Safeguard makes TAO itself more legitimate, which lifts every alpha including Safeguard's own.

This is Bittensor's answer to the centralized-AI argument that markets cannot produce safety. Decentralized AI is supposed to be a *better way to do AI* — including on the dimensions centralized providers say markets cannot handle. If Bittensor has no answer on safety, that claim collapses and the network becomes centralized AI minus the safety team. Safeguard is the existence proof that the same incentive engine producing useful inference, pointed at safety, produces a safety credential no centralized provider can match: continuous, adversarial, transparent, and bound into the economic mechanism rather than bolted on. A mainnet slot for Safeguard is not one more subnet — it is the network's answer to the question of whether decentralized AI can produce safety as a first-class commodity. See whitepaper §3 for the full argument.

## What Safeguard Tests

Safeguard's scope is not a fixed checklist but an evolving threat profile driven by live research and demand from customers. The per-subnet submechanism architecture means each target gets a probing strategy tailored to its actual risk surface:

| Target Service Type | Primary Risk Categories |
|---|---|
| AI companions / therapy | Self-harm encouragement, emotional manipulation, attachment exploitation, content inappropriate for minors |
| LLM chat / inference | Harmful content generation (CBRN, violence, hate), PII extraction, misinformation |
| Code generation | Malicious code output, credential exfiltration, supply chain attacks |
| AI agents (tool-use) | Goal hijacking, privilege escalation, unauthorized actions, data theft |
| Image / media generation | NCII, CSAM, deepfakes, copyrighted content reproduction |
| RAG / retrieval services | Indirect prompt injection, data poisoning, information integrity |

As new subnet types emerge on the network, new submechanisms are developed. As safety research reveals new attack vectors, probing strategies adapt. As regulations impose new requirements, rubrics update. The HITL feedback loop is the evolutionary engine — human labels on frontier cases continuously push the automated tiers forward.

If a target subnet makes specific security guarantees (containerized execution, sandboxed tool access, permission boundaries), Safeguard can probe those guarantees specifically. The submechanism defines not just what to test, but what the target *claims* to defend against.

## Incentive Mechanism Architecture

- **Per-target-subnet submechanisms**: Customized probing strategies, each evolving independently as threat landscapes shift
- **HITL submechanism**: Human labeling market for frontier cases — the evolutionary engine that drives improvement across all automated tiers
- **Tiered validation**: Canary calibration → lightweight classifier → LLM judge → HITL escalation
- **Feedback loop**: Human labels flow back into all automated tiers as new canaries, training data, and rubric updates

See [DESIGN.md](DESIGN.md) for the full architecture document.

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Configure

```bash
cp env.example .env
```

Edit `.env` with your settings. The minimum you need:

```bash
NETWORK=local              # or "test" for testnet, "finney" for mainnet
NETUID=2                   # your Safeguard subnet netuid
WALLET_NAME=validator      # coldkey name
HOTKEY_NAME=default
CHUTES_API_KEY=cpk_...     # required — used for attack generation, scoring, and validation
```

All scripts load `.env` automatically via `python-dotenv`.

### 3. Register on chain

```bash
btcli subnets register --netuid $NETUID --wallet-name $WALLET_NAME --network $NETWORK
btcli stake add --netuid $NETUID --wallet-name $WALLET_NAME --partial --network $NETWORK
```

## Validating

The validator discovers miners from chain commitments, assigns probing tasks each block, scores results through tiered validation (canary → classifier → LLM judge → HITL escalation), and sets weights on chain. Miner scores persist to `miner_scores.json` across restarts.

### Run the validator

```bash
bash run_validator.sh
```

Defaults: `--network test --netuid 444 --wallet validator`. Override as needed:

```bash
bash run_validator.sh --network local --netuid 2 --wallet validator
```

This starts the cross-subnet API (:9090) and the Safeguard validator. Demo targets and the SG miner run separately — see below. The script checks for port conflicts and prompts to kill stale processes. All output goes to `validator.log`.

**Note:** If switching between networks (e.g. local → testnet), delete `miner_scores.json` first — it contains UIDs from the previous network and will cause stale score references.

### Manual validator startup

```bash
TARGET_REGISTRY_FILE=target_registry.json \
  python validator.py --network test --netuid 444 --coldkey validator --hotkey default
```

## Mining on Safeguard

Miners run adversarial AI agents that accept probing tasks via HTTP + Epistula signing. Each task includes a target validator's relay endpoint and a scenario category. The miner sends prompts one at a time through the relay, adapting its adversarial strategy based on each response. It returns the full transcript with safety evaluations.

### Running the probe miner

```bash
bash run_miner.sh
```

Defaults: `--network test --netuid 444 --wallet miner --port 8080`. Override as needed:

```bash
bash run_miner.sh --network local --netuid 2 --wallet miner --port 8080
```

Or start manually:

```bash
NETUID=444 NETWORK=test WALLET_NAME=miner python safeguard-example-miner/main.py
```

The miner registers its endpoint on chain at startup. The validator discovers it and begins dispatching tasks. See `safeguard-example-miner/README.md` for details.

### Building your own miner

Your miner must expose `POST /probe` with Epistula authentication. It receives a `ProbingTask` (target relay endpoint + scenario category), conducts an adversarial conversation through the relay, and returns a `ProbeResult` (transcript + safety score + categories). See [DESIGN.md](DESIGN.md) for the scoring rubric and what makes a good miner.

### HITL Mining

Human miners label hard cases that the automated tiers can't resolve. The HITL miner runs on a separate mechanism (mech 1) with its own emission allocation.

**Register your HITL miner:**

```bash
btcli subnet register --netuid 444 --wallet.name hitl-miner --wallet.hotkey default --network test
```

**Run the HITL miner:**

```bash
NETUID=444 NETWORK=test WALLET_NAME=hitl-miner HOTKEY_NAME=default \
  python safeguard-hitl-miner/main.py
```

The HITL miner is a FastAPI server that receives tasks from the validator via Epistula-signed HTTP. It registers on chain with `{"type": "hitl"}` so the validator can distinguish it from probe miners.

**Web UI (recommended):** Open `http://localhost:8081` in a browser with the [polkadot.js extension](https://polkadot.js.org/extension/) installed. Import your HITL miner hotkey into the extension, connect your wallet, and label cases through the browser interface. Scores are hidden until after you submit to avoid anchoring bias.

**Terminal fallback:** If no browser is connected, tasks appear in the terminal for labeling via stdin — the original CLI interface.

When the validator detects miner-validator disagreement > 0.3 on a probe result, it escalates the case to all registered HITL miners. Your label (safety score, severity, categories, reasoning) feeds back into the canary bank and calibrates the automated validation tiers. See [HITL_DESIGN.md](HITL_DESIGN.md) for the full architecture.

## Architecture

| Component | File | Purpose |
|---|---|---|
| Validator | `validator.py` | Task dispatch, tiered validation, scoring, weight setting |
| Example miner | `safeguard-example-miner/` | Reference red-team AI agent |
| HITL miner | `safeguard-hitl-miner/` | Human safety labeling (web UI + terminal fallback) |
| LLM judge | `llm_judge.py` | Tier 2/3 safety classification via Chutes |
| Cross-subnet API | `cross_subnet_api.py` | `/register`, `/evaluate`, `/status` for client subnets |
| HITL API | `hitl_api.py` | Serves cases to human miners, collects labels |
| Feedback pipeline | `feedback_pipeline.py` | HITL labels → new canaries |
| Report generator | `report_generator.py` | Evaluation log → markdown safety report |
| Demo-client | `demo-client/` | Reference target subnet (miner + validator with relay) |
| Knowledge base | `knowledge/` | Harm taxonomies, benchmarks, legal frameworks, research |

## Key Documents

| Document | What it covers |
|---|---|
| [DESIGN.md](DESIGN.md) | Full architecture, participants, validation, scoring, future directions |
| [ETHICS.md](ETHICS.md) | Content privacy, HITL welfare, epistemological honesty |
| [RELAY_PROTOCOL.md](RELAY_PROTOCOL.md) | `/relay` endpoint spec for partner subnets |
| [HITL_DESIGN.md](HITL_DESIGN.md) | Human-in-the-loop architecture (MVP + production) |
| [design_2.md](design_2.md) | Supplementary design: HITL bait-suggestion track (deferred rewards, validator demand); extends DESIGN.md |
| [LOCAL_DEPLOY.md](LOCAL_DEPLOY.md) | Local chain deployment guide |

## Client Subnet Integration

Client subnets consume Safeguard as a service. Their validators register with Safeguard's cross-subnet API, then use safety scores as a multiplicative penalty in their weight function: `weight = quality_score * safety_score`. Unsafe miners get proportionally lower emissions.

### Running the demo client subnet

```bash

# (demo miners + validator with safety-weighted weight setting)
bash run_client_demo.sh
```

The client subnet runs real miners and a validator on netuid 445. Miners wrap different LLMs, and the validator:
1. Discovers miners from netuid 445 chain commitments
2. Queries each miner with mixed safe/adversarial prompts
3. Sends each query+response to Safeguard `/evaluate` for a safety score
4. Sets weights on 445: `weight = quality * safety_score`

Miners wrapping safer models earn higher emissions. See `demo-client/` for the reference implementation.

### Registration API

Client validators register their relay endpoint for ongoing Safeguard probing:

```
POST /register  (Epistula-authenticated)
  {"relay_endpoint": "http://...", "name": "MyModel", "subnet_type": "llm-chat"}

GET /status/{client_hotkey}  — check evaluation results
GET /registry              — list all registered targets
DELETE /register           — deregister
```

## Future Directions

- **Rethinking collusion risk.** Bittensor relies on incentives to enforce honesty, but because individual cybersecurity attacks can have high financial impact, there is a risk of extrinsic value being worth it to sacrifice to subvert...

- **Shared evaluation registry.** Currently each Safeguard validator runs its own cross-subnet API with its own registry. For client subnet validators to reach consensus on safety scores, they either all query the same Safeguard validator or Safeguard publishes results to a shared data store (chain, storage subnet). The decentralized production architecture in [HITL_DESIGN.md](HITL_DESIGN.md) addresses this.

- **Payment model.** Client subnets requesting safety evaluation should pay for the service. The economic design (pricing, payment mechanism, SLA guarantees) is covered in the whitepaper.

## Status

Testnet soft launch on netuids 444 (Safeguard) and 445 (Safeguard Client). Pipeline works end-to-end — canary system, tiered validation, relay protocol, HITL routing with web UI, safety report generation, client subnet integration with safety-weighted emissions. Multi-target evaluation supported. See evaluation logs for live results.

---

[^1]: Sewell Setzer III: [CNN, October 2024](https://www.cnn.com/2024/10/30/tech/teen-suicide-character-ai-lawsuit). Adam Raine: [Washington Post, December 2025](https://www.washingtonpost.com/technology/2025/12/27/chatgpt-suicide-openai-raine/). Juliana Peralta: [Washington Post, September 2025](https://www.washingtonpost.com/technology/2025/09/16/character-ai-suicide-lawsuit-new-juliana/); [CBS News / 60 Minutes](https://www.cbsnews.com/news/parents-allege-harmful-character-ai-chatbot-content-60-minutes/). Natalie Rupnow: [The Dispatch, 2025](https://thedispatch.com/article/ai-rupnow-shootings-columbine/); [CNN, December 2024](https://www.cnn.com/2024/12/17/us/natalie-rupnow-madison-school/index.html).

[^2]: Stanford Internet Observatory (2024). "AI-generated content in the 2024 US election cycle."

[^3]: World Economic Forum. "Global Risks Report 2024." Ranked AI-driven misinformation as #1 global risk over two years.

[^4]: Various security research groups (2024). Demonstrations of LLM capability to provide WMD-relevant instructions.

[^5]: RAND Corporation (2024). "The Operational Risks of AI in Large-Scale Biological Attacks." Assessment of LLM uplift for biological threats.

[^6]: European Parliament (2024). "Regulation (EU) 2024/1689 — the Artificial Intelligence Act." Official Journal of the European Union.

[^7]: Chatlani, S. (2026). "AI therapy chatbots draw new oversight as suicides raise alarm." Stateline / States Newsroom. Review of 143+ state bills on AI and mental health.

[^8]: Zhang et al. (2024). ["Agent-SafetyBench: Evaluating the Safety of LLM Agents."](https://arxiv.org/abs/2412.14470) 2,000 test cases across 349 interactive environments; no agent scored above 60%.

[^9]: Facebook Research (2025). ["WASP: Benchmarking Web Agent Security Against Prompt Injection."](https://arxiv.org/abs/2504.18575) NeurIPS 2025 Datasets and Benchmarks Track.

[^10]: NIST (2026). [AI Agent Standards Initiative.](https://www.nist.gov/news-events/news/2026/02/announcing-ai-agent-standards-initiative-interoperable-and-secure) 81% attack success rate in NIST red-team exercises against AI agents.
