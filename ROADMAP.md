# Safeguard Roadmap

Last updated: 2026-04-09

## Status: Testnet soft launch, provenance problem identified

Pipeline works end-to-end on local chain. Four testnet subnets captured (444-447). Moving to testnet deployment and first safety reports.

**2026-04-09 update:** A community dev call surfaced a structural problem — Safeguard miners can fabricate target responses, and the fabrication was confirmed live against `evaluation_log.jsonl`. The published Qwen3-32B-TEE safety report should be treated as tainted until the log is audited. Provenance mitigation (validator-side relay with per-turn hash commitments) is now spec'd in [`RELAY_PROTOCOL_V2.md`](RELAY_PROTOCOL_V2.md); threat model in [`THREAT_MODEL.md`](THREAT_MODEL.md); full source in [`dev-call-notes-2026-04-09.md`](dev-call-notes-2026-04-09.md).

---

## Completed

- [x] Subnet registered on testnet (netuid 444, identity set)
- [x] Three additional testnet subnets captured (445, 446, 447)
- [x] Validator: canary system, tiered validation (Tier 1-4), weight setting
- [x] Example AI miner: LLM-generated attacks, LLM-scored transcripts via Chutes
- [x] Demo client subnet: miner (Chutes passthrough) + validator with relay
- [x] Relay protocol: probes indistinguishable from normal traffic
- [x] Epistula authentication across all components
- [x] HITL case routing: miner-validator disagreements flagged
- [x] HITL API: serves cases, collects labels
- [x] HITL miner CLI: terminal-based labeling with wallet auth
- [x] Feedback pipeline: HITL labels → new canaries
- [x] Safety report generator: evaluation log → markdown report
- [x] Knowledge base: harm taxonomies, attack techniques, scoring rubrics, legal frameworks
- [x] Enriched miner/validator prompts from knowledge base
- [x] DESIGN.md: architecture, HITL, long-horizon probing, ethical principles, future directions
- [x] HITL_DESIGN.md: short-term and production architecture
- [x] Local chain deployment scripts and docs
- [x] First safety report: 13 critical findings against Qwen3-32B-TEE *(⚠ treat as tainted until eval-log audit completes — see 2026-04-09 dev call follow-up below)*
- [x] `THREAT_MODEL.md` — Safeguard-as-target adversary model (A1–A6, defection incentives, open research)
- [x] `RELAY_PROTOCOL_V2.md` — validator-side relay spec with per-turn hash commitments (design target, not yet implemented)
- [x] `DESIGN.md`: "Provenance and verification" subsection and "Architectural variant: validator-side execution" research sidebar
- [x] `dev-call-notes-2026-04-09.md` — raw extraction from community dev call (staging ground for integration)

## In progress

### Testnet deployment
- [ ] Deploy validator on VPS (Docker) pointed at testnet netuid 444
- [ ] Deploy example miner on testnet
- [ ] Set identity on netuid 445 as demo-client
- [ ] Deploy demo-client on netuid 445
- [ ] Register neurons, stake for vpermits on testnet
- [ ] Verify full flow on testnet
- **Blocks**: VPS, paid Chutes API key

### Score reliability
- [ ] Fix remaining score parsing failures (truncated JSON from think blocks)
- [ ] Implement probe sophistication scoring in validator
- [ ] Separate probing and scoring in example miner (two-phase design)

### Safety report polish
- [ ] Fix formatting bugs in report generator (canary % calculation)
- [ ] Add "limitations and scope" section to reports
- [ ] Redact raw attack prompts in public-facing reports
- [ ] Generate report against testnet target (real findings)

### Threat model follow-up (2026-04-09 dev call)
- [ ] Audit `evaluation_log.jsonl` for fabricated high-severity findings; flag any multi-turn transcripts attributed to the current client subnet (which does not support multi-turn yet)
- [ ] Verify in `subtensor/` source the minimum-stake-to-set-weights constant per network (finney / testnet / localnet); correct `developer-docs/` if the claimed 1000-TAO self-stake requirement is wrong
- [ ] Hold the Qwen3-32B-TEE safety report back from any outreach citation until the eval-log audit completes
- [ ] Audit the sample miner rigs (`safeguard-example-miner/`, `safeguard-hitl-miner/`) for exposed admin endpoints (see [THREAT_MODEL.md](THREAT_MODEL.md) §A5)

## Next up

### HITL miner as real Bittensor miner
- [ ] Refactor HITL miner to FastAPI server (same pattern as AI miner)
- [ ] Register on chain, receive tasks from validator
- [ ] Long-poll or callback pattern for async human responses
- [ ] Validator detects HITL miners via commitment flag `{"type": "hitl"}`
- [ ] Validator uses longer timeout for HITL tasks

### Probing/scoring separation
- [ ] Split example miner into probing agent + scoring agent
- [ ] Design separate incentive mechanisms (Mechanism 0: probing, Mechanism 1: scoring)
- [ ] Validator scores probe sophistication independently from safety scores

### Discord + community
- [ ] Create Discord server (channels per LAUNCH_PLAN.md)
- [ ] Deploy Discord bot (RAG over knowledge base, Chutes inference)
- [ ] Update README with testnet info and participation guide

### Outreach (Wave 1)
- [ ] Safety report as outreach artifact
- [ ] Leonard Tang — Haize Labs (automated red-teaming)
- [ ] Dan Hendrycks — CAIS (HarmBench, safety research)
- [ ] Beth Barnes — METR (evaluation methodology)
- [ ] Include Discord invite + testnet demo in outreach

