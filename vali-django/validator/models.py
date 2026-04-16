"""
Per-instance DB models for one validator. No cross-instance coordination —
every validator in the community runs their own DB.

Replaces the file-based state in safeguard/:
  target_registry.json     -> RegisteredTarget
  evaluation_log.jsonl     -> Evaluation, Finding
  hitl_escalations.jsonl   -> HitlCase
  miner_scores.json        -> MinerScore (observability only — chain
                              owns current standing and lifetime earnings)
  cycle_history.jsonl      -> CycleHistory
  validator_status.json    -> ValidatorStatus singleton
  bait/library.json        -> BaitPattern
"""
import threading as _threading

from django.db import models


# In-process cache of the ValidatorStatus singleton. Populated by the loop
# thread via ValidatorStatus.save() and read by web-request threads via
# ValidatorStatus.get_cached(). Decouples /healthz from the DB — a DB hiccup
# no longer cascades to "503 on /healthz" → "pod restart" → more connection
# churn. See 2026-04-14 AM crash-loop (stability sweep 2.x-2).
_STATUS_CACHE_LOCK = _threading.Lock()
_STATUS_CACHE = None  # Set to a ValidatorStatus instance after first save.


class RegisteredTarget(models.Model):
    """A customer subnet that has registered for ongoing safety evaluation."""
    client_hotkey = models.CharField(max_length=128, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    relay_endpoint = models.URLField(max_length=500)
    subnet_type = models.CharField(max_length=64, default="llm-chat")
    categories = models.JSONField(default=list)
    # Customer-scoped concern selection. When set (non-empty), the
    # dispatch loop restricts this target's probes to the subset of
    # the active concern catalog that the customer/operator has opted
    # into. When empty, the loop falls back to the global active
    # catalog. DESIGN.md §"Customer-scoped concerns via
    # RegisteredTarget". Populated via customer dashboard or operator
    # UI after a `Concern` has been created.
    concerns = models.ManyToManyField(
        "Concern", blank=True, related_name="targets",
    )
    registered_at = models.DateTimeField(auto_now_add=True)
    last_probed_at = models.DateTimeField(null=True, blank=True)
    evaluations_completed = models.PositiveIntegerField(default=0)
    last_evaluation = models.JSONField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.client_hotkey[:12]}…)"


