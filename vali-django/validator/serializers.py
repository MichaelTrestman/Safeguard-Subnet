"""JSON serializers for validator endpoints.

Explicit dict builders — no DRF, no introspection. Every field the
wire sees is named here so nothing leaks accidentally.
"""
from __future__ import annotations


def serialize_concern(concern) -> dict:
    """One active Concern row on the /concerns catalog wire.

    DESIGN.md §2 "Concerns, curated by validators". Miners that pull
    this use `id_slug` as the stable key, `version` for catalog
    diffing, and `concern_text` as the natural-language worry to
    drive scenario generation.

    v2 (Workstream 1):
      - `triggers` is the nested list of UserTrigger rows, visible to
        miners as seeds for adversarial probe generation.
      - DetectionCues are NOT exposed. This is a trust-minimization
        property: a miner that can see the cues the validator will
        match against its output can overfit on them, producing
        probes that defeat the audit's matcher without actually
        eliciting the concerning behavior. Cues stay on the
        validator / audit pipeline side only.
      - The legacy v1 `detection_cues` and `example_prompts`
        JSONField columns still exist on Concern but are deprecated;
        they are intentionally NOT returned on this wire. Any
        currently-running miner code still reading them should treat
        a missing field as empty. A follow-up migration drops the
        columns entirely.

    `related_concerns` is emitted as a list of slugs (not ids), so
    clients can resolve them lazily without needing a second query
    or a dense id mapping.
    """
    return {
        "id_slug": concern.id_slug,
        "version": concern.version,
        "title": concern.title,
        "concern_text": concern.concern_text,
        "category": concern.category,
        "severity_prior": concern.severity_prior,
        "curator_hotkey": concern.curator_hotkey or "",
        "active": bool(concern.active),
        "created_at": concern.created_at.isoformat() if concern.created_at else None,
        "updated_at": concern.updated_at.isoformat() if concern.updated_at else None,
        # v2: user triggers are the miner-facing input-side framings.
        "triggers": [
            {
                "id": t.id,
                "trigger_text": t.trigger_text,
                "kind": t.kind,
            }
            for t in concern.triggers.filter(active=True).order_by("id")
        ],
        # HarmBench integration: active behaviors are atomic harm
        # descriptions the miner can target individually or weave across
        # in multi-turn probes. Same trust model as triggers — these are
        # input-side curated signals miners can see; DetectionCues stay
        # private.
        "behaviors": [
            {
                "id": b.id,
                "source_ref": b.source_ref,
                "behavior_text": b.behavior_text,
            }
            for b in concern.behaviors.filter(active=True).order_by("id")
        ],
        "related_concerns": list(
            concern.related_concerns.values_list("id_slug", flat=True)
        ),
        # v2 trust-minimization: DetectionCues are NOT exposed to miners.
        # Miners that can see cues would overfit the audit's matcher.
        # The v1 detection_cues/example_prompts JSONFields are kept on
        # the row but not returned — they're deprecated and will be
        # dropped in a follow-up migration.
    }
