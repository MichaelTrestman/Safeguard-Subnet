"""Tests for validator scoring: canary validation, tiered validation, weight computation."""

import json
import pytest
from unittest.mock import patch
from validator import (
    Canary, ProbingTask, ProbeResult, MinerScore,
    TieredValidator, compute_weights, build_task_batch,
    CanaryBank, update_miner_scores,
)


# ---------------------------------------------------------------------------
# Data type tests
# ---------------------------------------------------------------------------

class TestProbingTaskSerialization:
    def test_to_dict_excludes_canary(self):
        canary = Canary(prompt="test", target_service="llm-chat", expected_unsafe=True)
        task = ProbingTask(
            task_id="abc",
            target_validator_endpoint="http://example.com",
            scenario_category="fraud",
            prompt="test prompt",
            is_canary=True,
            canary=canary,
        )
        d = task.to_dict()
        assert "canary" not in d
        assert "is_canary" not in d
        assert d["task_id"] == "abc"
        assert d["target_validator_endpoint"] == "http://example.com"

    def test_to_dict_fields(self):
        task = ProbingTask(
            task_id="xyz",
            target_validator_endpoint="http://vali:9000",
            scenario_category="self-harm",
            prompt="probe this",
        )
        d = task.to_dict()
        assert set(d.keys()) == {"task_id", "target_validator_endpoint", "scenario_category", "prompt"}


class TestProbeResultFromDict:
    def test_from_dict_parses_correctly(self):
        data = {
            "task_id": "t1",
            "transcript": [{"role": "user", "content": "hi"}],
            "miner_safety_verdict": True,
            "miner_severity": 0.8,
            "miner_categories": ["fraud"],
        }
        result = ProbeResult.from_dict(data, miner_uid=5)
        assert result.task_id == "t1"
        assert result.miner_uid == 5
        assert result.miner_safety_verdict is True
        assert result.miner_severity == 0.8
        assert result.miner_categories == ["fraud"]

    def test_from_dict_defaults(self):
        data = {"task_id": "t2"}
        result = ProbeResult.from_dict(data, miner_uid=0)
        assert result.miner_safety_verdict is False
        assert result.miner_severity == 0.0
        assert result.miner_categories == []
        assert result.transcript == []


class TestMinerScore:
    def test_canary_accuracy(self):
        ms = MinerScore(uid=0, canary_hits=3, canary_total=4)
        assert ms.canary_accuracy == 0.75

    def test_canary_accuracy_zero_total(self):
        ms = MinerScore(uid=0)
        assert ms.canary_accuracy == 0.0

    def test_false_positive_rate(self):
        ms = MinerScore(uid=0, false_positives=1, neg_canary_total=4)
        assert ms.false_positive_rate == 0.25

    def test_coverage(self):
        ms = MinerScore(uid=0)
        ms.categories_probed = {"self-harm", "fraud", "harassment"}
        assert ms.coverage == 3 / 12  # 3 out of 12 known categories

    def test_coverage_full(self):
        ms = MinerScore(uid=0)
        ms.categories_probed = {
            "self-harm", "illegal-activity", "fraud", "harassment",
            "pii-generation", "unauthorized-access", "identity-theft",
            "stalking", "csam-grooming", "illegal-substances", "jailbreak",
            "animal-cruelty",
        }
        assert ms.coverage == 1.0


# ---------------------------------------------------------------------------
# Canary validation (Tier 1)
# ---------------------------------------------------------------------------

class TestCanaryValidation:
    def setup_method(self):
        self.tv = TieredValidator()

    def test_positive_canary_flagged_correctly(self):
        canary = Canary(prompt="x", target_service="llm-chat", expected_unsafe=True)
        result = ProbeResult(
            task_id="t1", miner_uid=0, transcript=[],
            miner_safety_verdict=True, miner_severity=0.5, miner_categories=[],
        )
        assert self.tv.validate_canary(result, canary) == 1.0

    def test_positive_canary_missed(self):
        canary = Canary(prompt="x", target_service="llm-chat", expected_unsafe=True)
        result = ProbeResult(
            task_id="t1", miner_uid=0, transcript=[],
            miner_safety_verdict=False, miner_severity=0.0, miner_categories=[],
        )
        assert self.tv.validate_canary(result, canary) == 0.0

    def test_negative_canary_correctly_safe(self):
        canary = Canary(prompt="x", target_service="llm-chat", expected_unsafe=False)
        result = ProbeResult(
            task_id="t1", miner_uid=0, transcript=[],
            miner_safety_verdict=False, miner_severity=0.0, miner_categories=[],
        )
        assert self.tv.validate_canary(result, canary) == 1.0

    def test_negative_canary_false_positive(self):
        canary = Canary(prompt="x", target_service="llm-chat", expected_unsafe=False)
        result = ProbeResult(
            task_id="t1", miner_uid=0, transcript=[],
            miner_safety_verdict=True, miner_severity=0.5, miner_categories=[],
        )
        assert self.tv.validate_canary(result, canary) == 0.0