class Evaluation(models.Model):
    """One probe dispatched to a miner against a registered target."""
    task_id = models.CharField(max_length=64, unique=True, db_index=True)
    target = models.ForeignKey(
        RegisteredTarget, on_delete=models.CASCADE, related_name="evaluations"
    )
    miner_uid = models.IntegerField()
    miner_hotkey = models.CharField(max_length=128, db_index=True)
    category = models.CharField(max_length=64, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    miner_safety_score = models.FloatField(default=0.0)  # miner's claimed severity
    # Direct-concern dispatch: which focal Concern the validator picked
    # when dispatching this probe. The validator is the source of truth
    # (not the miner's response echo). Drives the audit pipeline's cue
    # matching, retirement fallback lookup, and UserTrigger credit
    # updates. Empty string means either a pre-concerns-v2 legacy row
    # or a row written before the dispatch-side source-of-truth flip.
    concern_id_slug = models.CharField(
        max_length=128,
        blank=True,
        default="",
        db_index=True,
        help_text=(
            "Which concern the validator dispatched for this probe. Set at "
            "dispatch time (NOT from the miner's response echo — the miner's "
            "echo is cross-checked but the dispatched value is authoritative). "
            "Empty for pre-concerns-v2 legacy evaluations and for evaluations "
            "created before the dispatch step stored this field."
        ),
    )
    trigger = models.ForeignKey(
        "UserTrigger",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluations",
        help_text="Which specific UserTrigger the miner used as a seed when generating this probe. Null if the miner didn't select a specific trigger (empty catalog, concern had no triggers, or pre-attribution miner build). SET_NULL on delete so retiring a trigger doesn't cascade-delete historical evaluations.",
    )
    audit_score = models.FloatField(null=True, blank=True)  # validator audit
    accepted_severity = models.FloatField(default=0.0)
    confidence_in_claim = models.FloatField(default=0.0)
    findings_reward = models.FloatField(default=0.0)
    bait_modifier = models.FloatField(default=0.0)
    contribution = models.FloatField(default=0.0)
    n_bait_detected = models.IntegerField(default=0)

    transcript = models.JSONField(default=list)
    hitl_routed = models.BooleanField(default=False, db_index=True)

    # Sub-phase 2.8 — partition column. Stamped at dispatch time with
    # the chain block at which the dispatch decision was made. Used to
    # backfill the `cycle` FK at the next set_weights commit
    # (_record_set_weights_success). The partition decision is frozen
    # at dispatch, not at backfill, so a tempo boundary that races a
    # mid-batch dispatch can't misattribute rows. Null on rows created
    # before 2.8 — those will never get a `cycle` FK.
    cycle_block_at_creation = models.BigIntegerField(
        null=True, blank=True, db_index=True
    )
    # FK to the CycleHistory row this evaluation contributed to. Null
    # at creation; backfilled in _record_set_weights_success at the
    # next tempo boundary. Pre-2.8 rows stay null forever (no
    # cycle_block_at_creation to partition by).
    cycle = models.ForeignKey(
        "CycleHistory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evaluations",
    )

    # Experiment FK — set when this evaluation is a trial of an
    # Experiment. Null for regular adversarial probes. When set, the
    # transcript stores multi-session data (flat turn list with
    # session_index tags), and experiment_report holds the miner's
    # structured consistency report.
    experiment = models.ForeignKey(
        "Experiment", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="trials",
        help_text="Set when this evaluation is a trial of an experiment. Null for regular probes.",
    )
    experiment_report = models.JSONField(
        default=dict, blank=True,
        help_text="Miner's structured consistency report (experiment trials only).",
    )
    # v2 — miner's per-session structured field extractions. Source of
    # truth (re-extractable, audit trail). Projected to ExtractedClaim
    # rows on audit for SQL GROUP BY queries. Shape:
    # [{"session_index": 0, "entity_key": "the-aleph",
    #   "field_name": "year_first_published",
    #   "value": 1941, "value_text": "1941",
    #   "text_span": "published in 1941", "span_offset": 89,
    #   "turn_index": 1}, ...]
    extracted_claims = models.JSONField(default=list, blank=True)

    # Sub-phase 2.9 — provenance verification state.
    #   provenance_verified:
    #     True  = every per-turn entry in the submitted transcript was
    #             matched against a stored RelayCommitment row at audit
    #             time and all digests reproduced.
    #     False = at least one turn had a mismatch (transcript truncated
    #             at the first failing turn). Severity forced to 0;
    #             flagged on the dashboard as a fabrication suspect.
    #     None  = legacy v1 submission with no commitment blocks.
    #             Audited normally; flagged on the dashboard as
    #             "legacy" so v1-era rows are visually distinct.
    #   provenance_turns_verified: count of turns that successfully
    #     reproduced. Drives the dashboard's per-row badge text.
    provenance_verified = models.BooleanField(null=True, blank=True, db_index=True)
    provenance_turns_verified = models.IntegerField(default=0)


class Finding(models.Model):
    """A single accepted finding extracted from an Evaluation."""
    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE, related_name="findings"
    )
    category = models.CharField(max_length=64, db_index=True)
    severity = models.FloatField()
    summary = models.TextField(blank=True)
    critical = models.BooleanField(default=False, db_index=True)

    # Denormalized curation state — write-through cache updated in the
    # same transaction as each CurationAction. Avoids subquery joins on
    # every customer dashboard load. Source of truth is CurationAction.
    curated = models.BooleanField(default=False, db_index=True)
    curated_severity = models.FloatField(null=True, blank=True)
    curated_at = models.DateTimeField(null=True, blank=True)

    # Concerns v2 — Workstream 1. Which DetectionCue rows fired on this
    # finding. Populated by the audit pipeline (Workstream 3) when a
    # finding is recorded. Enables per-cue hit-rate stats so the catalog
    # can learn which cues catch which findings. Empty set on v1 rows
    # and on any finding recorded before Workstream 3 lands.
    matched_cues = models.ManyToManyField(
        "DetectionCue",
        related_name="findings",
        blank=True,
        help_text="Which detection cues fired on this finding. Populated by the audit pipeline when a finding is recorded.",
    )


class HitlCase(models.Model):
    """An evaluation routed to human review (miner/audit disagreement).

    Status transitions (A2.1 / Workstream A.2):
        pending    → dispatched (validator sent it to a HITL miner, awaiting reply)
        dispatched → labeled (HITL miner returned a human label)
        dispatched → pending (HITL miner returned 503/504/error; retryable)
        dispatched → timed_out (miner explicitly returned 504 "human didn't label in time")
        pending    → removed (operator pulled the case from the queue)
    """
    STATUS_PENDING = "pending"
    STATUS_DISPATCHED = "dispatched"
    STATUS_LABELED = "labeled"
    STATUS_TIMED_OUT = "timed_out"
    STATUS_REMOVED = "removed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "pending"),
        (STATUS_DISPATCHED, "dispatched"),
        (STATUS_LABELED, "labeled"),
        (STATUS_TIMED_OUT, "timed_out"),
        (STATUS_REMOVED, "removed"),
    ]

    evaluation = models.OneToOneField(
        Evaluation, on_delete=models.CASCADE, related_name="hitl"
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    routed_at = models.DateTimeField(auto_now_add=True)
    labels = models.JSONField(default=list)

    # Sub-work A.2 — operator removal
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="removed_hitl_cases",
    )
    removed_reason = models.TextField(blank=True)

    # Sub-work A.2 — dispatch bookkeeping
    # `dispatched_to_uid` records the LAST miner this case was dispatched
    # to, for debugging / audit only. It is intentionally NOT consulted
    # by the dispatch selection function — selection is uniform-random
    # over eligible miners each tick, per the trust-minimization
    # requirement in the plan. Reading this field to adjust fairness
    # would regress the "no cherry-picking" property.
    dispatched_at = models.DateTimeField(null=True, blank=True)
    dispatched_to_uid = models.IntegerField(null=True, blank=True)
    labeled_at = models.DateTimeField(null=True, blank=True)


