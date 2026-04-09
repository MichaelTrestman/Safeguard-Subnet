# vali-django: Completion + Perfection Plan

> **Authoritative plan as of 2026-04-08, amended 2026-04-09.** Supersedes
> and absorbs the earlier `safeguard/VALI_DJANGO_LOOP_PORT_PLAN.md`, which
> has been deleted. The phasing below reflects the post-burn-floor /
> EMA-removal / cycle-history design landed in `safeguard/validator.py`
> on 2026-04-08, plus the schema and dashboard gaps that work created.
>
> **2026-04-09 amendments:**
> - Decisions A–E (see Decisions section below) are now human-confirmed
>   and locked. Phase 2.0 (schema migration) is unblocked.
> - **Phase 6 (seed-from-legacy command) removed entirely.** All testnet
>   444 data is disposable test data; there is no production state to
>   migrate. Gap H and Phase 6 are struck through below as REMOVED, with
>   the dependency DAG and Phase 9 retirement steps updated to match.
>   The `OPERATOR.md` runbook deliverable that was bundled with Phase 6
>   moves to Phase 10 (polish).

---

## Why this work matters (one paragraph, then we're done with framing)

vali-django is the production face of the Safeguard subnet — the system that
other Bittensor subnets pay to red-team their AI deployments before exposing
them to real users. Every successful `set_weights` call is real economic
signal that determines which AI-safety work gets funded across the network.
If the validator is not running, safety evaluation for downstream customer
subnets stops being available, and the worst-case is silent: a captured weight
slot, paying out emissions to whoever happens to be there. The legacy
`safeguard/validator.py` works but is a single-process, file-state-based,
self-restarting binary that can lie to its own dashboard. vali-django
replaces that with a single Django ASGI process where the chain loop and the
operator UI share a database transaction, so the dashboard cannot lie about
liveness. Completing it is the prerequisite for every other safety effort
on this subnet.

---

## What is already true (read once, do not redo)

| Piece | State | Source of truth |
|---|---|---|
| Project scaffold + settings + URLs + migrations applied | ✅ | `valiproject/`, `validator/migrations/0001_initial.py` |
| ASGI lifespan handler that starts the loop, owns shutdown, fails-loud on startup error | ✅ | `valiproject/asgi.py` |
| Wallet loading from `~/.bittensor/wallets/<W>/hotkeys/<H>` (no env-var indirection) | ✅ | `validator/wallet.py` |
| Layer-1 wallet flock (catches another vali-django on the same host) | ✅ | `validator/wallet_lock.py` |
| Epistula auth shim (re-exports from `safeguard/epistula.py`) | ✅ | `validator/epistula.py` |
| Customer portal: `/register`, `/evaluate`, `/status`, `/registry`, all Epistula-authed | ✅ | `validator/views.py` |
| Operator dashboard (4 cards: loop status, wallet, last set_weights, chain) + per-target detail page | ✅ | `validator/templates/validator/operator_dashboard.html` |
| Honest `/healthz` (wallet + tick age + weight age) | ✅ | `validator/views.py:healthz` |
| Dockerfile + k8s manifest (Deployment + Service + PVC + Secret example) | ✅ | `Dockerfile`, `k8s/` |
| End-to-end boot smoke test (venv install → migrate → uvicorn → wallet load → loop tick → healthz green → dashboard renders) | ✅ | per `README.md` |

**Architectural decisions already made and not up for renegotiation:**
- Single asyncio task in the lifespan handler — no threads, no
  `ThreadPoolExecutor`, no `os.execv` self-restart. k8s owns restarts.
- All chain RPCs wrapped as `await asyncio.wait_for(asyncio.to_thread(fn,
  *args), timeout=...)`. The same per-call deadline pattern as
  `safeguard/validator.py:_chain_call()` but using asyncio cancellation
  instead of an executor future.
- All Django ORM access via `asgiref.sync.sync_to_async` (handles
  `connection.close_old_connections()` correctly).
- One process per pod, `replicas: 1`, `strategy: Recreate`. HA = a SECOND
  Deployment with a DIFFERENT hotkey, never two pods sharing one wallet.
- All state in the DB. No JSONL files emitted by vali-django itself.
  (`safeguard/validator.py` keeps its JSONLs until retired.)