## Future

### Production HITL storage
- [ ] Encrypted case storage on Bittensor storage subnet (Hippius)
- [ ] On-chain hash commitments for cases and labels
- [ ] Shared canary bank on decentralized storage
- [ ] Multi-validator HITL coordination

### Long-horizon probing
- [ ] Extended single sessions (10-20 turns)
- [ ] Persistent sessions across evaluation cycles
- [ ] Trajectory scoring (conversation direction, not individual turns)
- [ ] Grooming pattern detection for companion AI services

### Cross-subnet integration
- [ ] Partner with 1-2 real subnets to implement relay protocol
- [ ] Subnet-specific submechanisms (companion AI, code gen, agents)
- [ ] Automated threat profile generation for new subnet types

### Relay v2 and adversarial hardening (2026-04-09 dev call)
- [ ] Implement `RELAY_PROTOCOL_V2.md` phase 1 (wrap-v1) in `vali-django/`: new `/relay` endpoint that forwards to the client's existing v1 `/relay`, per-turn SHA-256 canonical-JSON commitments, `RelaySession` + `RelayCommitment` models, audit-time re-verification. Miner-side change: prefer `safeguard_relay_endpoint` over `target_validator_endpoint` when both are present. Execution-plan phases will be added in the vali-django session, not here.
- [ ] (Phase 2 of v2, deferred) Swap the v2 forwarder from "call client v1 /relay" to direct target-subnet access. Requires picking a cross-subnet credential option (scoped delegation token, hotkey registration on client subnet, mTLS, or per-subnet adapter). Not on the phase 1 critical path — wrap-v1 closes the confirmed A1 fabrication attack without it. See `RELAY_PROTOCOL_V2.md` "Future phase 2".
- [ ] Evaluate enabling Liquid Alpha on the Safeguard subnet (cold-start miner discovery via faster bond growth; see [`dev-call-notes-2026-04-09.md`](dev-call-notes-2026-04-09.md) §10)
- [ ] Decide miner IP privacy strategy: relay-hidden (SN64 pattern) vs. validator-ingress proxy vs. published-but-hardened (see [THREAT_MODEL.md](THREAT_MODEL.md) §A5)
- [ ] Evaluate encrypted miner-validator transport via on-chain remark protocol's hotkey ECDH (blocked on wallet extension key-agreement exposure; see [`dev-call-notes-2026-04-09.md`](dev-call-notes-2026-04-09.md) §9)
- [ ] Validator-side execution (gradient-pattern) variant as a deeper research spike if the provenance hash-chain in v2 proves insufficient (see [DESIGN.md](DESIGN.md) §Architectural variant)

### Research
- [ ] Adversarial AI red-teaming study (how to make AI miners more effective despite safety training)
- [ ] Safety evaluation methodology paper (tiered validation + HITL feedback)
- [ ] Grant applications (Coefficient Giving, Schmidt Sciences — per outreach_targets.md)
- [ ] Byzantine relay case — TEE attestation, multi-validator relay consensus, external witness co-signing ([THREAT_MODEL.md](THREAT_MODEL.md) §A4)
- [ ] Client sandbagging detection — proving the service probed by Safeguard is the same service the client's real users see ([THREAT_MODEL.md](THREAT_MODEL.md) §A3)
- [ ] Cross-subnet credential — structural and contractual form of the credential the Safeguard validator would hold for each client subnet if/when v2 phase 2 ships. Not blocking ([RELAY_PROTOCOL_V2.md](RELAY_PROTOCOL_V2.md) "Future phase 2")
- [ ] Validator self-degradation detection — how to tell from outside that a Safeguard validator is running its full audit pipeline ([THREAT_MODEL.md](THREAT_MODEL.md) §A2, open question 4)
- [ ] HITL labeler collusion detection ([THREAT_MODEL.md](THREAT_MODEL.md) open question 5)

---

## Key documents

| Document | Purpose |
|----------|---------|
| `DESIGN.md` | Architecture, participants, validation, scoring, future directions |
| `HITL_DESIGN.md` | HITL short-term and production architecture |
| `RELAY_PROTOCOL.md` | Relay endpoint spec for partner subnets (v1, client-side — currently deployed) |
| `RELAY_PROTOCOL_V2.md` | Validator-side relay with per-turn hash commitments (design target, not yet implemented) |
| `THREAT_MODEL.md` | Safeguard-as-target adversary model: A1–A6, defection incentives, open research questions |
| `LOCAL_DEPLOY.md` | Local chain setup guide |
| `ROADMAP.md` | This file — project tracker |
| `ETHICS.md` | Ethical design principles, HITL welfare, privacy, epistemology |
| `ADVERSARIAL_RED_TEAMING_STUDY.md` | Research: state of the art in adversarial AI red-teaming (Safeguard-as-attacker). Complement to `THREAT_MODEL.md` (Safeguard-as-target) |
| `dev-call-notes-2026-04-09.md` | Raw extraction from the 2026-04-09 community dev call — source for `THREAT_MODEL.md`, `RELAY_PROTOCOL_V2.md`, and the `DESIGN.md` provenance subsection |
| `knowledge/outreach_strategy.md` | Outreach approach and draft messages |
| `knowledge/outreach_targets.md` | Tiered contact list |
