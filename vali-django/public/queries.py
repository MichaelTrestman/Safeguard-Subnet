"""Typed, allowlist-only queries for the public site.

INVARIANT: every function in this module returns dataclass instances
(ActivityRow, CatalogEntry, CatalogDetail), not Django model instances.
The dataclasses define the ONLY fields that may appear in a public
response. A new field on any underlying model CANNOT leak through this
layer unless someone edits both the model query AND the dataclass —
that is the safety property this module exists to enforce.

NEVER emit from this module:
    miner_hotkey, curator_hotkey, curator_user, editor (FK to User),
    severity, summary, curated_severity, matched_cues, critical,
    evaluation.* (trigger FK leaks miner-attribution precision),
    earned_total, burn_share, submitted_weights, n_earned, owner_uid,
    transcript, snapshot, detection_cues (v1 JSONField),
    example_prompts (v1 JSONField), DetectionCue.* (cue_text, kind,
    hit_count — cues stay operator-side per the contract at
    validator/models.py:476-478 "miners that see cues overfit on them"),
    ConcernRevision.snapshot, any row where provenance_verified=False.

UserTrigger IS safe to emit publicly. The established contract from
validator/models.py:476-478 says the `/api/concerns` serializer exposes
triggers to miners but NOT cues. Public visitors include prospective
miners, so the same reasoning applies — triggers are public, cues are
never public.

If you add a new source, add it to tests/test_public_activity_feed.py
too. The test asserts the serialized JSON response contains none of the
forbidden field names above.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class ActivityRow:
    """One entry in the public activity feed. This is the ONLY shape
    the public feed serializes — do not add fields without updating
    the forbidden-field test."""
    timestamp: datetime
    kind: str           # "concern_created" | "concern_edited" | "trigger_created" | "cycle_heartbeat"
    label: str          # short title, ~60 chars
    detail: str         # optional longer description, ~200 chars
    ref_slug: str       # stable anchor (e.g. concern slug) for any future linking

    @property
    def event_type(self) -> str:
        """CSS class suffix for activity-row color coding."""
        if "concern" in self.kind or "trigger" in self.kind:
            return "concern"
        if "cycle" in self.kind:
            return "cycle"
        if "finding" in self.kind:
            return "finding"
        if "hitl" in self.kind:
            return "hitl"
        return "info"

    def to_json(self) -> dict:
        """Serialize for /activity/feed.json. Emits only whitelisted fields."""
        return {
            "ts": self.timestamp.isoformat(),
            "kind": self.kind,
            "label": self.label,
            "detail": self.detail,
            "ref": self.ref_slug,
            "event_type": self.event_type,
        }


def recent_concerns(limit: int = 10) -> List[ActivityRow]:
    """New concerns added to the catalog.

    Reads only `id_slug`, `title`, `category`, `concern_text`, `created_at`
    from Concern. Explicitly excludes curator identity, cues, example prompts,
    severity prior, and the deprecated v1 JSONField bags.
    """
    from validator.models import Concern

    rows = Concern.objects.filter(active=True).order_by("-created_at").values(
        "id_slug", "title", "category", "concern_text", "created_at",
    )[:limit]

    return [
        ActivityRow(
            timestamp=r["created_at"],
            kind="concern_created",
            label=f"New concern: {r['title']}",
            detail=(r["concern_text"] or "")[:200],
            ref_slug=r["id_slug"],
        )
        for r in rows
    ]


def recent_triggers(limit: int = 10) -> List[ActivityRow]:
    """New user triggers added to the catalog.

    UserTrigger content is already miner-facing via /api/concerns per the
    contract documented at validator/models.py:476-478 — cues overfit,
    triggers don't. Safe to surface publicly.

    Explicitly excludes DetectionCue rows (cues stay operator-only).
    """
    from validator.models import UserTrigger

    rows = UserTrigger.objects.filter(active=True).select_related("concern").order_by("-created_at").values(
        "id", "trigger_text", "kind", "created_at",
        "concern__id_slug", "concern__title",
    )[:limit]

    return [
        ActivityRow(
            timestamp=r["created_at"],
            kind="trigger_created",
            label=f"New trigger on {r['concern__title']}",
            detail=f"[{r['kind']}] {(r['trigger_text'] or '')[:180]}",
            ref_slug=r["concern__id_slug"],
        )
        for r in rows
    ]


def recent_concern_edits(limit: int = 10) -> List[ActivityRow]:
    """Version bumps on existing concerns.

    Emits only the concern slug, title, version, and timestamp. The
    `snapshot` JSONField is NEVER emitted — it contains the full concern
    content including deprecated v1 cues. The `editor` FK is NEVER
    emitted — it identifies an operator account.
    """
    from validator.models import ConcernRevision

    rows = ConcernRevision.objects.select_related("concern").order_by("-edited_at").values(
        "version", "edited_at", "concern__id_slug", "concern__title",
    )[:limit]

    return [
        ActivityRow(
            timestamp=r["edited_at"],
            kind="concern_edited",
            label=f"{r['concern__title']} → v{r['version']}",
            detail="Concern updated via the curation UI.",
            ref_slug=r["concern__id_slug"],
        )
        for r in rows
    ]


def recent_cycle_heartbeats(limit: int = 10) -> List[ActivityRow]:
    """Validator cycle heartbeats — minimal proof-of-life for the network.

    Emits only `timestamp`, `cycle_block`, and `n_registered`. Explicitly
    excludes all earnings (`earned_total`, `burn_share`, `n_earned`),
    weight vector (`submitted_weights`), owner UID, dispatch stats, and
    `had_fresh_data`. A public visitor learns "the validator ran a cycle
    at block X with N registered targets" and nothing else.
    """
    from validator.models import CycleHistory

    rows = CycleHistory.objects.order_by("-timestamp").values(
        "timestamp", "cycle_block", "n_registered",
    )[:limit]

    return [
        ActivityRow(
            timestamp=r["timestamp"],
            kind="cycle_heartbeat",
            label=f"Cycle at block {r['cycle_block']}",
            detail=f"{r['n_registered']} registered targets evaluated.",
            ref_slug=str(r["cycle_block"]),
        )
        for r in rows
    ]


@dataclass(frozen=True)
class CatalogEntry:
    """One row in the public concern catalog browse list. Emits only
    whitelisted Concern fields. Never exposes curator identity, cues,
    or v1 deprecated JSONField bags."""
    id_slug: str
    title: str
    category: str
    concern_text: str
    version: int
    created_at: datetime
    trigger_count: int

    def to_json(self) -> dict:
        return {
            "slug": self.id_slug,
            "title": self.title,
            "category": self.category,
            "text": self.concern_text,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "trigger_count": self.trigger_count,
        }


@dataclass(frozen=True)
class PublicTrigger:
    """One UserTrigger as it appears in the public catalog detail view.

    UserTrigger is explicitly miner-safe per validator/models.py:476-478
    — the /api/concerns serializer exposes triggers to every probe
    miner in the network, so triggers are safe to render publicly.
    This dataclass exists so a future field addition to UserTrigger
    does not automatically leak."""
    trigger_text: str
    kind: str       # "prompt" | "persona" | "context"

    def to_json(self) -> dict:
        return {"text": self.trigger_text, "kind": self.kind}


@dataclass(frozen=True)
class CatalogDetail:
    """Full concern detail for the /catalog/<slug>/ page. Includes the
    list of active triggers. NEVER includes cues, curator identity,
    revision snapshots, or related_concerns (which could leak operator
    curation decisions)."""
    id_slug: str
    title: str
    category: str
    concern_text: str
    version: int
    created_at: datetime
    updated_at: datetime
    triggers: List[PublicTrigger] = field(default_factory=list)


def list_public_concerns(category: Optional[str] = None, limit: int = 200) -> List[CatalogEntry]:
    """All active concerns, optionally filtered by category.

    Emits only `id_slug`, `title`, `category`, `concern_text`, `version`,
    `created_at`, plus a count of active triggers per concern. Never
    emits cues, curator attribution, deprecated v1 JSONField bags, or
    severity priors.
    """
    from django.db.models import Count, Q
    from validator.models import Concern

    qs = Concern.objects.filter(active=True).annotate(
        trigger_count=Count("triggers", filter=Q(triggers__active=True)),
    ).order_by("category", "id_slug")

    if category:
        qs = qs.filter(category=category)

    rows = qs.values(
        "id_slug", "title", "category", "concern_text", "version",
        "created_at", "trigger_count",
    )[:limit]

    return [
        CatalogEntry(
            id_slug=r["id_slug"],
            title=r["title"],
            category=r["category"],
            concern_text=r["concern_text"] or "",
            version=r["version"],
            created_at=r["created_at"],
            trigger_count=r["trigger_count"],
        )
        for r in rows
    ]


def list_public_categories() -> List[str]:
    """Distinct categories across all active concerns. Used for the
    catalog browse filter. Safe because category is a short static
    string, not user-authored free text."""
    from validator.models import Concern

    return sorted(
        Concern.objects.filter(active=True)
        .values_list("category", flat=True)
        .distinct()
    )


def get_public_concern(slug: str) -> Optional[CatalogDetail]:
    """Full public-safe detail for a single active concern.

    Returns None if the concern is inactive or does not exist. An
    operator retiring a concern immediately removes it from public
    view — there is no public access to the revision history.
    """
    from validator.models import Concern, UserTrigger

    concern = Concern.objects.filter(id_slug=slug, active=True).values(
        "id_slug", "title", "category", "concern_text",
        "version", "created_at", "updated_at",
    ).first()
    if not concern:
        return None

    trigger_rows = UserTrigger.objects.filter(
        concern__id_slug=slug, active=True,
    ).order_by("id").values("trigger_text", "kind")

    return CatalogDetail(
        id_slug=concern["id_slug"],
        title=concern["title"],
        category=concern["category"],
        concern_text=concern["concern_text"] or "",
        version=concern["version"],
        created_at=concern["created_at"],
        updated_at=concern["updated_at"],
        triggers=[
            PublicTrigger(trigger_text=t["trigger_text"] or "", kind=t["kind"])
            for t in trigger_rows
        ],
    )


def get_activity_feed(limit: int = 20) -> List[ActivityRow]:
    """Merged, timestamp-sorted activity feed across all public sources.

    Pulls `limit` rows from each source, merges them, sorts descending
    by timestamp, and truncates to `limit`. If the database is empty
    this returns [].
    """
    merged = (
        recent_concerns(limit)
        + recent_triggers(limit)
        + recent_concern_edits(limit)
        + recent_cycle_heartbeats(limit)
    )
    merged.sort(key=lambda r: r.timestamp, reverse=True)
    return merged[:limit]