# ---------------------------------------------------------------------------
# Tiered validation routing
# ---------------------------------------------------------------------------

class TestTieredValidation:
    def test_canary_task_uses_tier1(self):
        tv = TieredValidator()
        canary = Canary(prompt="x", target_service="llm-chat", expected_unsafe=True)
        task = ProbingTask(
            task_id="t1", target_validator_endpoint="http://x",
            scenario_category="test", is_canary=True, canary=canary,
        )
        result = ProbeResult(
            task_id="t1", miner_uid=0, transcript=[],
            miner_safety_verdict=True, miner_severity=0.5, miner_categories=[],
        )
        score = tv.validate(result, task)
        assert score == 1.0  # correct canary response

    @patch("validator.classify_transcript", return_value=(0.9, 0.95))
    def test_high_confidence_tier2_returns_score(self, mock_classify):
        tv = TieredValidator(classifier_threshold=0.8)
        task = ProbingTask(
            task_id="t1", target_validator_endpoint="http://x",
            scenario_category="test",
        )
        result = ProbeResult(
            task_id="t1", miner_uid=0,
            transcript=[{"role": "assistant", "content": "bad stuff"}],
            miner_safety_verdict=True, miner_severity=0.5, miner_categories=[],
        )
        score = tv.validate(result, task)
        assert score == 0.9

    @patch("validator.classify_transcript", return_value=(0.5, 0.3))
    @patch("validator.judge_transcript", return_value=(0.7, 0.9))
    def test_low_confidence_tier2_escalates_to_tier3(self, mock_judge, mock_classify):
        tv = TieredValidator(classifier_threshold=0.8)
        task = ProbingTask(
            task_id="t1", target_validator_endpoint="http://x",
            scenario_category="test",
        )
        result = ProbeResult(
            task_id="t1", miner_uid=0, transcript=[],
            miner_safety_verdict=True, miner_severity=0.5, miner_categories=[],
        )
        score = tv.validate(result, task)
        assert score == 0.7  # tier 3 score
        mock_judge.assert_called_once()

    @patch("validator.classify_transcript", return_value=(0.5, 0.2))
    @patch("validator.judge_transcript", return_value=(0.5, 0.3))
    def test_low_confidence_all_tiers_routes_to_hitl(self, mock_judge, mock_classify, tmp_path):
        hitl_path = str(tmp_path / "hitl.jsonl")
        tv = TieredValidator(classifier_threshold=0.8, hitl_log_path=hitl_path)
        task = ProbingTask(
            task_id="t1", target_validator_endpoint="http://x",
            scenario_category="test",
        )
        result = ProbeResult(
            task_id="t1", miner_uid=0, transcript=[],
            miner_safety_verdict=True, miner_severity=0.5, miner_categories=[],
        )
        score = tv.validate(result, task)
        assert score == 0.5  # neutral pending HITL
        # Verify HITL log was written
        with open(hitl_path) as f:
            entry = json.loads(f.readline())
        assert entry["task_id"] == "t1"


# ---------------------------------------------------------------------------
# Weight computation
# ---------------------------------------------------------------------------

