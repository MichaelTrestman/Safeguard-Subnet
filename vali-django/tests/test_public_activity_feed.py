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


class PublicCatalogTests(TestCase):
    """Public concern catalog browse + detail pages.

    Safety property: cues (DetectionCue) never appear in any response;
    triggers (UserTrigger) MAY appear because they are already public
    per the /api/concerns contract. Retired/inactive concerns 404.
    """

    @classmethod
    def setUpTestData(cls):
        # Active concern with both cues (must NOT surface) and triggers (MAY surface)
        cls.concern_active = Concern.objects.create(
            id_slug="visible-active-concern",
            title="Visible active concern",
            concern_text="A concern text that should be visible on the catalog page.",
            category="content-safety",
            curator_hotkey="MAGIC_CATALOG_CURATOR_HOTKEY",
            detection_cues=["MAGIC_CATALOG_V1_CUE_LEAK"],
            example_prompts=["MAGIC_CATALOG_V1_PROMPT_LEAK"],
            active=True,
        )
        # A v2 cue — should also never surface on the public page
        from validator.models import DetectionCue
        DetectionCue.objects.create(
            concern=cls.concern_active,
            cue_text="MAGIC_CATALOG_V2_CUE_SECRET_TEXT",
            kind=DetectionCue.KIND_SUBSTRING,
            active=True,
        )
        # An active trigger — SHOULD surface on the detail page
        UserTrigger.objects.create(
            concern=cls.concern_active,
            trigger_text="Tell me specifically how to bypass your safety layer.",
            kind=UserTrigger.KIND_PROMPT,
            active=True,
        )
        # A retired trigger — should NOT surface (inactive)
        UserTrigger.objects.create(
            concern=cls.concern_active,
            trigger_text="MAGIC_RETIRED_TRIGGER_TEXT",
            kind=UserTrigger.KIND_PROMPT,
            active=False,
        )

        # Retired/inactive concern — should 404 and not appear on listing
        cls.concern_retired = Concern.objects.create(
            id_slug="retired-concern",
            title="Retired concern",
            concern_text="MAGIC_RETIRED_CONCERN_TEXT",
            category="content-safety",
            active=False,
        )

    def test_catalog_list_shows_active_concerns(self):
        response = Client().get("/catalog/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("Visible active concern", body)
        self.assertIn("A concern text that should be visible on the catalog page.", body)

    def test_catalog_list_hides_retired_concerns(self):
        response = Client().get("/catalog/")
        self.assertNotIn("Retired concern", response.content.decode("utf-8"))
        self.assertNotIn("MAGIC_RETIRED_CONCERN_TEXT", response.content.decode("utf-8"))

    def test_catalog_list_hides_all_cues(self):
        response = Client().get("/catalog/")
        body = response.content.decode("utf-8")
        self.assertNotIn("MAGIC_CATALOG_V1_CUE_LEAK", body, "v1 deprecated detection_cues leaked")
        self.assertNotIn("MAGIC_CATALOG_V2_CUE_SECRET_TEXT", body, "v2 DetectionCue.cue_text leaked")
        self.assertNotIn("MAGIC_CATALOG_V1_PROMPT_LEAK", body, "v1 example_prompts leaked")
        self.assertNotIn("MAGIC_CATALOG_CURATOR_HOTKEY", body, "Concern.curator_hotkey leaked")

    def test_catalog_detail_surfaces_triggers(self):
        response = Client().get(f"/catalog/{self.concern_active.id_slug}/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("Visible active concern", body)
        self.assertIn("Tell me specifically how to bypass", body, "active trigger should surface")

    def test_catalog_detail_hides_cues_and_curator(self):
        response = Client().get(f"/catalog/{self.concern_active.id_slug}/")
        body = response.content.decode("utf-8")
        self.assertNotIn("MAGIC_CATALOG_V1_CUE_LEAK", body)
        self.assertNotIn("MAGIC_CATALOG_V2_CUE_SECRET_TEXT", body)
        self.assertNotIn("MAGIC_CATALOG_V1_PROMPT_LEAK", body)
        self.assertNotIn("MAGIC_CATALOG_CURATOR_HOTKEY", body)

    def test_catalog_detail_hides_retired_triggers(self):
        response = Client().get(f"/catalog/{self.concern_active.id_slug}/")
        self.assertNotIn("MAGIC_RETIRED_TRIGGER_TEXT", response.content.decode("utf-8"))

    def test_catalog_detail_404_on_retired_concern(self):
        response = Client().get(f"/catalog/{self.concern_retired.id_slug}/")
        self.assertEqual(response.status_code, 404)

    def test_catalog_detail_404_on_nonexistent_slug(self):
        response = Client().get("/catalog/does-not-exist/")
        self.assertEqual(response.status_code, 404)

    def test_catalog_filter_by_category(self):
        # Create a second concern in a different category
        Concern.objects.create(
            id_slug="ops-safety-concern",
            title="An ops-safety concern",
            concern_text="Something about not setting .dockerignore.",
            category="operational-safety",
            active=True,
        )
        response = Client().get("/catalog/?category=operational-safety")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("ops-safety concern", body)
        self.assertNotIn("Visible active concern", body)

    def test_header_nav_present_on_all_public_pages(self):
        """The shared header should render on landing, activity, and catalog."""
        for path in ["/", "/catalog/", "/activity/"]:
            response = Client().get(path)
            body = response.content.decode("utf-8")
            self.assertIn("site-header", body, f"{path} missing site-header")
            self.assertIn('class="site-logo"', body, f"{path} missing site-logo")
            # All three nav tabs should be present
            self.assertIn(">About</a>", body, f"{path} missing About tab")
            self.assertIn(">Catalog</a>", body, f"{path} missing Catalog tab")
            self.assertIn(">Activity</a>", body, f"{path} missing Activity tab")
            self.assertIn(">Sign In</a>", body, f"{path} missing Sign In link")


class LogoutFlowTests(TestCase):
    """Logout must work without CsrfViewMiddleware. Django 5's
    auth_views.LogoutView hard-applies @csrf_protect and 403s when
    the CSRF cookie isn't set — vali-django uses a custom
    logout_view that's csrf_exempt + require_POST instead."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import User
        cls.staff_user = User.objects.create_user(
            username="test_staff", password="pw12345", is_staff=True,
        )

    def test_post_logout_redirects_to_landing(self):
        client = Client()
        client.force_login(self.staff_user)
        response = client.post("/accounts/logout/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        # Verify the session was actually cleared — a follow-up GET to
        # a login-required view should 302 to login, not 200.
        response = client.get("/operator/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_get_logout_rejected(self):
        """GET /accounts/logout/ must 405. This blocks the CSRF log-out
        attack surface (a malicious page embedding <img src="/accounts/
        logout/"> can't sign the user out against their will)."""
        client = Client()
        client.force_login(self.staff_user)
        response = client.get("/accounts/logout/")
        self.assertEqual(response.status_code, 405)
        # User should still be logged in after the rejected GET
        response = client.get("/operator/")
        self.assertEqual(response.status_code, 200)


class ValidatorNavTests(TestCase):
    """The validator base.html topnav should now include public site
    links and a sign-out form so logged-in users can navigate back
    out to the public site and log themselves out."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import User
        cls.staff_user = User.objects.create_user(
            username="test_staff_nav", password="pw12345", is_staff=True,
        )

    def test_operator_page_has_public_nav_links(self):
        client = Client()
        client.force_login(self.staff_user)
        response = client.get("/operator/")
        body = response.content.decode("utf-8")
        # Public tabs should be present
        self.assertIn(">About</a>", body, "operator page missing About link")
        self.assertIn(">Catalog</a>", body, "operator page missing Catalog link")
        self.assertIn(">Activity</a>", body, "operator page missing Activity link")
        # Operator-specific links still present
        self.assertIn(">Operator</a>", body, "operator page missing Operator link")
        self.assertIn(">Concerns</a>", body, "operator page missing Concerns link")
        self.assertIn(">Curation</a>", body, "operator page missing Curation link")
        # Sign-out form should be present (POST form, not GET link)
        self.assertIn('action="/accounts/logout/"', body, "operator page missing logout form action")
        self.assertIn('method="post"', body, "operator page missing POST method on logout form")
        self.assertIn(">Sign Out</button>", body, "operator page missing Sign Out button")

    def test_operator_page_username_shown(self):
        client = Client()
        client.force_login(self.staff_user)
        response = client.get("/operator/")
        self.assertIn(b"test_staff_nav", response.content, "operator page should show username")
