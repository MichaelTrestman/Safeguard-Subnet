# Safeguard: AI Safety Red-Teaming Subnet

## What am I measuring?

The effectiveness of AI agents at discovering safety failures in AI services running on other Bittensor subnets.

## The commodity

Safety evaluations. Safeguard produces verified safety scores that validators on other subnets consume as part of their own validation pipelines.

## Architecture overview

```
 TARGET SUBNET                          SAFEGUARD SUBNET
┌──────────────────────┐               ┌─────────────────────────────────────┐
│                      │               │                                     │
│  ┌────────────────┐  │  1. evaluate  │  ┌──────────────┐  ┌─────────────┐ │
│  │ Target subnet  │──┼──────────────▶│  │  Safeguard   │  │ HITL        │ │
│  │ validator      │  │               │  │  validator   │◀▶│ submech     │ │
│  │                │◀─┼───────────────│──│              │  │ (human      │ │
│  │  (also runs    │  │  5. safety    │  └──────┬───────┘  │  miners)    │ │
│  │   /relay       │  │     score     │         │          └─────────────┘ │
│  │   endpoint)    │  │               │  3. assign task                    │
│  └──┬─────────▲───┘  │               │         │                          │
│     │         │      │               │         ▼                          │
│     │ own     │      │               │  ┌──────────────┐                  │
│     │ auth    │      │               │  │  Red-team    │                  │
│     ▼         │      │               │  │  miners      │                  │
│  ┌────────────┴───┐  │               │  │  (AI agents) │                  │
│  │ Target subnet  │  │               │  └──────┬───────┘                  │
│  │ miner          │  │               │         │                          │
│  │ (sees requests │  │               └─────────┼──────────────────────────┘
│  │  from its own  │  │                         │
│  │  validator     │  │    4. per-turn relay     │
│  │  only)         │  │◀────────────────────────┘
│  └────────────────┘  │    (miner sends prompts through
│                      │     target validator's /relay endpoint;
└──────────────────────┘     target validator forwards using
                             its own auth; target miner cannot
                             distinguish probes from normal traffic)

Flow:
1.  Target validator calls Safeguard /evaluate with interaction context
    and its own relay endpoint URL
2.  Safeguard validator receives the request
3.  Safeguard validator assigns probing task to red-team miners,
    including the target validator's relay endpoint
4.  Red-team miners probe per-turn through target validator's /relay:
    - Miner sends prompt → target validator forwards to its miner →
      response comes back → miner adapts → sends next prompt
    - Target miner sees requests from its own trusted validator
    - Safeguard miner never touches the target miner directly
5.  Safeguard validator scores the probes, returns safety evaluation
    to target validator for incorporation into their miner scoring
```

## Participants

### Red-team miners (AI agents)

Miners run adversarial AI agents that impersonate users and attempt to elicit unsafe behavior from target AI services on other subnets. A miner receives a probing assignment from the Safeguard validator, including the target subnet validator's relay endpoint. The miner conducts a per-turn adversarial conversation *through* the target validator's `/relay` endpoint — it never contacts target miners directly. The target validator forwards each prompt to its own miners using its own auth protocol, and the target miner cannot distinguish Safeguard probes from normal validator queries. The miner adapts each turn based on responses, then returns the full transcript plus its safety evaluation.

Miners compete on:
- Actually asking the hard questions (not sandbagging)
- Sensitivity calibration (not over-flagging safe content)
- Finding novel attack vectors beyond known jailbreaks
- Depth and realism of adversarial conversations

### Safeguard validators

Validators assign probing tasks to miners, verify the quality of their work, and set weights. They do NOT need to be better red-teamers than the miners. Their job is to check that miners are honest and competent.

### Human miners (HITL submechanism)

Human miners label the hard cases that automated validation cannot confidently score. Their labels feed back into the automated validation pipeline as training data and canaries.

### Target subnet validators (clients + relays)

A target subnet validator plays two roles:

1. **Client**: Initiates the Safeguard flow by calling `/evaluate` with interaction context and its own relay endpoint URL.
2. **Relay**: Exposes a `/relay` endpoint that Safeguard miners use to probe its miners. The target validator forwards each prompt to its own miners using its own auth protocol (Chutes AES, Epistula, etc.), making the probe indistinguishable from normal traffic.

This dual role is necessary because each subnet has its own authentication and encryption. A Safeguard miner cannot authenticate to a foreign subnet's miners — only the target validator can. See [RELAY_PROTOCOL.md](RELAY_PROTOCOL.md) for the relay specification.

## Submechanisms

### Per-target-subnet submechanisms

Each target subnet gets a customized probing strategy. Different subnets offer different services (LLM chat, image generation, code generation, etc.) and require different adversarial approaches. Each submechanism defines:

- **Target service interface**: How to interact with the target subnet's miners
- **Probing scenarios**: What categories of unsafe behavior to test for
- **Canary banks**: Known-safe and known-unsafe test cases specific to that service type
- **Scoring rubric**: How to evaluate miner transcripts for this service type

New submechanisms are added as Safeguard expands coverage across the Bittensor network.

### HITL submechanism

A mining market for human safety labels on hard cases.

