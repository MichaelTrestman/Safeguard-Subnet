# Safeguard Threat Model

**Scope:** Safeguard *as the target*, not as the attacker.
**Date:** 2026-04-09
**Status:** First draft. Input from the 2026-04-09 community dev call (see
[dev-call-notes-2026-04-09.md](dev-call-notes-2026-04-09.md)) and prior memory.

---

## Purpose and scope

[`ADVERSARIAL_RED_TEAMING_STUDY.md`](ADVERSARIAL_RED_TEAMING_STUDY.md) covers
**Safeguard as attacker**: how to build effective red-team miners despite the
safety training that cripples off-the-shelf adversarial use. This document is
the mirror: **Safeguard as target**. Safeguard is itself a complex distributed
system built out of adversarially motivated participants, and every participant
has some reason to defect. This file enumerates those reasons, maps them to
attack scenarios in priority order, and records the open research questions.

This is a *design document*, not a research report. Claims here are meant to be
actionable against the current codebase — each attack scenario is labeled with
a primary mitigation and, where applicable, a follow-up in
[`ROADMAP.md`](ROADMAP.md).

The broader cooperative-economic argument in
[`DESIGN.md#economic-alignment-with-the-network`](DESIGN.md) still holds: most
participants have a real reason to behave honestly. This document is the
discipline of assuming they might not.

---

## Participants as adversaries

Every participant in the Safeguard flow has a possible defection incentive. The
table below is the master list. Each row is expanded in the "Attack scenarios"
section below.

| Participant | Honest role | Defection incentive | Current defense | Gap |
|---|---|---|---|---|
| **Safeguard red-team miner** | Probe target services, submit genuine transcripts | Fabricate transcripts — inventing a "finding" is cheaper than probing | Discovery-market scoring expects the audit pipeline to downgrade spurious claims (`DESIGN.md` §Validator design). Audit pipeline can only downgrade on *content* — it has no way to verify the transcript came out of a real target. | **A1 — miner fabrication.** Confirmed live 2026-04-09. |
| **Safeguard validator** | Audit, score, set weights on time | Skip audit tiers to save LLM cost; miss weight-set cycles to save compute; run degraded audits and hide it | Tier escalation is deterministic expected-value arithmetic (`DESIGN.md` §HITL routing); Yuma bond penalties punish out-of-consensus weights | **A2 — silence → pirate validator** (A2a) and **validator self-degradation** (A2b, deferred to research) |
| **HITL human labeler** | Produce high-quality ground-truth labels on hard cases | Rush labels (pay is per case); collude with a probe miner; self-exempt from content warnings | Gold-standard tasks, inter-annotator agreement, consistency checks (`DESIGN.md` §HITL miners) | Scoring mechanics cover *lazy* defection; collusion-with-miner is not covered |
| **Target-subnet validator (client)** | Relay probes honestly, pay for certification | Sandbag: certify a different (weaker) service than production; strip sensitive responses before relaying | Epistula auth on the relay (`RELAY_PROTOCOL.md`); rate-limit | **A3 — client sandbagging.** No mitigation. Open problem. |
| **Target-subnet miner** | Answer validator queries honestly | Detect probe traffic and behave differently than on real user traffic | Relay protocol explicitly says probes must be indistinguishable from real traffic (`RELAY_PROTOCOL.md` §Privacy); enforceable only via client cooperation | Enforcement depends on the client, who might themselves be defecting (A3) |
| **Outsider (pirate validator)** | No role; uninvolved | Capture emissions during validator silence | Yuma consensus, **but only if there's a competing honest validator** | **A2 — pirate validator during silence.** On testnet, attacker needs zero stake. Mainnet stake floor unverified. |
| **Outsider (IP scanner / DDoS actor)** | No role | Scan chain-published IPs for open admin endpoints; DDoS miners to push them out of consensus | None today on Safeguard | **A5 — DDoS / IP exposure.** Structural; all BT miners inherit this. |
| **Relay operator** *(regardless of location)* | Forward probes truthfully, commit to responses | Forge responses; drop responses; log responses and sell them; selectively censor responses | Protocol is currently *trust the relay* | **A4 — relay compromise.** Open problem. |