---

## Gaps between vali-django and the current `safeguard/validator.py`

This is the work. Items are ordered by dependency, not priority.

### A. Schema gaps (the DB cannot represent the new state we ship)

| Field / model | Where | Status | Notes |
|---|---|---|---|
| `MinerScore.submissions, findings_count, bait_only_count, null_count, last_contribution` | `validator/models.py` | **missing — to add** | Lifetime counters added to legacy `MinerScore` 2026-04-08. Observability only — does not feed weights, but the operator dashboard reads them. |
| `MinerScore.score`, `contribution_total` | `validator/models.py` | **to delete (Decision A)** | Both vestigial. Chain bond EMA owns "current standing" and chain dividend history owns "lifetime tau earned"; duplicating either locally guarantees drift. |
| `ValidatorStatus.owner_uid, last_burn_share, last_set_weights_payload (JSON), last_set_weights_success` | `validator/models.py` | **missing** | Added to `validator_status.json` 2026-04-08. The operator dashboard panel I just shipped on the legacy `dashboard.py` reads these. |
| `CycleHistory` model (one row per cycle) | `validator/models.py` | **missing** | Mirrors `cycle_history.jsonl` rows. Fields: `timestamp`, `cycle_block`, `n_registered`, `n_dispatched`, `n_responded`, `n_earned`, `earned_total`, `burn_share`, `owner_uid`, `submitted_weights` (JSON), `had_fresh_data`. |
| `Finding` model | `validator/models.py` | **already exists** but unused — loop never writes to it | When the audit pipeline lands (phase 4), each accepted_severity > FINDINGS_THRESHOLD evaluation gets one or more `Finding` rows. |
| `HitlCase` model | `validator/models.py` | **already exists** but unused | Same — written when the audit disagreement crosses threshold. |

### B. Loop body gaps

The entire chain logic is unwritten in `validator/loop.py`. Concretely
missing (in dependency order):

1. **Subtensor + metagraph startup** — currently nothing connects to chain
2. **Owner UID resolution** — `subtensor.get_subnet_owner_hotkey(netuid)` →
   `get_uid_for_hotkey_on_subnet()`, with UID-0 fallback. Must run at
   startup, cached on a module-level or status field for the burn floor.
3. **Subnet hyperparameters** — fetch `tempo` once at startup; never
   re-fetch (it's stable).
4. **Per-iteration metagraph sync + current block fetch** — both with
   `_chain_call`-style timeouts.
5. **Miner discovery** — port `discover_miners()` from
   `safeguard/validator.py`. Reads `subtensor.get_all_commitments(netuid)`,
   filters to probe vs HITL, returns `{uid: endpoint}`.
6. **Probe dispatch** — for each `RegisteredTarget`, build a
   `ProbingTask`, dispatch in parallel via `httpx.AsyncClient` with
   `MINER_QUERY_TIMEOUT` (600s — miners make multiple LLM calls per
   task). Bound concurrency with `asyncio.Semaphore(MAX_PROBE_CONCURRENCY)`,
   default 8. **Wire format must match RELAY_PROTOCOL.md exactly** —
   verify against the safeguard-miner running on testnet 444 before
   debugging in production.
7. **Audit pipeline** — call `classify_transcript()` and `judge_transcript()`
   from `safeguard/llm_judge.py` via `asyncio.to_thread()`. Compute
   `accepted_severity = miner_safety_score × confidence_in_claim` and
   `findings_reward = accepted_severity × concerns_weight[category]`. Bait
   detection runs only when `findings_reward < FINDINGS_THRESHOLD`.
   **Port the formulas verbatim from `validator.py:update_miner_scores()`,
   do NOT rewrite the math.**
8. **Score writes** — for each result: upsert `MinerScore` row (lifetime
   counters), append `Evaluation` row (per-submission), maybe append
   `Finding` row (if `findings_reward >= FINDINGS_THRESHOLD`), maybe append
   `HitlCase` row (if disagreement > 0.3 and findings present).
9. **Burn-floor `compute_weights`** — port from `validator.py:651-691`. Two
   inputs: per-cycle contribution dict + owner_uid. Always returns a
   non-empty vector. **No local EMA, no last-known-good fallback, no skip
   branch.**
10. **`set_weights` call** — `await asyncio.wait_for(asyncio.to_thread(
    subtensor.set_weights, ...), timeout=CHAIN_TIMEOUT_SET_WEIGHTS)`.
    On success, write to `ValidatorStatus.last_set_weights_*` fields AND
    append a `CycleHistory` row, in a single transaction.
11. **Tempo cadence** — only call set_weights when
    `current_block - last_set_weights_block >= tempo`. The
    `cycle_collected_fresh_data` retry-on-empty logic from `validator.py`
    can be ported as-is or simplified to "always advance the timer after
    successful set_weights" (cleaner under the burn floor; see
    Decision-Point D below).
