from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    # Public (anon) routes: /, /activity/, /activity/feed.json. Must resolve
    # before validator.urls so the landing page is reachable without login.
    path("", include("public.urls")),
    # Validator (operator + customer + Epistula API + /app/ dispatcher)
    path("", include("validator.urls")),
]
