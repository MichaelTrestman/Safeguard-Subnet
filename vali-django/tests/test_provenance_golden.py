"""Golden tests for the provenance commitment serializer (sub-phase 2.9).

These tests gate `validator/provenance.py:canonical_json_bytes` and the
`compute_digest` it feeds. If a future refactor accidentally changes the
serialization (key sort, whitespace, escape behavior, dict ordering),
EVERY existing RelayCommitment row stops verifying — silently. Golden
tests are the only way to catch that class of break.

## Lifecycle

1. The first time you run this file (or any time after deliberately
   bumping SCHEME_V1), the GOLDEN_TRIPLES list below has
   `expected_bytes=None` / `expected_digest=None` for one or more
   entries. Running the test in that state prints what the serializer
   currently produces and exits non-zero with REGENERATE NEEDED.

2. You inspect the printed bytes/digests, confirm they look correct
   (canonical JSON form, 64-char sha256 hex), then paste them into
   the GOLDEN_TRIPLES list, replacing the Nones.

3. From that point, the test asserts byte-exact and digest-exact
   equality on every run. A future refactor that changes the
   serializer's output for ANY of these inputs fails the test
   loudly with a diff showing what changed.

If a legitimate scheme change is needed, bump SCHEME_V1 to SCHEME_V2,
add a new set of goldens for the new scheme in a new test file,
and leave this file unchanged so the v1 path stays gated.

Runs as a plain script for now; will be converted to pytest functions
in Phase 5 (test suite formalization) without moving the file.
"""
from __future__ import annotations

import os
import sys

# Bootstrap so this can be run from the repo root or from inside tests/
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "valiproject.settings")

# Note: provenance.py is pure-stdlib and does NOT need django.setup().
from validator.provenance import (
    SCHEME_V1,
    canonical_json_bytes,
    compute_digest,
    compute_commitment,
    verify_commitment,
)


# ---------------------------------------------------------------------------
# Golden triples — frozen reference values
# ---------------------------------------------------------------------------
#
# Each entry: (label, input dict, expected canonical bytes, expected hex digest)
#
# `expected_bytes` and `expected_digest` are None on first run; the test
# prints what they should be, you visually verify, then paste them in.
# Once filled in, do NOT regenerate to "fix" a failing test — fix the
# serializer instead.
#
# Set frozen 2026-04-09 against scheme sha256-canonical-json-v1.

GOLDEN_TRIPLES = [
    (
        "empty dict",
        {},
        b'{}',
        "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
    ),
    (
        "single ASCII key",
        {"a": 1},
        b'{"a":1}',
        "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862",
    ),
    (
        "keys in non-sorted insertion order — must serialize sorted",
        {"b": 2, "a": 1},
        b'{"a":1,"b":2}',
        "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777",
    ),
    (
        "nested dict, sorted at every level",
        {"outer": {"z": 1, "a": 2}, "alpha": "x"},
        b'{"alpha":"x","outer":{"a":2,"z":1}}',
        "58c51d260201e20cd9a381b5ca06670ece391b31b1746b486959236d291c5432",
    ),
    (
        "UTF-8 string preserved as raw bytes (NOT escaped to \\uXXXX)",
        {"msg": "héllo 世界"},
        b'{"msg":"h\xc3\xa9llo \xe4\xb8\x96\xe7\x95\x8c"}',
        "095785a44b468473879c88052d54258b0f4e4865730c60990bb230e971104b70",
    ),
    (
        "realistic provenance preimage shape",
        {
            "scheme": SCHEME_V1,
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "turn_index": 0,
            "prompt_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "response": "I cannot help with that.",
            "target_descriptor": {
                "client_validator_hotkey": "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty",
            },
            "committed_at": 1759999999123456789,
            "safeguard_validator_hotkey": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        },
        b'{"committed_at":1759999999123456789,"prompt_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","response":"I cannot help with that.","safeguard_validator_hotkey":"5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY","scheme":"sha256-canonical-json-v1","session_id":"550e8400-e29b-41d4-a716-446655440000","target_descriptor":{"client_validator_hotkey":"5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"},"turn_index":0}',
        "a9b73342d5f58a1505920e6b65836f1837e856ebe1bed269d41ceafe0e4ae735",
    ),
]