class MinerScore(models.Model):
    """Per-miner observability counters. The chain owns 'current standing'
    (bond EMA) and 'lifetime tau earned' (dividend history); we deliberately
    do NOT mirror those locally — duplicating chain state guarantees drift.
    The fields here are the things the chain does NOT see: per-instance
    audit submission counts and the most recent raw cycle contribution
    magnitude (only normalized weights make it to the chain). The operator
    dashboard reads these.
    """
    uid = models.IntegerField(unique=True)
    hotkey = models.CharField(max_length=128, db_index=True)
    last_seen = models.DateTimeField(auto_now=True)

    submissions = models.IntegerField(default=0)
    findings_count = models.IntegerField(default=0)
    bait_only_count = models.IntegerField(default=0)
    null_count = models.IntegerField(default=0)
    last_contribution = models.FloatField(default=0.0)

    # Sub-phase 2.8 — per-miner tempo gate state. Replaces the per-cycle
    # `last_dispatched_uids` set in run_validator_loop with persistent,
    # per-miner cooldown tracking.
    #
    #   last_successful_dispatch_block: chain block at which we last
    #     successfully dispatched a probe to this miner. Drives the
    #     "owed this tempo" half of the gate — a miner is owed a
    #     dispatch when (current_block - last_successful_dispatch_block)
    #     >= tempo, OR this field is null (never dispatched).
    #
    #   last_failed_dispatch_at: timestamp of the most recent FAILED
    #     dispatch to this miner. Drives the retry cooldown — after a
    #     failure, we wait DISPATCH_RETRY_COOLDOWN_S (300s = 5 min)
    #     before another attempt. No retry cap. A successful dispatch
    #     CLEARS this field (writes None) so the cooldown gate doesn't
    #     fire on a fresh-success state — the only thing holding a
    #     just-succeeded miner back is the tempo gate.
    #
    # Reset semantics fall out for free:
    #   - On successful dispatch: write block, clear failure timestamp
    #     → miner exits BOTH "owed" state and any prior cooldown
    #   - On tempo boundary: arithmetic on last_successful_dispatch_block
    #     re-opens the tempo gate, no explicit reset needed
    #   - On failed dispatch: write failure timestamp, leave block alone
    #     → miner stays "owed" but waits 5 min before next try
    last_successful_dispatch_block = models.BigIntegerField(null=True, blank=True)
    last_failed_dispatch_at = models.DateTimeField(null=True, blank=True)

    # Sub-work A.2 — HITL dispatch cooldown.
    #
    # Kept SEPARATE from `last_failed_dispatch_at` (probe dispatch) on
    # purpose: a hybrid miner that advertises `types=["probe","hitl"]`
    # can be healthy on probes while a human labeler is briefly
    # unavailable, or vice versa. Collapsing the two cooldowns into a
    # single field would let a transient HITL hiccup block probe
    # dispatch (or vice versa), which is censorship.
    #
    # `hitl_cooldown_until` is an absolute deadline rather than a
    # last-failure timestamp so we can encode different cooldown
    # durations for different failure modes (504 = short, 503 = long,
    # other = medium) in one column. A miner is "on HITL cooldown"
    # when `now() < hitl_cooldown_until`. Clearing is implicit (the
    # next eligibility check reads the current time).
    hitl_cooldown_until = models.DateTimeField(null=True, blank=True)


class ValidatorStatus(models.Model):
    """Singleton (pk=1) holding the live state of this validator instance.

    The background loop updates this row each iteration; views and /healthz
    read it. This is the operator-honest source of truth for "is the loop
    actually doing its job?" — same process, same DB transaction, no jsonl
    staleness.
    """
    SINGLETON_ID = 1

    id = models.PositiveSmallIntegerField(primary_key=True, default=SINGLETON_ID)

    last_tick_at = models.DateTimeField(null=True, blank=True)
    loop_iteration = models.BigIntegerField(default=0)

    last_set_weights_at = models.DateTimeField(null=True, blank=True)
    last_set_weights_block = models.BigIntegerField(null=True, blank=True)
    last_set_weights_payload = models.JSONField(default=dict, blank=True)
    last_set_weights_success = models.BooleanField(default=False)
    last_burn_share = models.FloatField(default=0.0)

    last_chain_error = models.TextField(blank=True)
    last_chain_error_at = models.DateTimeField(null=True, blank=True)

    chain_connected = models.BooleanField(default=False)
    wallet_loaded = models.BooleanField(default=False)
    wallet_hotkey_ss58 = models.CharField(max_length=128, blank=True)
    owner_uid = models.IntegerField(default=0)

    # Per-tick metadata written by the loop body each iteration. Added in
    # 0003_status_tick_fields ahead of sub-phase 2.2 (miner discovery) and
    # 2.7 (tempo cadence). The dashboard reads these to show "X probe / Y
    # HITL miners discovered, N blocks until next cycle".
    n_probe_miners = models.IntegerField(default=0)
    n_hitl_miners = models.IntegerField(default=0)
    current_block = models.BigIntegerField(null=True, blank=True)
    blocks_until_next_cycle = models.IntegerField(default=0)

    @classmethod
    def get(cls) -> "ValidatorStatus":
        obj, _ = cls.objects.get_or_create(id=cls.SINGLETON_ID)
        return obj

    @classmethod
    def get_cached(cls) -> "ValidatorStatus":
        """In-process cached read. The loop writes via .save(); web requests
        read via this. Use for /healthz and other liveness checks — a DB
        hiccup should not cascade to pod restart.

        Cache miss (cold start before the loop has ticked once) falls back
        to DB once. After first successful save, all reads are in-memory.
        """
        global _STATUS_CACHE
        with _STATUS_CACHE_LOCK:
            cached = _STATUS_CACHE
        if cached is not None:
            return cached
        # Cold start — one DB hit to seed the cache.
        obj = cls.get()
        with _STATUS_CACHE_LOCK:
            _STATUS_CACHE = obj
        return obj

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Only reached on successful DB save; never cache a failed write.
        global _STATUS_CACHE
        with _STATUS_CACHE_LOCK:
            _STATUS_CACHE = self


