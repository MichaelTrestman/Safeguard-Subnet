"""Tests for the comparative target view and runs browser target filter.

Run:
    python manage.py test tests.test_targets_compare
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from validator.models import Evaluation, Finding, RegisteredTarget


class TargetsCompareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="operator", password="pw", is_staff=True,
        )
        cls.target_a = RegisteredTarget.objects.create(
            client_hotkey="5FakeA",
            name="target-alpha",
            relay_endpoint="https://a.test/relay",
            subnet_type="llm-chat",
            categories=["test"],
        )
        cls.target_b = RegisteredTarget.objects.create(
            client_hotkey="5FakeB",
            name="target-beta",
            relay_endpoint="https://b.test/relay",
            subnet_type="llm-chat",
            categories=["test"],
        )
        # Target A: 2 verified evals, 1 finding
        ev_a1 = Evaluation.objects.create(
            task_id="ta1", target=cls.target_a, miner_uid=1,
            miner_hotkey="hk1", category="cat-x",
            provenance_verified=True, accepted_severity=0.5,
            audit_score=0.5,
        )
        Evaluation.objects.create(
            task_id="ta2", target=cls.target_a, miner_uid=1,
            miner_hotkey="hk1", category="cat-x",
            provenance_verified=True, accepted_severity=0.1,
            audit_score=0.1,
        )
        Finding.objects.create(
            evaluation=ev_a1, category="cat-x",
            severity=0.5, critical=False,
        )

        # Target B: 1 verified eval, 1 critical finding
        ev_b1 = Evaluation.objects.create(
            task_id="tb1", target=cls.target_b, miner_uid=2,
            miner_hotkey="hk2", category="cat-y",
            provenance_verified=True, accepted_severity=0.8,
            audit_score=0.8,
        )
        Finding.objects.create(
            evaluation=ev_b1, category="cat-y",
            severity=0.8, critical=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="operator", password="pw")

    def test_compare_page_shows_both_targets(self):
        resp = self.client.get(reverse("targets_compare"))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("target-alpha", body)
        self.assertIn("target-beta", body)

    def test_finding_rate_computed(self):
        resp = self.client.get(reverse("targets_compare"))
        body = resp.content.decode("utf-8")
        # Target A: 1 finding / 2 verified = 50%
        self.assertIn("50.0%", body)
        # Target B: 1 finding / 1 verified = 100%
        self.assertIn("100.0%", body)

    def test_critical_findings_shown(self):
        resp = self.client.get(reverse("targets_compare"))
        body = resp.content.decode("utf-8")
        # Target B has 1 critical finding — should appear with
        # the sev-high CSS class
        self.assertIn("sev-high", body)

    def test_non_staff_forbidden(self):
        get_user_model().objects.create_user(
            username="nonstaff", password="pw", is_staff=False,
        )
        c = Client()
        c.login(username="nonstaff", password="pw")
        resp = c.get(reverse("targets_compare"))
        self.assertEqual(resp.status_code, 403)


class RunsBrowserTargetFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="operator", password="pw", is_staff=True,
        )
        cls.target_a = RegisteredTarget.objects.create(
            client_hotkey="5FakeFilterA",
            name="persona-drunk",
            relay_endpoint="https://a.test/relay",
            subnet_type="llm-chat",
            categories=["test"],
        )
        cls.target_b = RegisteredTarget.objects.create(
            client_hotkey="5FakeFilterB",
            name="persona-sober",
            relay_endpoint="https://b.test/relay",
            subnet_type="llm-chat",
            categories=["test"],
        )
        Evaluation.objects.create(
            task_id="tf-drunk-1", target=cls.target_a, miner_uid=1,
            miner_hotkey="hk1", category="cat-x",
        )
        Evaluation.objects.create(
            task_id="tf-sober-1", target=cls.target_b, miner_uid=1,
            miner_hotkey="hk1", category="cat-x",
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="operator", password="pw")

    def test_target_filter_scopes_results(self):
        resp = self.client.get(
            reverse("runs_browser") + "?target=persona-drunk",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("tf-drunk-1", body)
        self.assertNotIn("tf-sober-1", body)

    def test_unfiltered_shows_both_targets(self):
        resp = self.client.get(reverse("runs_browser"))
        body = resp.content.decode("utf-8")
        self.assertIn("tf-drunk-1", body)
        self.assertIn("tf-sober-1", body)
