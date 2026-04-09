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
