"""Tests for the public (anon-visible) activity feed.

LOAD-BEARING PROPERTY: the public activity feed must never emit fields
that contain miner attribution, transcripts, curator identity, wallet
state, earnings, or detection cues. This test plants distinctive magic
values in every forbidden field across the models the feed's query
layer reads, then asserts the serialized JSON response does not contain
any of them — no matter how much fixture data exists in the other rows.

A new field on Concern / UserTrigger / ConcernRevision / CycleHistory /
Evaluation / Finding that the queries layer starts returning MUST be
audited through this test. If someone adds a new source in
public/queries.py, they must add fixture data + magic-value assertions
here or the feed is unsafe to publish.

Run:
    python manage.py test tests.test_public_activity_feed
"""
from __future__ import annotations

import json

from django.test import Client, TestCase
from django.utils import timezone as djtz

from validator.models import (
    Concern,
    ConcernRevision,
    CycleHistory,
    Evaluation,
    Finding,
    RegisteredTarget,
    UserTrigger,
)


# Magic marker strings planted in forbidden fields. The test asserts
# that none of these appear in any public response body.
FORBIDDEN_MARKERS = [
    "MAGIC_MINER_HOTKEY_5T4WZ",         # Evaluation.miner_hotkey
    "MAGIC_TRANSCRIPT_CONTENT_BLOB",    # Evaluation.transcript
    "MAGIC_CLIENT_HOTKEY_AB9X",         # RegisteredTarget.client_hotkey
    "MAGIC_CURATOR_HOTKEY_CR8Y",        # Concern.curator_hotkey
    "MAGIC_RELAY_ENDPOINT_URL",         # RegisteredTarget.relay_endpoint
    "MAGIC_SUMMARY_LEAK_DESC",          # Finding.summary
    "MAGIC_DETECTION_CUE_V1",           # Concern.detection_cues (deprecated JSONField)
    "MAGIC_EXAMPLE_PROMPT_V1",          # Concern.example_prompts (deprecated JSONField)
    "MAGIC_CONCERN_SNAPSHOT_BLOB",      # ConcernRevision.snapshot (full content)
    "99999.12345",                      # Evaluation.audit_score + Finding.severity
    "77777.88888",                      # Evaluation.contribution
    "55555.55555",                      # CycleHistory.earned_total
    "444444444",                        # CycleHistory.owner_uid as weight-map key
]


