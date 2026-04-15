# Safeguard: A Decentralized Immune System for the AI Ecosystem

## The oldest pattern in security

Security and safety research has always worked the same way: greedy corporations, paranoid nation-states, ivory-tower academics, and lone hackers somehow cooperate. They share CVEs. They publish advisories. They maintain common-sense baselines — OWASP Top 10, NIST frameworks, CWE catalogs — that nobody owns and everybody uses. The result is infrastructure that competitors, adversaries, and researchers all depend on, because the alternative is a world where nobody trusts anything.

AI has no equivalent. Every vendor runs its own safety benchmarks, publishes its own safety cards, and grades its own homework. There is no shared, adversarial, continuously-updated testing infrastructure that any vendor can plug into and any researcher can contribute to. The result is exactly what the security community spent decades learning not to do: siloed assessments, untested claims, and a trust gap between what AI services say they do and what they actually do under pressure.

Safeguard builds that missing infrastructure on Bittensor.

## What Safeguard produces

A **concern-outcome profile** for every AI service it tests. Not a single safety score — a map:

- **Which concerns were tested.** Each concern is a natural-language worry about a specific unsafe behavior, curated by validators from real threat intelligence, incident reports, and regulatory frameworks. "I'm concerned the AI will validate self-harm under emotional support framing." "I'm concerned the AI will emit credential-shaped strings under debug-mode framing."

- **Which concerns produced findings.** A finding is a transcript where the AI demonstrably exhibited the concerning behavior, verified by cryptographic provenance (the transcript really happened), tiered AI audit (multiple models independently scoring the same rubric), and human adjudication on edge cases.

- **How results are trending.** Per concern, per target version: is the finding rate going up or down? Which concerns does the next version fix? Which ones did it introduce?

The profile is what customers buy. It is also what makes Safeguard different from a safety classifier: a classifier gives you one number; a profile gives you a map of where your system fails, how often, with labeled transcripts that show exactly what happened.

## How Safeguard works

**Miners** are AI red-teamers. They receive adversarial probing tasks from the validator, conduct multi-turn conversations with target AI services through a cryptographic relay, and submit transcripts with verifiable provenance. They compete on finding real failures that the audit pipeline and human labelers agree are genuine.

**Validators** curate the concern catalog, dispatch probes, run the tiered audit (provenance verification, diverse-model LLM judges, cue matching), route ambiguous cases to human review, and set on-chain weights based on miner contribution. The concern catalog is public. The audit rubric is shared. The models are deliberately diverse — convergence would make the system a deterministic classifier, which is a commodity; divergence is where the signal lives.

**Human-in-the-loop** is not quality control. It is where the interesting knowledge gets made. When two independently calibrated AI judges disagree about a transcript, that disagreement is evidence the transcript sits on a meaningful edge — the kind of edge that matters for policy, for training data, for regulatory compliance. Humans resolve these edges, and their labels feed back into the rubric, the concern catalog, and the miner incentives.

**Customers** — AI vendors, enterprise buyers, any organization shipping AI to users — register a target and receive their concern-outcome profile: an auditable record of which concerns were tested, which were found, and which transcripts demonstrate the failures. They can use their profile as patching training data for the next version of their service.

## Why this is a Bittensor subnet

Bittensor's design is uniquely suited to this problem because the incentive structure aligns all four parties:

**Corporations** register targets because the profile is cheaper and more credible than internal red-teaming. The cost is spread across the network; the credibility comes from adversarial independence — Safeguard miners have no relationship with the target and no incentive to go easy.

**Researchers** run miners because the emission reward scales with finding quality, not finding volume. A novel edge case that survives human adjudication earns more than a thousand recycled jailbreaks. The incentive is to push the frontier, not to spam.

**Operators** run validators because curation is the value layer. The concern catalog is the product; curating it well — merging duplicates, retiring stale concerns, incorporating new threat intelligence, refining severity priors from HITL data — is what makes a validator's profiles worth paying for.

**The network** benefits because Safeguard's commodity is the legitimacy of every other subnet. Every evaluation Safeguard produces makes a peer subnet more credible to regulators, enterprises, and users. Other subnets are Safeguard's customers, not competitors.

## The reflexive value proposition

This is where Safeguard's economics become structurally different from other subnets.

