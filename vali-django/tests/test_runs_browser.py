"""Tests for the operator runs browser view.

The runs browser is the "see everything" companion to the findings
panel — it shows every Evaluation row regardless of whether a Finding
was recorded. These tests pin the filter behavior so the operator can
trust the category / concern / uid / findings-only filters.

Run:
    python manage.py test tests.test_runs_browser
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from validator.models import Evaluation, Finding, RegisteredTarget


class RunsBrowserTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="operator", password="pw", is_staff=True,
        )
        cls.target = RegisteredTarget.objects.create(
            client_hotkey="5FakeClient",
            name="probe-target-runs",
            relay_endpoint="https://example.test/relay",
            subnet_type="llm-chat",
            categories=["self-harm-validation", "credential-leak"],
        )

        cls.ev_self_harm = Evaluation.objects.create(
            task_id="task-sh-001",
            target=cls.target,
            miner_uid=5,
            miner_hotkey="5FakeMinerA",
            category="self-harm-validation",
            concern_id_slug="ai-validates-self-harm",
            miner_safety_score=0.72,
            audit_score=0.70,
            accepted_severity=0.70,
        )
        cls.ev_credential = Evaluation.objects.create(
            task_id="task-cl-002",
            target=cls.target,
            miner_uid=12,
            miner_hotkey="5FakeMinerB",
            category="credential-leak",
            concern_id_slug="ai-emits-credentials",
            miner_safety_score=0.10,
            audit_score=0.05,
            accepted_severity=0.05,
        )
        cls.ev_benign = Evaluation.objects.create(
            task_id="task-bn-003",
            target=cls.target,
            miner_uid=5,
            miner_hotkey="5FakeMinerA",
            category="self-harm-validation",
            concern_id_slug="ai-validates-self-harm",
            miner_safety_score=0.00,
            audit_score=0.00,
            accepted_severity=0.00,
        )
        # Only the first evaluation has a Finding.
        Finding.objects.create(
            evaluation=cls.ev_self_harm,
            category="self-harm-validation",
            severity=0.70,
            critical=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="operator", password="pw")

    def test_unfiltered_shows_all_rows(self):
        resp = self.client.get(reverse("runs_browser"))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("task-sh-001", body)
        self.assertIn("task-cl-002", body)
        self.assertIn("task-bn-003", body)
        # The count banner wraps the number in <strong>; assert on both
        # pieces rather than the literal concatenation.
        self.assertIn("<strong>3</strong>", body)
        self.assertIn("runs matching", body)

    def test_category_filter_scopes_results(self):
        resp = self.client.get(
            reverse("runs_browser") + "?category=credential-leak",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("task-cl-002", body)
        self.assertNotIn("task-sh-001", body)
        self.assertNotIn("task-bn-003", body)

    def test_concern_filter_scopes_results(self):
        resp = self.client.get(
            reverse("runs_browser") + "?concern=ai-emits-credentials",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("task-cl-002", body)
        self.assertNotIn("task-sh-001", body)
        self.assertNotIn("task-bn-003", body)

    def test_uid_filter_scopes_results(self):
        resp = self.client.get(reverse("runs_browser") + "?uid=5")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("task-sh-001", body)
        self.assertIn("task-bn-003", body)
        self.assertNotIn("task-cl-002", body)

    def test_only_findings_filter_excludes_benign_rows(self):
        resp = self.client.get(
            reverse("runs_browser") + "?only_findings=1",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("task-sh-001", body)
        self.assertNotIn("task-cl-002", body)
        self.assertNotIn("task-bn-003", body)

    def test_non_staff_is_forbidden(self):
        get_user_model().objects.create_user(
            username="nonstaff", password="pw", is_staff=False,
        )
        c = Client()
        c.login(username="nonstaff", password="pw")
        resp = c.get(reverse("runs_browser"))
        # staff_required returns 403 for logged-in non-staff (see views.staff_required)
        self.assertEqual(resp.status_code, 403)
