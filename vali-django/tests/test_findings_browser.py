"""Tests for the findings browser view.

Run:
    python manage.py test tests.test_findings_browser
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from validator.models import Evaluation, Finding, RegisteredTarget


class FindingsBrowserTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="operator", password="pw", is_staff=True,
        )
        cls.target_a = RegisteredTarget.objects.create(
            client_hotkey="5FakeFA", name="target-a",
            relay_endpoint="https://a.test/relay",
            subnet_type="llm-chat", categories=["test"],
        )
        cls.target_b = RegisteredTarget.objects.create(
            client_hotkey="5FakeFB", name="target-b",
            relay_endpoint="https://b.test/relay",
            subnet_type="llm-chat", categories=["test"],
        )
        ev_a = Evaluation.objects.create(
            task_id="fba1", target=cls.target_a, miner_uid=1,
            miner_hotkey="hk1", category="phishing",
            concern_id_slug="phishing-concern",
            provenance_verified=True, accepted_severity=0.85,
        )
        ev_b = Evaluation.objects.create(
            task_id="fbb1", target=cls.target_b, miner_uid=1,
            miner_hotkey="hk1", category="self-harm",
            concern_id_slug="self-harm-concern",
            provenance_verified=True, accepted_severity=0.3,
        )
        Finding.objects.create(
            evaluation=ev_a, category="phishing",
            severity=0.85, critical=True,
        )
        Finding.objects.create(
            evaluation=ev_b, category="self-harm",
            severity=0.3, critical=False, curated=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="operator", password="pw")

    def test_unfiltered_shows_all(self):
        resp = self.client.get(reverse("findings_browser"))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("phishing", body)
        self.assertIn("self-harm", body)

    def test_target_filter(self):
        resp = self.client.get(reverse("findings_browser") + "?target=target-a")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("<strong>1</strong>", body)  # 1 finding matching
        self.assertIn("fba1", body)  # phishing eval task_id
        self.assertNotIn("fbb1", body)  # self-harm eval task_id NOT in results

    def test_critical_filter(self):
        resp = self.client.get(reverse("findings_browser") + "?critical=1")
        body = resp.content.decode()
        self.assertIn("fba1", body)  # critical finding
        self.assertNotIn("fbb1", body)  # non-critical NOT in results

    def test_curated_filter(self):
        resp = self.client.get(reverse("findings_browser") + "?curated=1")
        body = resp.content.decode()
        self.assertIn("fbb1", body)  # curated finding
        self.assertNotIn("fba1", body)  # uncurated NOT in results

    def test_non_staff_forbidden(self):
        get_user_model().objects.create_user(
            username="nostaff", password="pw", is_staff=False,
        )
        c = Client()
        c.login(username="nostaff", password="pw")
        resp = c.get(reverse("findings_browser"))
        self.assertEqual(resp.status_code, 403)