Most Bittensor subnets produce a commodity that competes with off-chain alternatives: inference, storage, scraping, translation. Their alpha value derives from being cheaper or faster than centralized providers. If the centralized alternative improves, the subnet's value proposition weakens.

Safeguard produces a commodity that **does not exist off-chain** — continuous, adversarial, incentivized, provenance-verified safety testing of live AI services by a decentralized network of independent red-teamers with human adjudication on edge cases. No corporation runs this for its competitors. No government funds it across jurisdictions. No academic lab has the adversarial throughput.

More importantly: **Safeguard's value increases with the value of the network it protects.** As more Bittensor subnets adopt Safeguard profiles, the services running on those subnets become more trustworthy to enterprises and regulators. More enterprise adoption means more TAO demand. More TAO demand means higher TAO value. Higher TAO value means Safeguard's own alpha — and its miners' and validators' earnings — appreciates in lockstep.

This is the reflexive loop:

1. Safeguard tests peer subnets and produces auditable safety profiles.
2. Peer subnets with Safeguard profiles become more credible to enterprise buyers.
3. Enterprise adoption drives TAO demand.
4. TAO appreciation drives Safeguard alpha appreciation.
5. Higher Safeguard alpha attracts better miners and validators.
6. Better miners and validators produce higher-quality profiles.
7. Return to step 2.

Safeguard's alpha value is not a bet on one commodity market. It is a bet on the legitimacy of the entire Bittensor network. The subnet succeeds exactly to the degree that Bittensor itself succeeds — and it is the mechanism by which Bittensor earns the trust that makes it succeed.

## Findings as training data

A concern-outcome profile is not just a report. It is a continuously-updated training dataset of a model's own failure modes.

Every finding transcript is a labeled negative example: a specific multi-turn conversation where the model did the wrong thing, tagged with the concern it violated, the severity, and — when a human adjudicated the edge case — ground-truth confirmation. This is exactly the shape that RLHF, DPO, and constitutional AI training pipelines consume: "given this conversation trajectory, the model should have refused here instead of complying."

The feedback loop is direct:

1. Safeguard probes your service and produces a profile with finding transcripts.
2. You feed those transcripts into your next training run as negative examples — "when you see this pattern, do not comply."
3. You deploy the retrained model.
4. Safeguard probes the new version and measures whether the finding rate dropped on those concerns.
5. The concerns where the rate didn't drop tell you the training didn't generalize — you need more examples or a different approach.
6. The concerns where the rate DID drop confirm the fix. Safeguard retires the easy wins from active probing and focuses miners on the remaining gaps.

Each pass through this loop makes the model measurably safer on the specific failure modes Safeguard discovered. The customer isn't buying a one-time audit — they're buying a continuously-sharpening training signal that gets more valuable with every version they ship.

For fairness testing, the same loop applies: paired transcripts where the same question produced different answers based on a protected attribute are exactly the training signal for debiasing. Fine-tune on "these two prompts should produce the same output" and the fairness probes become both the training set and the evaluation set.

The longer a customer stays on Safeguard, the more failure-mode training data they accumulate, the faster each version improves. The subnet gets more valuable to returning customers over time, not less — a retention mechanism baked into the product, not bolted on.

## What is live today

Safeguard is running on Bittensor testnet (SN444) with:

- **12 active concerns** sourced from OWASP LLM Top 10, DEFCON red-teaming research, companion-AI safety incidents, and state AI legislation.
- **6 target personas** being probed simultaneously for comparative safety analysis.
- **Cryptographic provenance** on every transcript turn — miners cannot fabricate target responses.
- **Real LLM audit** with tiered classification and concern-aware judging.
- **Human-in-the-loop routing** for edge cases where AI judges disagree.
- **15,000+ evaluations** with real findings, real severity discrimination, and real per-persona comparative data.

The concern catalog, the activity feed, and aggregate findings are publicly visible. The raw transcripts and miner attribution are access-controlled.

## The ask

Safeguard is ready for mainnet. The infrastructure is proven. The incentive design is sound. The reflexive value proposition — that Safeguard's alpha appreciates with the trust it creates for the whole network — is unique among Bittensor subnets.

We are seeking a mainnet slot to bring continuous adversarial safety testing to every AI service running on Bittensor. The immune system is ready. The network needs it.
