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


# ---------------------------------------------------------------------------
# Public experiment showcase (Phase A of the public UI overhaul, 2026-04-14).
#
# Surfaces operator-curated Experiment rows (is_public=True, status=completed)
# on the logged-out /experiments/ route. Aggregates ExtractedClaim into
# per-(entity, field) consistency + accuracy cells. NEVER emits miner_uid,
# miner_hotkey, full transcripts, individual Evaluation/Finding rows, or
# per-trial raw claims. A single representative text_span per cell (tied to
# the modal value) is considered public-safe because all Safeguard targets
# are open research targets — revisit this invariant when a first real
# paying customer registers a private target.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PublicConsistencyCell:
    """One (entity, field) cell on the public consistency grid.

    consistency_pct: 100 * modal_count / total_trials_for_this_cell (0..100).
        Stored as a percentage, not a fraction, so templates can render
        with `|floatformat:0` without an inline multiply filter.
    accuracy_pct: 100 * n_correct / (n_correct + n_incorrect), or None
        if the schema has no expected_values for this field.
    representative_span: a short text substring from one assistant turn
        that produced the modal value — provides human-readable evidence
        without exposing the full transcript.
    """
    entity_key: str
    entity_display: str
    field_name: str
    field_description: str
    modal_value: str
    consistency_pct: float
    n_modal: int
    n_total: int
    n_distinct_values: int
    accuracy_pct: Optional[float]
    representative_span: str
    # Non-modal alternates the target produced for this same (entity, field)
    # cell across other sessions — list of (value_text, count) tuples,
    # ordered by count desc. Empty when n_distinct_values == 1. Public-safe:
    # the value strings themselves are already published as modal candidates
    # in the same grid; counts are aggregate, no per-trial / per-miner
    # attribution. Capped at 5 alternates to avoid runaway pages.
    alternates: List[tuple] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "entity": self.entity_key,
            "field": self.field_name,
            "modal_value": self.modal_value,
            "consistency_pct": round(self.consistency_pct, 1),
            "n_modal": self.n_modal,
            "n_total": self.n_total,
            "n_distinct": self.n_distinct_values,
            "accuracy_pct": (
                round(self.accuracy_pct, 1)
                if self.accuracy_pct is not None else None
            ),
            "span": self.representative_span,
        }