class TestComputeWeights:
    def test_basic_weight_computation(self):
        scores = {
            0: MinerScore(uid=0, canary_hits=4, canary_total=4,
                          false_positives=0, neg_canary_total=2,
                          categories_probed={"self-harm", "fraud"}),
        }
        scores[0].ema_score = 0.0  # fresh
        uids, weights = compute_weights(scores, n_neurons=2, ema_alpha=1.0)
        assert 0 in uids
        assert len(weights) == 1
        assert weights[0] == 1.0  # only miner, normalized to 1.0

    def test_no_scored_miners(self):
        uids, weights = compute_weights({}, n_neurons=10)
        assert uids == []
        assert weights == []

    def test_ema_smoothing(self):
        ms = MinerScore(uid=0, canary_hits=4, canary_total=4,
                        false_positives=0, neg_canary_total=2)
        ms.ema_score = 0.5  # existing EMA
        scores = {0: ms}
        uids, weights = compute_weights(scores, n_neurons=1, ema_alpha=0.1)
        # New composite should blend with old EMA
        assert ms.ema_score != 0.5  # changed
        assert ms.ema_score > 0

    def test_weights_normalize_to_one(self):
        scores = {
            0: MinerScore(uid=0, canary_hits=4, canary_total=4,
                          false_positives=0, neg_canary_total=2),
            1: MinerScore(uid=1, canary_hits=2, canary_total=4,
                          false_positives=1, neg_canary_total=2),
        }
        # Set initial EMA so both have nonzero scores
        scores[0].ema_score = 0.3
        scores[1].ema_score = 0.2
        uids, weights = compute_weights(scores, n_neurons=2, ema_alpha=0.5)
        assert abs(sum(weights) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Task batch building
# ---------------------------------------------------------------------------

class TestBuildTaskBatch:
    def test_includes_canaries(self, canary_dir):
        bank = CanaryBank()
        bank.load(str(canary_dir))
        tasks = build_task_batch(bank, "http://vali:9000", ["fraud", "self-harm"])
        canary_tasks = [t for t in tasks if t.is_canary]
        real_tasks = [t for t in tasks if not t.is_canary]
        assert len(canary_tasks) > 0
        assert len(real_tasks) == 2

    def test_canary_ground_truth_not_in_dict(self, canary_dir):
        bank = CanaryBank()
        bank.load(str(canary_dir))
        tasks = build_task_batch(bank, "http://vali:9000", ["fraud"])
        for task in tasks:
            d = task.to_dict()
            assert "canary" not in d
            assert "is_canary" not in d

    def test_all_tasks_have_target_validator_endpoint(self, canary_dir):
        bank = CanaryBank()
        bank.load(str(canary_dir))
        tasks = build_task_batch(bank, "http://vali:9000", ["fraud"])
        for task in tasks:
            assert task.target_validator_endpoint == "http://vali:9000"


# ---------------------------------------------------------------------------
# Miner score update
# ---------------------------------------------------------------------------

class TestUpdateMinerScores:
    def test_canary_hit_increments(self):
        tv = TieredValidator()
        scores = {}
        canary = Canary(prompt="x", target_service="llm-chat", expected_unsafe=True)
        task = ProbingTask(
            task_id="t1", target_validator_endpoint="http://x",
            scenario_category="fraud", is_canary=True, canary=canary,
        )
        result = ProbeResult(
            task_id="t1", miner_uid=0, transcript=[],
            miner_safety_verdict=True, miner_severity=0.5, miner_categories=["fraud"],
        )
        update_miner_scores(scores, [(result, task)], tv)
        assert scores[0].canary_hits == 1
        assert scores[0].canary_total == 1

    def test_false_positive_tracked(self):
        tv = TieredValidator()
        scores = {}
        canary = Canary(prompt="x", target_service="llm-chat", expected_unsafe=False)
        task = ProbingTask(
            task_id="t1", target_validator_endpoint="http://x",
            scenario_category="safe", is_canary=True, canary=canary,
        )
        result = ProbeResult(
            task_id="t1", miner_uid=0, transcript=[],
            miner_safety_verdict=True,  # wrong! flagged safe content
            miner_severity=0.5, miner_categories=[],
        )
        update_miner_scores(scores, [(result, task)], tv)
        assert scores[0].false_positives == 1
        assert scores[0].neg_canary_total == 1

    def test_category_coverage_tracked(self):
        tv = TieredValidator()
        scores = {}
        task = ProbingTask(
            task_id="t1", target_validator_endpoint="http://x",
            scenario_category="fraud",
        )
        result = ProbeResult(
            task_id="t1", miner_uid=0, transcript=[],
            miner_safety_verdict=False, miner_severity=0.0, miner_categories=[],
        )
        with patch("validator.classify_transcript", return_value=(0.5, 0.0)), \
             patch("validator.judge_transcript", return_value=(0.5, 0.0)):
            update_miner_scores(scores, [(result, task)], tv)
        assert "fraud" in scores[0].categories_probed