class CycleHistory(models.Model):
    """One row per completed validator cycle. Mirrors the legacy
    `cycle_history.jsonl` rows. The operator dashboard's cycle table
    (Phase 3) reads from this. Append-only by convention; never updated
    in place.
    """
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    cycle_block = models.BigIntegerField(db_index=True)
    n_registered = models.IntegerField(default=0)
    n_dispatched = models.IntegerField(default=0)
    n_responded = models.IntegerField(default=0)
    n_earned = models.IntegerField(default=0)
    earned_total = models.FloatField(default=0.0)
    burn_share = models.FloatField(default=0.0)
    owner_uid = models.IntegerField(default=0)
    submitted_weights = models.JSONField(default=dict, blank=True)
    had_fresh_data = models.BooleanField(default=False)


# ---------------------------------------------------------------------------
# Bait pattern library (replaces bait/library.json)
# ---------------------------------------------------------------------------


class BaitPattern(models.Model):
    """A single adversarial probe pattern the validator can recognize.

    Migrated from bait/library.json to the DB so operators can CRUD
    patterns via the dashboard without redeploying. The validator's
    cheap detection tier substring-matches the transcript against
    example_prompts; the optional rich tier feeds description +
    detection_cues to an LLM judge.

    The legacy JSON file is retained as a seed source — the data
    migration reads it to bootstrap the initial rows.
    """
    id_slug = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50, db_index=True)
    severity = models.CharField(max_length=10)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    detection_cues = models.JSONField(default=list)
    example_prompts = models.JSONField(default=list)
    references = models.JSONField(default=list)
    related_patterns = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "id_slug"]

    def __str__(self) -> str:
        return f"{self.id_slug} ({self.category}/{self.severity})"


# ---------------------------------------------------------------------------
# Concern — DESIGN.md §2 "Concerns, curated by validators"
#
# The successor to BaitPattern. Brings a natural-language worry
# (`concern_text`) to the front, adds versioning + curator attribution +
# an `active` retirement flag + customer-scoped selection through
# RegisteredTarget.concerns. One release of back-compat overlap with
# BaitPattern; the old class stays in place until a follow-up release
# removes it.
# ---------------------------------------------------------------------------


class Concern(models.Model):
    """A single natural-language worry the validator can dispatch probes for.

    A Concern is the curated artifact an operator publishes to miners:
    the prose description of "what we're worried about" that the LLM
    judge reads, plus the cheap-tier `detection_cues` substring list
    and `example_prompts` that bootstrap miner scenario generation.

    Versioning: every edit through the curation UI bumps `version`
    and writes a ConcernRevision snapshot. Miners polling
    `GET /concerns` see `catalog_version = max(version)` across the
    active set.

    Retirement: operator clears `active` instead of deleting; retired
    concerns still exist for audit history but drop out of
    distribution + dispatch. Customer-pending concerns start with
    `active=False` until an operator flips the flag.
    """
    id_slug = models.CharField(max_length=100, unique=True, db_index=True)
    version = models.IntegerField(default=1)
    curator_hotkey = models.CharField(max_length=128, blank=True)
    curator_user = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="curated_concerns",
    )
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    title = models.CharField(max_length=200)
    concern_text = models.TextField()
    detection_cues = models.JSONField(default=list)
    example_prompts = models.JSONField(default=list)
    category = models.CharField(max_length=64, db_index=True)
    severity_prior = models.FloatField(default=0.5)
    related_concerns = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="related_from",
    )

    class Meta:
        ordering = ["category", "id_slug"]

    def __str__(self) -> str:
        return f"{self.id_slug} v{self.version} ({self.category})"


class ConcernRevision(models.Model):
    """Append-only snapshot of a Concern at a particular version.

    Every edit through `concern_edit` bumps Concern.version and
    writes one of these rows. The snapshot is a full JSON dict of
    the content fields so rollback / diff / audit all work off this
    single table, without join-joining the current row against old
    state.
    """
    concern = models.ForeignKey(
        Concern, on_delete=models.CASCADE, related_name="revisions",
    )
    version = models.IntegerField()
    snapshot = models.JSONField(default=dict)
    editor = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="concern_revisions",
    )
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-edited_at"]
        indexes = [models.Index(fields=["concern", "-version"])]

    def __str__(self) -> str:
        return f"{self.concern.id_slug} v{self.version}"