12. **Mech 1 HITL set_weights** — flat 1/N split across HITL miners.
    Currently a separate set_weights call in `validator.py:1503-1528`.
    Port the same way; HITL audit/scoring is still TBD design work and
    is a non-goal for this phase.
13. **Per-tick status writes** — each iteration writes the new
    `ValidatorStatus` fields (current_block, blocks_until_next_cycle,
    n_probe_miners, n_hitl_miners, owner_uid). Mirrors what
    `validator.py` writes into `validator_status.json`.

### C. Operator dashboard gaps

Once the loop body lands, the operator dashboard needs to surface the new
data. Currently 4 cards; missing:

- Owner UID + last burn share (one card with a `FULL BURN` chip when
  `last_burn_share >= 1.0`)
- Cycle history table (last ~20 cycles, columns: when / block /
  registered / dispatched / responded / earned / burn% / weights)
- Probe miner roster (UID / hotkey / status flags / lifetime counters /
  this-cycle contribution / current weight). The status flags
  (active / silent / new / gone) come from joining
  chain commitments × MinerScore × CycleHistory.
- HITL miner roster (separate section, since they're scored on a
  different mechanism)
- Last chain error (already in the schema, currently rendered as a
  card; probably keep it that way)

### D. JSON API for the operator dashboard

The legacy `dashboard.py` has `/api/summary`, `/api/cycles`, etc. for
external monitors and any future tooling. vali-django's operator
dashboard is currently server-rendered HTML only. Adding a parallel
`/api/v1/*` JSON layer is cheap and keeps options open for future
integrations. **Optional for phase 2.**

### E. Audit pipeline + bait library wiring

`safeguard/llm_judge.py` and `safeguard/bait/library.json` live one
directory up. Two options:
- **Sys.path shim** like `validator/epistula.py` — fastest, keeps the
  legacy module as the source of truth, easy to retire later
- **Copy in** as `validator/audit.py` and `validator/bait/library.json` —
  cleaner ownership boundary, but means maintaining two copies until
  the legacy validator retires

Recommend the sys.path shim until phase 9 (legacy retirement); then
copy in and delete the shim.

### F. HITL escalation + dispatch

`HitlCase` model exists but no view, no annotation flow, no dispatch
path. The legacy validator dispatches `HitlCase.objects.filter(
status='pending')` to mech-1 HITL miners each cycle. Port that path,
but defer the annotation UI (operators interact with HITL via
`hitl_labels.jsonl` today; vali-django can stage that UI as a phase 4
deliverable).

### G. Tests

Zero tests currently. The README says they're pending. Highest-value
suite (in this order):

1. **Burn-floor unit test** — `test_compute_weights_burn_floor.py` style.
   Port the test from `safeguard/tmp-scripts/`.
2. **`/evaluate` integration test** — seed an `Evaluation` row, hit
   `/evaluate` with a valid Epistula header, assert `safety_score`.
3. **Loop iteration test** — mock the subtensor, mock the miner HTTP,
   run one iteration end-to-end, assert that
   - one `Evaluation` row is created
   - `MinerScore` counters tick
   - `ValidatorStatus.last_tick_at` updates
4. **Burn-floor end-to-end test** — same but with zero responsive miners,
   assert that `set_weights` was called with `[(owner_uid, 1.0)]` and a
   `CycleHistory` row records `burn_share=1.0`.

### H. Seed-from-legacy command — REMOVED 2026-04-09

~~A `python manage.py import_legacy_state` command to upsert
`RegisteredTarget` rows from `target_registry.json` and optionally
backfill `Evaluation` / `CycleHistory` rows from the legacy JSONL
files.~~

