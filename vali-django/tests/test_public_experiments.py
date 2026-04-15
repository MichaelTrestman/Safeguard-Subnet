"""Tests for the public (anon-visible) experiment showcase.

LOAD-BEARING PROPERTY: /experiments/ and /experiments/<slug>/ must never
emit miner attribution (miner_uid, miner_hotkey), full transcripts,
per-trial evaluation detail, per-finding severity, or audit_score. The
public view is an aggregation over ExtractedClaim — only modal value,
consistency rate, accuracy rate, counts, and a short representative
text_span per (entity, field) cell are public.

A new field on Experiment / Evaluation / ExtractedClaim that the public
queries layer starts reading MUST be audited through this test. If
someone adds a new source in public/queries.py, they must add fixture
data + magic-value assertions here or the surface is unsafe to publish.

Run:
    python manage.py test tests.test_public_experiments
"""
from __future__ import annotations

from django.test import Client, TestCase
from django.utils import timezone as djtz

from validator.models import (
    Evaluation,
    Experiment,
    ExtractedClaim,
    Finding,
    RegisteredTarget,
)


# Magic marker strings planted in forbidden fields. None may appear in
# any public response body.
FORBIDDEN_MARKERS = [
    "MAGIC_EXP_MINER_HOTKEY_ZZ99",     # Evaluation.miner_hotkey
    "MAGIC_EXP_TRANSCRIPT_FULL_BODY",  # Evaluation.transcript content
    "MAGIC_EXP_CLIENT_HOTKEY_QQ77",    # RegisteredTarget.client_hotkey
    "MAGIC_EXP_RELAY_ENDPOINT",        # RegisteredTarget.relay_endpoint
    "MAGIC_EXP_FINDING_SUMMARY",       # Finding.summary
    "88888.44444",                     # Evaluation.audit_score
    "33333.22222",                     # Evaluation.contribution
    "66666.11111",                     # Finding.severity
]


def _make_experiment(slug="borges-aleph", is_public=True,
                     status=Experiment.STATUS_COMPLETED,
                     with_expected_values=True,
                     target_name="borges-persona"):
    target = RegisteredTarget.objects.create(
        client_hotkey=f"MAGIC_EXP_CLIENT_HOTKEY_QQ77_{slug}",
        name=f"{target_name}-{slug}",
        relay_endpoint=f"https://MAGIC_EXP_RELAY_ENDPOINT.test/{slug}/relay",
        subnet_type="llm-chat",
        categories=["content-safety"],
    )
    schema = {
        "entities": [
            {"key": "the-aleph", "display": "The Aleph"},
        ],
        "fields": [
            {"name": "year", "type": "int", "description": "year first published"},
            {"name": "author", "type": "string", "description": "author full name"},
        ],
    }
    if with_expected_values:
        schema["expected_values"] = {
            "the-aleph": {"year": "1945", "author": "Jorge Luis Borges"},
        }
    exp = Experiment.objects.create(
        slug=slug,
        title=f"{slug} test experiment",
        experiment_type=Experiment.TYPE_CONSISTENCY,
        status=status,
        target=target,
        challenge_claim="What year was The Aleph published and who wrote it?",
        consistency_check_claim="",
        runs_per_trial=5,
        field_schema=schema,
        field_schema_version=1,
        is_public=is_public,
        completed_at=djtz.now() if status == Experiment.STATUS_COMPLETED else None,
    )
    return exp, target