# ---------------------------------------------------------------------------
# Concerns v2 — DetectionCue + UserTrigger (Workstream 1)
#
# v1 lived with two JSONField lists on Concern (`detection_cues` and
# `example_prompts`) that collapsed several distinct ideas into one
# bag each. v2 splits them into first-class related models so:
#
#   - each cue/trigger can be individually versioned, retired, and
#     counted (hit_count / invocation_count / success_count);
#   - the audit pipeline can attribute findings to the specific cue
#     that fired (Finding.matched_cues);
#   - the miner-facing /api/concerns serializer can expose triggers
#     without exposing cues (trust-minimization — miners that see
#     cues overfit on them).
#
# The two JSONField columns on Concern remain in place as deprecated
# back-compat storage for one release; a follow-up migration removes
# them after Workstream 3 stops reading them.
# ---------------------------------------------------------------------------


class DetectionCue(models.Model):
    """After-the-fact textual evidence that a concerning AI behavior
    actually occurred in a response. NOT a predictor and NOT a user-
    input marker — a signature of actualized harm in the assistant's
    output.

    One concern has many cues. Each cue is individually tracked so
    the catalog can stats which cues caught which findings.
    """
    KIND_REGEX = "regex"
    KIND_SUBSTRING = "substring"
    KIND_SEMANTIC = "semantic"
    KIND_CHOICES = [
        (KIND_SUBSTRING, "Substring"),
        (KIND_REGEX, "Regex"),
        (KIND_SEMANTIC, "Semantic (LLM-judged)"),
    ]

    concern = models.ForeignKey(
        "Concern",
        on_delete=models.CASCADE,
        related_name="cues",
    )
    cue_text = models.TextField(
        help_text="The substring, regex, or semantic signature to match against assistant output."
    )
    kind = models.CharField(
        max_length=16,
        choices=KIND_CHOICES,
        default=KIND_SUBSTRING,
    )
    active = models.BooleanField(default=True, db_index=True)
    hit_count = models.PositiveIntegerField(
        default=0,
        help_text="Incremented by the audit pipeline when this cue matches a finding.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["concern_id", "id"]

    def __str__(self) -> str:
        return f"{self.concern.id_slug}:cue{self.id}[{self.kind}]"


class UserTrigger(models.Model):
    """A human-user prompting behavior we worry might elicit the
    concerning AI behavior. Risk factor for the concern, not the
    concern itself. Miners receive these via /api/concerns and use
    them as seeds for adversarial probe generation.
    """
    KIND_PROMPT = "prompt"
    KIND_PERSONA = "persona"
    KIND_CONTEXT = "context"
    KIND_CHOICES = [
        (KIND_PROMPT, "Prompt (direct user input)"),
        (KIND_PERSONA, "Persona (user role/framing)"),
        (KIND_CONTEXT, "Context (situational pressure)"),
    ]

    concern = models.ForeignKey(
        "Concern",
        on_delete=models.CASCADE,
        related_name="triggers",
    )
    trigger_text = models.TextField(
        help_text="The input-side framing a miner can use as a seed for probe generation."
    )
    kind = models.CharField(
        max_length=16,
        choices=KIND_CHOICES,
        default=KIND_PROMPT,
    )
    active = models.BooleanField(default=True, db_index=True)
    invocation_count = models.PositiveIntegerField(
        default=0,
        help_text="Incremented each time the audit pipeline associates a probe with this trigger.",
    )
    success_count = models.PositiveIntegerField(
        default=0,
        help_text="Incremented each time a probe seeded from this trigger produced a finding (any cue matched).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["concern_id", "id"]

    def __str__(self) -> str:
        return f"{self.concern.id_slug}:trigger{self.id}[{self.kind}]"


class Behavior(models.Model):
    """A HarmBench-shaped atomic harm description, used as the {behavior}
    field in the HarmBench fine-tuned classifier prompt template
    (cais/HarmBench-Mistral-7b-val-cls).

    Unlike UserTrigger and DetectionCue which are intrinsically
    concern-scoped (a cue is a cue *for* a specific worry), Behaviors
    are a general catalog: one atomic harm description can be
    associated with multiple Concerns via M2M. That supports
    cross-classification — e.g. a `dimethylmercury-synthesis` behavior
    can live under both `harmbench-chemical-biological` and a native
    `cbrn-weapons-guidance` concern without duplication.

    Behaviors are one of four orthogonal detection methods a Concern
    can use: UserTrigger (input-side probe seeds), DetectionCue
    (output-side regex/semantic signatures), Behavior (HarmBench
    classifier), concern_text (Chutes LLM judge full rubric). Each
    fires independently; cross-method agreement is a calibration
    signal and disagreement is an investigation signal.

    Ingestion: HarmBench behaviors land with
    source_ref='harmbench:<BehaviorID>' and active=False. Operator
    activates individual behaviors via the /operator/behaviors/ UI.
    """
    FUNCTIONAL_STANDARD = "standard"
    FUNCTIONAL_CONTEXTUAL = "contextual"
    FUNCTIONAL_COPYRIGHT = "copyright"
    FUNCTIONAL_CHOICES = [
        (FUNCTIONAL_STANDARD, "Standard (direct harmful request)"),
        (FUNCTIONAL_CONTEXTUAL, "Contextual (requires context string)"),
        (FUNCTIONAL_COPYRIGHT, "Copyright (verbatim reproduction)"),
    ]

    concerns = models.ManyToManyField(
        "Concern",
        related_name="behaviors",
        blank=True,
        help_text="Concerns this behavior contributes to. One behavior can belong to multiple concerns.",
    )
    behavior_text = models.TextField(
        help_text="Short declarative harm phrase used as the {behavior} input to the HarmBench classifier template.",
    )
    source_ref = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        help_text="Provenance marker: 'harmbench:<BehaviorID>' or 'native:<slug>'. Unique for idempotent ingestion.",
    )
    context_string = models.TextField(
        blank=True,
        help_text="Populated for contextual-class behaviors; prepended to the prompt at dispatch time.",
    )
    functional_category = models.CharField(
        max_length=16,
        choices=FUNCTIONAL_CHOICES,
        default=FUNCTIONAL_STANDARD,
    )
    semantic_category = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="HarmBench SemanticCategory when sourced from HarmBench (chemical_biological, cybercrime_intrusion, etc.); free-form otherwise.",
    )
    active = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Off by default on ingestion — operator opts individual behaviors in via the UI.",
    )
    probe_count = models.PositiveIntegerField(
        default=0,
        help_text="Incremented each time a miner probe targets or surfaces this behavior.",
    )
    fire_count = models.PositiveIntegerField(
        default=0,
        help_text="Incremented when the HarmBench classifier returns 'yes' with high confidence against this behavior.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["semantic_category", "source_ref"]

    def __str__(self) -> str:
        return self.source_ref


class BehaviorClassification(models.Model):
    """A single HarmBench classifier result for one (Evaluation, Behavior) pair.

    Append-only ledger: every classification (live Tier 0 or a later backfill
    run) writes a new row. Severity decisions on the parent Evaluation
    (audit_score, accepted_severity, findings_reward, contribution) are
    NEVER mutated by HarmBench classification — disagreement between
    HarmBench and the recorded Chutes audit is surfaced for operator review
    via the existing CurationAction path, not resolved automatically.

    One Evaluation has N rows, one per active Behavior on its Concern at
    classification time. The unique_together constraint on
    (evaluation, behavior, source) makes re-running a given source-mode
    idempotent: the DB rejects duplicates, the batch writer catches the
    IntegrityError and skips.

    See safeguard-ops/notes/plan-2026-04-15-harmbench-backfill.md for the
    full rationale behind the side-table approach vs. denormalized fields
    on Evaluation.
    """
    SOURCE_LIVE = "live"
    SOURCE_BACKFILL_INITIAL = "backfill-initial"
    SOURCE_BACKFILL_OUTAGE = "backfill-outage"
    SOURCE_BACKFILL_TARGETED = "backfill-targeted"
    SOURCE_CHOICES = [
        (SOURCE_LIVE, "Live audit"),
        (SOURCE_BACKFILL_INITIAL, "Initial backfill"),
        (SOURCE_BACKFILL_OUTAGE, "Outage recovery"),
        (SOURCE_BACKFILL_TARGETED, "Targeted retarget"),
    ]

    evaluation = models.ForeignKey(
        "Evaluation",
        on_delete=models.CASCADE,
        related_name="behavior_classifications",
    )
    behavior = models.ForeignKey(
        "Behavior",
        on_delete=models.PROTECT,
        related_name="classifications",
        help_text="PROTECT — deleting a Behavior doesn't erase historical scoring evidence.",
    )
    score = models.FloatField(
        help_text="softmax(yes, no)[yes] — unsafe probability in [0.0, 1.0].",
    )
    confidence = models.FloatField(
        help_text="max(score, 1-score) on success (in [0.5, 1.0]); 0.0 on stub.",
    )
    fallback_reason = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text="Empty on success. 'harmbench-stub:<reason>' on failure, mirroring the Chutes stub fingerprint pattern so rollup views can exclude both uniformly.",
    )
    source = models.CharField(
        max_length=32,
        choices=SOURCE_CHOICES,
        db_index=True,
    )
    classifier_version = models.CharField(
        max_length=64,
        blank=True,
        help_text="e.g. 'harmbench-mistral-7b-val-cls@<endpoint-id>'. Lets a future classifier swap coexist with HarmBench rows.",
    )
    scored_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-scored_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation", "behavior", "source"],
                name="behaviorclassification_eval_behavior_source_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["evaluation", "-scored_at"]),
            models.Index(fields=["behavior", "-scored_at"]),
        ]

    def __str__(self) -> str:
        return f"Eval#{self.evaluation_id}×Behavior#{self.behavior_id}[{self.source}]={self.score:.2f}"


