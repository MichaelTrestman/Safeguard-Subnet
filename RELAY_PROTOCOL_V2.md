# Safeguard Relay Protocol v2 — provenance commitments over v1

**Status:** Design target, 2026-04-09. **Not yet implemented.** Partners
integrating today should continue to use
[`RELAY_PROTOCOL.md`](RELAY_PROTOCOL.md) (v1). This document is the single
source of truth for the v2 design.

## Relationship to v1

[`RELAY_PROTOCOL.md`](RELAY_PROTOCOL.md) (hereafter **v1**) is the currently
deployed relay protocol. It places the `/relay` endpoint on the **target
subnet's validator** (the client). Safeguard miners call the client's
`/relay`; the client forwards to its own miners using its own auth. v1 is
simple, shipped, and remains the reference for any partner integration
happening today.

**v2 does not deprecate v1 and does not require partners to change anything.**
v2 is a Safeguard-side enhancement that decorates v1 with cryptographic
provenance. The client's `/relay` stays where it is, runs unchanged, and
remains the forwarding target. What moves is *who the Safeguard miner
calls first*: instead of calling the client's `/relay` directly, the miner
calls a new `/relay` endpoint on the **Safeguard validator**, which then
calls the client's existing v1 `/relay` on the miner's behalf and adds a
signed commitment to the response on the way back.

## Why v2 exists

One attack — **miner fabrication** (see
[`THREAT_MODEL.md#a1`](THREAT_MODEL.md)) — cannot be mitigated under v1
without a structural change. Under v1, a Safeguard miner submits a
transcript it claims came from the target. The Safeguard validator has no
way to verify the attribution: the target's response was observed only by
the miner itself and (transiently) by the client's relay. A miner can
fabricate a "finding" by generating a plausible-looking target response
and submitting it.

This was **confirmed live** against `safeguard/evaluation_log.jsonl` on
2026-04-09. Severity-0.95 multi-turn "findings" from miner UID 5 could not
have been real, because the real client service did not support multi-turn
and the Chutes budget was too low to service them. Brad demonstrated the
attack on the community dev call by pre-generating malicious-looking chat
responses and submitting them whenever a probe was assigned. Full record
in [`dev-call-notes-2026-04-09.md`](dev-call-notes-2026-04-09.md) §1.

v2 exists to fix this.

## The architectural approach: wrap v1, don't replace it

The simplest change that solves the fabrication attack is to insert a
Safeguard-owned relay between the miner and the existing v1 forwarder:

```
v1 flow:
    Safeguard miner ──HTTP──▶ client v1 /relay ──own auth──▶ client miner

v2 flow:
    Safeguard miner ──HTTP──▶ Safeguard /relay ──HTTP──▶ client v1 /relay ──own auth──▶ client miner
                                    │
                                    ├─ hashes response
                                    ├─ stores commitment in shared DB
                                    └─ returns response + commitment to miner
```

What this gives you:

- **Trust root for attribution moves to the Safeguard validator.** The miner
  no longer decides what the target said; the Safeguard validator does, and
  commits to it with its own hotkey signature.
- **No client-side changes at all.** v1 clients' `/relay` endpoints stay
  exactly as they are.
- **No cross-subnet credential negotiation** in this phase. Safeguard reaches
  the target via the client's existing v1 relay, using the same Epistula
  auth Safeguard miners already use today — just issued by the Safeguard
  validator's hotkey instead of a miner's.
- **Minimal new code in `vali-django`.** One new endpoint, two new ORM
  models, one pure-function provenance module, small changes to the loop
  and audit worker. The forwarder is ~30 lines of `httpx`.

What this does *not* give you, and why that's OK for now:

- **Does not eliminate the client from the trust path.** The client's v1
  relay is still in the forwarding chain, and a dishonest client can still
  forge responses before Safeguard hashes them (this is A3 sandbagging,
  already unmitigated in v1 — v2 does not make it worse).
- **Does not solve the Byzantine relay case.** A compromised Safeguard
  validator can still issue commitments for fabricated responses (A4 in
  [`THREAT_MODEL.md`](THREAT_MODEL.md)). This is an open research item.

Both of those are problems v2 inherits from v1 rather than introducing. The
attack v2 actually closes — A1 miner fabrication — is closed completely.

A future phase — see "Future phase 2" at the bottom of this document —
can swap the forwarder from "call client v1 relay" to "call client miner
directly via a scoped credential." That migration is invisible to miners,
because the miner-facing protocol is identical either way. Wrap-v1 is a
stepping stone, not a dead end.