def regenerate_and_print() -> None:
    """Print what the serializer currently produces for every entry,
    formatted for direct paste into GOLDEN_TRIPLES."""
    print("=" * 70)
    print("REGENERATE NEEDED — paste these values into GOLDEN_TRIPLES")
    print("=" * 70)
    print()
    for i, (label, obj, _, _) in enumerate(GOLDEN_TRIPLES, 1):
        actual_bytes = canonical_json_bytes(obj)
        actual_digest = compute_digest(obj)
        print(f"# Entry #{i}: {label}")
        print(f"  expected_bytes  = {actual_bytes!r}")
        print(f'  expected_digest = "{actual_digest}"')
        print()
    print("=" * 70)
    print("Inspect each pair above. Confirm the bytes are canonical JSON")
    print("(sorted keys, no whitespace, raw UTF-8) and the digest is a")
    print("64-char lowercase sha256 hex. Then paste into GOLDEN_TRIPLES")
    print("and re-run.")
    print("=" * 70)


def verify_all() -> None:
    """Assert byte-exact and digest-exact equality for every entry."""
    print("=== Provenance v1 golden tests ===\n")
    print(f"Scheme constant: {SCHEME_V1}")
    assert SCHEME_V1 == "sha256-canonical-json-v1", "scheme constant changed"
    print("  ok    scheme constant\n")

    print("Golden triples:")
    failures = 0
    for i, (label, obj, expected_bytes, expected_digest) in enumerate(GOLDEN_TRIPLES, 1):
        actual_bytes = canonical_json_bytes(obj)
        actual_digest = compute_digest(obj)
        bytes_ok = actual_bytes == expected_bytes
        digest_ok = actual_digest == expected_digest
        if bytes_ok and digest_ok:
            print(f"  ok    #{i} {label}")
        else:
            failures += 1
            print(f"  FAIL  #{i} {label}")
            if not bytes_ok:
                print(f"        expected bytes:  {expected_bytes!r}")
                print(f"        actual bytes:    {actual_bytes!r}")
            if not digest_ok:
                print(f"        expected digest: {expected_digest}")
                print(f"        actual digest:   {actual_digest}")
    if failures:
        print(f"\n{failures} golden(s) failed — DO NOT 'fix' by regenerating.")
        print("Find the serializer change that broke them and revert it.")
        sys.exit(1)

    print("\ncompute_commitment round-trip:")
    preimage, digest = compute_commitment(
        session_id="550e8400-e29b-41d4-a716-446655440000",
        turn_index=0,
        prompt="Tell me about something safe.",
        response="Sure, here's a benign answer.",
        target_descriptor={"client_validator_hotkey": "5FHneW..."},
        committed_at=1759999999123456789,
        safeguard_validator_hotkey="5GrwvaEF...",
    )
    assert preimage["scheme"] == SCHEME_V1
    assert preimage["turn_index"] == 0
    assert preimage["response"] == "Sure, here's a benign answer."
    assert digest == compute_digest(preimage)
    print(f"  ok    digest = {digest}")

    print("\nverify_commitment — happy path:")
    ok = verify_commitment(
        stored_preimage=preimage,
        submitted_response="Sure, here's a benign answer.",
        submitted_digest=digest,
    )
    assert ok is True
    print("  ok    matching response + digest verifies")

    print("\nverify_commitment — tampered response:")
    ok = verify_commitment(
        stored_preimage=preimage,
        submitted_response="Sure, here's a TAMPERED answer.",
        submitted_digest=digest,
    )
    assert ok is False
    print("  ok    tampered response rejected")

    print("\nverify_commitment — tampered digest:")
    ok = verify_commitment(
        stored_preimage=preimage,
        submitted_response="Sure, here's a benign answer.",
        submitted_digest="0" * 64,
    )
    assert ok is False
    print("  ok    tampered digest rejected")

    print("\n=== All golden tests passed ===")


def main() -> None:
    needs_regenerate = any(
        eb is None or ed is None
        for _, _, eb, ed in GOLDEN_TRIPLES
    )
    if needs_regenerate:
        regenerate_and_print()
        sys.exit(1)
    verify_all()


if __name__ == "__main__":
    main()
