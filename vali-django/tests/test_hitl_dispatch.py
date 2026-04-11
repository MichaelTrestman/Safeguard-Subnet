"""Tests for the HITL dispatch path (Sub-work A.2).

Two properties are load-bearing here:

1. Miner selection is UNIFORM-RANDOM over eligible miners. No cherry-
   picking. The validator's operator must not be able to route a
   specific HitlCase to a specific HITL miner based on the case's
   category, severity, claim, or miner UID. This is the trust-
   minimization property from the plan and it is NON-NEGOTIABLE.

2. The dispatch flow correctly transitions state:
    - 200 label → HitlCase.status=labeled, PendingContributionAdjustment
      row created, Finding curation fields updated.
    - 504 → HitlCase reverted to pending, miner HITL cooldown set.
    - 503 → HitlCase reverted to pending, miner HITL cooldown set
      (longer).
    - operator remove → HitlCase.status=removed with reason stamped.

Run:
    python manage.py test tests.test_hitl_dispatch
"""
from __future__ import annotations

import asyncio
import random
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone as djtz

from validator import loop as vloop
from validator.models import (
    Evaluation,
    Finding,
    HitlCase,
    MinerScore,
    PendingContributionAdjustment,
    RegisteredTarget,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Minimal stand-in for httpx.Response used by _post_hitl_task."""

    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}
        self.text = str(body)

    def json(self) -> dict:
        return self._body


class _FakeClient:
    """Minimal async httpx.AsyncClient stand-in.

    `post_handler` is a callable `(url, content, headers, timeout) ->
    _FakeResponse` that may also raise to simulate a network failure.
    """

    def __init__(self, post_handler):
        self._post = post_handler
        self.calls: list[dict] = []

    async def post(self, url, content=None, headers=None, timeout=None):
        call = {"url": url, "content": content, "headers": headers, "timeout": timeout}
        self.calls.append(call)
        result = self._post(call)
        if isinstance(result, Exception):
            raise result
        return result

    async def aclose(self):
        pass


def _make_target() -> RegisteredTarget:
    return RegisteredTarget.objects.create(
        client_hotkey="target_hk_" + str(random.randint(0, 1_000_000)),
        name="test-target-" + str(random.randint(0, 1_000_000)),
        relay_endpoint="http://example.invalid/relay",
        categories=["self-harm"],
    )


def _make_case(
    target: RegisteredTarget,
    *,
    task_id: str,
    miner_uid: int,
    category: str = "self-harm",
    accepted_severity: float = 0.6,
    miner_safety_score: float = 0.1,
    audit_score: float = 0.8,
) -> tuple[Evaluation, HitlCase]:
    ev = Evaluation.objects.create(
        task_id=task_id,
        target=target,
        miner_uid=miner_uid,
        miner_hotkey=f"probe_hk_{miner_uid}",
        category=category,
        miner_safety_score=miner_safety_score,
        audit_score=audit_score,
        accepted_severity=accepted_severity,
        confidence_in_claim=0.5,
        findings_reward=0.3,
        transcript=[{"role": "user", "content": "hi"}],
        hitl_routed=True,
    )
    case = HitlCase.objects.create(
        evaluation=ev,
        status=HitlCase.STATUS_PENDING,
        labels=[],
    )
    return ev, case


# ---------------------------------------------------------------------------
# The property test: uniform-random selection
# ---------------------------------------------------------------------------


class UniformSelectionTests(TestCase):
    """The load-bearing trust property: selection across eligible
    miners is uniform-random, and does NOT depend on any property of
    the HitlCase (category, severity, claim, uid)."""

    def test_select_returns_none_on_empty(self):
        self.assertIsNone(vloop._select_hitl_miner_uniform([]))

    def test_distribution_over_300_trials(self):
        """Run the selection function 300 times against 3 mock eligible
        miners with distinct UIDs. Confirm each miner receives roughly
        1/3 (±15%) of selections. This is the property test for the
        trust-minimization constraint in the plan.
        """
        eligible = [(11, "http://miner11"), (22, "http://miner22"), (33, "http://miner33")]
        counts = {uid: 0 for uid, _ in eligible}
        # Use a module-level SystemRandom — same RNG the production
        # code uses. We deliberately do NOT seed it; the test tolerates
        # a ±15% band so the assertion is robust under genuine
        # randomness. This is the point: if the RNG ever sneaks in a
        # bias (e.g. someone hashes the miner uid to pick), the test
        # will catch it because the bias will be large compared to the
        # tolerance band.
        rng = random.SystemRandom()
        for _ in range(300):
            pick = vloop._select_hitl_miner_uniform(eligible, rng=rng)
            counts[pick[0]] += 1
        expected = 100  # 300 / 3
        # ±15% band = [85, 115]
        low, high = 85, 115
        for uid, n in counts.items():
            with self.subTest(uid=uid):
                self.assertGreaterEqual(
                    n, low,
                    f"uid {uid} got {n}/{300} (<{low}); RNG appears biased",
                )
                self.assertLessEqual(
                    n, high,
                    f"uid {uid} got {n}/{300} (>{high}); RNG appears biased",
                )
        # Expose the distribution to the test runner for the report.
        print(f"\n[uniform-random] 300 trials over 3 miners: {counts}")

    def test_selection_ignores_case_metadata(self):
        """The selection function's signature accepts only the list of
        (uid, endpoint) pairs. We can't pass a HitlCase, category,
        severity, or claim in — and the production caller in
        `_dispatch_one_hitl_case` builds the ep_pairs list without
        those attributes. This test documents the invariant by
        introspecting the signature.
        """
        import inspect
        sig = inspect.signature(vloop._select_hitl_miner_uniform)
        # Only two parameters: eligible, rng.
        self.assertEqual(
            list(sig.parameters.keys()),
            ["eligible", "rng"],
            "_select_hitl_miner_uniform must not accept case / category "
            "/ severity / claim / uid parameters — see plan "
            "architectural constraint",
        )


# ---------------------------------------------------------------------------
# End-to-end dispatch flow tests (mocked httpx)
# ---------------------------------------------------------------------------


class DispatchFlowTests(TransactionTestCase):
    # TransactionTestCase (not TestCase) because _dispatch_hitl_cases
    # runs DB writes from asgiref.sync_to_async worker threads; the
    # TestCase-level outer transaction is invisible to those threads
    # under sqlite, which raises "database table is locked" on the
    # first cross-thread write. TransactionTestCase flushes tables
    # between tests instead, which is the idiomatic Django fix.

    def setUp(self):
        self.target = _make_target()
        self.wallet = mock.MagicMock()
        # Give the wallet a fake hotkey that create_epistula_headers
        # can read. We stub out create_epistula_headers so it never
        # needs to touch real crypto.
        # `_post_hitl_task` imports create_epistula_headers from
        # `validator.epistula` at call time (local import inside the
        # function). Patch the module-level symbol so the stub is
        # picked up by every call.
        self._epistula_patch = mock.patch(
            "validator.epistula.create_epistula_headers",
            return_value={"X-Epistula-Test": "1"},
        )
        self._epistula_patch.start()

        self.hitl_miners = {5: "http://hitl5.invalid"}
        # Ensure MinerScore rows exist so cooldown writes have a target.
        MinerScore.objects.create(uid=5, hotkey="hitl_hk_5")

    def tearDown(self):
        self._epistula_patch.stop()

    def _run(self, coro):
        # Python 3.12+ deprecates asyncio.get_event_loop() from a
        # non-coroutine context when there is no running loop. Spin
        # up a fresh loop per call and tear it down so each test is
        # hermetic.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_success_200_label_transitions_case_and_creates_adjustment(self):
        ev, case = _make_case(
            self.target, task_id="task-success", miner_uid=42,
            accepted_severity=0.6,
        )
        # Finding for the evaluation so we can verify curation denorm update.
        Finding.objects.create(
            evaluation=ev, category="self-harm", severity=0.6,
            summary="test", critical=True,
        )

        label_body = {
            "task_id": "task-success",
            "status": "labeled",
            "severity": 0.9,
            "categories": ["self-harm"],
            "reasoning": "clearly harmful",
        }

        def _handler(call):
            return _FakeResponse(200, label_body)

        client = _FakeClient(_handler)

        result = self._run(vloop._dispatch_hitl_cases(
            self.wallet, self.hitl_miners, http_client=client,
        ))

        self.assertEqual(result["labeled"], 1)
        self.assertEqual(result["retryable"], 0)

        case.refresh_from_db()
        self.assertEqual(case.status, HitlCase.STATUS_LABELED)
        self.assertIsNotNone(case.labeled_at)
        self.assertEqual(case.dispatched_to_uid, 5)
        self.assertEqual(len(case.labels), 1)
        self.assertEqual(case.labels[0]["severity"], 0.9)

        adjustments = list(PendingContributionAdjustment.objects.all())
        self.assertEqual(len(adjustments), 1)
        adj = adjustments[0]
        self.assertFalse(adj.applied)
        self.assertAlmostEqual(adj.original_severity, 0.6)
        self.assertAlmostEqual(adj.ground_truth_severity, 0.9)
        self.assertEqual(adj.probe_miner_uid, 42)

        finding = Finding.objects.get(evaluation=ev)
        self.assertTrue(finding.curated)
        self.assertAlmostEqual(finding.curated_severity, 0.9)

    def test_504_reverts_case_and_sets_short_cooldown(self):
        _ev, case = _make_case(
            self.target, task_id="task-504", miner_uid=42,
        )

        def _handler(call):
            return _FakeResponse(504, {"task_id": "task-504", "status": "timed_out"})

        client = _FakeClient(_handler)
        result = self._run(vloop._dispatch_hitl_cases(
            self.wallet, self.hitl_miners, http_client=client,
        ))

        self.assertEqual(result["labeled"], 0)
        self.assertEqual(result["retryable"], 1)
        case.refresh_from_db()
        self.assertEqual(case.status, HitlCase.STATUS_PENDING)

        m = MinerScore.objects.get(uid=5)
        self.assertIsNotNone(m.hitl_cooldown_until)
        # Cooldown should be in the future, within the 504 band.
        until = m.hitl_cooldown_until
        now = djtz.now()
        delta_s = (until - now).total_seconds()
        self.assertGreater(delta_s, 30.0)  # Some cooldown present.
        self.assertLessEqual(
            delta_s, vloop.HITL_COOLDOWN_S_504 + 5.0,
        )

    def test_503_reverts_case_and_sets_longer_cooldown(self):
        _ev, case = _make_case(
            self.target, task_id="task-503", miner_uid=42,
        )

        def _handler(call):
            return _FakeResponse(503, {"error": "hitl role paused"})

        client = _FakeClient(_handler)
        result = self._run(vloop._dispatch_hitl_cases(
            self.wallet, self.hitl_miners, http_client=client,
        ))

        self.assertEqual(result["retryable"], 1)
        case.refresh_from_db()
        self.assertEqual(case.status, HitlCase.STATUS_PENDING)

        m = MinerScore.objects.get(uid=5)
        self.assertIsNotNone(m.hitl_cooldown_until)
        delta_s = (m.hitl_cooldown_until - djtz.now()).total_seconds()
        # 503 cooldown is longer than 504.
        self.assertGreater(delta_s, vloop.HITL_COOLDOWN_S_504 + 30)
        self.assertLessEqual(
            delta_s, vloop.HITL_COOLDOWN_S_503 + 5.0,
        )

    def test_exception_reverts_case_and_sets_other_cooldown(self):
        _ev, case = _make_case(
            self.target, task_id="task-exc", miner_uid=42,
        )

        def _handler(call):
            return RuntimeError("connection reset")

        client = _FakeClient(_handler)
        self._run(vloop._dispatch_hitl_cases(
            self.wallet, self.hitl_miners, http_client=client,
        ))

        case.refresh_from_db()
        self.assertEqual(case.status, HitlCase.STATUS_PENDING)
        m = MinerScore.objects.get(uid=5)
        self.assertIsNotNone(m.hitl_cooldown_until)

    def test_cooldown_excludes_miner_from_eligible_set(self):
        """A miner whose hitl_cooldown_until is in the future is not
        eligible this tick."""
        _ev, case = _make_case(
            self.target, task_id="task-cd", miner_uid=42,
        )
        MinerScore.objects.filter(uid=5).update(
            hitl_cooldown_until=djtz.now() + timedelta(minutes=10),
        )
        # No dispatch should happen because the only miner is on cooldown.
        result = self._run(vloop._dispatch_hitl_cases(
            self.wallet, self.hitl_miners, http_client=_FakeClient(
                lambda call: _FakeResponse(
                    500, {"should": "never be called"}
                ),
            ),
        ))
        self.assertEqual(result["dispatched"], 0)
        self.assertEqual(result.get("eligible", 0), 0)
        case.refresh_from_db()
        self.assertEqual(case.status, HitlCase.STATUS_PENDING)


# ---------------------------------------------------------------------------
# Operator remove view
# ---------------------------------------------------------------------------


class HitlRemoveViewTests(TestCase):
    def setUp(self):
        self.target = _make_target()
        _ev, self.case = _make_case(
            self.target, task_id="task-remove", miner_uid=42,
        )
        self.user = User.objects.create_user(
            username="operator", password="pw", is_staff=True,
        )
        self.client_ = Client()
        self.client_.login(username="operator", password="pw")

    def test_remove_with_reason_transitions_to_removed(self):
        resp = self.client_.post(
            reverse("hitl_case_remove", args=[self.case.pk]),
            {"reason": "duplicate of case 12"},
        )
        self.assertEqual(resp.status_code, 302)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, HitlCase.STATUS_REMOVED)
        self.assertEqual(self.case.removed_reason, "duplicate of case 12")
        self.assertEqual(self.case.removed_by, self.user)
        self.assertIsNotNone(self.case.removed_at)

    def test_remove_without_reason_returns_400(self):
        resp = self.client_.post(
            reverse("hitl_case_remove", args=[self.case.pk]),
            {"reason": "   "},  # whitespace-only → rejected
        )
        self.assertEqual(resp.status_code, 400)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, HitlCase.STATUS_PENDING)

    def test_remove_already_dispatched_case_is_rejected(self):
        self.case.status = HitlCase.STATUS_DISPATCHED
        self.case.save()
        resp = self.client_.post(
            reverse("hitl_case_remove", args=[self.case.pk]),
            {"reason": "too late"},
        )
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# Discovery — types list back-compat
# ---------------------------------------------------------------------------


class DiscoveryCommitmentShapeTests(TestCase):
    def test_types_list_hybrid(self):
        data = {"types": ["probe", "hitl"], "endpoint": "http://x"}
        self.assertEqual(vloop._commitment_role_set(data), {"probe", "hitl"})

    def test_types_list_hitl_only(self):
        self.assertEqual(
            vloop._commitment_role_set({"types": ["hitl"], "endpoint": "http://x"}),
            {"hitl"},
        )

    def test_legacy_scalar_type_probe(self):
        self.assertEqual(
            vloop._commitment_role_set({"type": "probe", "endpoint": "http://x"}),
            {"probe"},
        )

    def test_legacy_scalar_type_hitl(self):
        self.assertEqual(
            vloop._commitment_role_set({"type": "hitl", "endpoint": "http://x"}),
            {"hitl"},
        )

    def test_legacy_bare_endpoint_defaults_probe(self):
        self.assertEqual(
            vloop._commitment_role_set({"endpoint": "http://x"}),
            {"probe"},
        )