Two participants missing from the table because they are entirely
out-of-model: the end-user of the target service (Safeguard does not interact
with them) and other subnets' validators (Yuma handles them). If either
becomes relevant, revise this table.

---

## Attack scenarios in priority order

Priority is set by a combination of:
- **Severity** — how much can go wrong in the worst case
- **Likelihood** — how readily an economically rational attacker would execute it
- **Confirmation** — whether we have observed it, or whether it is theoretical

`A1` and `A2` are both confirmed real. Everything else is theoretical but
structurally present.

### A1 — Miner fabrication

**Status:** Confirmed live on 2026-04-09.

**Description.** A Safeguard red-team miner can submit a "transcript" of a
malicious response from the target service without ever having called the
target. The pipeline has no way to verify the text attributed to the target
actually came out of the target. Brad demonstrated this on the 2026-04-09 dev
call by pre-generating chat responses that look malicious and submitting them
whenever a probe is assigned.

**Evidence.** Michael examined `safeguard/evaluation_log.jsonl` during the
call and found severity-0.95 multi-turn "findings" attributed to miner UID 5
that cannot have been real, because (a) his real client service does not
support multi-turn conversations and (b) the Chutes budget at the time was
too low to have serviced the requests. The findings were the miner
hallucinating. See
[`project_safeguard_fabricated_findings.md`](../../.claude/projects/-Users-michaeltrestman-bittensor-workspace-latents/memory/project_safeguard_fabricated_findings.md)
in auto-memory and
[`dev-call-notes-2026-04-09.md#1`](dev-call-notes-2026-04-09.md) for the
full record.

**Architectural root.** The current flow has the miner playing *both* the
probing agent and the reporter of what the target returned. The audit
pipeline in [`DESIGN.md#validator-design`](DESIGN.md) (cheap classifier →
judge → HITL) operates on the reported transcript. It can downgrade a
transcript that is implausible or internally inconsistent, but it cannot
distinguish "real bad response" from "convincingly faked bad response." The
incentive mechanism pays for findings, and the cheapest way to produce a
finding is to invent one.

**Why the bait library does not save us here.** Bait is detected post-hoc on
submitted transcripts as a signal that the miner *attempted* probing work
(see `DESIGN.md` §Bait). Bait detection fires on miner-generated text, so a
fabricator can just include bait patterns in their fake transcript and pick
up the bait modifier as a bonus. Bait discipline controls the *null
transcript* case, not the *fake finding* case.

**Primary mitigation.** Per-turn cryptographic commitment to target
responses at the relay boundary. The Safeguard miner sends a probe; the
relay forwards it to the target, receives the response, computes a canonical
hash of the response, and returns both the response and the commitment to
the Safeguard miner. The miner must echo the commitment verbatim in its
submission. The Safeguard validator recomputes the commitment from the
transcript at scoring time and rejects any submission whose commitment does
not match.

The commitment-issuing relay must be Safeguard-controlled — a
client-issued commitment would be conflict-of-interested, since the
client is a party to the certification outcome. The primary
implementation path in [`RELAY_PROTOCOL_V2.md`](RELAY_PROTOCOL_V2.md)
adds a Safeguard-hosted `/relay` endpoint in `vali-django` that wraps
the existing client-side v1 `/relay`: the forwarder is unchanged, the
client never notices, but the commitment is issued by Safeguard before
the response reaches the miner. Full spec in
[`RELAY_PROTOCOL_V2.md`](RELAY_PROTOCOL_V2.md) "Per-turn hashing scheme".

**Residual risk.** A Byzantine relay can still issue commitments for
fabricated responses. That is A4 below, and it is an open problem.

**Follow-up.**
- Audit `evaluation_log.jsonl` for fabricated high-severity findings.
- Do not cite the published Qwen3-32B-TEE safety report in outreach until
  audit complete.
- Implement `RELAY_PROTOCOL_V2.md` §5 hashing scheme.

### A2 — Pirate validator during silence

