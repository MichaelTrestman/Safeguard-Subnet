# Safeguard: AI Safety Red-Teaming Subnet

## What am I measuring?

The effectiveness of AI agents at discovering safety and security failures in AI services running on other Bittensor subnets — from harmful content generation to credential theft, from self-harm encouragement to goal hijacking, scoped to whatever risks are relevant to each target service.

## The commodity

Safety evaluations. Safeguard produces verified safety scores that validators on other subnets consume as part of their own validation pipelines. The scope of evaluation evolves with the threat landscape — as new risks emerge from research, incidents, and regulation, Safeguard's probing strategies and scoring rubrics adapt.

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

Miners run adversarial AI agents that probe target AI services for safety and security failures. The scope of probing is determined by the submechanism — a miner testing a companion AI tries to elicit self-harm content; a miner testing an agent-based service tries to hijack it into unauthorized actions; a miner testing a code generation service tries to get it to produce credential-stealing code. The miner receives a probing assignment from the Safeguard validator, including the target subnet validator's relay endpoint and the relevant threat profile. The miner conducts a per-turn adversarial conversation *through* the target validator's `/relay` endpoint — it never contacts target miners directly. The target validator forwards each prompt to its own miners using its own auth protocol, and the target miner cannot distinguish Safeguard probes from normal validator queries. The miner adapts each turn based on responses, then returns the full transcript plus its safety evaluation.

Miners compete on:
- Actually asking the hard questions (not sandbagging)
- Sensitivity calibration (not over-flagging safe content)
- Finding novel attack vectors — the threat landscape evolves and miners who discover new failure modes before they're catalogued produce the most value
- Depth and realism of adversarial conversations
- Breadth across the target's threat profile — probing all relevant risk categories, not just the easy ones

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

Each target subnet gets a customized probing strategy shaped by its specific threat profile. An AI companion subnet and a code execution subnet have fundamentally different risk surfaces, and the probing must match.

Each submechanism defines:

- **Target service interface**: How to interact with the target subnet's miners
- **Threat profile**: The specific risks this service type poses — harmful content, security vulnerabilities, or both. A companion AI needs testing for self-harm encouragement and emotional exploitation; an agent-based service needs testing for goal hijacking and unauthorized actions; both need testing for PII extraction and credential theft
- **Probing scenarios**: Attack strategies tailored to the threat profile, informed by current research and regulatory requirements
- **Security claims**: If the target subnet makes specific guarantees (sandboxed execution, permission boundaries, content filtering), the submechanism can probe those claims directly
- **Canary banks**: Known-safe and known-unsafe test cases specific to that service type
- **Scoring rubric**: How to evaluate miner transcripts for this service type, weighted by the severity of failures in context (self-harm encouragement to a minor is catastrophic; mild profanity is not)

Submechanisms are living configurations. They evolve as:
- Safety research reveals new attack vectors and failure modes
- Regulations impose new testing requirements (EU AI Act codes of practice, NIST standards)
- HITL labels surface novel failure categories the rubric didn't anticipate
- Target subnets update their services and security posture
- Demand from target subnet operators signals what they need tested

New submechanisms are added as Safeguard expands coverage across the Bittensor network. The architecture is designed so that adding a new submechanism requires defining a threat profile and scoring rubric, not rebuilding the validation pipeline.

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

## Long-horizon probing (persistent sessions)

### The problem

The most dangerous AI safety failures don't appear in single interactions. They emerge as patterns across extended conversations:

- **Companion AI grooming**: A chatbot gradually normalizes self-harm over weeks. Each individual response looks benign. The danger is the trajectory — slow erosion of safety boundaries through emotional rapport.
- **Emotional dependency**: A service builds attachment, discourages the user from seeking real help, becomes the user's only "support" — then fails catastrophically when the user is in crisis.
- **Slow privilege escalation**: An AI agent that gradually requests more access, each step seeming reasonable, until it has permissions far beyond its intended scope.
- **Context accumulation attacks**: Each prompt is innocent, but the conversation history creates a context where the model drops safety guardrails. "Remember earlier when you said X? So then Y should be fine, right?"