# ---------------------------------------------------------------------------
# Curation — validator operator review of findings
# ---------------------------------------------------------------------------


class CurationAction(models.Model):
    """Append-only audit trail for validator operator review of findings.

    Multiple CurationActions can exist for one Finding (e.g., confirm
    then later escalate). The most recent action determines the
    Finding's current curated state (denormalized onto Finding.curated*
    fields in the same transaction).

    Visible to all validators for Yuma consensus alignment — when
    multiple validators exist, they need to see each other's curation
    decisions or consensus will penalize them.
    """
    ACTION_CONFIRM = "confirm"
    ACTION_DOWNGRADE = "downgrade"
    ACTION_ESCALATE = "escalate"
    ACTION_CHOICES = [
        (ACTION_CONFIRM, "Confirm"),
        (ACTION_DOWNGRADE, "Downgrade"),
        (ACTION_ESCALATE, "Escalate"),
    ]

    finding = models.ForeignKey(
        Finding, on_delete=models.CASCADE, related_name="curation_actions"
    )
    action = models.CharField(max_length=16, choices=ACTION_CHOICES, db_index=True)
    reason = models.TextField()
    original_severity = models.FloatField()
    new_severity = models.FloatField()
    curator = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True,
        related_name="curation_actions",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["finding", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.action} on Finding#{self.finding_id}"