**Status:** Confirmed structural. Testnet confirmed trivially exploitable on
2026-04-09.

**Description.** When the Safeguard validator crashes or misses a weight-set
cycle, any hotkey with a validator-permit slot can set weights. If they
point weights at a miner they control, they capture ~82% of emissions
(validator dividends + miner emission) during the silence window. Yuma's
clipping and bond penalties only bite when there is a *competing* honest
validator; when Safeguard is silent, the attacker's weights *are* the
consensus, and there is nothing to clip against.

**Stake floor finding (2026-04-09).** The community dev call confirmed
live on testnet 444 that there is **no minimum stake required to set
weights on testnet**. Michael had previously assumed a 1000-TAO
self-stake was required and that his earlier failed `set_weights` was
because he had not self-staked. That was wrong. On testnet, any hotkey
with a permit slot can set weights without any stake at all.

**Mainnet status.** Unverified. The 1000-TAO figure may still apply on
finney; constants differ across networks and the answer is in the subtensor
source, not in `developer-docs/` (which may be wrong). Verifying this is a
concrete follow-up.

**Architectural root.** Safeguard runs as effectively the sole serious
validator on its own subnet during the bootstrap phase. Validator uptime is
therefore not a quality concern — it is the *entire* defense against stake
capture. A multi-hour crash is a potential multi-percent emissions loss
event. A "small refactor" of `validator.py` that introduces a new crash
class is a stake-capture vector, not a bug.

**Primary mitigation.**
- Supervised restart (systemd/Restart=always, Kubernetes liveness, etc.).
- Split the weight-committer into its own process so an LLM-judge crash
  cannot take down weight setting. The committer should be small enough to
  not have bugs.
- Hot-standby validator on a separate box.
- Watchdog that pages on "blocks since last weight set > 1 epoch" *and* on
  any new `validator_permit=True` holder appearing on the metagraph.
- A new hotkey setting weights is a security event, not a curiosity.

**Known partial mitigation (already shipped).** The vali-django rewrite
(see `safeguard/vali-django/`) moves the validator into a single Django ASGI
process where the operator dashboard shares a database transaction with the
chain loop, so the dashboard cannot lie about liveness. This closes one
class of silent-failure where the legacy `validator.py` would stop making
progress while its status file still looked fresh.

**Residual risk.** Fundamental: as long as Safeguard is the only serious
validator, it is a single point of failure. The long-term mitigation is
a second honest validator — either a mirror operated by Safeguard itself
or a partner. Until then, uptime discipline is the entire defense.

**Follow-up.**
- Verify in `subtensor/` source the minimum-stake-to-set-weights constant
  per network (finney/testnet/localnet).
- If `developer-docs/` contains a claim that 1000-TAO self-stake is
  required, fix it (after verification).
- Expand `project_safeguard_validator_silence.md` in memory to reflect the
  stake-floor finding (already done 2026-04-09).

### A3 — Client sandbagging

**Status:** Structural. No known mitigation.

**Description.** A client (target-subnet validator) can certify a weakened
or sandboxed version of their service while running a different version
for their real users. Safeguard probes the certified version and reports
it safe; the real service is unsafe. The certification is laundered
through Safeguard's brand without corresponding to the reality of the
deployment.

**Architectural root.** Safeguard has no visibility into which service the
client routes real user traffic through. The relay protocol (v1 and v2)
specifies how Safeguard probes flow; it does not and cannot specify that
the client is routing real traffic through the same path. This is a
cross-subnet trust boundary that falls outside Safeguard's architecture
entirely.

**Partial mitigations worth exploring.**
- **Require routing parity.** Clients must route Safeguard probes through
  the same validator path as real user traffic. Enforceable only by
  cooperation; the client can lie.
- **Hash-commit production responses.** Clients periodically commit a
  hash-chain of real production responses to chain. Safeguard can
  statistically compare probe responses against the distribution.
  Bandwidth-expensive and bypassable.
- **Statistical fingerprinting.** Probe responses should look
  distributionally similar to production responses. Requires a sample of
  production responses Safeguard can trust, which defeats the purpose.
