"""Anon-visible views for the Safeguard public site.

All GET, no auth, no CSRF dependency. Data reads go through
public/queries.py, which enforces the public-field allowlist.
"""
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from . import queries


def landing_view(request: HttpRequest) -> HttpResponse:
    """Marketing landing page for unauthenticated visitors."""
    return render(request, "public/landing.html")


def activity_view(request: HttpRequest) -> HttpResponse:
    """Server-rendered list of recent public activity.

    Uses only public/queries.py helpers. No direct model access.
    """
    feed = queries.get_activity_feed(limit=40)
    return render(request, "public/activity.html", {"feed": feed})


def activity_feed_json(request: HttpRequest) -> JsonResponse:
    """JSON version of the activity feed for landing-page embed and
    anyone who wants to consume it programmatically.

    Emits only fields serialized by ActivityRow.to_json() — no model
    instances, no extra attributes. Cached for 60s at the CDN layer
    (set via Cache-Control header).
    """
    feed = queries.get_activity_feed(limit=20)
    payload = {"items": [row.to_json() for row in feed]}
    response = JsonResponse(payload)
    response["Cache-Control"] = "public, max-age=60"
    return response