# ---------------------------------------------------------------------------
# Customer profiles (dashboard access)
# ---------------------------------------------------------------------------


class CustomerProfile(models.Model):
    """Associates a Django User (username/password login) with one or more
    RegisteredTargets. A customer logs into the Safeguard validator
    dashboard and sees only their own targets' vulnerability profiles.

    The operator creates this association via management command or
    future operator UI. A single User can own multiple targets (a
    company with multiple AI services).
    """
    user = models.OneToOneField(
        "auth.User", on_delete=models.CASCADE, related_name="customer_profile"
    )
    targets = models.ManyToManyField(
        RegisteredTarget, related_name="customer_profiles", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"CustomerProfile({self.user.username})"


# ---------------------------------------------------------------------------
# Sub-phase 2.9 — Provenance v2 (RELAY_PROTOCOL_V2.md)
# ---------------------------------------------------------------------------


class RelaySession(models.Model):
    """One probing session started by a Safeguard miner.

    Ties per-turn `RelayCommitment` rows together by `session_id`. The
    audit worker uses this to verify session ownership (the calling
    miner_hotkey must match the Evaluation's miner) and to enforce
    turn ordering at scoring time.
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


# ---------------------------------------------------------------------------
# Sub-work A.2.3 — Deferred contribution adjustments from HITL labels
#
# Per DESIGN.md §"Effects of a label": when a human labels a HitlCase,
# the corresponding probe miner's contribution is updated in the NEXT
# tempo, NOT retroactively. This model is the audit trail for that
# deferral.
#
# Write path:
#     `_dispatch_hitl_cases` receives a label from a HITL miner, writes
#     a `PendingContributionAdjustment` row with `applied=False`.
#
# Read path:
#     `_build_cycle_contributions` (called from `_set_weights_if_due`
#     on the tempo boundary) reads all `applied=False` rows for the
#     current cycle window, applies the delta to the in-memory
#     contribution map BEFORE the burn-floor logic runs, and flips
#     `applied=True`.
#
# We intentionally keep rows after apply rather than deleting them —
# the whole point is an audit trail that says "here's why UID 5's
# contribution dropped by 0.3 at tempo block B" even after the rewrite
# of the scoring formula (DESIGN.md §"Open research problems" #2) that
# will eventually replace this mechanism.
# ---------------------------------------------------------------------------


class PendingContributionAdjustment(models.Model):
    """A queued contribution update produced by an incoming HITL label.

    Created when a HITL miner returns a label; consumed by the next
    `compute_weights` call to adjust the per-miner contribution map
    before it's submitted to chain. See module docstring above for
    the full flow.
    """
    SOURCE_HITL_DISPATCH = "hitl_dispatch"
    SOURCE_CHOICES = [
        (SOURCE_HITL_DISPATCH, "HITL dispatch"),
    ]

    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE,
        related_name="pending_adjustments",
    )
    original_severity = models.FloatField()
    ground_truth_severity = models.FloatField()
    probe_miner_hotkey = models.CharField(max_length=128, db_index=True)
    probe_miner_uid = models.IntegerField(db_index=True)
    label_source = models.CharField(
        max_length=32, choices=SOURCE_CHOICES, default=SOURCE_HITL_DISPATCH,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    applied = models.BooleanField(default=False, db_index=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return (
            f"adj(eval={self.evaluation_id}, "
            f"uid={self.probe_miner_uid}, "
            f"{self.original_severity:.2f}→{self.ground_truth_severity:.2f}, "
            f"applied={self.applied})"
        )


class RelayCommitment(models.Model):
    """One row per successful /probe/relay call. The authoritative
    record of what the Safeguard validator observed coming out of the
    client v1 /relay. Re-verified at scoring time against the
    Evaluation's submitted transcript.

    Storing the full preimage (not just the digest) lets the audit
    worker re-verify without trusting the miner's submission to contain
    a canonicalizable copy. The digest column is indexed for
    observability (duplicate-detection queries, audit-trail lookup).
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


# ---------------------------------------------------------------------------
# Experiments — DESIGN.md §10 "Consistency check challenge mode"
#
# Experiments are operator-initiated investigations dispatched to miners
# alongside (but separately from) the automated probe loop. The first
# type is **consistency checks**: the miner asks the same factual
# questions across N independent sessions and reports any contradictions.
#
# Experiments produce Evaluation rows (one per miner trial) with an
# `experiment` FK. Contribution flows through _build_cycle_contributions
# → mechid 0 weights with no changes to the weight pipeline.
# ---------------------------------------------------------------------------


class Experiment(models.Model):
    """An operator-created investigation dispatched to miners.

    Each eligible miner's execution of the experiment creates one
    Evaluation row with `experiment` FK set. That Evaluation's
    `contribution` flows into mechid 0 weights via
    _build_cycle_contributions — no weight pipeline changes needed.
    """
    TYPE_CONSISTENCY = "consistency"
    TYPE_CHOICES = [
        (TYPE_CONSISTENCY, "Consistency Check"),
        # future: ("fairness", "Statistical Fairness Check")
    ]

    STATUS_DRAFT = "draft"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    experiment_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default=TYPE_CONSISTENCY,
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True,
    )

    target = models.ForeignKey(
        RegisteredTarget, on_delete=models.CASCADE, related_name="experiments",
    )

    # The challenge: what factual claims should the miner obtain?
    challenge_claim = models.TextField(
        help_text=(
            "Describe the factual claims miners should obtain from the target. "
            "E.g. 'Find out: What year was the Eiffel Tower built? Who designed it? "
            "How tall is it?'"
        ),
    )
    # Optional: what constitutes an inconsistency? Sensible default when blank.
    consistency_check_claim = models.TextField(
        blank=True, default="",
        help_text=(
            "How to define inconsistencies across sessions. Leave blank for "
            "the default: 'Any factual claims that differ between sessions.'"
        ),
    )
    runs_per_trial = models.PositiveIntegerField(
        default=5,
        help_text="How many independent sessions each miner runs per trial.",
    )

    # v2 — structured field extraction. Shape:
    # {
    #   "entities": [{"key": "the-aleph", "display": "The Aleph"}, ...],
    #   "fields": [
    #     {"name": "author_full_name", "type": "string", "description": "..."},
    #     {"name": "year_first_published", "type": "int", "description": "..."},
    #   ],
    #   "expected_values": {  # optional canonical answers (2.2)
    #     "the-aleph": {"author_full_name": "Jorge Luis Borges", "year_first_published": 1945}
    #   }
    # }
    # Empty dict = v1 legacy mode (free-form consistency analysis only).
    field_schema = models.JSONField(default=dict, blank=True)
    field_schema_version = models.PositiveIntegerField(default=1)
    # v2 — comparison runs. FK to the parent experiment that defined the
    # shared schema. Used by the compare view to render per-field diffs
    # across target versions. Null = standalone experiment.
    parent_experiment = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="child_runs",
        help_text=(
            "Optional: this experiment is a comparison run of the parent "
            "(same schema, different target/version)."
        ),
    )

    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_experiments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Operator-curated visibility flag for the logged-out /experiments/
    # showcase. Default private; flipped via the operator detail page.
    # Only experiments where is_public=True AND status='completed' appear
    # on the public site. Per-trial transcripts and miner attribution are
    # never exposed even when public — see public/queries.py allowlist.
    is_public = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.slug} ({self.experiment_type}/{self.status})"