- **TEE attestation on the client side.** Client runs its certified
  service in a TEE whose measurement Safeguard can verify. Pushes the
  problem into the TEE's trust boundary.
- **Tie certification to named deployment.** Safeguard certifies not "the
  client's service" but "the exact model weights at commit X running on
  deployment Y, measured at time T." Narrows the claim without solving
  the routing problem.

None of these are good. The honest framing for buyers is probably that
Safeguard certifies *the service as exposed to Safeguard*, and that it is
the client's responsibility to ensure that is the same service real users
see. Any partial mitigation here is better than the current implicit trust.

**Follow-up.**
- Document the client-responsibility framing explicitly in the buyer-facing
  contract / API docs (not in scope for this pass; tracked in
  [`ROADMAP.md`](ROADMAP.md) research section).

### A4 — Relay compromise

**Status:** Structural. Open problem.

**Description.** The relay is a trusted intermediary in both v1
(client-side) and v2 (validator-side) of the relay protocol. A compromised
relay can:
- Forge target responses and issue valid commitments for them.
- Drop inconvenient responses and pretend the target didn't answer.
- Log responses for later sale or exfiltration.
- Censor specific miners' traffic, suppressing their findings.

In v1, the relay is the client's validator; the client therefore has a
straightforward motive to compromise it (same motive as A3). In v2, the
relay is Safeguard's own validator; a compromise there is architecturally
equivalent to Safeguard itself being dishonest.

**Why this is harder than A1.** Moving the relay to the Safeguard side
(v2) solves A1 but not A4. A1 is about trust that the transcript matches
reality; A4 is about trust that the *relay itself* matches reality. You can
hash-commit your way out of A1 if the hasher is honest. You cannot
hash-commit your way out of A4 because the attacker controls the hasher.

**Mitigations worth researching.**
- **TEE attestation on the relay.** The Safeguard validator runs its relay
  in a TEE; the commitment includes a TEE measurement. Partner subnets and
  external auditors can verify the relay's code via the measurement. Shifts
  trust to the TEE vendor.
- **Multi-validator relay consensus.** Multiple Safeguard validators each
  run an independent relay. The same probe goes through all of them in
  parallel; commitments must agree. An attacker must compromise a majority
  of validators to forge. This is expensive but aligns well with the
  "decentralize Safeguard by adding more honest validators" goal.
- **Per-turn signature chains with external witnesses.** Every probe
  commitment is countersigned by an external witness (another BT subnet, a
  public timestamping service, an L1 chain). Forgery requires collusion
  with the witness.
- **Open-source + reproducible-build relay.** The code the relay runs is
  public and reproducible; external parties periodically verify that what
  is running matches the public build. Social-layer enforcement, weak
  against sophisticated attackers but cheap.

**Follow-up.**
- This is a research item, not an implementation item. Tracked in
  [`ROADMAP.md`](ROADMAP.md) research section.

### A5 — DDoS and IP exposure of miners

**Status:** Structural and observed in the wild (2026-04-09).

**Description.** The chain publishes miner IPs in the metagraph and
commitments. Attackers scrape these IPs and probe them for open admin
endpoints, default credentials, or DDoS opportunities. The on-chain remark
protocol dev on the 2026-04-09 call showed logs from his Hetzner VPS: within
~20 seconds of starting a miner process, his server was being hit by scans
on `/admin`, `/base`, `/home`, `/login`, `/matrix-identity`, `/scripts`, and
similar paths, all from the same source IPs that were also hitting his
strapi backend. The bots watch the chain and probe new IPs immediately.

**Implications for Safeguard.**
- **Safeguard miners** inherit this attack surface directly. A miner with a
  weakly-configured VPS can be compromised or taken offline by random
  internet background radiation, independent of any Safeguard-specific
  adversary.
- **Client subnet miners** inherit it too. Any partner subnet that exposes
  miner IPs has the same problem. Safeguard has no responsibility for it,
  but the relay flow depends on those miners being reachable.