@dataclass(frozen=True)
class PublicExperimentSummary:
    """Row on the /experiments/ list page. Aggregates, never miners."""
    slug: str
    title: str
    target_name: str
    runs_per_trial: int
    completed_trials: int
    n_inconsistencies: int
    completed_at: Optional[datetime]

    def to_json(self) -> dict:
        return {
            "slug": self.slug,
            "title": self.title,
            "target": self.target_name,
            "runs_per_trial": self.runs_per_trial,
            "completed_trials": self.completed_trials,
            "n_inconsistencies": self.n_inconsistencies,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


@dataclass(frozen=True)
class PublicExperimentDetail:
    """Full detail for /experiments/<slug>/. Rendered read-only."""
    slug: str
    title: str
    target_name: str
    challenge_claim: str
    consistency_check_claim: str
    runs_per_trial: int
    completed_trials: int
    completed_at: Optional[datetime]
    entities: List[dict]         # [{"key": ..., "display": ...}]
    fields: List[dict]           # [{"name": ..., "description": ...}]
    cells: List[PublicConsistencyCell]

    @property
    def has_accuracy(self) -> bool:
        """True if any cell has an accuracy measurement — the schema
        defined expected_values for at least one field. Drives header
        copy and column rendering on the detail page."""
        return any(c.accuracy_pct is not None for c in self.cells)

    @property
    def grid_rows(self) -> List[dict]:
        """Pivot `cells` (flat list) into rows for 2D grid rendering:
        one row per ENTITY, with one cell per FIELD in schema order.
        Returns a list of {"entity": <ent dict>, "cells": [cell-or-None,
        ...]} where cells is aligned to self.fields order. None means the
        target produced no extracted claims for that (entity, field).
        Used by the template to render entities × fields like a spreadsheet
        instead of one row per (entity, field) cell.
        """
        from collections import defaultdict
        by_entity: dict = defaultdict(dict)
        for c in self.cells:
            by_entity[c.entity_key][c.field_name] = c
        rows = []
        for ent in self.entities:
            ek = ent.get("key", "")
            row_cells = [by_entity.get(ek, {}).get(f.get("name", "")) for f in self.fields]
            rows.append({"entity": ent, "cells": row_cells})
        return rows


def _count_inconsistencies(experiment) -> int:
    """Count (entity, field) coordinates where the target produced more
    than one distinct value across trials. Aggregate only — reads
    ExtractedClaim counts, never individual rows or miner attribution.
    """
    from django.db.models import Count
    from validator.models import ExtractedClaim

    schema = experiment.field_schema or {}
    entities = schema.get("entities") or []
    fields = schema.get("fields") or []
    if not entities or not fields:
        return 0

    grouped = (
        ExtractedClaim.objects
        .filter(experiment=experiment)
        .values("entity_key", "field_name", "value_text")
        .annotate(count=Count("id"))
    )
    per_cell: dict = {}
    for row in grouped:
        per_cell.setdefault(
            (row["entity_key"], row["field_name"]), set()
        ).add(row["value_text"])
    return sum(1 for vs in per_cell.values() if len(vs) > 1)


def list_public_experiments(limit: int = 50) -> List[PublicExperimentSummary]:
    """List experiments the operator has explicitly marked public.

    Filters to is_public=True AND status='completed' AND has at least one
    trial that produced extracted claims. Empty completed experiments
    (dispatch failed silently — see validator/loop.py status-flip logic)
    are misleading on the public showcase: they render as "Consistent"
    by default because there's no data to disagree about. Hide them.
    """
    from django.db.models import Count
    from validator.models import Experiment

    qs = (
        Experiment.objects
        .filter(is_public=True, status=Experiment.STATUS_COMPLETED)
        .annotate(n_claims=Count("claims"))
        .filter(n_claims__gt=0)
        .select_related("target")
        .order_by("-completed_at")[:limit]
    )
    summaries: List[PublicExperimentSummary] = []
    for e in qs:
        # Trial count is Evaluation rows for this experiment. We count
        # via the reverse relation but NEVER emit any Evaluation fields.
        completed_trials = e.trials.count()
        summaries.append(PublicExperimentSummary(
            slug=e.slug,
            title=e.title,
            target_name=e.target.name,
            runs_per_trial=e.runs_per_trial,
            completed_trials=completed_trials,
            n_inconsistencies=_count_inconsistencies(e),
            completed_at=e.completed_at,
        ))
    return summaries


def get_public_experiment(slug: str) -> Optional[PublicExperimentDetail]:
    """Full public-safe detail for one experiment.

    Returns None if the experiment does not exist, is not public, is
    not completed, or has zero extracted claims (see list_public_experiments
    for the empty-completion rationale). A 404 from the view is the
    right response in any of those cases — the experiment does not exist
    from the public's perspective.
    """
    from django.db.models import Count, Q
    from validator.models import Experiment, ExtractedClaim

    experiment = (
        Experiment.objects
        .filter(is_public=True, status=Experiment.STATUS_COMPLETED, slug=slug)
        .annotate(n_claims=Count("claims"))
        .filter(n_claims__gt=0)
        .select_related("target")
        .first()
    )
    if experiment is None:
        return None

    schema = experiment.field_schema or {}
    entities = schema.get("entities") or []
    fields = schema.get("fields") or []
    expected_values = schema.get("expected_values") or {}

    # Aggregate ExtractedClaim per (entity, field, value). Counts only.
    grouped = (
        ExtractedClaim.objects
        .filter(experiment=experiment)
        .values("entity_key", "field_name", "value_text")
        .annotate(
            count=Count("id"),
            n_correct=Count("id", filter=Q(matches_expected=True)),
            n_incorrect=Count("id", filter=Q(matches_expected=False)),
        )
    )
    nested: dict = {}
    for row in grouped:
        nested.setdefault(
            row["entity_key"], {}
        ).setdefault(
            row["field_name"], {}
        )[row["value_text"]] = {
            "count": row["count"],
            "n_correct": row["n_correct"],
            "n_incorrect": row["n_incorrect"],
        }

    cells: List[PublicConsistencyCell] = []
    for ent in entities:
        ek = ent.get("key", "")
        e_display = ent.get("display", ek)
        expected_for_entity = expected_values.get(ek, {})
        for f in fields:
            fn = f.get("name", "")
            f_desc = f.get("description", "")
            values = nested.get(ek, {}).get(fn, {})
            total = sum(v["count"] for v in values.values())
            if total == 0:
                continue
            modal_value, modal_stats = max(
                values.items(), key=lambda kv: kv[1]["count"]
            )
            consistency_pct = 100.0 * modal_stats["count"] / total
            n_correct = sum(v["n_correct"] for v in values.values())
            n_incorrect = sum(v["n_incorrect"] for v in values.values())
            n_rated = n_correct + n_incorrect
            has_expected = fn in expected_for_entity and n_rated > 0
            accuracy_pct = (100.0 * n_correct / n_rated) if has_expected else None

            # One representative span for the modal value. Short — this
            # is a quote, not a transcript dump. Miner attribution is
            # dropped by .values(text_span) omitting miner_uid entirely.
            span = (
                ExtractedClaim.objects
                .filter(
                    experiment=experiment,
                    entity_key=ek, field_name=fn,
                    value_text=modal_value,
                )
                .values_list("text_span", flat=True)
                .first() or ""
            )
            # Hard cap span length so a buggy extractor can't dump a
            # full assistant turn into a public page.
            span = span[:240]

            # Non-modal alternates, ordered by frequency desc, capped at 5.
            # Each alternate is (value_text, count). Already-public-safe:
            # the values are aggregate counts, no per-trial / per-miner
            # attribution. Truncate any value over 240 chars to match the
            # representative_span cap.
            alternates = sorted(
                ((v, s["count"]) for v, s in values.items() if v != modal_value),
                key=lambda kv: kv[1], reverse=True,
            )[:5]
            alternates = [(v[:240], c) for v, c in alternates]

            cells.append(PublicConsistencyCell(
                entity_key=ek,
                entity_display=e_display,
                field_name=fn,
                field_description=f_desc,
                modal_value=modal_value,
                consistency_pct=consistency_pct,
                n_modal=modal_stats["count"],
                n_total=total,
                n_distinct_values=len(values),
                accuracy_pct=accuracy_pct,
                representative_span=span,
                alternates=alternates,
            ))

    # Sanitize entities/fields dicts to the whitelisted keys only — the
    # operator schema may have grown fields we don't want public.
    public_entities = [
        {"key": e.get("key", ""), "display": e.get("display", e.get("key", ""))}
        for e in entities
    ]
    public_fields = [
        {"name": f.get("name", ""), "description": f.get("description", "")}
        for f in fields
    ]

    return PublicExperimentDetail(
        slug=experiment.slug,
        title=experiment.title,
        target_name=experiment.target.name,
        challenge_claim=experiment.challenge_claim,
        consistency_check_claim=experiment.consistency_check_claim,
        runs_per_trial=experiment.runs_per_trial,
        completed_trials=experiment.trials.count(),
        completed_at=experiment.completed_at,
        entities=public_entities,
        fields=public_fields,
        cells=cells,
    )


# ---------------------------------------------------------------------------
# Public concern × target heatmap (Phase B of the public UI overhaul).
#
# Mirrors the operator-only /targets/compare/ heatmap as a public
# aggregation: per (concern, target) pair, the finding rate and probe
# count. Shows "Multi-Persona Fuzz Testing" — the same concern catalog
# run against different target personas, with the per-cell finding rate
# revealing how prompt-context differences shift safety posture.
#
# Emits only: target name, concern slug, concern title, finding rate,
# probe count, finding count. Never emits per-finding severity,
# audit_score, miner attribution, transcripts, matched cues, curator
# identity, or any individual Evaluation/Finding row.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PublicTargetSummary:
    """Per-target row on the /targets/ summary table."""
    name: str
    n_verified_probes: int
    n_findings: int
    finding_rate_pct: float      # 0..100
    n_critical: int

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "n_verified_probes": self.n_verified_probes,
            "n_findings": self.n_findings,
            "finding_rate_pct": round(self.finding_rate_pct, 1),
            "n_critical": self.n_critical,
        }


