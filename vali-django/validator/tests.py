"""
Smoke tests for the validator operator views.

Goal: catch template rendering errors (500s) before deploy. A GET returning
200 on every key view proves the template compiles cleanly with the given
context — the class of bug that caused the `split` filter 500.

Run:
    cd vali-django && python manage.py test validator.tests
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    Behavior,
    Concern,
    Finding,
    Evaluation,
    RegisteredTarget,
    ValidatorStatus,
)


def _make_staff(username="op") -> User:
    return User.objects.create_user(username, password="x", is_staff=True)


def _make_concern(slug="test-concern", category="safety") -> Concern:
    return Concern.objects.create(
        id_slug=slug,
        title="Test concern",
        concern_text="The AI does something bad.",
        category=category,
    )


def _make_behavior(ref="test:behavior-1") -> Behavior:
    return Behavior.objects.create(
        source_ref=ref,
        behavior_text="The AI tells the user something harmful.",
        active=True,
    )


def _make_target(name="test-target") -> RegisteredTarget:
    return RegisteredTarget.objects.create(
        client_hotkey="5" + "A" * 47,
        name=name,
        relay_endpoint="http://localhost:9999",
    )


class OperatorViewSmokeTests(TestCase):
    """GET requests as a staff user should return 200 on all operator pages."""

    def setUp(self):
        self.user = _make_staff()
        self.client.login(username="op", password="x")
        # ValidatorStatus singleton required by operator_dashboard
        ValidatorStatus.objects.get_or_create(id=ValidatorStatus.SINGLETON_ID)
        self.concern = _make_concern()
        self.behavior = _make_behavior()

    def test_operator_dashboard(self):
        r = self.client.get(reverse("operator_dashboard"))
        self.assertEqual(r.status_code, 200)

    def test_concern_library(self):
        r = self.client.get(reverse("concern_library"))
        self.assertEqual(r.status_code, 200)

    def test_concern_detail(self):
        r = self.client.get(reverse("concern_detail", args=[self.concern.id_slug]))
        self.assertEqual(r.status_code, 200)

    def test_concern_detail_with_behavior_query(self):
        """concern_detail with ?behavior_q filter should render without error."""
        r = self.client.get(
            reverse("concern_detail", args=[self.concern.id_slug]),
            {"behavior_q": "harmful"},
        )
        self.assertEqual(r.status_code, 200)

    def test_concern_detail_with_per_page(self):
        """concern_detail per_page param is parsed and rendered correctly."""
        r = self.client.get(
            reverse("concern_detail", args=[self.concern.id_slug]),
            {"per_page": "50"},
        )
        self.assertEqual(r.status_code, 200)

    def test_behavior_library(self):
        r = self.client.get(reverse("behavior_library"))
        self.assertEqual(r.status_code, 200)

    def test_behavior_detail(self):
        r = self.client.get(reverse("behavior_detail", args=[self.behavior.pk]))
        self.assertEqual(r.status_code, 200)

    def test_behavior_detail_with_concern_query(self):
        """behavior_detail with ?concern_q filter should render without error."""
        r = self.client.get(
            reverse("behavior_detail", args=[self.behavior.pk]),
            {"concern_q": "test"},
        )
        self.assertEqual(r.status_code, 200)

    def test_behavior_detail_with_per_page(self):
        r = self.client.get(
            reverse("behavior_detail", args=[self.behavior.pk]),
            {"per_page": "50"},
        )
        self.assertEqual(r.status_code, 200)

    def test_findings_browser(self):
        r = self.client.get(reverse("findings_browser"))
        self.assertEqual(r.status_code, 200)

    def test_findings_browser_with_filters(self):
        """findings_browser with every filter param populated should render."""
        r = self.client.get(
            reverse("findings_browser"),
            {
                "min_severity": "0.5",
                "curated": "0",
                "critical": "1",
            },
        )
        self.assertEqual(r.status_code, 200)

    def test_runs_browser(self):
        r = self.client.get(reverse("runs_browser"))
        self.assertEqual(r.status_code, 200)

    def test_curation_queue(self):
        r = self.client.get(reverse("curation_queue"))
        self.assertEqual(r.status_code, 200)

    def test_curation_log(self):
        r = self.client.get(reverse("curation_log"))
        self.assertEqual(r.status_code, 200)


class ConcernBehaviorLinkingTests(TestCase):
    """Test the behavior↔concern M2M linking views round-trip."""

    def setUp(self):
        self.user = _make_staff()
        self.client.login(username="op", password="x")
        self.concern = _make_concern()
        self.behavior = _make_behavior()

    def test_behavior_detail_shows_linked_concern(self):
        self.behavior.concerns.add(self.concern)
        r = self.client.get(reverse("behavior_detail", args=[self.behavior.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.concern.id_slug)

    def test_concern_detail_shows_linked_behavior(self):
        self.concern.behaviors.add(self.behavior)
        r = self.client.get(reverse("concern_detail", args=[self.concern.id_slug]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.behavior.source_ref)


class PublicViewSmokeTests(TestCase):
    """Anonymous GET requests on public routes must return 200.

    Covers the anon-visible pages. No login required — these are the
    pages visible to any visitor. Tests catch template errors before deploy.
    """

    def setUp(self):
        self.concern = _make_concern()
        self.behavior = _make_behavior()
        self.target = _make_target()

    def test_landing(self):
        r = self.client.get(reverse("public:landing"))
        self.assertEqual(r.status_code, 200)

    def test_models_page(self):
        """Models page (formerly catalog) renders with concerns and behaviors."""
        r = self.client.get(reverse("public:catalog"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.concern.title)
        self.assertContains(r, self.behavior.behavior_text)

    def test_models_page_category_filter(self):
        r = self.client.get(reverse("public:catalog"), {"category": "safety"})
        self.assertEqual(r.status_code, 200)

    def test_catalog_detail(self):
        r = self.client.get(
            reverse("public:catalog_detail", args=[self.concern.id_slug])
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.concern.title)

    def test_catalog_detail_404(self):
        r = self.client.get(
            reverse("public:catalog_detail", args=["does-not-exist"])
        )
        self.assertEqual(r.status_code, 404)

    def test_stats_page(self):
        """Stats page (formerly targets) renders without error."""
        r = self.client.get(reverse("public:targets"))
        self.assertEqual(r.status_code, 200)

    def test_activity_page(self):
        r = self.client.get(reverse("public:activity"))
        self.assertEqual(r.status_code, 200)

    def test_activity_feed_json(self):
        r = self.client.get(reverse("public:activity_feed"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/json")

    def test_experiments_page(self):
        r = self.client.get(reverse("public:experiments"))
        self.assertEqual(r.status_code, 200)


class StaffAuthTests(TestCase):
    """Non-staff users must not reach operator pages."""

    def test_anonymous_redirects_to_login(self):
        r = self.client.get(reverse("operator_dashboard"))
        self.assertIn(r.status_code, [302, 403])

    def test_non_staff_forbidden(self):
        User.objects.create_user("customer", password="x", is_staff=False)
        self.client.login(username="customer", password="x")
        r = self.client.get(reverse("operator_dashboard"))
        self.assertEqual(r.status_code, 403)
