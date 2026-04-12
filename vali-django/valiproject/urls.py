from django.urls import path, include

from validator.views import login_view, logout_view

urlpatterns = [
    # Custom login_view replaces auth_views.LoginView because the latter
    # hard-applies @csrf_protect and vali-django has no CsrfViewMiddleware.
    path("accounts/login/", login_view, name="login"),
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
