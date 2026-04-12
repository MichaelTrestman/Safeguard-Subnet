from django.contrib.auth import views as auth_views
from django.urls import path, include

from validator.views import logout_view

urlpatterns = [
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    # Custom logout_view replaces auth_views.LogoutView because the latter
    # hard-applies @csrf_protect and vali-django has no CsrfViewMiddleware
    # (settings.py lean-by-design). See validator/views.py:logout_view.
    path("accounts/logout/", logout_view, name="logout"),
    # Public (anon) routes: /, /activity/, /activity/feed.json. Must resolve
    # before validator.urls so the landing page is reachable without login.
    path("", include("public.urls")),
    # Validator (operator + customer + Epistula API + /app/ dispatcher)
    path("", include("validator.urls")),
]