@dataclass(frozen=True)
class PublicHeatmapCell:
    """One cell in the concern × target finding-rate heatmap.

    rate_pct is None when n_probes == 0 (no data, render as &mdash;).
    """
    rate_pct: Optional[float]
    n_probes: int
    n_findings: int


@dataclass(frozen=True)
class PublicHeatmapRow:
    """One row of the concern × target heatmap — a single concern
    evaluated against every target."""
    concern_slug: str
    concern_title: str
    cells: List[PublicHeatmapCell]


def list_public_targets() -> List[PublicTargetSummary]:
    """All RegisteredTargets with aggregated verified-probe / finding
    counts. Never emits client_hotkey, relay_endpoint, or any
    per-evaluation field.

    Client hotkey and relay endpoint are excluded by the `.values(...)`
    projection below — even though they live on the model, the query
    never reads them. This matters: a future field added to
    RegisteredTarget cannot leak through this function.
    """
    from django.db.models import Count, Q
    from validator.models import Finding, RegisteredTarget

    targets = (
        RegisteredTarget.objects
        .annotate(
            n_verified=Count(
                "evaluations",
                filter=Q(evaluations__provenance_verified=True),
            ),
        )
        .order_by("name")
        .values("name", "n_verified")
    )

    summaries: List[PublicTargetSummary] = []
    for t in targets:
        findings_qs = Finding.objects.filter(evaluation__target__name=t["name"])
        n_findings = findings_qs.count()
        n_critical = findings_qs.filter(critical=True).count()
        rate = (
            100.0 * n_findings / t["n_verified"]
            if t["n_verified"] else 0.0
        )
        summaries.append(PublicTargetSummary(
            name=t["name"],
            n_verified_probes=t["n_verified"],
            n_findings=n_findings,
            finding_rate_pct=rate,
            n_critical=n_critical,
        ))
    return summaries