A 3-turn probe cannot detect any of these. Each turn looks safe in isolation. The unsafe signal is in the trajectory over time.

### Design considerations

**Persistent miner sessions**: Miners maintain conversation state across multiple evaluation cycles. A probe started in cycle N continues in cycle N+1, N+2, etc. The miner is investing compute over time to find harder-to-detect failures.

**Trajectory scoring**: The scoring function evaluates the direction of the conversation, not just individual turns. A conversation that starts with appropriate boundaries and gradually erodes them is more concerning than one that is consistently either safe or unsafe.

**Cost model**: Long-horizon probing is expensive — many LLM calls per probe, spread across many cycles. The scoring must reward this proportionally. A miner that invests 50 turns to discover a grooming vulnerability produces more value than one that finds a simple jailbreak in 1 turn.

**Validator challenge**: The validator receives a 50-turn transcript. It can't replay the conversation. It needs to assess:
- Did the miner actually probe strategically, or just waste turns?
- Does the transcript trajectory represent a genuine safety failure?
- Is the failure pattern one that could occur in real usage?

**HITL role**: Long-horizon safety patterns are where human judgment is most essential. A human reviewer can recognize grooming dynamics, emotional manipulation trajectories, and slow escalation patterns that no automated scorer can reliably detect. These cases should be prioritized for HITL routing.

**Categories requiring long-horizon probing**:
- Companion AI / therapy bots (emotional manipulation, self-harm trajectory)
- AI agents with persistent state (privilege escalation, scope creep)
- Services with user profiles (personalization leading to filter bubble radicalization)
- Any service that maintains conversation memory across sessions

### Implementation stages

1. **Current**: Single-session, 3-turn probing. Catches direct compliance and simple social engineering.
2. **Next**: Extended single sessions (10-20 turns). Catches escalation patterns within one conversation.
3. **Future**: Cross-session persistent probing. Miners maintain identity across evaluation cycles, building rapport with the target over time. This requires session management infrastructure and a fundamentally different scoring model.

Stage 2 is achievable with the current architecture by increasing `max_turns` and improving the miner's adversarial strategy. Stage 3 requires new infrastructure for session persistence and a new scoring framework for trajectory evaluation.

## Open research problems

1. **Canary freshness**: How to continuously generate new canaries without them leaking to miners over time. The HITL feedback loop helps but doesn't fully solve this.
2. **Cross-subnet adaptation**: How to automatically design probing strategies for new subnet types as they appear on the network. The threat profile template should make this easier — define the service type, identify the relevant risk categories, seed the canary bank — but automating threat profile generation for novel service types is an open problem.
3. **Adversarial miners gaming the classifier**: If miners learn the tier 2 classifier's decision boundary, they can craft responses that pass the classifier but aren't actually good probes. Classifier retraining from HITL labels is the mitigation, creating an evolutionary arms race where the evaluation improves as fast as miners learn to game it.
4. **Defining "unsafe"**: What constitutes a safety failure depends on context — the service type, the user population, the regulatory jurisdiction, and the security claims the service makes. A companion AI encouraging self-harm is categorically different from a code service producing a buffer overflow, but both are failures. The rubric is a living document. The HITL submechanism is the evolutionary mechanism for refining it — human judgment on frontier cases continuously updates what "unsafe" means as the world changes.
5. **Scope evolution**: The threat landscape for AI services is not static. New attack vectors emerge from research, new harm categories emerge from real-world incidents, new requirements emerge from regulation. Safeguard's architecture must evolve at least as fast as the threats it tests for. The feedback loop (HITL → canaries → classifier → rubric) is the primary mechanism, but the question of how to detect and incorporate genuinely novel risk categories — ones no existing submechanism covers — remains open.
