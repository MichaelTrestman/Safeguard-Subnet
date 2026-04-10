from django.urls import path

from . import views

urlpatterns = [
    # Root dispatch (routes by user role: staff -> operator, customer -> /dashboard/)
    path("", views.root_dispatch, name="root"),

    # Operator UI (staff only)
    path("operator/", views.operator_dashboard, name="operator_dashboard"),
    path("targets/<str:name>/", views.target_detail, name="target_detail"),

    # Customer dashboard (customer login)
    path("dashboard/", views.customer_dashboard, name="customer_dashboard"),
    path("dashboard/target/<str:name>/", views.customer_target_detail, name="customer_target_detail"),
    path("dashboard/target/<str:name>/findings/", views.customer_findings, name="customer_findings"),
    path("dashboard/finding/<int:finding_id>/", views.customer_finding_detail, name="customer_finding_detail"),

    # Curation (staff only)
    path("curation/", views.curation_queue, name="curation_queue"),
    path("curation/finding/<int:finding_id>/", views.curation_detail, name="curation_detail"),
    path("curation/finding/<int:finding_id>/action/", views.curation_action, name="curation_action"),
    path("curation/log/", views.curation_log, name="curation_log"),

    # Bait management (staff only)
    path("bait/", views.bait_library, name="bait_library"),
    path("bait/create/", views.bait_create, name="bait_create"),
    path("bait/<str:slug>/", views.bait_detail, name="bait_detail"),
    path("bait/<str:slug>/edit/", views.bait_edit, name="bait_edit"),

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
