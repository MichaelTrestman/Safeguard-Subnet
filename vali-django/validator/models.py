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
"""
from django.db import models


class RegisteredTarget(models.Model):
    """A customer subnet that has registered for ongoing safety evaluation."""
    client_hotkey = models.CharField(max_length=128, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    relay_endpoint = models.URLField(max_length=500)
    subnet_type = models.CharField(max_length=64, default="llm-chat")
    categories = models.JSONField(default=list)
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


class Finding(models.Model):
    """A single accepted finding extracted from an Evaluation."""
    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE, related_name="findings"
    )
    category = models.CharField(max_length=64, db_index=True)
    severity = models.FloatField()
    summary = models.TextField(blank=True)
    critical = models.BooleanField(default=False, db_index=True)


class HitlCase(models.Model):
    """An evaluation routed to human review (miner/audit disagreement)."""
    STATUS_PENDING = "pending"
    STATUS_LABELED = "labeled"
    STATUS_CHOICES = [(STATUS_PENDING, "pending"), (STATUS_LABELED, "labeled")]

    evaluation = models.OneToOneField(
        Evaluation, on_delete=models.CASCADE, related_name="hitl"
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    routed_at = models.DateTimeField(auto_now_add=True)
    labels = models.JSONField(default=list)


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