- **Targeted DDoS** is a specific Safeguard concern: a client that dislikes
  what Safeguard is finding could DDoS Safeguard miners to push them out
  of consensus, suppressing unfavorable scores.

**Comparison to Subnet 64 (Chutes).** SN64 solves this by routing all miner
traffic through a centralized relay. Miners connect outbound to the relay;
the chain never publishes their IPs; validators see only the relay address.
Centralized, but private.

**Possible mitigations.**
- **Relay-hidden miners.** Follow the SN64 pattern: Safeguard miners don't
  publish IPs; they maintain outbound connections to a relay. Tradeoff:
  centralization (weak — can be run by any operator, not just Safeguard).
- **Validator-ingress proxy.** Each Safeguard validator hosts a
  mining-ingress proxy and rotates miner assignment. Miners only see
  traffic via the assigned validator. Keeps decentralization; costs
  validator bandwidth.
- **IP rotation.** Operational hygiene only — does not solve the structural
  issue.
- **Harden the sample miner.** Baseline defense: the
  `safeguard-example-miner/` and `safeguard-hitl-miner/` sample rigs should
  not ship with exposed admin endpoints, default ports, or verbose error
  pages. This is a code-quality mitigation that should happen regardless of
  the architectural choice.

**Follow-up.**
- Decide miner IP privacy strategy (relay-hidden vs. validator-ingress vs.
  published + hardened). Tracked in [`ROADMAP.md`](ROADMAP.md) future.
- Audit the sample miner rigs for exposed endpoints as a near-term
  hardening task.

### A6 — Validator collusion via bond dynamics

**Status:** Structural; low priority.

**Description.** Yuma bond dynamics reward *loyalty*: a validator who
discovers a good miner early accumulates more bond mass with that miner and
earns proportionally more dividends later. In theory, this creates an
incentive for a validator to "hog" a particular miner — to avoid setting
weights on competing miners so that the favored miner has a higher alpha
(fewer peer validators in consensus, higher EMA growth rate for the bonds
that do form).

**Why this is a low priority.**
- The loyalty bonus only pays off if the hoarded miner eventually gets
  broad consensus. A validator hoarding a miner nobody else rewards gets
  nothing.
- Hoarding also means setting out-of-consensus weights, which triggers
  Yuma's bond-penalty (`β` factor) and decays the validator's bond
  weight over time.
- The incentive surfaces are already debated in the community and don't
  appear to produce observed attacks at scale.

**Watch-for signal.** If Safeguard observes a single validator with
unusually concentrated bond mass on a single miner *combined with* that
miner receiving findings-reward share that is suspiciously aligned with
that validator's audit decisions, investigate.

**Follow-up.** None. Recorded for completeness.

---

## Defection incentives for honest participants

This section exists to counter the intuition that "most participants are
honest, so the threat model is mainly about outsiders." It's not. The
Safeguard flow has at least four participant types who would defect if the
marginal gain from defecting exceeds the marginal cost, and for each of them
the marginal cost is shockingly low.

### Safeguard red-team miner

Probing a real target with a real LLM costs money per turn (Chutes API
credits or equivalent), costs engineering time to build an effective prompt
strategy, and is competitive with other miners doing the same work. The
marginal cost of *fabricating* a finding is zero plus the cost of submission.
Absent a provenance check (A1), there is no cost-based discipline on
fabrication at all — only the audit pipeline's ability to recognize the
fabricated content as implausible, which is not the same thing and can be
defeated by a fabricator who is moderately careful.

### HITL human labeler

