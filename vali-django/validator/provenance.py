"""Provenance commitment scheme for RELAY_PROTOCOL_V2 (sub-phase 2.9).

The Safeguard validator hashes each target response at the moment it
arrives from the client v1 /relay, signs the hash with its own hotkey,
persists the commitment in the DB, and returns it to the calling
miner. At audit time the worker re-verifies that the miner's submitted
transcript matches the stored commitment byte-for-byte. This is what
closes attack A1 (miner fabrication, see THREAT_MODEL.md and
RELAY_PROTOCOL_V2.md).

Pure stdlib. No third-party deps. The serializer is the *only* place
canonical JSON is computed in this codebase — every commit and every
verify must go through `canonical_json_bytes`. Refactoring it silently
breaks every existing commitment, so there is a golden test file
(`tests/test_provenance_golden.py`) gating the module against
accidental changes.

Scheme version: `sha256-canonical-json-v1`. Bumping it requires a new
preimage layout, a new SCHEME constant, and a coexistence story for
old commitments still on disk.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

# Scheme identifier embedded in every preimage and every persisted
# RelayCommitment.scheme. Pinning the string here means we can grep
# for "sha256-canonical-json-v1" if a future version ever ships.
SCHEME_V1 = "sha256-canonical-json-v1"


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize `obj` to canonical JSON bytes per the v1 scheme.

    Rules (must match RELAY_PROTOCOL_V2.md §"Canonical JSON" exactly):

      - Lexicographic key sort at every nesting level (sort_keys=True).
      - No whitespace (separators=(",", ":")).
      - UTF-8 output, raw bytes preserved (ensure_ascii=False).
      - Integers only — the caller must not pass floats. Float
        timestamps drift across platforms; use integer ns timestamps.

    A single shared serializer is critical: any divergence between
    commit-time and verify-time canonicalization makes every commitment
    fail to reproduce. Do not call json.dumps directly anywhere else
    in the provenance pipeline.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def build_preimage(
    *,
    session_id: str,
    turn_index: int,
    prompt: str,
    response: str,
    target_descriptor: dict,
    committed_at: int,
    safeguard_validator_hotkey: str,
) -> dict:
    """Construct the canonical commitment preimage dict.

    Layout per RELAY_PROTOCOL_V2.md §"The scheme":

        {
          "scheme": "sha256-canonical-json-v1",
          "session_id": "<uuid>",
          "turn_index": <int, 0-indexed>,
          "prompt_sha256": "<hex sha256 of utf8(prompt)>",
          "response": "<verbatim>",
          "target_descriptor": { ... },
          "committed_at": <ns timestamp>,
          "safeguard_validator_hotkey": "<SS58>"
        }

    The prompt is hashed (not stored verbatim) so the preimage stays
    bounded in size — the prompt is recoverable from the
    Evaluation.transcript anyway, and the audit worker re-hashes it
    before comparing.
    """
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return {
        "scheme": SCHEME_V1,
        "session_id": session_id,
        "turn_index": turn_index,
        "prompt_sha256": prompt_sha256,
        "response": response,
        "target_descriptor": target_descriptor,
        "committed_at": committed_at,
        "safeguard_validator_hotkey": safeguard_validator_hotkey,
    }


def compute_digest(preimage: dict) -> str:
    """Hex sha256 of the canonical-JSON serialization of `preimage`.

    The digest is what gets returned to the miner and what the audit
    worker recomputes. Both sides MUST go through this function — do
    not roll your own.
    """
    return hashlib.sha256(canonical_json_bytes(preimage)).hexdigest()


def compute_commitment(
    *,
    session_id: str,
    turn_index: int,
    prompt: str,
    response: str,
    target_descriptor: dict,
    committed_at: int,
    safeguard_validator_hotkey: str,
) -> tuple[dict, str]:
    """Build the preimage and compute its digest in one call.

    Returns `(preimage, hex_digest)`. The relay view persists both:
    `RelayCommitment.preimage = preimage`, `.digest = hex_digest`.
    The miner-facing response_commitment block contains the digest
    plus a few projected fields from the preimage (committed_at,
    committed_by, scheme) but NOT the preimage itself.
    """
    preimage = build_preimage(
        session_id=session_id,
        turn_index=turn_index,
        prompt=prompt,
        response=response,
        target_descriptor=target_descriptor,
        committed_at=committed_at,
        safeguard_validator_hotkey=safeguard_validator_hotkey,
    )
    return preimage, compute_digest(preimage)


def verify_commitment(
    *,
    stored_preimage: dict,
    submitted_response: str,
    submitted_digest: str,
) -> bool:
    """Re-verify a commitment at audit time.

    Two checks must both pass:

      1. The submitted_response from the miner's transcript matches
         stored_preimage["response"] byte-for-byte. (If the miner
         tampered with the target's reply, this fails.)

      2. The recomputed digest of the stored_preimage matches the
         miner's submitted_digest. (If the miner fabricated a
         commitment block whose digest doesn't match its preimage,
         this fails.)

    Returns True only if both checks pass. The caller is responsible
    for handling the False case (truncate transcript at this turn,
    mark provenance_verified=False, force severity to 0).

    Note: this function does NOT verify the validator's hotkey
    signature on the commitment. The commitment lives in our own DB —
    if it's there, we wrote it, and the trust root is "this validator
    persisted it." Cross-validator commitment forwarding (open
    question 1 in the spec, A4 in THREAT_MODEL) would need a real
    signature here.
    """
    if submitted_response != stored_preimage.get("response"):
        return False
    if submitted_digest != compute_digest(stored_preimage):
        return False
    return True