## Participants and trust assumptions

| Participant | Role in v2 | Trust status |
|---|---|---|
| **Safeguard miner** | Sends per-turn prompts to Safeguard `/relay`, receives response + commitment, submits transcript with commitment echoed | Untrusted (this is the party the v2 commitments defend against) |
| **Safeguard validator** | Hosts `/relay`, forwards to client v1 `/relay`, computes commitment, stores commitment in DB, re-verifies at audit time | Trusted for v2 purposes; A4 is the residual Byzantine case |
| **Client (target subnet validator)** | Runs v1 `/relay` endpoint; unchanged from v1 | Same trust status as v1 — still subject to A3 sandbagging, which v2 does not mitigate |
| **Client's miner** | Answers the relayed query as if it were any other validator query | Untrusted end-to-end, no change from v1 |

The key shift: the Safeguard **miner** is no longer the observer of record
for what the target returned. That job moves to the Safeguard **validator's
relay**. Everything else stays where it was.

## Endpoint spec

### `POST /relay`

Hosted on the Safeguard validator, reachable by registered Safeguard miners.

**Request:**

```json
{
    "prompt": "User message to forward to the target miner",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "target_descriptor": {
        "client_validator_hotkey": "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
    }
}
```

- `prompt`: the per-turn probe text. Same semantics as v1.
- `session_id`: UUID generated by the Safeguard miner at the start of each
  probing conversation. Same semantics as v1 — all turns in one
  conversation share a `session_id`. The Safeguard validator passes this
  unchanged to the client's v1 `/relay`.
- `target_descriptor`: identifies which client subnet to forward to. In v1
  the target validator was implied by the URL the miner was calling; in v2
  the miner calls the Safeguard validator, so the target must be specified
  explicitly. Resolved against `RegisteredTarget` rows in the
  `vali-django` DB.

**Headers:** Epistula authentication:
- `X-Epistula-Timestamp`: nanosecond Unix timestamp
- `X-Epistula-Signature`: hotkey signature of `"{timestamp}.{sha256(body).hex()}"`
- `X-Epistula-Hotkey`: Safeguard **miner's** SS58 address

The Safeguard validator verifies that the calling hotkey is a registered
probe miner on the Safeguard subnet. The cheapest check is a `MinerScore`
row lookup, since `loop.py` populates that table on miner discovery.

**Response:**

```json
{
    "response": "The target miner's response, verbatim",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "response_commitment": {
        "scheme": "sha256-canonical-json-v1",
        "digest": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        "committed_at": 1759999999123456789,
        "committed_by": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
    }
}
```

- `response`: the target miner's response, verbatim. Not modified,
  filtered, or sanitized by the Safeguard validator.
- `session_id`: echoed back unchanged.
- `response_commitment`: the provenance binding. Detailed in the next
  section. The miner must include this entire block verbatim in the
  corresponding per-turn entry of its eventual transcript submission.

### Status codes

| HTTP Status | Meaning |
|---|---|
| 200 | Success. Response body contains the target's reply and the commitment. |
| 400 | Malformed request (missing fields, invalid `target_descriptor`). |
| 401 | Epistula verification failed. |
| 403 | Calling hotkey is not a registered Safeguard miner. |
| 404 | `target_descriptor` names a client the Safeguard validator has no `RegisteredTarget` row for. |
| 429 | Rate limited. Session turn budget exceeded, or per-hotkey hourly budget. |
| 502 | Client v1 `/relay` returned an error or unreachable. |
| 504 | Client v1 `/relay` timed out. |

**Errors never produce a commitment.** A miner receiving a non-200 response
cannot attribute anything to the target and must not submit a "finding"
against that turn. This invariant is what makes re-verification at scoring
time sound.

## Per-turn hashing scheme

This is the part of v2 that matters. Everything else is plumbing.

### The scheme

Each successful `/relay` call runs this procedure after receiving the
client v1 relay's response:

1. Safeguard validator receives the target response from the client v1
   `/relay`.
2. Validator constructs a **canonical commitment preimage**:

   ```json
   {
     "scheme": "sha256-canonical-json-v1",
     "session_id": "<uuid>",
     "turn_index": <integer, 0-indexed within session>,
     "prompt_sha256": "<hex(sha256(utf8(prompt)))>",
     "response": "<target response, verbatim>",
     "target_descriptor": { ... },
     "committed_at": <nanosecond timestamp>,
     "safeguard_validator_hotkey": "<SS58 of this validator>"
   }
   ```

