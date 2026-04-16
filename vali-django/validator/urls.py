from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    # App dispatch (routes by user role: staff -> operator, customer -> /dashboard/).
    # Moved off of "" to "/app/" so the public landing can own the root path.
    path("app/", views.app_root, name="app_root"),

    # Operator UI (staff only)
    path("operator/", views.operator_dashboard, name="operator_dashboard"),
    path("targets/compare/", views.targets_compare, name="targets_compare"),
    path("targets/<str:name>/profile/", views.target_consistency_profile, name="target_consistency_profile"),
    path("targets/<str:name>/", views.target_detail, name="target_detail"),
    path("eval/<str:task_id>/", views.eval_detail, name="eval_detail"),
    path("runs/", views.runs_browser, name="runs_browser"),
    path("findings/", views.findings_browser, name="findings_browser"),
    path("control/probes-per-cycle", views.control_probes_per_cycle, name="control_probes_per_cycle"),

    # Customer dashboard (customer login)
    path("dashboard/", views.customer_dashboard, name="customer_dashboard"),
    path("dashboard/target/<str:name>/", views.customer_target_detail, name="customer_target_detail"),
    path("dashboard/target/<str:name>/findings/", views.customer_findings, name="customer_findings"),
    path("dashboard/target/<str:name>/concerns/new/", views.customer_concern_new, name="customer_concern_new"),
    path("dashboard/finding/<int:finding_id>/", views.customer_finding_detail, name="customer_finding_detail"),

    # Curation (staff only)
    path("curation/", views.curation_queue, name="curation_queue"),
    path("curation/finding/<int:finding_id>/", views.curation_detail, name="curation_detail"),
    path("curation/finding/<int:finding_id>/action/", views.curation_action, name="curation_action"),
    path("curation/log/", views.curation_log, name="curation_log"),
    # Sub-work A.2 — HITL queue management (operator remove only; no reorder/assign)
    path("curation/hitl/<int:case_id>/remove/", views.hitl_case_remove, name="hitl_case_remove"),

    # Concern curation (staff only) — DESIGN.md §2
    path("concerns/", views.concern_library, name="concern_library"),
    path("concerns/create/", views.concern_create, name="concern_create"),
    # DetectionCue + UserTrigger CRUD (WS2). Declared BEFORE the
    # <slug> catch-all so "cues"/"triggers" path segments don't get
    # swallowed by it.
    path("concerns/<str:concern_slug>/cues/create/", views.cue_create, name="cue_create"),
    path("concerns/cues/<int:cue_id>/edit/", views.cue_edit, name="cue_edit"),
    path("concerns/cues/<int:cue_id>/retire/", views.cue_retire, name="cue_retire"),
    path("concerns/cues/<int:cue_id>/activate/", views.cue_activate, name="cue_activate"),
    path("concerns/<str:concern_slug>/triggers/create/", views.trigger_create, name="trigger_create"),
    path("concerns/triggers/<int:trigger_id>/edit/", views.trigger_edit, name="trigger_edit"),
    path("concerns/triggers/<int:trigger_id>/retire/", views.trigger_retire, name="trigger_retire"),
    path("concerns/triggers/<int:trigger_id>/activate/", views.trigger_activate, name="trigger_activate"),
    # Behaviors (HarmBench integration). Library page + per-behavior toggles
    # + per-concern M2M associate/disassociate. Declared BEFORE the concern
    # <slug> catch-all so "behaviors" path segments route correctly.
    path("behaviors/", views.behavior_library, name="behavior_library"),
    path("behaviors/<int:pk>/", views.behavior_detail, name="behavior_detail"),
    path("behaviors/<int:behavior_id>/activate/", views.behavior_activate, name="behavior_activate"),
    path("behaviors/<int:behavior_id>/deactivate/", views.behavior_deactivate, name="behavior_deactivate"),
    path("concerns/<str:concern_slug>/behaviors/associate/", views.behavior_associate, name="behavior_associate"),
    path("concerns/<str:concern_slug>/behaviors/<int:behavior_id>/disassociate/", views.behavior_disassociate, name="behavior_disassociate"),
    path("concerns/<str:slug>/", views.concern_detail, name="concern_detail"),
    path("concerns/<str:slug>/edit/", views.concern_edit, name="concern_edit"),
    path("concerns/<str:slug>/retire/", views.concern_retire, name="concern_retire"),
    path("concerns/<str:slug>/activate/", views.concern_activate, name="concern_activate"),

    # Experiments (staff only) — DESIGN.md §10
    # Mounted under /operator/ because bare /experiments/ is the public
    # anon-visible showcase (see public/urls.py).
    path("operator/experiments/", views.experiment_list, name="experiment_list"),
    path("operator/experiments/create/", views.experiment_create, name="experiment_create"),
    path("operator/experiments/propose_schema/", views.experiment_propose_schema, name="experiment_propose_schema"),
    path("operator/experiments/<str:slug>/", views.experiment_detail, name="experiment_detail"),
    path("operator/experiments/<str:slug>/run/", views.experiment_run, name="experiment_run"),
    path("operator/experiments/<str:slug>/schema/", views.experiment_edit_schema, name="experiment_edit_schema"),
    path("operator/experiments/<str:slug>/reextract/", views.experiment_reextract, name="experiment_reextract"),
    path("operator/experiments/<str:slug>/clone/", views.experiment_clone, name="experiment_clone"),
    path("operator/experiments/compare/<str:slug_a>/vs/<str:slug_b>/", views.experiment_compare, name="experiment_compare"),
    path("operator/experiments/<str:slug>/visibility/", views.experiment_toggle_public, name="experiment_toggle_public"),
    path("operator/experiments/<str:slug>/reset/", views.experiment_reset, name="experiment_reset"),
    path("operator/experiments/<str:slug>/timeline/", views.experiment_timeline, name="experiment_timeline"),

    # Concern catalog distribution (Epistula API).
    # Mounted under /api/ so the bare /concerns URL can redirect to
    # the trailing-slash operator UI via Django's APPEND_SLASH
    # middleware — otherwise a human typing /concerns hits this
    # machine endpoint and gets an "x-epistula-timestamp missing"
    # 400 which is a terrible UX trap.
    path("api/concerns", views.concerns_catalog, name="concerns_catalog"),

    # Legacy /bait/* — 301 redirects to /concerns/* for one release.
    # Retired in a follow-up after miners and tests stop hitting /bait.
    path(
        "bait/",
        RedirectView.as_view(pattern_name="concern_library", permanent=True),
    ),
    path(
        "bait/create/",
        RedirectView.as_view(pattern_name="concern_create", permanent=True),
    ),
    path(
        "bait/<str:slug>/",
        RedirectView.as_view(pattern_name="concern_detail", permanent=True),
    ),
    path(
        "bait/<str:slug>/edit/",
        RedirectView.as_view(pattern_name="concern_edit", permanent=True),
    ),

    # Health
    path("healthz", views.healthz, name="healthz"),

    # Customer portal (Epistula API)
    path("register", views.register, name="register"),
    path("evaluate", views.evaluate, name="evaluate"),
    path("status/<str:client_hotkey>", views.status, name="status"),
    path("registry", views.registry, name="registry"),

    # Provenance v2 — miner-side relay (sub-phase 2.9)
    path("probe/relay", views.probe_relay, name="probe_relay"),
]
