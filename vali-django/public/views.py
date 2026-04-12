"""Anon-visible views for the Safeguard public site.

All GET, no auth, no CSRF dependency. Data reads go through
public/queries.py, which enforces the public-field allowlist.
"""
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
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


def catalog_view(request: HttpRequest) -> HttpResponse:
    """Public read-only browse of the active concern catalog.

    Lists every active concern with whitelisted fields only (title,
    category, concern_text snippet, version, trigger count). Cues are
    NEVER surfaced — operator-only per the contract at
    validator/models.py:476-478.

    Supports ?category=<slug> to filter.
    """
    selected_category = request.GET.get("category", "").strip() or None
    concerns = queries.list_public_concerns(category=selected_category)
    categories = queries.list_public_categories()
    return render(request, "public/catalog.html", {
        "concerns": concerns,
        "categories": categories,
        "selected_category": selected_category,
    })


def catalog_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Public detail page for one active concern.

    Returns 404 for retired / inactive concerns — they do not exist
    from the public's perspective.
    """
    detail = queries.get_public_concern(slug)
    if detail is None:
        raise Http404(f"No active concern with slug {slug!r}")
    return render(request, "public/catalog_detail.html", {"concern": detail})