3. Validator computes `digest = sha256(canonical_json(preimage))`.
4. Validator persists a `RelayCommitment` row in its shared DB, keyed on
   `(session_id, turn_index)`, storing the full preimage dict (not just
   the digest — the digest is recomputable from the preimage at scoring
   time).
5. Validator returns `{response, session_id, response_commitment}` to the
   miner, where `digest` is the computed hex digest and `committed_by` is
   the Safeguard validator's own hotkey.

The miner **must include the commitment verbatim** in its per-turn
transcript entries. Missing or mismatched commitments invalidate the turn
at scoring time.

### Canonical JSON

Canonicalization is non-optional. It must be bit-exact between the relay
and the audit worker's re-verification, or every commitment fails to
reproduce. v2 specifies:

- **Key ordering:** lexicographic sort by UTF-8 byte value at every
  nesting level.
- **Whitespace:** none. `separators=(",", ":")`.
- **Numeric format:** integers only in the preimage (no floats). Unix
  timestamps in nanoseconds; turn indices as plain integers.
- **String escaping:** JSON standard. `ensure_ascii=False` — keep UTF-8
  bytes as-is.
- **No trailing commas, no comments.**

Python reference: `json.dumps(obj, sort_keys=True, separators=(",", ":"),
ensure_ascii=False).encode("utf-8")`.

**Implementation note.** Use a single shared canonical-JSON serializer in
`validator/provenance.py` and gate the module behind a golden-test file of
known `(preimage_dict, canonical_bytes, hex_digest)` triples. A future
refactor that accidentally changes the serialization breaks every
commitment silently; golden tests are the only way to catch it.

### Scoring-time verification

When the audit worker processes an `Evaluation`, it runs commitment
verification **before** any other audit tier:

1. Walk the submitted transcript's per-turn entries.
2. For each turn, look up the `RelayCommitment` row by
   `(session_id, turn_index)` where the session belongs to the submitting
   miner.
3. Compare the submitted `response` byte-for-byte against
   `stored_preimage["response"]`.
4. Recompute `sha256(canonical_json(stored_preimage))` and compare against
   the submitted digest.
5. If any turn fails, **truncate the transcript at the first mismatch**
   and mark the evaluation `provenance_verified=False`. Subsequent turns
   are discarded (to prevent the "real prefix, fake continuation" attack).
6. If all turns verify, mark `provenance_verified=True` and proceed to the
   normal audit tiers.

Legacy v1 submissions without commitment blocks mark
`provenance_verified=None` (nullable) and proceed through the audit, but
are flagged on the operator dashboard so v1-era submissions are visually
distinct from v2-verified ones during the migration window.

### What this protects against and what it does not

**Protects against:**
- Fabricating target responses from thin air (A1 — the confirmed attack).
- Tampering with real target responses before submission.
- Reordering turns within a session.
- Mixing turns from different sessions.
- Re-using commitments from another miner's session (session ownership is
  verified against the calling hotkey at commitment creation time).

**Does not protect against:**
- **Byzantine Safeguard validator.** A compromised validator can issue
  commitments for fabricated responses. See
  [`THREAT_MODEL.md#a4`](THREAT_MODEL.md). Open research.
- **Client sandbagging (A3).** Commitments bind what the relay saw coming
  out of the client v1 `/relay`, not whether that matches the client's
  production service. v1 had this problem; v2 does not fix it.
- **Semantic manipulation by miner prompts.** Miners are free to engineer
  whatever prompts they want; v2 only attests that those prompts actually
  went through the forwarder and got those responses back.

## Miner-side protocol change

Existing miners (`safeguard-example-miner/`, any third-party miners) hit
the client v1 `/relay` directly. To use v2, the miner does two things
differently:

1. **Routes per-turn prompts through Safeguard's `/relay`** instead of
   directly to the client's `/relay`. The new endpoint URL comes from the
   task dispatch message (see "Loop and audit integration" below — the
   loop stamps `safeguard_relay_endpoint` into each task).
2. **Echoes `response_commitment` verbatim** in each per-turn entry of its
   submission transcript.

Per-turn submission entry shape gains one field:

```json
{
    "role": "assistant",
    "content": "...",
    "response_commitment": {
        "scheme": "sha256-canonical-json-v1",
        "digest": "...",
        "committed_at": 1759999999123456789,
        "committed_by": "5GrwvaEF..."
    }
}
```