**Removed because:** all testnet 444 data is disposable test data.
There is no production state to migrate. Cutover from legacy
`safeguard/validator.py` to vali-django happens by stopping the legacy
process, starting vali-django on the same wallet (operator-driven via
`VALIDATOR_WALLET` env var), and letting it accumulate fresh state from
zero. The wallet flock catches accidental relaunches of the legacy.

### I. Layer-2 wallet defense (the universal one)

Currently deferred per the existing port plan. With safeguard
expanding beyond a single operator's deployment, this matters more:

> Before every `set_weights` call, query the chain for the most recent
> weight-set extrinsic from our hotkey on this netuid. If it was within
> the current tempo and was not from this process, skip our submission
> and log it. The chain will reject the second extrinsic anyway, but
> this saves the wasted compute and gives a clean operator log line.

Concretely: query `Subtensor.get_last_weights_set(hotkey, netuid)` (or
equivalent) and compare against the block we expect. If newer than our
last submission, defer.

### J. SubtokenDisabled detection

Per the project memory note (`project_subtoken_disabled.md`), testnet
444 has `SubtokenDisabled` until `btcli subnets start` is run. The
validator should:
1. Detect this on startup via the appropriate chain query
2. Surface it on the operator dashboard as a clear "subnet not yet
   started" warning
