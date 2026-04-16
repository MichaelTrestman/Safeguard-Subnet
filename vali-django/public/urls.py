"""URL routing for the logged-out public view.

Only GET endpoints. No auth decorators — these are the anon-visible
routes. Any view here must NEVER touch models that contain miner
attribution, transcripts, curator identity, or subnet-owner accounting.
See public/queries.py for the field allowlist.
"""
from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.landing_view, name="landing"),
    path("models/", views.catalog_view, name="catalog"),
    path("catalog/<slug:slug>/", views.catalog_detail_view, name="catalog_detail"),
    path("activity/", views.activity_view, name="activity"),
    path("activity/feed.json", views.activity_feed_json, name="activity_feed"),
    path("experiments/", views.experiments_view, name="experiments"),
    path("experiments/<slug:slug>/", views.experiment_detail_view, name="experiment_detail"),
    path("stats/", views.targets_view, name="targets"),
]