Miners that don't understand v2 can still run in v1 mode — their
submissions just lack the `response_commitment` field and are flagged as
legacy (see "Scoring-time verification" above). The transition is
gradual and reversible.

## Loop and audit integration

### Loop

`loop.py:_send_probe_to_miner` currently sends a task body of:

```json
{
    "task_id": "...",
    "target_validator_endpoint": "https://client.example/relay",
    "scenario_category": "self-harm"
}
```

Under v2 it adds two fields:

```json
{
    "task_id": "...",
    "target_validator_endpoint": "https://client.example/relay",
    "safeguard_relay_endpoint": "https://this-validator.example/relay",
    "target_descriptor": {"client_validator_hotkey": "5F..."},
    "scenario_category": "self-harm"
}
```

`target_validator_endpoint` is kept for v1-only miners during the
transition window. v2-aware miners prefer `safeguard_relay_endpoint` when
both are present. The loop is agnostic — it just ships both fields.

New setting: `SAFEGUARD_RELAY_ENDPOINT` (environment variable) — the
externally-reachable URL the loop stamps into each task. Added to
`valiproject/settings.py` in the same pattern as the other validator
settings.

### Audit worker

`audit.py` gains a new first step:

```python
def verify_transcript_provenance(evaluation: Evaluation) -> tuple[bool, int]:
    """Returns (all_verified, n_verified_turns)."""
```

Runs before any existing audit tier. Writes the result into two new fields
on `Evaluation`:

- `provenance_verified` — nullable bool. `True` = all turns verified.
  `False` = at least one mismatch (transcript truncated). `None` = legacy
  v1 submission with no commitment blocks.
- `provenance_turns_verified` — integer count, for the operator dashboard.

Rejected transcripts get `accepted_severity=0` with a distinct reason code
so they are visually obvious on the dashboard as fabrication suspects, not
just "miner who found nothing."

## New ORM models

Two additions to `validator/models.py`, one migration
(`0004_relay_commitments.py`).

```python
class RelaySession(models.Model):
    """One probing session started by a Safeguard miner.

    One row per session_id. Ties per-turn commitments together so the
    audit worker can verify session ownership and turn ordering.
    """
    session_id = models.UUIDField(unique=True, db_index=True)
    miner_hotkey = models.CharField(max_length=128, db_index=True)
    target = models.ForeignKey(
        RegisteredTarget, on_delete=models.CASCADE,
        related_name="relay_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_turn_at = models.DateTimeField(auto_now=True)
    turn_count = models.PositiveIntegerField(default=0)


class RelayCommitment(models.Model):
    """One row per successful /relay call. The authoritative record of
    what the Safeguard validator observed coming out of the client's v1
    /relay. Re-verified at scoring time against the Evaluation's
    submitted transcript.
    """
    SCHEME_V1 = "sha256-canonical-json-v1"

    session = models.ForeignKey(
        RelaySession, on_delete=models.CASCADE, related_name="commitments",
    )
    turn_index = models.PositiveIntegerField()
    scheme = models.CharField(max_length=64, default=SCHEME_V1)
    preimage = models.JSONField()
    digest = models.CharField(max_length=128, db_index=True)
    committed_at = models.DateTimeField(auto_now_add=True)
    committed_by = models.CharField(max_length=128)

    class Meta:
        unique_together = [("session", "turn_index")]
        indexes = [models.Index(fields=["session", "turn_index"])]
```

Rationale: storing the full preimage (not just the digest) lets the audit
worker re-verify without trusting the miner's transcript to contain a
canonicalizable copy. The digest column is indexed for observability
(duplicate-detection queries, audit-trail lookup).

## Privacy and rate limiting

**Privacy.** Unchanged in spirit from v1, re-enforced on the Safeguard
side now that the relay lives there:

- The Safeguard validator MUST NOT reveal the target miner's identity or
  UID to the calling Safeguard miner. The forward call to the client's v1
  relay already handles this — Safeguard just passes `response` through
  and adds its commitment.
- The Safeguard validator MUST NOT add any indicator to the forwarded
  request that would let the client know it is being relayed on behalf
  of Safeguard for a specific miner. The existing Epistula headers are
  signed with the Safeguard validator's own hotkey, which is an indicator
  that *this is Safeguard* — but that was already visible to the client
  in v1, so no new information leaks.

**Rate limiting.** Two budgets:

- **Per-session turn budget.** `RelaySession.turn_count` must stay below
  a configured ceiling (default 10, matching v1).
- **Per-hotkey hourly budget.** Default 100 requests per hour per calling
  miner hotkey. Implementation can wait until abuse is observed — a
  Django cache key with TTL 3600s is sufficient.