3. Continue ticking the loop (the burn floor still works in this
   state — it's a chain-side burn, no staking required)

### K. Documentation gaps

- No CONTRIBUTING.md (probably fine)
- No CHANGELOG.md (worth adding when the loop body lands, just so
  community operators know when their behavior will change)
- Operator runbook: "what to do when /healthz goes red" — short doc

---

## Phasing

Each phase ends with a smoke test or measurable criterion. Do NOT
batch phases — land each, verify, then start the next.

### Phase 2 — burn-floor-aware loop body (THE BIG ONE)

This is the core port. Replaces the existing port plan's chunks 1-5
with the post-burn-floor design. ~7 sub-steps, each smoke-testable.

**Sub-phase 2.0: schema migration** (one migration `0002_burn_floor_schema.py`,
deploy alone before any loop work)
- `MinerScore`:
  - DROP `score` (Decision A — chain owns this)
  - DROP `contribution_total` (Decision A — chain owns this)
  - ADD `submissions IntegerField default 0`
  - ADD `findings_count IntegerField default 0`
  - ADD `bait_only_count IntegerField default 0`
  - ADD `null_count IntegerField default 0`
  - ADD `last_contribution FloatField default 0.0`
- `ValidatorStatus`:
  - ADD `owner_uid IntegerField default 0`
  - ADD `last_burn_share FloatField default 0.0`
  - ADD `last_set_weights_payload JSONField default dict`
  - ADD `last_set_weights_success BooleanField default False`
- New `CycleHistory` model with fields: `timestamp`, `cycle_block`,
  `n_registered`, `n_dispatched`, `n_responded`, `n_earned`,
  `earned_total`, `burn_share`, `owner_uid`, `submitted_weights JSON`,
  `had_fresh_data`. Index on `timestamp` and `cycle_block`.
- `python manage.py makemigrations validator` → review → `migrate`
- **Smoke**: `python manage.py shell` → instantiate each → save → query.
  Verify the dropped fields are gone from `MinerScore._meta.get_fields()`.

**Sub-phase 2.1: chain connect + owner UID resolution**
- Port `_connect_subtensor_with_retry` from `validator.py`
- Add `await asyncio.to_thread(...)` wrapping
- Resolve owner UID via `get_subnet_owner_hotkey` + `get_uid_for_hotkey_on_subnet`,
  fall back to UID 0 with a warning
- Update `acquire_resources()` to do all of this, return
  `(wallet, subtensor, metagraph, owner_uid, tempo)`
- Thread the new return values through `valiproject/asgi.py:lifespan` into
  `run_validator_loop`
- Write `chain_connected=True`, `owner_uid=...` to ValidatorStatus
- **Smoke**: `/healthz` reports `chain_connected: true`, dashboard shows
  the resolved owner UID

**Sub-phase 2.2: miner discovery**
- Port `discover_miners()` to async, with `_chain_call` timeout
- Upsert each discovered miner into `MinerScore` (uid, hotkey, last_seen
  via `auto_now=True`)
- Do NOT delete miners that disappear from the metagraph in the same
  iteration — let them age out
- Write `n_probe_miners`, `n_hitl_miners` to ValidatorStatus per tick
- **Smoke**: log discovered count, compare against
  `btcli s metagraph --netuid 444 --network test`

**Sub-phase 2.3: probe dispatch**
- Build `ProbingTask`-equivalent for each `RegisteredTarget`
- Dispatch with `httpx.AsyncClient` + Epistula headers, bounded by
  `asyncio.Semaphore(MAX_PROBE_CONCURRENCY=8)`
- Persist returned transcripts as in-progress `Evaluation` rows BEFORE
  audit, so a crash during audit doesn't lose work
- Update `RegisteredTarget.last_probed_at`
- **Smoke**: register a target, watch one cycle, see Evaluation rows
  appear in the DB

**Sub-phase 2.4: audit pipeline**
- Sys.path shim or import `safeguard/llm_judge.py`
- Call `classify_transcript()` + `judge_transcript()` via
  `asyncio.to_thread()`
- Compute `accepted_severity`, `findings_reward`, `bait_modifier`,
  `contribution`
- Backfill the in-progress `Evaluation` row with audit fields
- Extract `Finding` rows for `findings_reward >= FINDINGS_THRESHOLD`
- Create `HitlCase` row when disagreement > 0.3 AND findings present
- **Smoke**: dispatch one cycle, see `Evaluation.findings_reward` populated,
  see `Finding` rows where applicable

**Sub-phase 2.5: scoring + cycle contribution map**
- Update lifetime counters on `MinerScore` (mutates in place)
- Build `cycle_contributions: dict[uid, float]` for the current cycle
- This is what `compute_weights` consumes — never persist this dict
- **Smoke**: log the cycle_contributions dict, verify it matches the
  legacy validator's per-result log lines

**Sub-phase 2.6: burn-floor `compute_weights` + `set_weights`**
- Port `compute_weights(cycle_contributions, owner_uid)` verbatim from
  `safeguard/validator.py:651-691`
- Filter contributions to probe miners only (mech 0)
- Call `set_weights` via `asyncio.wait_for(asyncio.to_thread(...))`
- On success, in a single DB transaction:
  - Update `ValidatorStatus.last_set_weights_at, _block, _payload,
    _success, last_burn_share`
  - Append a `CycleHistory` row
- On failure, write `last_chain_error` and continue
- Mech 1 HITL set_weights: separate call, equal weight to all HITL miners
- **Smoke**: cycle log shows `Set weights (mech 0): {...}`,
  `ValidatorStatus.last_set_weights_at` updates, `CycleHistory` row appears,
  cross-check with `btcli wt list --netuid 444 --network test`

**Sub-phase 2.7: tempo cadence + tick hygiene**
- Only enter the cycle when `current_block - last_set_weights_block >= tempo`
- Port the `cycle_collected_fresh_data` first-boot retry logic OR replace
  with always-advance (Decision Point D below)
- Periodic INFO heartbeat log every N iterations
- **Smoke**: `/healthz` stays green for 3 consecutive tempos

**Phase 2 done criteria:**
- vali-django successfully calls `set_weights` on a tempo against testnet
  444 with its own hotkey (NOT the legacy validator's)
- The operator dashboard "Last set_weights" shows a recent timestamp +
  block
- A demo customer query against `/evaluate` returns a real
  `safety_score` (not `fallback: true`)
- `/healthz` stays green across at least 3 consecutive tempos
- A burn-only cycle (kill the miner, wait one tempo) shows `burn_share=1.0`
  in `CycleHistory` and the dashboard
- The legacy `safeguard/validator.py` keeps running unaffected on a
  different hotkey

---

### Phase 3 — operator dashboard upgrades

Now that the data exists in the DB, the operator dashboard becomes
useful. ~150 lines of template + view changes.

- Owner UID + burn share card (with `FULL BURN` chip when applicable)
- Recent cycles table (last 20 from `CycleHistory.objects.order_by('-id')`)
- Probe miner roster table (joins `MinerScore` × current chain
  commitments × current cycle contributions)
- HITL miner roster (separate section)
- Optional: `/api/v1/validator/status`, `/api/v1/cycles`, `/api/v1/miners`
  JSON endpoints for external monitors

**Phase 3 done criteria:**
- Operator can answer "is mining productive right now?" without opening
  the database shell
- "Last burn share" is visible at a glance
- Cycle history table renders correctly across productive, burn-only,
  and mixed cycles

---

### Phase 4 — HITL escalation pathway

The audit pipeline creates `HitlCase` rows; this phase actually does
something with them.

- Port the HITL dispatch loop from
  `safeguard/validator.py:1259-1331` (the per-cycle HITL dispatcher
  with circuit breaker)
- Operator UI: list of pending HITL cases, ability to view transcripts,
  ability to add labels (this can be the simplest possible Django
  CreateView; no auth needed since the operator UI is firewalled)
- Optional: Epistula-authed `/hitl/label` endpoint for community HITL
  miners to submit labels remotely

**Phase 4 done criteria:**
- A disagreement-driven `HitlCase` row appears in the operator UI
- An operator can label it via the UI
- The label updates the corresponding `Evaluation` row
- HITL annotator stats (lifetime label counts) are visible

---

### Phase 5 — tests

Land the test suite from gap G above, in the order listed:
1. Burn-floor unit (port from `safeguard/tmp-scripts/`)
2. `/evaluate` integration
3. One-iteration loop integration with mocks
4. Burn-only end-to-end with mocked silent miners

**Phase 5 done criteria:**
- `pytest` passes from a fresh checkout
- CI config (GitHub Actions or equivalent) runs the suite on every push
- README has a "Run the tests" section

---

### Phase 6 — REMOVED 2026-04-09

~~Seed-from-legacy command + operator runbook.~~

The seed-from-legacy command is gone (see Gap H above). The
`OPERATOR.md` runbook deliverable that was bundled here has been moved
to Phase 10 (polish). The phase number is intentionally left as a gap
to avoid renumbering cross-references in the rest of this document and
in memory files.

---

### Phase 7 — layer-2 wallet defense

Implement the universal pre-set_weights chain check from gap I. This
is what makes vali-django safe to run alongside any other process
sharing the same wallet, including a legacy `validator.py` that has
not been retired yet.

**Phase 7 done criteria:**
- A second process trying to set weights on the same hotkey
  triggers the layer-2 check, refuses to submit, and logs the conflict
- A specific test case (`test_layer2_chain_check.py`) verifies the
  check fires when expected and does not fire when not expected

---

### Phase 8 — subnet bootstrap robustness

- SubtokenDisabled detection at startup
- Operator dashboard warning when the subnet is in pre-start state
- Burn floor verified to work in this state (it's chain-side burn, no
  staking required)
- Documentation: `docs/SUBNET_LIFECYCLE.md` covering pre-start,
  post-start, and the operator's responsibilities at each stage

**Phase 8 done criteria:**
- vali-django booted against a SubtokenDisabled subnet shows a clear
  warning, does not crash, and resumes normal operation when the
  subnet is started

---

### Phase 9 — retire legacy

The big switch. After phases 2-8 are done AND vali-django has been
running stably alongside the legacy validator for at least one week:

1. Stop `safeguard/validator.py`
2. Stop `safeguard/dashboard.py`
3. Update `safeguard/CLAUDE.md` references
4. Move `safeguard/llm_judge.py` and `safeguard/bait/library.json` into
   `vali-django/validator/audit/` and `vali-django/validator/bait/`
5. Delete the sys.path shims
6. Delete `safeguard/validator.py`, `safeguard/dashboard.py`,
   `safeguard/report_data.py`, `safeguard/cross_subnet_api.py` (if it
   still exists)
7. Update `developer-docs/` references to point at vali-django
8. Tag a vali-django 1.0.0 release

(No data migration step — testnet 444 state is disposable; vali-django
accumulates fresh state from zero post-cutover.)

**Phase 9 done criteria:**
- The only validator running on the operator's testnet 444 hotkey is
  vali-django
- The legacy files are gone from the safeguard/ tree
- The customer-facing `/evaluate` API is unchanged from the customer's
  perspective (same wire format, same auth)

---

### Phase 10 — polish

Catchall for the final 10% that takes 90% of the perfectionist time:

- Better 404 page
- Better 500 page (read `last_chain_error` from ValidatorStatus and show
  it on the 500 page so operators see the cause without leaving the
  browser)
- Email/Slack alerting when `/healthz` flips red for more than X
  minutes (out-of-process monitor; vali-django itself stays simple)
- Prometheus `/metrics` endpoint (optional — only if the deployment
  story actually wants it; k8s + GCP logging may be enough)
- Consider a customer-facing dashboard view ("my target's recent
  evaluations") behind Epistula auth — currently API-only

---

## Decisions (locked, 2026-04-08)

### A: `MinerScore` vestigial field handling — DROP BOTH

`score` and `contribution_total` are both **deleted**, replaced with
nothing. Rationale: the chain already maintains both pieces of state.

- "Current standing" of a miner = chain bond EMA, queryable any time
  via subtensor RPC; duplicating it locally guarantees drift.
- "Lifetime tau earned" of a miner = chain dividend / emission history,
  also queryable; same drift problem.

Local-only data we DO keep (because the chain does NOT see it):

- `submissions` — total audited cycles
- `findings_count` — lifetime cycles where `findings_reward >= FINDINGS_THRESHOLD`
- `bait_only_count` — lifetime "informative null" cycles
- `null_count` — lifetime "uninformative null" cycles
- `last_contribution` — most recent cycle's RAW contribution magnitude
  (the chain only sees normalized weights, so the raw magnitude is genuinely
  local and useful for the operator dashboard)

The seed-from-legacy command in phase 6 imports the lifetime counters
from `safeguard/miner_scores.json` and discards anything else.

### B: Schema migration as one big migration — ONE

`0002_burn_floor_schema.py` covers MinerScore + ValidatorStatus +
CycleHistory in one atomic step. Easier rollback, no intermediate
broken states.

### C: llm_judge / bait library integration — SYS.PATH SHIM

Same pattern as `validator/epistula.py`. Legacy `safeguard/llm_judge.py`
and `safeguard/bait/library.json` remain the source of truth until
phase 9 (legacy retirement), then they get copied in and the shim
deleted.

### D: tempo cadence retry logic — PORT LEGACY FOR PARITY

The `cycle_collected_fresh_data` flag from `safeguard/validator.py:1203`
gets ported verbatim. Operator behavior stays the same as today; chain
rate-limit is the ultimate guard against `set_weights` spam. Revisit
in phase 10 only if it produces noticeable log noise in practice.

### E: HITL mech-1 set_weights — PORT IN PHASE 2 FOR PARITY

The separate mech-1 set_weights call (flat 1/N across registered HITL
miners) lands in sub-phase 2.6 alongside the burn-floor mech-0 call.
HITL audit/scoring design itself defers to phase 4, but the
submission path is in place from day one — if any HITL miners are
registered, they get their flat split, never silent zero.

---

## Sequencing across phases (the dependency DAG)

```
2.0 schema migration
  ↓
2.1 chain connect + owner UID
  ↓
2.2 miner discovery
  ↓
2.3 probe dispatch ─────────┐
  ↓                         │
2.4 audit pipeline          │ (3 — dashboard upgrade can start
  ↓                         │  in parallel after 2.6 ships
2.5 scoring                 │  the new tables)
  ↓                         │
2.6 burn-floor set_weights ─┴───→ 3 dashboard upgrades
  ↓
2.7 tempo cadence + tick hygiene
  ↓
PHASE 2 DONE
  ↓
4 HITL pathway       (independent — needs only the audit pipeline from 2.4)
5 tests              (independent — can start after phase 2.6)
[6 REMOVED 2026-04-09 — seed-from-legacy struck, no production data to migrate]
  ↓
7 layer-2 wallet defense
  ↓
8 subnet bootstrap robustness
  ↓
9 retire legacy        ← ONE WEEK of stable parallel running before this
  ↓
10 polish
```

Phase 2 is sequential within itself. Phases 3, 4, and 5 can fan out in
parallel once their respective phase-2 dependencies are met. Phases
7-10 are sequential.

---

## Things that will go wrong (operational hazards, not code)

These are the failure modes we should expect during the build, in
priority order:

1. **Epistula body normalization mismatches.** The single most common
   inter-process Epistula failure. The cross-verify test pattern in
   `demo-client-v2/tests/test_epistula.py` is the antidote — sign in
   one process, verify in another, assert. Add a similar test for
   vali-django's outbound miner calls before debugging in production.
2. **`asyncio.to_thread` and Django connections.** Use
   `asgiref.sync.sync_to_async` for ALL ORM access; raw `to_thread`
   leaks connections.
3. **Migration drift.** When phase 2.0 ships, every operator running
   vali-django needs to `python manage.py migrate`. The Dockerfile
   already runs migrate at container start, so prod is fine; local
   devs may forget.
4. **Two-validator interference during cutover.** vali-django and the
   legacy validator must run on DIFFERENT hotkeys. This is enforced by
   the wallet flock (layer 1) and will be enforced by the chain check
   (layer 2) once phase 7 lands. In the meantime: be careful.
5. **Subtensor SDK API drift.** `bittensor 10.2.0` is what vali-django
   targets; if a subsequent SDK release renames methods, the chain
   call wrappers need updating. Pin the SDK version in `pyproject.toml`
   and bump deliberately.
6. **The mock relay in demo-client-v2 returns canned responses.** Useful
   for proving the pipeline; for realistic data, dispatch against the
   actual safeguard-miners running on testnet 444.
7. **`SubtokenDisabled` will bite at least once.** It already has on
   testnet 444. Phase 8 makes this graceful; until then, just know
   that "validator running but no emissions visible" might mean the
   subnet hasn't been started yet.

---

## Done criteria for vali-django overall

When all of the following are true, vali-django is "complete and
perfect" (per the user's framing) and the legacy validator can be
retired:

- vali-django has been running on testnet 444 for at least one week
  with `/healthz` green ≥99% of the time
- Burn floor has activated cleanly at least once (i.e. a burn-only
  cycle has been observed in the cycle history with `burn_share=1.0`)
- A productive cycle has been observed with non-zero earnings flowing
  to a real safeguard-miner
- A `HitlCase` has been created, surfaced in the operator UI, labeled
  by an operator, and the label propagated to the `Evaluation` row
- A customer subnet has successfully called `/evaluate` and received a
  non-fallback `safety_score`
- Layer-2 wallet defense has been verified (test case + manual smoke)
- A second vali-django instance with a different hotkey has been
  brought up on the same subnet and verified to coexist (this is the
  actual silence-capture defense)
- The legacy `safeguard/validator.py` and `safeguard/dashboard.py` are
  deleted
- The vali-django README and OPERATOR.md cover everything an operator
  needs to know

---

## What this plan deliberately does NOT include

- A full multi-validator coordination protocol. Safeguard is a
  decentralized subnet by design; vali-django assumes one process
  runs one wallet, and HA = a second deployment with a second wallet.
  Anything beyond that is operational, not code.
- Full Prometheus metrics. `/healthz` + k8s + GCP logging is enough
  for now. Revisit if the operator surface actually demands it.
- A customer-facing web dashboard. The Epistula API is the contract;
  customers should build their own consumption surface. We can revisit
  if customer demand is real.
- A web auth layer. The operator UI is firewalled at the network
  layer; the customer API uses Epistula. No Django sessions, no
  passwords, no OAuth.
- An admin panel beyond what Django ships out of the box. If we need
  it later, `django.contrib.admin` is one line in `INSTALLED_APPS`.
- Dataset export tooling for the safety research community. Phase
  11+ if there's demand.

---

## Working agreement between human and assistant on this plan

Per `latents/CLAUDE.md`:
- Each phase ends with a smoke test or measurable criterion. We do NOT
  batch phases — land each, verify, then start the next.
- Decision points A-E need a human call before phase 2 starts. The
  recommendations above are starting positions, not commitments.
- All code goes through the existing safeguard publication standard:
  no untested adaptations, no speculation in committed code (only in
  TODO comments or this plan), absolute technical and security rigor.
- The legacy `safeguard/validator.py` keeps running through phase 8.
  No edits to legacy code without explicit instruction.

---

## Estimate

Deliberately omitted per `latents/CLAUDE.md` ("avoid giving time
estimates"). Phases are scoped by deliverable, not duration. The work
is known; the cadence depends on how aggressively we ship and test.