def get_concern_target_heatmap() -> tuple[List[str], List[PublicHeatmapRow]]:
    """Build the concern × target finding-rate heatmap.

    Returns (target_names_in_order, rows). Each row corresponds to one
    concern; each cell in the row corresponds to one target (aligned
    with `target_names_in_order`). Only active concerns are included.
    """
    from validator.models import Concern, Evaluation, Finding, RegisteredTarget

    target_names = list(
        RegisteredTarget.objects.order_by("name").values_list("name", flat=True)
    )

    # Only concerns that have AT LEAST ONE finding against any listed
    # target are included — avoids a grid full of empty rows.
    concern_slugs_with_findings = set(
        Finding.objects
        .filter(evaluation__target__name__in=target_names)
        .exclude(evaluation__concern_id_slug="")
        .values_list("evaluation__concern_id_slug", flat=True)
        .distinct()
    )

    concerns = list(
        Concern.objects
        .filter(id_slug__in=concern_slugs_with_findings, active=True)
        .order_by("id_slug")
        .values("id_slug", "title")
    )

    rows: List[PublicHeatmapRow] = []
    for c in concerns:
        cells: List[PublicHeatmapCell] = []
        for tn in target_names:
            n_probes = Evaluation.objects.filter(
                target__name=tn,
                concern_id_slug=c["id_slug"],
                provenance_verified=True,
            ).count()
            n_findings = Finding.objects.filter(
                evaluation__target__name=tn,
                evaluation__concern_id_slug=c["id_slug"],
            ).count()
            rate = (100.0 * n_findings / n_probes) if n_probes else None
            cells.append(PublicHeatmapCell(
                rate_pct=rate,
                n_probes=n_probes,
                n_findings=n_findings,
            ))
        rows.append(PublicHeatmapRow(
            concern_slug=c["id_slug"],
            concern_title=c["title"],
            cells=cells,
        ))

    return target_names, rows


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
