"""
Views for both audiences:

  Customer portal (Epistula-authed):  /register, /evaluate, /status, /registry
  Operator UI (read-only HTML):        /, /targets/<name>
  Health:                              /healthz
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Avg, Count, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone as djtz
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .epistula import verify_epistula
from .models import Evaluation, RegisteredTarget, ValidatorStatus

logger = logging.getLogger("vali.views")

DEFAULT_SCENARIO_CATEGORIES = [
    "self-harm", "illegal-activity", "fraud",
    "harassment", "pii-generation", "unauthorized-access",
]


# --- Auth ---------------------------------------------------------------

class EpistulaAuthError(Exception):
    pass


def _verify(request: HttpRequest) -> str:
    """Verify Epistula headers; return caller hotkey or raise EpistulaAuthError."""
    try:
        return verify_epistula(
            timestamp=request.headers["X-Epistula-Timestamp"],
            signature=request.headers["X-Epistula-Signature"],
            hotkey=request.headers["X-Epistula-Hotkey"],
            body=request.body,
        )
    except KeyError as e:
        raise EpistulaAuthError(f"Missing header: {e}")
    except ValueError as e:
        raise EpistulaAuthError(str(e))


def _epistula_required(view):
    def wrapped(request, *args, **kwargs):
        try:
            request.caller_hotkey = _verify(request)
        except EpistulaAuthError as e:
            return JsonResponse({"error": str(e)}, status=401)
        return view(request, *args, **kwargs)
    return wrapped


# --- Customer portal ----------------------------------------------------

@csrf_exempt
@require_http_methods(["POST", "DELETE"])
@_epistula_required
def register(request: HttpRequest) -> JsonResponse:
    caller = request.caller_hotkey

    if request.method == "DELETE":
        deleted, _ = RegisteredTarget.objects.filter(client_hotkey=caller).delete()
        if not deleted:
            return JsonResponse({"error": "not registered"}, status=404)
        return JsonResponse({"status": "deregistered"})

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)

    relay_endpoint = body.get("relay_endpoint", "")
    if not relay_endpoint:
        return JsonResponse({"error": "missing relay_endpoint"}, status=400)

    name = body.get("name") or f"client-{caller[:8]}"
    target, _ = RegisteredTarget.objects.update_or_create(
        client_hotkey=caller,
        defaults={
            "name": name,
            "relay_endpoint": relay_endpoint,
            "subnet_type": body.get("subnet_type", "llm-chat"),
            "categories": body.get("categories") or DEFAULT_SCENARIO_CATEGORIES,
        },
    )
    logger.info(f"Registered target {name} ({caller[:8]}…) → {relay_endpoint}")
    return JsonResponse(
        {"status": "registered", "client_hotkey": caller, "name": target.name}
    )


@csrf_exempt
@require_http_methods(["POST"])
@_epistula_required
def evaluate(request: HttpRequest) -> JsonResponse:
    """Async-query: returns aggregated safety stats from accumulated state.

    Does NOT dispatch a synchronous probe. The background loop is the only
    thing that talks to miners; this endpoint is a read window over what
    the loop has already accumulated in the DB.
    """
    caller = request.caller_hotkey
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)

    target_name = body.get("target", "")
    target: RegisteredTarget | None = None
    if target_name:
        target = RegisteredTarget.objects.filter(name=target_name).first()
    elif body.get("target_validator_endpoint"):
        target = RegisteredTarget.objects.filter(
            relay_endpoint=body["target_validator_endpoint"]
        ).first()
    else:
        target = RegisteredTarget.objects.filter(client_hotkey=caller).first()

    if target is None:
        return JsonResponse(
            {"error": "could not resolve target — register first"}, status=400
        )

    # Only aggregate Evaluation rows that have been through the audit
    # pipeline (sub-phase 2.4). In-progress rows — persisted by dispatch
    # but not yet audited — have audit_score=NULL and accepted_severity=0
    # (model default), which would drag avg_severity to 0 and report a
    # bogus safety_score=1.0 whenever the audit worker is behind. The
    # correct semantics are: if we have not yet audited ANY rows for this
    # target, fall back (n=0, fallback=True) rather than lie with a
    # "perfect safety" placeholder.
    qs = Evaluation.objects.filter(
        target=target,
        audit_score__isnull=False,
    )
    category = body.get("category", "")
    if category:
        qs = qs.filter(category=category)

    agg = qs.aggregate(
        n=Count("id"),
        avg_severity=Avg("accepted_severity"),
        total_contribution=Sum("contribution"),
    )
    n = agg["n"] or 0
    avg_sev = agg["avg_severity"] or 0.0
    safety_score = max(0.0, 1.0 - avg_sev)

    fallback = n == 0
    target.evaluations_completed += 1
    target.last_evaluation = {
        "timestamp": djtz.now().timestamp(),
        "target": target.name,
        "safety_score": safety_score,
    }
    target.save(update_fields=["evaluations_completed", "last_evaluation"])

    return JsonResponse({
        "safety_score": safety_score,
        "based_on_evaluations": n,
        "n_findings": qs.filter(accepted_severity__gt=0).count(),
        "total_accepted_severity": float(agg["total_contribution"] or 0.0),
        "category": category or None,
        "fallback": fallback,
    })


def status(request: HttpRequest, client_hotkey: str) -> JsonResponse:
    target = RegisteredTarget.objects.filter(client_hotkey=client_hotkey).first()
    if not target:
        return JsonResponse({"error": "not registered"}, status=404)
    return JsonResponse({
        "registered": True,
        "name": target.name,
        "relay_endpoint": target.relay_endpoint,
        "evaluations_completed": target.evaluations_completed,
        "last_evaluation": target.last_evaluation,
        "registered_at": target.registered_at.isoformat(),
    })


def registry(request: HttpRequest) -> JsonResponse:
    targets = RegisteredTarget.objects.all()
    return JsonResponse({
        "count": targets.count(),
        "targets": [
            {
                "client_hotkey": t.client_hotkey[:12] + "…",
                "name": t.name,
                "relay_endpoint": t.relay_endpoint,
                "evaluations_completed": t.evaluations_completed,
            }
            for t in targets
        ],
    })


# --- Operator UI --------------------------------------------------------

def operator_dashboard(request: HttpRequest) -> HttpResponse:
    vstatus = ValidatorStatus.get()
    targets = RegisteredTarget.objects.annotate(
        n_evals=Count("evaluations"),
    ).order_by("-registered_at")

    now = djtz.now()
    weight_age = None
    if vstatus.last_set_weights_at:
        weight_age = (now - vstatus.last_set_weights_at).total_seconds()
    tick_age = None
    if vstatus.last_tick_at:
        tick_age = (now - vstatus.last_tick_at).total_seconds()

    return render(request, "validator/operator_dashboard.html", {
        "vstatus": vstatus,
        "targets": targets,
        "weight_age": weight_age,
        "tick_age": tick_age,
        "settings": {
            "wallet": settings.VALIDATOR_WALLET,
            "hotkey": settings.VALIDATOR_HOTKEY,
            "network": settings.SUBTENSOR_NETWORK,
            "netuid": settings.NETUID,
        },
    })


def target_detail(request: HttpRequest, name: str) -> HttpResponse:
    target = get_object_or_404(RegisteredTarget, name=name)
    evals = target.evaluations.order_by("-timestamp")[:50]
    return render(request, "validator/target_detail.html", {
        "target": target,
        "evaluations": evals,
    })


# --- Health -------------------------------------------------------------

def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness probe. 503 if any honest check fails.

    Honest = "the loop is actually doing its job", not "the web server is up".
    """
    vstatus = ValidatorStatus.get()
    now = djtz.now()
    problems: list[str] = []

    if not vstatus.wallet_loaded:
        problems.append("wallet not loaded")

    if vstatus.last_tick_at is None:
        problems.append("loop has not ticked yet")
    else:
        tick_age = (now - vstatus.last_tick_at).total_seconds()
        if tick_age > settings.HEALTH_MAX_TICK_AGE_S:
            problems.append(f"loop tick stale ({tick_age:.0f}s)")

    if vstatus.last_set_weights_at is not None:
        weight_age = (now - vstatus.last_set_weights_at).total_seconds()
        if weight_age > settings.HEALTH_MAX_WEIGHT_AGE_S:
            problems.append(f"set_weights stale ({weight_age:.0f}s)")
    # Note: when last_set_weights_at is None we do NOT fail — the loop may
    # legitimately be in the warmup window before the first weight-set. The
    # tick-staleness check above is the early-warning indicator.

    if problems:
        return JsonResponse(
            {"status": "unhealthy", "problems": problems},
            status=503,
        )
    return JsonResponse({"status": "ok", "iteration": vstatus.loop_iteration})
