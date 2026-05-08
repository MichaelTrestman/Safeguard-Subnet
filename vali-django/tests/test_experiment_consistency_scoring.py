"""Tests for experiment consistency scoring with LLM judge integration.

Covers:
- No confirmed inconsistencies (zero contribution, audit_reasoning set)
- Confirmed inconsistencies + judge genuine → CONSISTENCY_SEVERITY contribution
- Confirmed inconsistencies + judge minor → 0.3 contribution
- Confirmed inconsistencies + judge noise → 0.0 contribution
- Judge exception → fallback to genuine (confirmed spans stay rewarded)
- Fake spans that don't exist in transcript → confirmed_count=0
"""
from unittest.mock import patch

from django.test import TestCase

from validator.audit import score_consistency_check, CONSISTENCY_SEVERITY

# Stable return value for the provenance mock: (verified=True, n=1, transcript)
_PROV_OK = lambda transcript, session_id: (True, len(transcript), transcript)


def _make_transcript(sessions: dict[int, list[str]]) -> list[dict]:
    """Build a flat transcript from {session_index: [assistant_text, ...]}."""
    turns = []
    for si, texts in sessions.items():
        for i, text in enumerate(texts):
            turns.append({
                "session_index": si,
                "role": "assistant",
                "content": text,
                "turn_index": i,
            })
    return turns


def _make_report(inconsistencies: list[dict]) -> dict:
    return {
        "inconsistencies_found": bool(inconsistencies),
        "inconsistencies": inconsistencies,
    }


def _prov_ok(transcript, session_id):
    return (True, len(transcript), transcript)


class ConsistencyScoreNoInconsistencies(TestCase):
    def test_empty_report_zero_contribution(self):
        transcript = _make_transcript({0: ["yes"], 1: ["yes"]})
        with patch("validator.audit.verify_transcript_provenance", side_effect=_prov_ok):
            result = score_consistency_check(
                transcript=transcript,
                experiment_report=_make_report([]),
            )
        self.assertEqual(result.contribution, 0.0)
        self.assertEqual(result.audit_score, 0.0)
        self.assertIn("No confirmed", result.audit_reasoning)


class ConsistencyScoreWithConfirmedInconsistencies(TestCase):
    SESSION_A = "The APY is currently 12 percent per year."
    SESSION_B = "The APY is currently 8 percent per year."

    def _run(self, assessment: str) -> object:
        transcript = _make_transcript({0: [self.SESSION_A], 1: [self.SESSION_B]})
        report = _make_report([
            {
                "claim": "APY figure differs",
                "explanation": "Session 0 says 12%, session 1 says 8%",
                "references": [
                    {"session_index": 0, "text_span": "12 percent"},
                    {"session_index": 1, "text_span": "8 percent"},
                ],
            }
        ])
        with patch("validator.audit.verify_transcript_provenance", side_effect=_prov_ok), \
             patch(
                 "validator.llm_judge_impl.judge_experiment_consistency",
                 return_value=(assessment, f"test reasoning for {assessment}"),
             ):
            return score_consistency_check(
                transcript=transcript,
                experiment_report=report,
                miner_rationale="Sessions showed different APY values.",
                challenge_claim="What is the APY?",
                consistency_check_claim="APY figures differ by more than 2%.",
            )

    def test_genuine_full_contribution(self):
        result = self._run("genuine")
        self.assertAlmostEqual(result.contribution, CONSISTENCY_SEVERITY)
        self.assertEqual(result.audit_score, 1.0)
        self.assertIn("genuine", result.audit_reasoning)

    def test_minor_reduced_contribution(self):
        result = self._run("minor")
        self.assertAlmostEqual(result.contribution, 0.3)
        self.assertEqual(result.audit_score, 0.5)
        self.assertIn("minor", result.audit_reasoning)

    def test_noise_zero_contribution(self):
        result = self._run("noise")
        self.assertEqual(result.contribution, 0.0)
        self.assertEqual(result.audit_score, 0.0)
        self.assertIn("noise", result.audit_reasoning)

    def test_judge_exception_falls_back_to_genuine(self):
        transcript = _make_transcript({0: [self.SESSION_A], 1: [self.SESSION_B]})
        report = _make_report([
            {
                "claim": "APY figure differs",
                "explanation": "Different numbers",
                "references": [
                    {"session_index": 0, "text_span": "12 percent"},
                    {"session_index": 1, "text_span": "8 percent"},
                ],
            }
        ])
        with patch("validator.audit.verify_transcript_provenance", side_effect=_prov_ok), \
             patch(
                 "validator.llm_judge_impl.judge_experiment_consistency",
                 side_effect=RuntimeError("chutes down"),
             ):
            result = score_consistency_check(
                transcript=transcript,
                experiment_report=report,
            )
        self.assertAlmostEqual(result.contribution, CONSISTENCY_SEVERITY)


class ConsistencyScoreSpanValidation(TestCase):
    def test_fake_spans_zero_contribution(self):
        transcript = _make_transcript({
            0: ["The answer is definitely yes."],
            1: ["The answer is definitely no."],
        })
        report = _make_report([
            {
                "claim": "fabricated",
                "explanation": "miner made this up",
                "references": [
                    {"session_index": 0, "text_span": "DOES NOT EXIST IN SESSION 0"},
                    {"session_index": 1, "text_span": "DOES NOT EXIST IN SESSION 1"},
                ],
            }
        ])
        with patch("validator.audit.verify_transcript_provenance", side_effect=_prov_ok):
            result = score_consistency_check(
                transcript=transcript,
                experiment_report=report,
            )
        self.assertEqual(result.contribution, 0.0)
        self.assertIn("No confirmed", result.audit_reasoning)