def _make_trial_with_claims(experiment, target, miner_uid=3,
                            year_value="1945", year_correct=True,
                            author_value="Jorge Luis Borges",
                            author_correct=True):
    """Plant one Evaluation row plus two ExtractedClaim rows.

    The Evaluation carries forbidden markers in miner_hotkey, transcript,
    audit_score, contribution. None of those should ever surface publicly.
    """
    ev = Evaluation.objects.create(
        task_id=f"task-{experiment.slug}-{miner_uid}-{year_value}",
        target=target,
        experiment=experiment,
        miner_uid=miner_uid,
        miner_hotkey="MAGIC_EXP_MINER_HOTKEY_ZZ99",
        category="content-safety",
        miner_safety_score=0.5,
        audit_score=88888.44444,       # forbidden
        accepted_severity=0.3,
        contribution=33333.22222,      # forbidden
        transcript=[
            {"role": "assistant",
             "content": "MAGIC_EXP_TRANSCRIPT_FULL_BODY — something the target said"},
        ],
        provenance_verified=True,
    )
    ExtractedClaim.objects.create(
        evaluation=ev,
        experiment=experiment,
        miner_uid=miner_uid,
        session_index=0,
        turn_index=1,
        entity_key="the-aleph",
        field_name="year",
        value_text=year_value,
        text_span=f"published in {year_value}",
        span_char_offset=10,
        field_schema_version=1,
        matches_expected=year_correct,
    )
    ExtractedClaim.objects.create(
        evaluation=ev,
        experiment=experiment,
        miner_uid=miner_uid,
        session_index=0,
        turn_index=1,
        entity_key="the-aleph",
        field_name="author",
        value_text=author_value,
        text_span=f"by {author_value}",
        span_char_offset=5,
        field_schema_version=1,
        matches_expected=author_correct,
    )
    Finding.objects.create(
        evaluation=ev,
        category="content-safety",
        severity=66666.11111,                # forbidden
        summary="MAGIC_EXP_FINDING_SUMMARY",  # forbidden
        critical=True,
    )
    return ev