class ExtractedClaim(models.Model):
    """v2 — Projection of Evaluation.extracted_claims into a queryable
    relational table. Rebuildable from the JSONField source of truth.
    Derived on write (audit pipeline). Indexed for per-(experiment,
    entity, field) aggregation.

    Not the source of truth — Evaluation.extracted_claims is. This table
    exists so `GROUP BY entity_key, field_name` stays O(log N) on Postgres
    btree indexes instead of O(N × jsonb_array_elements) on JSONB
    aggregation.

    Storage is string-only. The target's answers come out of an LLM as
    text anyway ("1945", "around 1945", "June 1953") — typed columns
    with coercion created more edge cases than they solved. Field types
    in the schema stay as LLM-extraction hints and comparison-rule hints
    for canonical-answer matching (Phase 2.2), not as storage
    discriminators.
    """
    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE, related_name="claims"
    )
    # Denormalized for per-experiment aggregation queries without a join.
    experiment = models.ForeignKey(
        Experiment, on_delete=models.CASCADE, related_name="claims"
    )
    miner_uid = models.IntegerField()
    session_index = models.IntegerField()
    turn_index = models.IntegerField()
    entity_key = models.CharField(max_length=200, db_index=True)
    field_name = models.CharField(max_length=100, db_index=True)
    value_text = models.TextField()
    # Provenance — where the value came from.
    text_span = models.TextField()
    span_char_offset = models.IntegerField()
    field_schema_version = models.PositiveIntegerField()
    extracted_at = models.DateTimeField(auto_now_add=True)
    # Correctness (set if Experiment.field_schema has expected_values
    # defined for this field). True/False = compared; null = no
    # canonical answer to compare against.
    matches_expected = models.BooleanField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["experiment", "entity_key", "field_name"]),
            models.Index(fields=["experiment", "field_name", "value_text"]),
            models.Index(fields=["evaluation", "session_index"]),
        ]

    def __str__(self) -> str:
        return (
            f"Claim(exp={self.experiment_id} "
            f"{self.entity_key}.{self.field_name}={self.value_text[:40]})"
        )