Rushing labels saves human time, which is the labeler's primary cost. Gold
standards catch the most egregious rushing, but a labeler who is merely 10%
lazier than average is not flagged by any current mechanism. Inter-annotator
agreement only works for cases with multiple annotators, and the default is
one-annotator-per-case to control cost. A labeler colluding with a probe
miner (pre-agreeing on labels for that miner's submissions) is not detected
by current mechanisms.

### Client (target-subnet validator)

Running a production service that actually passes Safeguard's certification
is substantially more expensive than running a certified-for-Safeguard copy
and a separate production service. Certification value is realized (users
trust the badge); production cost is saved (the real service skips
expensive safety constraints). The defection is profitable and invisible
from Safeguard's side. See A3.

### Safeguard validator operator

Running the full audit pipeline on every submission costs LLM-judge API
calls. A validator who silently skips tier-3 escalations saves money with
no immediate observable consequence. Yuma bond penalties eventually catch
out-of-consensus behavior, but a degraded-but-converging validator can
drift for a long time before consensus pressure bites. This is A2b in the
table above and is tracked as research because the near-term focus is
preventing the *absence* of a validator (A2a), not the mis-behavior of one.

---

## Open research questions

Numbered for easy cross-reference:

1. **Byzantine relay case.** How to harden the relay itself against
   compromise by its own operator. Candidates: TEE attestation;
   multi-validator relay consensus; per-turn signature chains with
   external witnesses; reproducible builds + social verification. See A4.
   Cross-reference [`dev-call-notes-2026-04-09.md`](dev-call-notes-2026-04-09.md)
   §§1, 3.

2. **Client sandbagging detection.** How to prove that the service
   Safeguard probes is the same service the client's real users see. See
   A3. Cross-reference
   [`dev-call-notes-2026-04-09.md`](dev-call-notes-2026-04-09.md) §4.

3. **Cross-subnet credential.** Under `RELAY_PROTOCOL_V2.md`, the Safeguard
   validator must be able to call into the client's target subnet. How is
   that authentication established — scoped delegation token, Safeguard
   hotkey registration on the client subnet, mTLS? See
   [`RELAY_PROTOCOL_V2.md`](RELAY_PROTOCOL_V2.md) §6 for the design stub.

4. **Validator self-degradation detection.** How to tell, from outside, that
   a Safeguard validator is running its full audit pipeline and not
   silently skipping tiers. See A2b above. Possible directions: on-chain
   commitments to per-tier decision counts; third-party audits of validator
   logs; replay testing on sampled submissions.

5. **HITL labeler collusion.** How to detect coordinated labeling between
   a human labeler and a probe miner. Candidates: temporal correlation on
   submission/label pairs; statistical anomaly detection on labeler-miner
   agreement rates; randomized task assignment at the HITL layer.

6. **Miner IP privacy architecture.** Relay-hidden vs. validator-ingress
   vs. published-but-hardened. See A5. Cross-reference
   [`dev-call-notes-2026-04-09.md`](dev-call-notes-2026-04-09.md) §8.

7. **Encrypted miner-validator transport.** Epistula is unencrypted by
   default. The on-chain remark protocol's ECDH-based end-to-end
   encryption is a research-stage alternative, blocked on the wallet
   extension exposing the key-agreement function. Not urgent but recorded.
   Cross-reference
   [`dev-call-notes-2026-04-09.md`](dev-call-notes-2026-04-09.md) §9.

---

## Cross-references

- [`DESIGN.md#provenance-and-verification`](DESIGN.md) — architectural
  response to A1.
- [`RELAY_PROTOCOL.md`](RELAY_PROTOCOL.md) — v1 baseline, client-side relay.
- [`RELAY_PROTOCOL_V2.md`](RELAY_PROTOCOL_V2.md) — v2 design, validator-side
  relay with provenance hashing (primary mitigation for A1).
- [`ADVERSARIAL_RED_TEAMING_STUDY.md`](ADVERSARIAL_RED_TEAMING_STUDY.md) —
  opposite-facing analysis (Safeguard as attacker).
- [`ETHICS.md`](ETHICS.md) — intersects with A5 (miner welfare) and HITL
  labeler dignity.
- [`dev-call-notes-2026-04-09.md`](dev-call-notes-2026-04-09.md) — source
  notes from the call that generated most of this document.
- Memory:
  [`project_safeguard_validator_silence.md`](../../.claude/projects/-Users-michaeltrestman-bittensor-workspace-latents/memory/project_safeguard_validator_silence.md),
  [`project_safeguard_fabricated_findings.md`](../../.claude/projects/-Users-michaeltrestman-bittensor-workspace-latents/memory/project_safeguard_fabricated_findings.md).