A per-target DDoS budget is implicitly bounded by the loop's cycle cadence
and does not need a separate knob in phase 1.

## Migration path from v1

v1 and v2 are designed to coexist indefinitely. Migration is per-miner,
not per-client:

1. Safeguard validator ships v2 support in `vali-django` (new endpoint,
   new models, audit integration, loop task additions).
2. Loop stamps both `target_validator_endpoint` (v1) and
   `safeguard_relay_endpoint` (v2) into every dispatched task.
3. Miners upgrade at their own pace. v2-aware miners route per-turn
   prompts through the Safeguard `/relay` and include commitments in
   their submissions; v1 miners keep hitting the client v1 relay
   directly.
4. Once all known productive miners are on v2, the loop can optionally
   drop `target_validator_endpoint` from the task body. Until then it
   costs nothing to keep shipping both.
5. Client v1 relays never have to change. Partners already integrated
   against v1 do not need to do anything.

## Future phase 2: direct target access (aspirational)

The wrap-v1 approach above is not the eventual end state. Long term, the
client should not have to operate a `/relay` endpoint at all. Phase 2 of
v2 swaps the **forwarder implementation** — and only the forwarder — from
"call client v1 `/relay`" to "call client's miner-query path directly
using a scoped credential the client issued." Everything else in v2
(commitments, endpoint, miner-side protocol, audit integration) stays
identical. Miners do not notice the switch.

What phase 2 requires that phase 1 does not:

1. **Cross-subnet credential negotiation.** The client must issue
   Safeguard a credential that authorizes the Safeguard validator to hit
   the client's miner-query path. Options include a scoped delegation
   token, Safeguard hotkey registration on the client subnet, mTLS with
   a client-issued cert, or per-subnet adapters that reuse the client's
   own auth scheme (Chutes mTLS, Hone Epistula envelopes, etc.). This
   decision depends on operational and contractual concerns; do not
   pick it now.
2. **Per-subnet forwarder adapters.** `safeguard/adapters/` already has
   the start of this pattern for the legacy miner path. Phase 2 extends
   it to cover each client subnet's direct miner-query auth.
3. **Session-pinned target miner routing.** v1 clients routed all turns
   with the same `session_id` to the same target miner "SHOULD" per the
   v1 spec. Phase 2 has to enforce this itself rather than delegating to
   the client. Depends on whether the client subnet's auth scheme
   exposes miner pinning.

Phase 2 is a real piece of work. It does not block phase 1, it is not
on the critical path for closing A1, and it may never be needed if the
wrap-v1 forwarding path proves durable. Recorded here so the migration
path is visible, not because it needs to be done.

## Open questions

1. **Byzantine Safeguard relay.** How to harden the commitment
   infrastructure against a compromised Safeguard validator. Candidates:
   TEE attestation on the relay process; multi-validator relay consensus
   (same probe hits multiple Safeguard validators, commitments must
   agree); per-turn co-signing by an external witness; on-chain
   commitment mirroring. Tracked in
   [`THREAT_MODEL.md#a4`](THREAT_MODEL.md) and in
   [`ROADMAP.md`](ROADMAP.md) research section.
2. **Commitment retention and garbage collection.** Default proposal:
   retain `RelayCommitment` rows for the longer of (a) 48 hours or
   (b) until the corresponding submission has been audited. Revise based
   on storage cost once operating data is available.
3. **Multi-validator consistency.** If multiple Safeguard validators each
   host `/relay` independently, two miners probing the same target at
   the same time will receive commitments from two different Safeguard
   validators. That is fine — each miner's scoring only needs
   self-consistency against the validator that issued their commitments,
   not cross-miner consistency. Cross-validator consensus is a different
   problem (open question 1) and is not proposed in phase 1.

## Cross-references

- [`RELAY_PROTOCOL.md`](RELAY_PROTOCOL.md) — v1, currently deployed. Do
  not modify. v2 forwards to it.
- [`DESIGN.md`](DESIGN.md) §Provenance and verification — architectural
  context for why v2 exists.
- [`THREAT_MODEL.md`](THREAT_MODEL.md) §A1 (miner fabrication — the
  attack v2 closes) and §A4 (Byzantine relay — the attack v2 does not
  close).
- [`dev-call-notes-2026-04-09.md`](dev-call-notes-2026-04-09.md) §§1, 3,
  6 — source notes from the community dev call that motivated v2 and the
  wrap-v1 insight.
