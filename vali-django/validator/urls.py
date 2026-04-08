from django.urls import path

from . import views

urlpatterns = [
    # Operator UI
    path("", views.operator_dashboard, name="operator_dashboard"),
    path("targets/<str:name>/", views.target_detail, name="target_detail"),

    # Health
    path("healthz", views.healthz, name="healthz"),

    # Customer portal
    path("register", views.register, name="register"),
    path("evaluate", views.evaluate, name="evaluate"),
    path("status/<str:client_hotkey>", views.status, name="status"),
    path("registry", views.registry, name="registry"),
]