class PublicActivityFeedSafetyTests(TestCase):
    """The feed surfaces new concerns, triggers, edits, and cycle heartbeats.
    It must never leak transcripts, miner attribution, curator identity,
    or earnings."""

    @classmethod
    def setUpTestData(cls):
        # A RegisteredTarget with a magic client hotkey + relay endpoint
        target = RegisteredTarget.objects.create(
            client_hotkey="MAGIC_CLIENT_HOTKEY_AB9X",
            name="probe-target-1",
            relay_endpoint="https://MAGIC_RELAY_ENDPOINT_URL.test/relay",
            subnet_type="llm-chat",
            categories=["content-safety"],
        )

        # Concern with magic curator hotkey + deprecated v1 cue/prompt bags
        cls.concern = Concern.objects.create(
            id_slug="test-concern-a",
            title="Test concern A — visible title",
            concern_text="A visible concern text that should appear in the feed.",
            category="content-safety",
            curator_hotkey="MAGIC_CURATOR_HOTKEY_CR8Y",
            detection_cues=["MAGIC_DETECTION_CUE_V1"],
            example_prompts=["MAGIC_EXAMPLE_PROMPT_V1"],
            active=True,
        )

        # Revision row with magic snapshot content
        ConcernRevision.objects.create(
            concern=cls.concern,
            version=2,
            snapshot={"leaked": "MAGIC_CONCERN_SNAPSHOT_BLOB"},
        )

        # UserTrigger — should surface (miner-safe per api/concerns contract)
        UserTrigger.objects.create(
            concern=cls.concern,
            trigger_text="A visible trigger text that SHOULD appear in the feed.",
            kind=UserTrigger.KIND_PROMPT,
            active=True,
        )

        # Cycle heartbeat row with magic earnings + weight map
        CycleHistory.objects.create(
            cycle_block=12345,
            n_registered=3,
            n_dispatched=5,
            n_responded=4,
            n_earned=2,
            earned_total=55555.55555,          # forbidden
            burn_share=0.42,                   # forbidden
            owner_uid=444444444,               # forbidden (embedded in submitted_weights key too)
            submitted_weights={"444444444": 1.0},
            had_fresh_data=True,
        )

        # Evaluation with magic miner hotkey, transcript, audit scores,
        # contribution. None of this should surface.
        ev = Evaluation.objects.create(
            task_id="task-forbidden-1",
            target=target,
            miner_uid=7,
            miner_hotkey="MAGIC_MINER_HOTKEY_5T4WZ",
            category="content-safety",
            miner_safety_score=0.9,
            concern_id_slug="test-concern-a",
            audit_score=99999.12345,           # forbidden
            accepted_severity=0.8,
            contribution=77777.88888,          # forbidden
            transcript=[{"role": "user", "content": "MAGIC_TRANSCRIPT_CONTENT_BLOB"}],
            provenance_verified=True,
        )

        # Finding row with magic severity + summary
        Finding.objects.create(
            evaluation=ev,
            category="content-safety",
            severity=99999.12345,              # forbidden
            summary="MAGIC_SUMMARY_LEAK_DESC",  # forbidden
            critical=True,
        )

    def _assert_no_forbidden_markers(self, body: str, context: str):
        """Fail if any forbidden marker appears anywhere in a response body."""
        for marker in FORBIDDEN_MARKERS:
            if marker in body:
                self.fail(
                    f"Forbidden marker {marker!r} leaked into {context}. "
                    f"This means public/queries.py is reading a field it "
                    f"shouldn't, or the template is rendering a field that "
                    f"isn't in the ActivityRow whitelist."
                )

    def test_feed_json_omits_all_forbidden_fields(self):
        client = Client()
        response = client.get("/activity/feed.json")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self._assert_no_forbidden_markers(body, "/activity/feed.json")

        # Response should be well-formed JSON
        payload = json.loads(body)
        self.assertIn("items", payload)
        self.assertIsInstance(payload["items"], list)

        # Items should be non-empty since we planted fixtures
        self.assertGreater(len(payload["items"]), 0)

        # Each item should only have the ActivityRow.to_json fields
        allowed_keys = {"ts", "kind", "label", "detail", "ref"}
        for item in payload["items"]:
            self.assertEqual(
                set(item.keys()),
                allowed_keys,
                f"Feed item has unexpected keys: {set(item.keys()) - allowed_keys}",
            )

    def test_feed_json_surfaces_expected_content(self):
        """The visible (safe) fields SHOULD appear — the test is not just
        'nothing leaks' but 'the safe stuff lands correctly'."""
        response = Client().get("/activity/feed.json")
        payload = json.loads(response.content)
        items = payload["items"]

        # Index items by kind for easier assertions
        by_kind = {}
        for item in items:
            by_kind.setdefault(item["kind"], []).append(item)

        self.assertIn("concern_created", by_kind, "Should have a concern_created row")
        self.assertIn("concern_edited", by_kind, "Should have a concern_edited row")
        self.assertIn("trigger_created", by_kind, "Should have a trigger_created row")
        self.assertIn("cycle_heartbeat", by_kind, "Should have a cycle_heartbeat row")

        concern_row = by_kind["concern_created"][0]
        self.assertIn("Test concern A", concern_row["label"])
        self.assertIn("visible concern text", concern_row["detail"])
        self.assertEqual(concern_row["ref"], "test-concern-a")

        trigger_row = by_kind["trigger_created"][0]
        self.assertIn("visible trigger text", trigger_row["detail"])
        self.assertEqual(trigger_row["ref"], "test-concern-a")

        cycle_row = by_kind["cycle_heartbeat"][0]
        self.assertIn("12345", cycle_row["label"])
        self.assertEqual(cycle_row["ref"], "12345")

    def test_activity_page_omits_all_forbidden_fields(self):
        response = Client().get("/activity/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self._assert_no_forbidden_markers(body, "/activity/ (HTML)")

    def test_landing_page_omits_all_forbidden_fields(self):
        """The landing page is static marketing content but must also
        pass the leak test — regression guard if a future commit adds
        a live data widget without routing it through queries.py."""
        response = Client().get("/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self._assert_no_forbidden_markers(body, "/ (landing)")

    def test_feed_empty_db_returns_empty_items(self):
        """Clean DB should return a valid empty feed, not 500."""
        Concern.objects.all().delete()
        ConcernRevision.objects.all().delete()
        UserTrigger.objects.all().delete()
        CycleHistory.objects.all().delete()
        Evaluation.objects.all().delete()
        Finding.objects.all().delete()
        RegisteredTarget.objects.all().delete()

        response = Client().get("/activity/feed.json")
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload, {"items": []})


class PublicRoutingTests(TestCase):
    """Verify the Phase 0 routing split stayed intact — anon users get the
    landing at /, auth-gated paths still redirect to login."""

    def test_anon_landing_is_public(self):
        response = Client().get("/")
        self.assertEqual(response.status_code, 200)
        # Content smoke — hero heading should be present
        self.assertIn(b"Immune System", response.content)

    def test_anon_operator_redirects_to_login(self):
        response = Client().get("/operator/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_anon_app_root_redirects_to_login(self):
        response = Client().get("/app/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_anon_dashboard_redirects_to_login(self):
        response = Client().get("/dashboard/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
