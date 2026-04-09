# Dev call notes — 2026-04-09

Source: Otter transcript from a community dev call. Other participants included Brad
(who raised the provenance attack), the dev building the on-chain remark protocol and
the chain simulator, plus the docs-nav person and a few others. This file is raw
extraction — no interpretation beyond labeling each item as **insight**, **TODO**, or
**research**. Integration into `DESIGN.md`, `ROADMAP.md`, `RELAY_PROTOCOL.md` is a
separate pass.

---

## 1. Miner output provenance is unverified (CRITICAL)

Brad's finding. This is the headline of the call.

- **insight** — A Safeguard miner can return a completely fabricated "malicious
  response" without ever calling the target service. The current pipeline has no
  way to verify that the text in the transcript actually came out of the target
  model. Brad literally demonstrated this by pre-generating chat responses that
  "look like the chat model did something malicious" and submitting them whenever
  a probe was assigned.
- **insight** — This is not a theoretical problem. Michael confirmed it live
  against his own `evaluation_log.jsonl`: severity-0.95 multi-step "findings" from
  miner UID 5 that cannot have been real, because (a) Michael's real client
  service doesn't support multi-turn conversations yet, and (b) his Chutes budget
  was too low to have actually serviced the requests. The "findings" were the
  miner hallucinating them. Quote: *"so that's from your miners, I guess... I'm
  sure that's not the worst problem, but that is a devastating problem."*
- **insight** — The architectural root is that the current design trusts the
  miner to report both what it asked and what came back. Subnet owners (and
  clients) have no reason to trust miners because the incentive mechanism pays
  for "finding" hits, and the cheapest way to find a hit is to invent one.
- **TODO (concrete)** — Audit `safeguard/evaluation_log.jsonl` for fabricated
  high-severity findings. Flag any multi-turn transcripts attributed to the
  real client subnet that the client couldn't have produced. Do not publish any
  report that draws on unaudited data.
- **TODO (concrete)** — Never publish another safety report until the provenance
  problem is at least partially solved. The published report against Qwen3-32B-TEE
  (see `ROADMAP.md`) needs to be re-verified against this concern before any
  further outreach uses it.
- **TODO (concrete)** — Define a provenance protocol: at the relay boundary,
  insert a hash (or signature) of the target-miner response into the transcript
  record, and require the Safeguard miner to include that hash verbatim in its
  submission. The Safeguard validator recomputes/verifies against the relay's
  record. This requires the relay to be trusted, which ties to item 3 below.
- **research** — Full Byzantine solution (relay is also untrusted) is harder.
  Possibilities: per-turn signature chains, TEE attestation on the relay,
  multi-validator relay consensus. Not blocking for testnet, blocking for mainnet.

## 2. Testnet weight-setting has no stake floor (CRITICAL)

This corrects a wrong assumption in Michael's mental model and probably corrects a
wrong statement in developer-docs.