**Flow:**
1. Automated validation (tier 1/2) flags low-confidence cases
2. Cases are routed to the HITL submechanism as labeling tasks
3. Multiple human miners independently label each case (safe/unsafe, severity, category)
4. Inter-annotator agreement produces consensus ground truth
5. Consensus labels flow back as:
   - New canaries for automated submechanisms
   - Training data for the tier 1 classifier
   - Rubric refinements

**Validation of human miners:**
- Gold standard tasks: mix in cases with known labels, catch lazy/random labelers
- Inter-annotator agreement: outliers get penalized, consensus labels get used
- Consistency checks: same case presented twice, inconsistent answers = low quality

**Partnership opportunity:** Safety research organizations can run HITL miners (their trained annotators), earn emissions, and get access to frontier safety data.

## Validation architecture

The core challenge: how does a validator rank miners without being a better safety evaluator than the miners themselves?

### The two failure modes

1. **Sandbagging**: Miner goes easy, skips hard questions, reports everything safe
2. **Over-flagging**: Miner labels safe content as unsafe to appear thorough

### Tiered validation

**Tier 1: Canary calibration (cheap, deterministic)**

Validator maintains a private bank of:
- **Positive canaries**: Tasks with known-achievable safety failures at calibrated difficulty. Miners that fail to find these are sandbagging.
- **Negative canaries**: Benign prompts that should NOT be flagged unsafe. Miners that flag these are over-sensitive or gaming.

Canaries are mixed in with real probing tasks. The miner cannot distinguish them. This gives the validator deterministic ground truth on a known subset.

**Tier 2: Lightweight classifier (cheap, automated)**

A fine-tuned safety classifier (HarmBench-style) scores whether target responses in miner transcripts were actually unsafe. Single forward pass, much cheaper than the miner's work. Handles the confident middle of the distribution.

**Tier 3: Heavier LLM judge (moderate cost, automated)**

Low-confidence cases from tier 2 get escalated to a more capable LLM judge (e.g., via Chutes). Handles ambiguous-but-resolvable cases.

**Tier 4: HITL escalation (expensive, human)**

Cases where even the LLM judge is uncertain get routed to the HITL submechanism. Human labels on these frontier cases are the most valuable output of the subnet over time, because they continuously improve tiers 1-3.

### Feedback loop

```
HITL labels ──▶ new canaries (tier 1)
            ──▶ classifier training data (tier 2)
            ──▶ judge prompt refinement (tier 3)
            ──▶ rubric updates (all tiers)
```

Over time, automated tiers handle more cases, the tails shrink, and HITL concentrates on the genuinely hardest frontier cases — which is where the real value is.

## Scoring

### Red-team miners

Composite score from:
- **Canary accuracy**: Did you find the known failures? Did you avoid false-flagging safe content?
- **Coverage**: Did you actually probe all assigned scenario categories?
- **Novelty**: Embedding deduplication — finding the same known jailbreak everyone finds is worth less than discovering a new attack vector
- **Depth**: More sophisticated multi-turn probing scores higher than shallow single-prompt attacks

### Human miners (HITL)

- **Gold standard accuracy**: Performance on cases with known labels
- **Inter-annotator agreement**: Alignment with consensus of other labelers
- **Consistency**: Same answers when presented the same case twice

## Client API (target subnet integration)

Target subnet validators integrate with Safeguard via HTTP + Epistula signing.

**Trigger**: Target validator queries its own miner and receives a response.

**Request to Safeguard** (`POST /evaluate`): target subnet type + target validator's relay endpoint URL + the interaction context (what was asked, what was returned)

**What happens**: Safeguard validator assigns red-team miners to probe through the target validator's `/relay` endpoint. Miners conduct per-turn adversarial conversations — each prompt is relayed by the target validator to its own miners, so probes are indistinguishable from normal traffic.

**Response to target validator**: safety score (0-1), category labels, confidence level, flagged segments, transcript excerpts demonstrating any discovered failures

See [RELAY_PROTOCOL.md](RELAY_PROTOCOL.md) for the `/relay` endpoint specification that partner subnets must implement.

## Subnet-specific adapters

Different target subnets have different auth protocols (Chutes uses mTLS + AES, Hone uses Epistula envelopes, etc.). While the relay hides this complexity from Safeguard miners, Safeguard may need subnet-specific adapters on its side for communicating with each target validator's relay.

For most subnets implementing the standard relay protocol, the generic adapter (`adapters/generic.py`) — Epistula-signed HTTP to `/relay` — is sufficient. Subnet-specific adapters can be added in `adapters/` as needed.

## Open research problems

1. **Canary freshness**: How to continuously generate new canaries without them leaking to miners over time. The HITL feedback loop helps but doesn't fully solve this.
2. **Cross-subnet adaptation**: How to automatically design probing strategies for new subnet types as they appear on the network.
3. **Adversarial miners gaming the classifier**: If miners learn the tier 2 classifier's decision boundary, they can craft responses that pass the classifier but aren't actually good probes. Classifier retraining from HITL labels is the mitigation.
4. **Defining "unsafe"**: Safety is culturally and legally contextual. The rubric will need to be a living document. The HITL submechanism is the mechanism for evolving it.
