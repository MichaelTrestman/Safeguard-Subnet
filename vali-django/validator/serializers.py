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
        "detection_cues": list(concern.detection_cues or []),
        "example_prompts": list(concern.example_prompts or []),
        "curator_hotkey": concern.curator_hotkey or "",
        "active": bool(concern.active),
        "created_at": concern.created_at.isoformat() if concern.created_at else None,
        "updated_at": concern.updated_at.isoformat() if concern.updated_at else None,
        "related_concerns": list(
            concern.related_concerns.values_list("id_slug", flat=True)
        ),
    }