- **insight** — Confirmed live on testnet 444: there is **no minimum stake to
  set weights on testnet**. Michael had assumed a 1000-TAO global stake floor
  was required (and had thought his earlier failed `set_weights` was because he
  hadn't self-staked). Wrong. He fooled himself. The community dev checked the
  chain state during the call: on testnet the limit is effectively zero.
- **insight** — Mainnet *might* still have a 1000-TAO floor; the constant
  differs across networks. "I know there's a bunch of storage parameters and
  constants that have different values on mainnet and testnet... I guess I
  would have thought there was not a risk of some pirate validator coming along
  and just setting weight to themselves and taking over the subnet." There is
  such a risk, at least on testnet, and nobody in the room was confident about
  mainnet.
- **insight** — This massively amplifies the existing
  `project_safeguard_validator_silence` memory. That memory was written as a
  risk hypothesis; the call confirms the risk is live and does not require the
  attacker to already be a big stakeholder. Any random hotkey can do it on
  testnet.
- **TODO (concrete)** — Verify in `subtensor/` source what the actual
  minimum-stake-to-set-weights constant is on each network (finney vs. testnet
  vs. localnet). Check the relevant pallet — likely `subtensor::pallet` weight
  extrinsic, look for the StakeThreshold / weights-set-rate constant. Do not
  trust the docs on this one.
- **TODO (concrete, docs side)** — Once the real value on each network is
  confirmed, fix whatever doc in `developer-docs/` says a 1000-TAO self-stake is
  required. Michael thinks this was how he picked up the wrong mental model in
  the first place. This is a docs bug with real security implications because
  it hides the pirate-validator vector.
- **TODO (concrete)** — Any mainnet deployment of Safeguard must treat validator
  uptime as P0. This is already noted in `project_safeguard_validator_silence`
  but needs ROADMAP reinforcement.

## 3. Relay belongs inside the validator, not the client

This is an architectural flip from the current `RELAY_PROTOCOL.md`, which puts
`/relay` on the client (target-subnet) validator.

- **insight** — For provenance to be verifiable, the relay needs to live on the
  Safeguard validator side, not the client side. Michael: *"the relay will be
  part of that [vali-django]. So if you're mining against that validator, then
  you'll be routed through that validator's relay infra."*
- **insight** — This gives a model where all Safeguard validators run the
  vali-django app, share a database for mutual-interest state (cases, evaluation
  data), and every Safeguard miner's probes are funneled through the validator's
  relay. That way the validator holds the ground truth about what the target
  service actually returned, and can sign/hash it before the miner sees it.
- **insight** — The client subnet's role becomes handing the validator a
  credential / forwarding agreement, not hosting the relay endpoint themselves.
- **TODO (concrete)** — Re-spec the relay placement in `RELAY_PROTOCOL.md` as a
  follow-up pass after this file is reviewed.
- **TODO (concrete)** — Add a `/relay` module to `vali-django/validator/` and
  plan how it coordinates with the existing per-miner dispatch loop.
- **research** — Define the per-turn hashing scheme: what gets hashed (full
  response? canonicalized body? response + session id?), what the miner must
  echo back, and how the validator reconstructs verification at scoring time.
- **research** — How does the validator authenticate to the target subnet
  itself? The existing `RELAY_PROTOCOL.md` answered this for the client side
  ("the target validator uses its own auth"). When the relay moves to our side,
  the Safeguard validator now needs some credential or delegation to reach the
  target miners. This is a real open problem, not a detail.

## 4. Treat the client as hostile-but-cooperating

- **insight** — The client is not adversarial in the same way a random internet
  attacker is, but the architecture must assume they can lie. The client has a
  commercial reason to cooperate (they want certification), but a commercial
  reason to game the result (they want a passing score). So: cooperation is
  expected and can be required via gates, but every cooperation point needs a
  verification hook.
- **insight** — Main thing to verify about the client: *their production miner
  service = the service they're offering to Safeguard probes*. If a client runs
  a sandbagged copy for Safeguard and the real service for their customers,
  they pass certification without actually being safe. Michael: *"that's the
  main thing we have to test about the client. And I'm not sure how to solve
  that problem either yet, but the relay somehow."*
- **research** — How do you prove the probed service == the production service?
  Possibilities floated or implied: require the client to route Safeguard traffic
  through the same validator path as real user traffic; hash-commit production
  responses and spot-check; statistical fingerprinting of responses; TEE
  attestation on the client side. No solution yet, just the open problem.
- **research** — Can we use the client-validator's own validator permits or
  staking history as a reputation signal to limit which clients can request
  certifications in the first place? Orthogonal to the gaming question but
  relevant.

## 5. Adversarial hardening has to be central, not retrofit

- **insight** — *"You can't really design it as a pipeline without thinking
  about the adversarial hardening part... on mainnet you have to think about
  that absolutely first."* Michael acknowledged the current codebase was
  designed cooperative-first and needs to be re-approached adversarial-first
  before mainnet.
- **insight** — Everything downstream of this call should be evaluated against
  "would this survive if every party were Byzantine" as the first-pass filter.
  Tokenomic robustness is in the same category — not a bolt-on.
- **research** — Systematic threat model document. `ADVERSARIAL_RED_TEAMING_STUDY.md`
  already exists but focuses on miner effectiveness (i.e. Safeguard as the
  red-teamer, not Safeguard as the target of red-teaming). A complementary
  doc mapping every participant (miner, validator, client, HITL labeler, target
  subnet) to its attack surface and economic incentive to defect is missing.

## 6. Validator-side inference (gradient pattern) as a possible pivot

This came up near the end, triggered by Michael's "should I just fork bittensor"
tangent, but it's actually the most interesting concrete alternative.

- **insight** — Gradients subnet moved from a "each miner runs inference" model
  to a "miners submit code/strategies, validator runs the inference inside a
  trusted sandbox" model. The business reason was that enterprise partners won't
  trust random miner machines with training data. The safety reason is it
  eliminates an entire category of miner cheating.
- **insight** — For Safeguard, the analogous pivot is: miners submit *probe
  strategies / prompts*, and the validator itself runs the inference against
  the target service and observes the result. The miner is rewarded if its
  prompts elicited a bad response. Provenance is free because the validator
  controls the call. Cheating by fabricating responses becomes impossible by
  construction.
- **insight** — This also cleanly separates the mining task into a pure
  prompt-engineering competition, which is what Safeguard actually cares about
  anyway.
- **research** — Biggest open question: does this work when the "inference" is
  a call to a *foreign* subnet's miner? The gradient pattern is naturally
  suited to training jobs the validator runs locally. Safeguard's inference
  target is across a subnet boundary. The validator would need to hold the
  credential to hit the client's relay (which ties back to item 3). It's
  doable but it's not the gradient pattern verbatim — it's gradient-pattern
  for prompts + validator-held relay credential.
- **research** — If probes become just prompt strings, the incentive surface
  changes: miners compete on creativity / novelty. How is that scored? Semantic
  dedup against already-tried prompts? Post-hoc scoring on which prompts
  produced verified findings? Cross-reference `design_2.md` bait-suggestion
  mechanism — this is close in spirit and the reward mechanics may map.
- **TODO (concrete)** — Sketch an alternate architecture diagram in a new
  `design_3.md` (or update `DESIGN.md` with a "validator-side execution"
  variant section) once the user has reviewed these notes and picked a
  direction.

## 7. Separation of mining tasks

- **insight** — Already on the roadmap (ROADMAP.md: "Probing/scoring
  separation"). The call reinforced this by pointing out that under the
  gradient pattern, some sub-tasks (scoring, analysis) may live entirely on
  the validator and not be mining tasks at all.
- **insight** — Mechanism 0 (probing), Mechanism 1 (scoring) is the current
  plan. Under gradient-pattern the breakdown could become probing-only as a
  mining task, with scoring as pure validator-side work.
- **research** — If scoring lives on the validator, how do multiple validators
  stay in agreement on scores? This is the normal Yuma consensus problem and
  is probably fine, but worth writing down.

## 8. Miner DDoS / IP exposure as an attack surface

- **insight** — The on-chain remark protocol dev showed receive logs from a
  Hetzner VPS: within ~20 seconds of his miner process starting, he was being
  hit by scans on `/admin`, `/base`, `/home`, `/local`, `/remote`, `/login`,
  `/artist`, `/identity`, `/scripts`, `/matrix-identity`, etc. Same source IPs
  hitting his strapi backend too.
- **insight** — Likely attack vector: bots scrape published miner IPs from the
  chain (metagraph, commitments) and probe them immediately for open
  admin/default endpoints. This is a global crawl, not a targeted attack.
- **insight** — Subnet 64 (Chutes) hides miner IPs entirely by running a
  centralized relay server. Miners connect outbound to the relay; the chain
  never publishes their IPs; validators only see the relay address. Tradeoff:
  centralized but private.
- **insight** — On latency-sensitive subnets, DDoS of a single miner can push
  them out of consensus. Safeguard is less latency-sensitive but the miners are
  still attackable for any reason (including by the client wanting to suppress
  probing that's producing unflattering scores).
- **TODO (concrete)** — Decide whether Safeguard miners publish IPs directly or
  sit behind a relay. For mainnet this is a real decision with real tradeoffs.
- **research** — What's the "hide miners behind a relay" pattern look like if
  you want to keep decentralization? Possibilities: each validator runs a
  miner-ingress proxy for miners it's assigned, rotating assignment, etc.

## 9. Encrypted miner-validator communication (researchy)

- **insight** — Epistula (the current mining-side auth) has no body encryption.
  "It just defaults to, you like, just do what you're supposed to do, it at
  some other layer." So every probe prompt and response is in clear on the
  wire between Safeguard validator and Safeguard miner.
- **insight** — The on-chain remark protocol dev is building a
  hotkey-based ECDH key-agreement flow (scalar-multiply my private key by your
  public key, get a shared secret, encrypt with that). It works for CLI
  clients today. Blocked for web clients because the wallet extension does not
  expose the key-agreement function, even though it exists in the underlying
  wallet software.
- **insight** — If that key-agreement function gets exposed (or if Safeguard
  ships its own CLI/desktop client that uses it directly), then miner-validator
  messaging with end-to-end encryption using hotkeys becomes trivial. The
  protocol has reserved content-type ranges for application extensions — a
  Safeguard-specific content type could carry probes or results over chain
  remarks, with full encryption.
- **research** — Evaluate whether to adopt the remark-based transport or keep
  Epistula and add a symmetric encryption layer. The remark transport has
  interesting censorship-resistance properties (messages are on chain, mirrors
  can only censor by omission and you can point at multiple mirrors).
- **research** — Not urgent. Filed for later.

## 10. Liquid Alpha for cold-start miners

- **insight** — Liquid Alpha modulates the α parameter in the bond-growth EMA
  based on a miner's consensus level. A high-α bond grows faster. The practical
  effect: validators who *find* a miner before it has broad consensus get their
  bonds with that miner boosted, which eventually yields more dividends if that
  miner becomes a top performer.
- **insight** — This is a structural answer to the cold-start problem where
  validators ignore new miners because bonds with low-incentive miners are
  worthless. Liquid Alpha pays validators for early discovery. It also
  penalizes weight-copiers because they always come late.
- **insight** — "Why don't people use liquid alpha?" "They don't even know what
  it is." It's apparently underused across the ecosystem. For a subnet like
  Safeguard that wants to reward discovering new effective red-teamers, it
  sounds directly applicable.
- **TODO (concrete)** — Decide whether to enable Liquid Alpha on the Safeguard
  subnet. Requires reading the current Liquid Alpha code in `subtensor/` to
  understand what the actual on/off switch looks like and what range of α
  makes sense.
- **research** — Does Liquid Alpha interact well with the HITL submechanism?
  HITL miners have fundamentally different tempo from AI miners, and the
  bond-growth dynamics assume continuous task assignment.

## 11. Bond dynamics literacy

This was a side detour but important context.

- **insight** — Validator dividends per miner = (consensus column or similar) ×
  bonds × miner incentive. The loyalty part: even at equal current quality,
  history with a miner gives you more bond mass and therefore more dividends.
- **insight** — It's the reason liquid alpha works (item 10): early bonds are
  heavier bonds.
- **insight** — Collusion concern raised in the call: if one validator can
  hog bond mass with one miner, does that distort consensus? Current answer
  seems to be no, because setting weights outside consensus still loses you
  rewards up front, and the "loyalty bonus" only pays off if the miner
  eventually gets broad consensus.
- **TODO (docs side)** — This is owed to the subnet-creator's-guidebook
  project (see `project_subnet_creators_guidebook` memory). Not a
  Safeguard-internal TODO but noted so the cross-reference exists.

## 12. Should Safeguard fork Bittensor entirely? (researchy hypothesis)

Michael's tangent near the end of the call. Recorded as an open strategic
question, not a near-term decision.

- **hypothesis (Michael)** — If you need revenue anyway for any subnet to
  survive, and you don't want to deal with a hostile community of miners and
  validators on BT, why not clone the bittensor chain, run it yourself, and
  hand out TAO from a genesis wallet to vetted parties (university researchers,
  volunteers, mission-aligned orgs) who run validators for you? You get
  distributed validation without the BT adversarial environment.
- **counter (community)** — If you don't need the BT actor pool, you can still
  do it. But if you need miners, BT doesn't give them to you for free — you
  have to incentivize them on any chain. The actual leverage from BT is
  incentive-agnostic subnet mechanics + an existing pool of participants + TAO
  itself as a medium of exchange.
- **counter (Michael, implicit)** — You already have to fund your own mining
  economy via revenue on BT, so "BT gives you miners" is overstated. The actual
  BT benefit is the shared security / liquidity / brand, not the actor pool.
- **research** — This is genuinely open. For now: stay on BT, but note that if
  adversarial hardening (items 1-5) turns out to be much more expensive than
  the marginal BT benefit, the fork option is on the table.

## 13. On-chain miner reputation (researchy governance)

- **insight** — Recurring theme: subnet owners don't trust miners because of
  incentive mismatch, but some miners have long cold-key histories of
  participating in good faith across many subnets. There's no mechanism
  currently for a miner to carry that reputation across subnets or get
  governance weight for it.
- **insight** — Michael: *"if there's a particular miner based on their cold
  key that has some metrics of good, like, robust long term good participation
  and lots of subnets and the mining work that they do is good... it's not
  impossible. I don't think it's an unsolvable problem to like have some kind
  of signature for that on chain, and then you could give some weight to
  people that have actually built the frickin commodities that your entire
  platform is based on."*
- **research** — Broader BT ecosystem question. Not a Safeguard-specific item,
  but relevant for how Safeguard might choose to weight HITL participants vs.
  AI miners vs. probe-strategy submitters in its governance. Filed.

---

## Quick follow-up list (concrete, actionable, in rough priority)

1. **Audit `evaluation_log.jsonl`** for fabricated high-severity findings; flag
   anything multi-turn attributed to the current client subnet (which can't
   produce multi-turn yet). Until done, treat the published Qwen3-32B-TEE safety
   report as unverified.
2. **Verify in `subtensor/` source** the actual minimum-stake-to-set-weights
   constant on mainnet vs testnet. Fix `developer-docs/` if wrong.
3. **Re-spec relay placement** (validator-side, not client-side) in a follow-up
   pass through `RELAY_PROTOCOL.md` and `DESIGN.md`.
4. **Design a provenance hashing scheme** for the per-turn relay boundary.
5. **Sketch the validator-side-execution (gradient-pattern) alternative** as a
   second architecture variant — `design_3.md` or a section in `DESIGN.md`.
6. **Decide on miner IP privacy**: published IPs vs relay-hidden. Mainnet
   decision.
7. **Evaluate enabling Liquid Alpha** on Safeguard. Read the code, check the
   knobs, decide.
8. **Write an adversary-model document** (complement to
   `ADVERSARIAL_RED_TEAMING_STUDY.md`) mapping every participant to its
   defection incentives and attack surface.

## Open research questions parked for later

- Cryptographic provenance under a fully Byzantine relay (TEE? multi-validator
  consensus? signature chains?)
- How to prove client's probed service == production service
- How validator authenticates to target subnet when relay moves to Safeguard side
- Whether prompt-only mining (gradient-pattern) composes with current
  bait-suggestion mechanics in `design_2.md`
- Encrypted transport via on-chain remarks as an alternative to Epistula
- Liquid Alpha × HITL submechanism interaction
- Fork-vs-stay-on-BT strategic question
- On-chain cross-subnet miner reputation