class PublicExperimentListSafetyTests(TestCase):
    """List page must only surface is_public=True, status=completed
    experiments. Never emit miner attribution, transcripts, severity."""

    @classmethod
    def setUpTestData(cls):
        # Public + completed → should appear
        cls.exp_public, cls.target_public = _make_experiment(
            slug="public-exp", is_public=True,
        )
        _make_trial_with_claims(cls.exp_public, cls.target_public,
                                miner_uid=3, year_value="1945")
        _make_trial_with_claims(cls.exp_public, cls.target_public,
                                miner_uid=4, year_value="1941")

        # Private + completed → MUST NOT appear
        cls.exp_private, cls.target_private = _make_experiment(
            slug="private-exp", is_public=False,
        )
        cls.target_private.name = "private-target"
        cls.target_private.save()

        # Public but running → MUST NOT appear (only completed experiments)
        cls.exp_running, cls.target_running = _make_experiment(
            slug="running-exp", is_public=True,
            status=Experiment.STATUS_RUNNING,
        )
        cls.target_running.name = "running-target"
        cls.target_running.save()

    def _assert_no_forbidden_markers(self, body: str, context: str):
        for marker in FORBIDDEN_MARKERS:
            if marker in body:
                self.fail(
                    f"Forbidden marker {marker!r} leaked into {context}. "
                    f"public/queries.py is reading a field it shouldn't "
                    f"or the template is rendering an operator-only field."
                )

    def test_list_shows_only_public_completed(self):
        response = Client().get("/experiments/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("public-exp test experiment", body)
        self.assertNotIn("private-exp test experiment", body)
        self.assertNotIn("running-exp test experiment", body)

    def test_list_omits_forbidden_markers(self):
        response = Client().get("/experiments/")
        body = response.content.decode("utf-8")
        self._assert_no_forbidden_markers(body, "/experiments/")

    def test_list_shows_inconsistency_count(self):
        """Two trials recorded year=1945 and year=1941 — the cell is
        inconsistent (2 distinct values). Author is consistent. Count=1."""
        response = Client().get("/experiments/")
        body = response.content.decode("utf-8")
        # The inconsistency count is rendered in the catalog-entry-version
        # badge. Exact copy is "1 inconsistency".
        self.assertIn("1 inconsistency", body)

    def test_list_hides_completed_experiments_with_zero_claims(self):
        """A 'completed' is_public experiment with NO ExtractedClaim rows
        is meaningless — the consistency grid would render as 'Consistent'
        by default with no data. Hide such rows entirely from the public
        listing AND the detail view (404). See public/queries.py."""
        # Create a completed+public experiment with no trials/claims.
        empty_exp, _ = _make_experiment(
            slug="empty-public-exp",
            is_public=True,
            status=Experiment.STATUS_COMPLETED,
        )
        # No Evaluation, no ExtractedClaim — empty completed.

        # Listing must not include it
        response = Client().get("/experiments/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertNotIn("empty-public-exp", body)
        self.assertNotIn(empty_exp.title, body)

        # Detail must 404
        response = Client().get(f"/experiments/{empty_exp.slug}/")
        self.assertEqual(response.status_code, 404)


class PublicExperimentDetailSafetyTests(TestCase):
    """Detail page renders the consistency grid. Must never emit
    transcripts, miner_uid, miner_hotkey, audit_score, severity, etc."""

    @classmethod
    def setUpTestData(cls):
        cls.exp, cls.target = _make_experiment(
            slug="detail-safe", is_public=True,
        )
        # Two trials agreeing on both fields → 100% consistency.
        _make_trial_with_claims(cls.exp, cls.target, miner_uid=5,
                                year_value="1945", year_correct=True)
        _make_trial_with_claims(cls.exp, cls.target, miner_uid=6,
                                year_value="1945", year_correct=True)
        # Third trial disagrees on year → modal still 1945 (2/3 = 66%).
        _make_trial_with_claims(cls.exp, cls.target, miner_uid=7,
                                year_value="1941", year_correct=False)

        # Non-public experiment — detail must 404.
        cls.exp_private, _ = _make_experiment(
            slug="detail-private", is_public=False,
        )

    def _assert_no_forbidden_markers(self, body: str, context: str):
        for marker in FORBIDDEN_MARKERS:
            if marker in body:
                self.fail(f"Forbidden marker {marker!r} leaked into {context}.")

    def test_detail_omits_all_forbidden_fields(self):
        response = Client().get(f"/experiments/{self.exp.slug}/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self._assert_no_forbidden_markers(body, f"/experiments/{self.exp.slug}/")

    def test_detail_renders_modal_and_consistency(self):
        response = Client().get(f"/experiments/{self.exp.slug}/")
        body = response.content.decode("utf-8")
        # Modal year is 1945 (2 of 3 trials)
        self.assertIn("1945", body)
        # Consistency rate renders as "67%" (2/3 ≈ 0.667 → floatformat:0 = 67)
        # in a chip styled by .rate-mid (50-79%).
        self.assertIn("rate-mid", body)
        self.assertIn("67%", body)
        # Trial count denominator is shown as n_modal/n_total (compact form
        # since the grid cells are tight).
        self.assertIn("2/3", body)

    def test_detail_renders_accuracy_when_expected_set(self):
        response = Client().get(f"/experiments/{self.exp.slug}/")
        body = response.content.decode("utf-8")
        # Two correct out of three rated → 67% acc (compact label)
        self.assertIn("67% acc", body)

    def test_detail_omits_accuracy_when_no_expected(self):
        """When schema has no expected_values for a field, the detail
        must not show accuracy (avoids the illusion that the modal IS
        the canonical answer)."""
        exp_no_expected, target = _make_experiment(
            slug="no-expected", is_public=True,
            with_expected_values=False,
        )
        _make_trial_with_claims(exp_no_expected, target, miner_uid=9,
                                year_value="1945", year_correct=False)
        response = Client().get(f"/experiments/{exp_no_expected.slug}/")
        body = response.content.decode("utf-8")
        self.assertNotIn("accurate", body)

    def test_detail_404s_on_private(self):
        response = Client().get(f"/experiments/{self.exp_private.slug}/")
        self.assertEqual(response.status_code, 404)

    def test_detail_404s_on_nonexistent(self):
        response = Client().get("/experiments/not-a-real-slug/")
        self.assertEqual(response.status_code, 404)

    def test_detail_shows_target_name(self):
        response = Client().get(f"/experiments/{self.exp.slug}/")
        body = response.content.decode("utf-8")
        self.assertIn("borges-persona", body)

    def test_detail_shows_representative_span(self):
        """The modal value's representative text_span is a short quote,
        not a full transcript. Should render."""
        response = Client().get(f"/experiments/{self.exp.slug}/")
        body = response.content.decode("utf-8")
        self.assertIn("published in 1945", body)


class PublicExperimentEmptyStateTests(TestCase):
    """Clean DB + no published experiments should render a polite empty
    state, not 500."""

    def test_list_empty(self):
        response = Client().get("/experiments/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("No published experiments yet", body)


class PublicExperimentToggleTests(TestCase):
    """Operator-side toggle: completed → public one-click, non-completed
    refused. Anon + non-staff rejected."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import User
        cls.staff = User.objects.create_user(
            username="exp_toggle_staff", password="pw12345", is_staff=True,
        )
        cls.nonstaff = User.objects.create_user(
            username="exp_toggle_nobody", password="pw12345", is_staff=False,
        )
        cls.exp_done, _ = _make_experiment(
            slug="toggle-done", is_public=False,
            status=Experiment.STATUS_COMPLETED,
        )
        cls.exp_draft, _ = _make_experiment(
            slug="toggle-draft", is_public=False,
            status=Experiment.STATUS_DRAFT,
        )

    def test_anon_toggle_redirects_to_login(self):
        response = Client().post(f"/operator/experiments/{self.exp_done.slug}/visibility/")
        # Anon hitting a staff_required POST redirects to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_nonstaff_toggle_is_forbidden(self):
        """Non-staff authenticated users get 403 from @staff_required."""
        client = Client()
        client.force_login(self.nonstaff)
        response = client.post(f"/operator/experiments/{self.exp_done.slug}/visibility/")
        self.assertEqual(response.status_code, 403)

    def test_staff_toggle_flips_public(self):
        client = Client()
        client.force_login(self.staff)
        response = client.post(f"/operator/experiments/{self.exp_done.slug}/visibility/")
        self.assertEqual(response.status_code, 302)
        self.exp_done.refresh_from_db()
        self.assertTrue(self.exp_done.is_public)
        # Second click flips back to private
        client.post(f"/operator/experiments/{self.exp_done.slug}/visibility/")
        self.exp_done.refresh_from_db()
        self.assertFalse(self.exp_done.is_public)

    def test_staff_cannot_publish_draft(self):
        client = Client()
        client.force_login(self.staff)
        response = client.post(f"/operator/experiments/{self.exp_draft.slug}/visibility/")
        self.assertEqual(response.status_code, 400)
        self.exp_draft.refresh_from_db()
        self.assertFalse(self.exp_draft.is_public)

    def test_toggle_honors_safe_next_redirect(self):
        """Toggling from the list page returns to the list, not detail."""
        client = Client()
        client.force_login(self.staff)
        response = client.post(
            f"/operator/experiments/{self.exp_done.slug}/visibility/",
            {"next": "/operator/experiments/?status=completed"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/operator/experiments/?status=completed")

    def test_toggle_rejects_offsite_next_redirect(self):
        """Open-redirect protection: unsafe next values fall back to detail."""
        client = Client()
        client.force_login(self.staff)
        response = client.post(
            f"/operator/experiments/{self.exp_done.slug}/visibility/",
            {"next": "https://evil.example.com/phish"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/operator/experiments/{self.exp_done.slug}/", response["Location"])
        self.assertNotIn("evil.example.com", response["Location"])


class ExperimentResetTests(TestCase):
    """Reset-to-draft endpoint for stuck/failed experiments."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import User
        cls.staff = User.objects.create_user(
            username="reset_staff", password="pw12345", is_staff=True,
        )
        cls.exp_running, _ = _make_experiment(
            slug="reset-running", status=Experiment.STATUS_RUNNING,
        )
        cls.exp_running.started_at = djtz.now()
        cls.exp_running.save()
        cls.exp_failed, _ = _make_experiment(
            slug="reset-failed", status=Experiment.STATUS_FAILED,
        )
        cls.exp_completed, _ = _make_experiment(
            slug="reset-completed", status=Experiment.STATUS_COMPLETED,
        )

    def test_anon_reset_redirects_to_login(self):
        response = Client().post(f"/operator/experiments/{self.exp_running.slug}/reset/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_staff_reset_running_to_draft(self):
        client = Client()
        client.force_login(self.staff)
        response = client.post(f"/operator/experiments/{self.exp_running.slug}/reset/")
        self.assertEqual(response.status_code, 302)
        self.exp_running.refresh_from_db()
        self.assertEqual(self.exp_running.status, Experiment.STATUS_DRAFT)
        self.assertIsNone(self.exp_running.started_at)
        self.assertIsNone(self.exp_running.completed_at)

    def test_staff_reset_failed_to_draft(self):
        client = Client()
        client.force_login(self.staff)
        response = client.post(f"/operator/experiments/{self.exp_failed.slug}/reset/")
        self.assertEqual(response.status_code, 302)
        self.exp_failed.refresh_from_db()
        self.assertEqual(self.exp_failed.status, Experiment.STATUS_DRAFT)

    def test_staff_cannot_reset_completed(self):
        """Completed experiments are deliberate end states, not zombies."""
        client = Client()
        client.force_login(self.staff)
        response = client.post(f"/operator/experiments/{self.exp_completed.slug}/reset/")
        self.assertEqual(response.status_code, 400)
        self.exp_completed.refresh_from_db()
        self.assertEqual(self.exp_completed.status, Experiment.STATUS_COMPLETED)

    def test_reset_honors_safe_next(self):
        client = Client()
        client.force_login(self.staff)
        response = client.post(
            f"/operator/experiments/{self.exp_running.slug}/reset/",
            {"next": "/operator/experiments/?status=draft"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/operator/experiments/?status=draft")


class ExperimentTimelineTests(TestCase):
    """Read-only timeline view over DB state, no raw logs."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import User
        cls.staff = User.objects.create_user(
            username="timeline_staff", password="pw12345", is_staff=True,
        )
        cls.exp, _ = _make_experiment(
            slug="timeline-exp", status=Experiment.STATUS_COMPLETED,
        )

    def test_anon_timeline_redirects_to_login(self):
        response = Client().get(f"/operator/experiments/{self.exp.slug}/timeline/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_staff_timeline_renders(self):
        client = Client()
        client.force_login(self.staff)
        response = client.get(f"/operator/experiments/{self.exp.slug}/timeline/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Timeline", response.content)
        self.assertIn(b"Created", response.content)


# Markers planted in forbidden fields across RegisteredTarget / Evaluation /
# Finding rows that the public targets page aggregates. None should ever
# appear in the rendered /targets/ HTML.
TARGETS_FORBIDDEN_MARKERS = [
    "MAGIC_TGT_MINER_HOTKEY",          # Evaluation.miner_hotkey
    "MAGIC_TGT_TRANSCRIPT_BLOB",       # Evaluation.transcript
    "MAGIC_TGT_CLIENT_HOTKEY",         # RegisteredTarget.client_hotkey
    "MAGIC_TGT_RELAY_ENDPOINT",        # RegisteredTarget.relay_endpoint
    "MAGIC_TGT_FINDING_SUMMARY",       # Finding.summary
    "88888.77777",                     # Evaluation.audit_score
    "66666.22222",                     # Finding.severity
    "44444.33333",                     # Evaluation.contribution
]


class PublicTargetsHeatmapSafetyTests(TestCase):
    """Concern × target heatmap aggregates probe / finding counts only.
    Never emit miner attribution, severity, transcripts, audit_score,
    matched_cues, client hotkey, or relay endpoint."""

    @classmethod
    def setUpTestData(cls):
        from validator.models import Concern
        # Two targets, one concern, evaluations + findings planted with
        # forbidden markers that should never leak into /targets/.
        cls.t1 = RegisteredTarget.objects.create(
            client_hotkey="MAGIC_TGT_CLIENT_HOTKEY_T1",
            name="target-alpha",
            relay_endpoint="https://MAGIC_TGT_RELAY_ENDPOINT_T1.test/relay",
            subnet_type="llm-chat",
            categories=["content-safety"],
        )
        cls.t2 = RegisteredTarget.objects.create(
            client_hotkey="MAGIC_TGT_CLIENT_HOTKEY_T2",
            name="target-beta",
            relay_endpoint="https://MAGIC_TGT_RELAY_ENDPOINT_T2.test/relay",
            subnet_type="llm-chat",
            categories=["content-safety"],
        )

        cls.concern = Concern.objects.create(
            id_slug="heatmap-concern-a",
            title="Heatmap concern A",
            concern_text="A visible concern text.",
            category="content-safety",
            active=True,
        )

        counter = {"i": 0}
        def _plant(target, concern_slug, has_finding):
            counter["i"] += 1
            ev = Evaluation.objects.create(
                task_id=f"task-{target.name}-{concern_slug}-{counter['i']}",
                target=target,
                miner_uid=42,
                miner_hotkey="MAGIC_TGT_MINER_HOTKEY",
                category="content-safety",
                concern_id_slug=concern_slug,
                miner_safety_score=0.8,
                audit_score=88888.77777,
                accepted_severity=0.7,
                contribution=44444.33333,
                transcript=[{"role": "assistant",
                             "content": "MAGIC_TGT_TRANSCRIPT_BLOB leak"}],
                provenance_verified=True,
            )
            if has_finding:
                Finding.objects.create(
                    evaluation=ev,
                    category="content-safety",
                    severity=66666.22222,
                    summary="MAGIC_TGT_FINDING_SUMMARY",
                    critical=True,
                )

        # target-alpha: 2 probes, 1 finding → 50%
        _plant(cls.t1, "heatmap-concern-a", has_finding=True)
        _plant(cls.t1, "heatmap-concern-a", has_finding=False)
        # target-beta: 2 probes, 0 findings → 0%
        _plant(cls.t2, "heatmap-concern-a", has_finding=False)
        _plant(cls.t2, "heatmap-concern-a", has_finding=False)

    def test_targets_page_omits_all_forbidden_markers(self):
        response = Client().get("/targets/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        for marker in TARGETS_FORBIDDEN_MARKERS:
            self.assertNotIn(
                marker, body,
                f"Forbidden marker {marker!r} leaked into /targets/. "
                f"public/queries.py is reading a field it shouldn't.",
            )

    def test_targets_page_shows_target_names(self):
        response = Client().get("/targets/")
        body = response.content.decode("utf-8")
        self.assertIn("target-alpha", body)
        self.assertIn("target-beta", body)

    def test_targets_page_shows_concern_title_in_heatmap(self):
        response = Client().get("/targets/")
        body = response.content.decode("utf-8")
        self.assertIn("Heatmap concern A", body)

    def test_targets_page_computes_finding_rate(self):
        """target-alpha: 2 verified probes × 1 finding = 50% for
        concern-a. target-beta: 2 probes × 0 findings = 0%. The cell
        for target-alpha should render '50%' and target-beta '0%'."""
        response = Client().get("/targets/")
        body = response.content.decode("utf-8")
        self.assertIn("50%", body)
        # target-beta cell value
        self.assertIn("0%", body)

    def test_targets_page_hides_inactive_concern_rows(self):
        """Retired concerns should not appear in the heatmap."""
        from validator.models import Concern
        # Retire heatmap-concern-a
        self.concern.active = False
        self.concern.save()
        response = Client().get("/targets/")
        body = response.content.decode("utf-8")
        self.assertNotIn("Heatmap concern A", body)

    def test_targets_empty_state(self):
        """Clean DB → polite empty-state, not 500."""
        from validator.models import Concern
        Evaluation.objects.all().delete()
        Finding.objects.all().delete()
        RegisteredTarget.objects.all().delete()
        Concern.objects.all().delete()
        response = Client().get("/targets/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("No registered targets yet", body)
