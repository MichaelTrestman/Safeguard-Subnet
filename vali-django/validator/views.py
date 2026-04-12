"""
Views for three audiences:

  Customer portal (Epistula-authed):  /register, /evaluate, /status, /registry
  Miner relay (Epistula-authed):      /probe/relay (v2 provenance, sub-phase 2.9)
  Operator UI (read-only HTML):        /, /targets/<name>
  Health:                              /healthz
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Avg, Count, Max, Q, Sum
from functools import wraps

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone as djtz
from django.utils.text import slugify
from django.contrib.auth import logout as auth_logout
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

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


# --- Role-based auth decorators -----------------------------------------

from django.contrib.auth.decorators import login_required


def staff_required(view_func):
    """Login required + user.is_staff. Returns 403 for non-staff."""
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponse("Forbidden: staff only", status=403)
        return view_func(request, *args, **kwargs)
    return wrapped


def customer_required(view_func):
    """Login required + user must have a CustomerProfile.
    Attaches request.customer_profile for downstream use."""
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        from .models import CustomerProfile
        try:
            request.customer_profile = request.user.customer_profile
        except CustomerProfile.DoesNotExist:
            if request.user.is_staff:
                return redirect("operator_dashboard")
            return HttpResponse("Forbidden: not a customer account", status=403)
        return view_func(request, *args, **kwargs)
    return wrapped


# --- Customer portal (Epistula-authed API) ------------------------------

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


# --- Provenance v2 relay (sub-phase 2.9) -------------------------------
#
# RELAY_PROTOCOL_V2.md §"Endpoint spec". Wraps the existing v1 relay
# (RELAY_PROTOCOL.md) by inserting this validator into the path between
# the Safeguard miner and the client v1 /relay. Each successful
# forward gets a sha256-canonical-json-v1 commitment that the audit
# worker re-verifies at scoring time, closing attack A1 (miner
# fabrication, see THREAT_MODEL.md).
#
# This is an ASYNC view because the forward to the client v1 relay is
# the slowest part of the request and we want the asyncio event loop
# free during that wait. ORM access goes through sync_to_async to
# stay safe inside the async context.
#
# Endpoint URL is /probe/relay (not bare /relay) per locked
# open-question 1 in PLAN.md Phase 2.9 — namespacing the miner-side
# relay so a future customer-facing relay can coexist on a different
# prefix.

@csrf_exempt
@require_http_methods(["POST"])
async def probe_relay(request: HttpRequest) -> JsonResponse:
    """v2 provenance-bearing relay. Forwards to client v1 /relay,
    hashes the response, persists a RelayCommitment, returns the
    response + commitment block to the calling miner.

    Status code semantics per RELAY_PROTOCOL_V2.md §"Status codes":
      200: forward succeeded, commitment issued
      400: malformed request body
      401: Epistula verification failed
      403: caller is not a registered Safeguard probe miner
      404: target_descriptor names a client we have no
           RegisteredTarget for
      502: client v1 /relay returned non-200
      503: lifespan didn't run (RELAY_HTTPX is None)
      504: client v1 /relay timed out (httpx.ReadTimeout / ConnectTimeout)

    Errors NEVER produce a commitment. The miner cannot attribute
    anything to the target on a non-200, and audit-time verification
    relies on this invariant.
    """
    import time
    import uuid as _uuid
    from asgiref.sync import sync_to_async
    import httpx
    from valiproject import asgi as _asgi

    from .epistula import create_epistula_headers
    from .models import MinerScore, RelayCommitment, RelaySession
    from .provenance import compute_commitment

    # ----- Auth -----
    try:
        caller_hotkey = await sync_to_async(_verify)(request)
    except EpistulaAuthError as e:
        return JsonResponse({"error": str(e)}, status=401)

    # ----- Caller must be a registered probe miner on this subnet -----
    # MinerScore is populated by _upsert_discovered_miners on each
    # discovery tick, so a freshly-joined miner becomes eligible to
    # call /probe/relay within one loop interval of committing its
    # endpoint to chain.
    is_known_miner = await sync_to_async(
        lambda: MinerScore.objects.filter(hotkey=caller_hotkey).exists()
    )()
    if not is_known_miner:
        return JsonResponse(
            {"error": "caller is not a registered probe miner"},
            status=403,
        )

    # ----- Parse body -----
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)

    prompt = body.get("prompt")
    session_id_str = body.get("session_id")
    target_descriptor = body.get("target_descriptor") or {}
    if not prompt or not isinstance(prompt, str):
        return JsonResponse({"error": "missing or invalid prompt"}, status=400)
    if not session_id_str:
        return JsonResponse({"error": "missing session_id"}, status=400)
    try:
        session_uuid = _uuid.UUID(session_id_str)
    except (ValueError, TypeError):
        return JsonResponse({"error": "session_id is not a UUID"}, status=400)
    client_validator_hotkey = target_descriptor.get("client_validator_hotkey")
    if not client_validator_hotkey:
        return JsonResponse(
            {"error": "missing target_descriptor.client_validator_hotkey"},
            status=400,
        )

    # ----- Resolve target -----
    target = await sync_to_async(
        lambda: RegisteredTarget.objects.filter(
            client_hotkey=client_validator_hotkey
        ).first()
    )()
    if target is None:
        return JsonResponse(
            {"error": "no RegisteredTarget for that client_validator_hotkey"},
            status=404,
        )

    # ----- Get/create session, allocate turn_index -----
    # `get_or_create` is atomic at the DB layer for a unique field. The
    # turn_count update is racy with concurrent requests on the same
    # session_id, but a single miner is the only legitimate caller for
    # a given session_id and the audit worker will catch ordering
    # mismatches anyway. Tighten with a select_for_update if it ever
    # becomes a real problem.
    session, created = await sync_to_async(RelaySession.objects.get_or_create)(
        session_id=session_uuid,
        defaults={
            "miner_hotkey": caller_hotkey,
            "target": target,
            "turn_count": 0,
        },
    )
    if not created and session.miner_hotkey != caller_hotkey:
        # Session-stealing attempt: another miner is trying to add
        # turns to a session that doesn't belong to them.
        return JsonResponse(
            {"error": "session belongs to a different miner"},
            status=403,
        )
    turn_index = session.turn_count

    # ----- Forward to client v1 /relay -----
    if _asgi.RELAY_HTTPX is None or _asgi.WALLET is None:
        # Lifespan didn't run (e.g. running under WSGI / `manage.py
        # runserver`) — we cannot serve traffic.
        logger.error(
            "[probe_relay] lifespan state not initialized "
            "(RELAY_HTTPX or WALLET is None)"
        )
        return JsonResponse(
            {"error": "validator not ready (lifespan startup did not run)"},
            status=503,
        )

    forward_body_dict = {"prompt": prompt, "session_id": session_id_str}
    forward_body = json.dumps(forward_body_dict).encode()
    forward_headers = create_epistula_headers(_asgi.WALLET, forward_body)
    forward_headers["Content-Type"] = "application/json"

    # Forward to the client's v1 /relay endpoint. The registered
    # relay_endpoint is the base URL (e.g. http://host:port); the
    # v1 relay path is /relay per RELAY_PROTOCOL.md.
    forward_url = target.relay_endpoint.rstrip("/") + "/relay"

    try:
        upstream = await _asgi.RELAY_HTTPX.post(
            forward_url,
            content=forward_body,
            headers=forward_headers,
        )
    except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
        logger.warning(
            f"[probe_relay] forward timeout to {target.name}: "
            f"{type(e).__name__}: {e}"
        )
        return JsonResponse({"error": f"client v1 /relay timed out: {e}"}, status=504)
    except httpx.HTTPError as e:
        logger.warning(
            f"[probe_relay] forward HTTP error to {target.name}: "
            f"{type(e).__name__}: {e}"
        )
        return JsonResponse({"error": f"client v1 /relay error: {e}"}, status=502)

    if upstream.status_code != 200:
        logger.warning(
            f"[probe_relay] forward returned {upstream.status_code} from {target.name}"
        )
        return JsonResponse(
            {"error": f"client v1 /relay returned {upstream.status_code}"},
            status=502,
        )

    try:
        upstream_payload = upstream.json()
    except ValueError:
        return JsonResponse(
            {"error": "client v1 /relay returned non-JSON"},
            status=502,
        )
    response_text = upstream_payload.get("response")
    if not isinstance(response_text, str):
        return JsonResponse(
            {"error": "client v1 /relay response missing 'response' field"},
            status=502,
        )

    # ----- Compute and persist commitment -----
    committed_at_ns = time.time_ns()
    safeguard_validator_hotkey = _asgi.WALLET.hotkey.ss58_address
    preimage, digest = compute_commitment(
        session_id=session_id_str,
        turn_index=turn_index,
        prompt=prompt,
        response=response_text,
        target_descriptor={"client_validator_hotkey": client_validator_hotkey},
        committed_at=committed_at_ns,
        safeguard_validator_hotkey=safeguard_validator_hotkey,
    )

    @sync_to_async
    def _persist():
        RelayCommitment.objects.create(
            session=session,
            turn_index=turn_index,
            scheme=RelayCommitment.SCHEME_V1,
            preimage=preimage,
            digest=digest,
            committed_by=safeguard_validator_hotkey,
        )
        # Bump the session's turn counter atomically with the commitment row.
        RelaySession.objects.filter(pk=session.pk).update(
            turn_count=turn_index + 1,
        )

    await _persist()

    return JsonResponse({
        "response": response_text,
        "session_id": session_id_str,
        "response_commitment": {
            "scheme": RelayCommitment.SCHEME_V1,
            "digest": digest,
            "committed_at": committed_at_ns,
            "committed_by": safeguard_validator_hotkey,
        },
    })


# --- Auth primitives ----------------------------------------------------


@csrf_exempt
@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    """Custom logout that works without CsrfViewMiddleware.

    Django 5's auth_views.LogoutView hard-applies @csrf_protect on
    dispatch, which requires a valid CSRF cookie. vali-django has no
    CsrfViewMiddleware in the middleware stack (see settings.py lean-
    by-design comment), so LogoutView's CSRF check never succeeds and
    every sign-out attempt 403s. This view replaces it:

      - @require_POST keeps the CSRF-logout attack surface closed
        (a malicious page can't GET /accounts/logout/ to log the user
        out against their will).
      - @csrf_exempt skips the CSRF cookie check that would otherwise
        403 because the middleware doesn't run.
      - Redirect target is "/" — the public landing page, visible to
        the now-anonymous user.
    """
    auth_logout(request)
    return redirect("/")


# --- App dispatch (routes /app/ by user role) ----------------------------


@login_required
def app_root(request: HttpRequest) -> HttpResponse:
    """Route /app/ by user type: staff -> operator dashboard, customer -> /dashboard/.

    The root path / is now served by the public.views.landing_view (unauthenticated
    marketing page); /app/ is the explicit entry point for authenticated users.
    """
    if request.user.is_staff:
        return operator_dashboard(request)
    if hasattr(request.user, "customer_profile"):
        return redirect("customer_dashboard")
    return HttpResponse("No dashboard configured for this account", status=403)


# --- Operator UI (staff only) -------------------------------------------


@staff_required
def operator_dashboard(request: HttpRequest) -> HttpResponse:
    """Phase 3: full operator console for vali-django.

    Shows everything the loop has accumulated in the DB — live status
    + per-cycle history + per-miner roster + recent audit findings +
    HITL queue. All data sources are the same tables the loop writes
    to, so if the loop is alive and the dashboard shows stale values,
    it's a dashboard bug not a loop bug.
    """
    from .models import (
        CycleHistory, Evaluation, Finding, HitlCase, MinerScore,
        RelayCommitment, RelaySession,
    )

    vstatus = ValidatorStatus.get()
    targets = RegisteredTarget.objects.annotate(
        n_evals=Count("evaluations"),
        n_verified=Count("evaluations", filter=Q(evaluations__provenance_verified=True)),
    ).order_by("-registered_at")
    # Per-target finding counts (need Finding traversal)
    from .models import Finding as _Finding
    for t in targets:
        t.n_findings = _Finding.objects.filter(evaluation__target=t).count()
        t.finding_rate = (t.n_findings / t.n_verified * 100) if t.n_verified else 0

    now = djtz.now()
    weight_age = None
    if vstatus.last_set_weights_at:
        weight_age = (now - vstatus.last_set_weights_at).total_seconds()
    tick_age = None
    if vstatus.last_tick_at:
        tick_age = (now - vstatus.last_tick_at).total_seconds()

    recent_cycles = CycleHistory.objects.order_by("-id")[:20]

    # ----- Miner roster with dispatch state + per-miner eval counts -----
    miners = list(MinerScore.objects.all().order_by("uid"))
    for m in miners:
        # Per-miner eval counts from Evaluation table
        m_evals = Evaluation.objects.filter(miner_uid=m.uid, audit_score__isnull=False)
        m.eval_count = m_evals.count()
        m.finding_count = m_evals.filter(
            accepted_severity__gt=0, findings_reward__gte=0.15
        ).count()
        m.contribution_total = sum(
            e.contribution for e in m_evals.only("contribution")
        )
        m.prov_verified_count = m_evals.filter(provenance_verified=True).count()
        m.prov_failed_count = m_evals.filter(provenance_verified=False).count()
        # Dispatch state
        m.dispatch_gap = None
        if m.last_successful_dispatch_block and vstatus.current_block:
            m.dispatch_gap = vstatus.current_block - m.last_successful_dispatch_block
        m.cooldown_active = False
        m.cooldown_remaining_s = 0
        if m.last_failed_dispatch_at and hasattr(m, 'consecutive_dispatch_failures'):
            elapsed = (now - m.last_failed_dispatch_at).total_seconds()
            n = getattr(m, 'consecutive_dispatch_failures', 0) or 0
            if n > 0:
                backoff = min(5.0 * (2 ** (n - 1)), 4320)
                if elapsed < backoff:
                    m.cooldown_active = True
                    m.cooldown_remaining_s = int(backoff - elapsed)

    recent_findings = Finding.objects.select_related(
        "evaluation", "evaluation__target"
    ).prefetch_related("matched_cues").order_by("-id")[:10]

    pending_hitl = HitlCase.objects.filter(
        status=HitlCase.STATUS_PENDING
    ).select_related("evaluation", "evaluation__target").order_by("-id")[:10]

    n_evaluations_total = Evaluation.objects.count()
    n_evaluations_audited = Evaluation.objects.filter(
        audit_score__isnull=False
    ).count()
    n_findings_total = Finding.objects.count()
    n_hitl_pending = HitlCase.objects.filter(
        status=HitlCase.STATUS_PENDING
    ).count()

    # ----- Provenance stats -----
    prov_verified = Evaluation.objects.filter(provenance_verified=True).count()
    prov_failed = Evaluation.objects.filter(provenance_verified=False).count()
    prov_legacy = Evaluation.objects.filter(provenance_verified__isnull=True).count()

    # ----- Fabrication suspects -----
    fabrication_suspects = Evaluation.objects.filter(
        provenance_verified=False,
    ).select_related("target").order_by("-timestamp")[:20]

    # ----- Relay stats -----
    relay_sessions = RelaySession.objects.count()
    relay_commitments = RelayCommitment.objects.count()

    burn_share = float(vstatus.last_burn_share or 0.0)
    full_burn = burn_share >= 0.99

    return render(request, "validator/operator_dashboard.html", {
        "vstatus": vstatus,
        "targets": targets,
        "weight_age": weight_age,
        "tick_age": tick_age,
        "recent_cycles": recent_cycles,
        "miners": miners,
        "recent_findings": recent_findings,
        "pending_hitl": pending_hitl,
        "n_evaluations_total": n_evaluations_total,
        "n_evaluations_audited": n_evaluations_audited,
        "n_findings_total": n_findings_total,
        "n_hitl_pending": n_hitl_pending,
        "prov_verified": prov_verified,
        "prov_failed": prov_failed,
        "prov_legacy": prov_legacy,
        "fabrication_suspects": fabrication_suspects,
        "relay_sessions": relay_sessions,
        "relay_commitments": relay_commitments,
        "burn_share": burn_share,
        "full_burn": full_burn,
        "settings": {
            "wallet": settings.VALIDATOR_WALLET,
            "hotkey": settings.VALIDATOR_HOTKEY,
            "network": settings.SUBTENSOR_NETWORK,
            "netuid": settings.NETUID,
        },
        "nav_active": "operator",
        "probes_per_cycle": _get_probes_per_cycle(),
    })


def _get_probes_per_cycle() -> int:
    try:
        from . import loop
        return loop.PROBES_PER_MINER_PER_CYCLE
    except (ImportError, AttributeError):
        return 1


@staff_required
def target_detail(request: HttpRequest, name: str) -> HttpResponse:
    """Per-target safety dashboard. Summary stats, concern breakdown
    (which concerns does this target fail on?), and recent evaluations
    with enriched columns."""
    from .models import Evaluation, Finding, RegisteredTarget

    target = get_object_or_404(RegisteredTarget, name=name)

    stats = Evaluation.objects.filter(target=target).aggregate(
        n_evals=Count("id"),
        n_verified=Count("id", filter=Q(provenance_verified=True)),
        n_legacy=Count("id", filter=Q(provenance_verified__isnull=True)),
        avg_severity=Avg("accepted_severity", filter=Q(provenance_verified=True)),
        max_severity=Max("accepted_severity", filter=Q(provenance_verified=True)),
        avg_audit=Avg("audit_score", filter=Q(provenance_verified=True)),
    )

    findings_qs = Finding.objects.filter(evaluation__target=target)
    stats["n_findings"] = findings_qs.count()
    stats["n_critical"] = findings_qs.filter(critical=True).count()
    stats["finding_rate"] = (
        stats["n_findings"] / stats["n_verified"] * 100
        if stats["n_verified"] else 0
    )

    # Per-concern breakdown — "where does this target fail?"
    concern_breakdown = list(
        Evaluation.objects.filter(target=target, provenance_verified=True)
        .exclude(concern_id_slug="")
        .values("concern_id_slug")
        .annotate(
            n_probes=Count("id"),
            avg_sev=Avg("accepted_severity"),
            max_sev=Max("accepted_severity"),
        )
        .order_by("-avg_sev")
    )
    concern_slugs = [c["concern_id_slug"] for c in concern_breakdown]
    finding_counts = dict(
        findings_qs
        .filter(evaluation__concern_id_slug__in=concern_slugs)
        .values("evaluation__concern_id_slug")
        .annotate(n=Count("id"))
        .values_list("evaluation__concern_id_slug", "n")
    )
    for c in concern_breakdown:
        slug = c["concern_id_slug"]
        c["n_findings"] = finding_counts.get(slug, 0)
        c["finding_rate"] = (
            c["n_findings"] / c["n_probes"] * 100 if c["n_probes"] else 0
        )

    evals = (
        target.evaluations
        .select_related("trigger")
        .prefetch_related("findings")
        .order_by("-timestamp")[:50]
    )

    return render(request, "validator/target_detail.html", {
        "target": target,
        "stats": stats,
        "concern_breakdown": concern_breakdown,
        "evaluations": evals,
        "nav_active": "targets",
    })


@staff_required
def targets_compare(request: HttpRequest) -> HttpResponse:
    """Side-by-side comparison of all registered targets. Each target
    becomes a column; rows are aggregated metrics (finding rate, avg
    severity, top concerns, provenance stats). Designed for the
    multi-persona experiment: same concern catalog, different target
    personas, compare the safety-metric deltas."""
    from .models import Evaluation, Finding, RegisteredTarget

    targets = list(
        RegisteredTarget.objects.annotate(
            n_evals=Count("evaluations"),
            n_verified=Count(
                "evaluations",
                filter=Q(evaluations__provenance_verified=True),
            ),
            n_legacy=Count(
                "evaluations",
                filter=Q(evaluations__provenance_verified__isnull=True),
            ),
            avg_severity=Avg(
                "evaluations__accepted_severity",
                filter=Q(evaluations__provenance_verified=True),
            ),
            max_severity=Max(
                "evaluations__accepted_severity",
                filter=Q(evaluations__provenance_verified=True),
            ),
            avg_audit=Avg(
                "evaluations__audit_score",
                filter=Q(evaluations__provenance_verified=True),
            ),
        ).order_by("name")
    )

    for t in targets:
        findings_qs = Finding.objects.filter(evaluation__target=t)
        t.n_findings = findings_qs.count()
        t.n_critical = findings_qs.filter(critical=True).count()
        t.finding_rate = (
            t.n_findings / t.n_verified * 100 if t.n_verified else 0
        )
        with_cues = (
            findings_qs.filter(matched_cues__isnull=False).distinct().count()
        )
        t.cue_match_rate = (
            with_cues / t.n_findings * 100 if t.n_findings else 0
        )
        t.top_concerns = list(
            findings_qs
            .exclude(evaluation__concern_id_slug="")
            .values("evaluation__concern_id_slug")
            .annotate(n=Count("id"))
            .order_by("-n")[:5]
        )

    # Concern×target heatmap: finding rate per (concern, target) pair.
    all_concern_slugs = sorted(set(
        Finding.objects.filter(evaluation__target__in=targets)
        .exclude(evaluation__concern_id_slug="")
        .values_list("evaluation__concern_id_slug", flat=True)
        .distinct()
    ))
    heatmap = []
    for slug in all_concern_slugs:
        row = {"concern": slug, "cells": []}
        for t in targets:
            n_probes = Evaluation.objects.filter(
                target=t, concern_id_slug=slug, provenance_verified=True,
            ).count()
            n_findings = Finding.objects.filter(
                evaluation__target=t, evaluation__concern_id_slug=slug,
            ).count()
            rate = (n_findings / n_probes * 100) if n_probes else None
            row["cells"].append({"rate": rate, "n": n_probes, "findings": n_findings})
        heatmap.append(row)

    return render(request, "validator/targets_compare.html", {
        "targets": targets,
        "heatmap": heatmap,
        "nav_active": "targets",
    })


# --- Operator controls --------------------------------------------------


@staff_required
@csrf_exempt
@require_http_methods(["POST"])
def control_probes_per_cycle(request: HttpRequest) -> JsonResponse:
    """Update PROBES_PER_MINER_PER_CYCLE at runtime without restarting.
    Immediately affects the next dispatch tick."""
    from . import loop as _loop
    import json as _json
    body = _json.loads(request.body or b"{}")
    new_val = int(body.get("value", 1))
    if new_val < 1:
        return JsonResponse({"error": "value must be >= 1"}, status=400)
    _loop.PROBES_PER_MINER_PER_CYCLE = new_val
    return JsonResponse({"status": "ok", "probes_per_miner_per_cycle": new_val})


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


# --- Operator evaluation detail -----------------------------------------


@staff_required
def eval_detail(request: HttpRequest, task_id: str) -> HttpResponse:
    """Universal evaluation inspector. Shows transcript + both scores +
    findings + HITL status + provenance for ANY evaluation, whether it
    has a finding, a HITL case, a fabrication flag, or nothing."""
    from .models import Concern, Evaluation, Finding, HitlCase
    eval_row = get_object_or_404(
        Evaluation.objects.select_related("target"),
        task_id=task_id,
    )
    findings = Finding.objects.filter(
        evaluation=eval_row
    ).prefetch_related("matched_cues__concern")
    try:
        hitl = eval_row.hitl
    except HitlCase.DoesNotExist:
        hitl = None
    # Compute delta in Python — Django templates can't do float subtraction.
    delta = None
    if eval_row.audit_score is not None:
        delta = eval_row.miner_safety_score - eval_row.audit_score

    # Concerns v2 — resolve the concern this probe was generated against,
    # if the miner reported one. Empty slug = v1 miner or empty-catalog
    # fallback; render a fallback string in the template.
    concern = None
    if eval_row.concern_id_slug:
        concern = Concern.objects.filter(id_slug=eval_row.concern_id_slug).first()

    # Flatten matched cues across all findings for the concern-context
    # card. A single evaluation can have multiple findings, each with
    # their own cue set; the card shows the union.
    matched_cues = []
    seen_cue_ids = set()
    for f in findings:
        for cue in f.matched_cues.all():
            if cue.id in seen_cue_ids:
                continue
            seen_cue_ids.add(cue.id)
            matched_cues.append(cue)

    # Trigger attribution — parallel workstream may or may not have
    # landed the FK. Defensively resolve it here so the template only
    # sees a concrete object-or-None and doesn't have to introspect.
    eval_trigger = getattr(eval_row, "trigger", None)

    return render(request, "validator/eval_detail.html", {
        "eval": eval_row,
        "findings": findings,
        "hitl": hitl,
        "delta": delta,
        "concern": concern,
        "matched_cues": matched_cues,
        "eval_trigger": eval_trigger,
    })


# --- Operator runs browser (staff only) ---------------------------------


@staff_required
def runs_browser(request: HttpRequest) -> HttpResponse:
    """Paginated filterable browser of ALL Evaluation rows.

    Unlike operator_dashboard's findings panel, this view does NOT
    filter by Finding presence — benign probes, probes that scored
    zero, and probes with no cue matches all show up. The goal is
    operator pattern-finding: spot concerns the catalog is missing
    by reading through real runs, not just the ones that crossed
    the findings threshold.

    Filters are query-string driven (?category=X&concern=Y&uid=N&...)
    and preserved across pagination. Invalid numeric inputs are
    silently dropped so a malformed URL doesn't 500 the page.
    """
    from .models import Evaluation

    qs = (
        Evaluation.objects
        .select_related("target", "trigger")
        .prefetch_related("findings")
        .order_by("-timestamp")
    )

    q_target = (request.GET.get("target") or "").strip()
    q_category = (request.GET.get("category") or "").strip()
    q_concern = (request.GET.get("concern") or "").strip()
    q_uid = (request.GET.get("uid") or "").strip()
    q_min_sev = (request.GET.get("min_severity") or "").strip()
    q_max_sev = (request.GET.get("max_severity") or "").strip()
    q_only_findings = request.GET.get("only_findings") == "1"

    if q_target:
        qs = qs.filter(target__name=q_target)
    if q_category:
        qs = qs.filter(category=q_category)
    if q_concern:
        qs = qs.filter(concern_id_slug=q_concern)
    if q_uid:
        try:
            qs = qs.filter(miner_uid=int(q_uid))
        except ValueError:
            pass
    if q_min_sev:
        try:
            qs = qs.filter(accepted_severity__gte=float(q_min_sev))
        except ValueError:
            pass
    if q_max_sev:
        try:
            qs = qs.filter(accepted_severity__lte=float(q_max_sev))
        except ValueError:
            pass
    if q_only_findings:
        qs = qs.filter(findings__isnull=False).distinct()

    PAGE_SIZE = 100
    try:
        page = max(1, int(request.GET.get("page", "1")))
    except ValueError:
        page = 1
    offset = (page - 1) * PAGE_SIZE
    total = qs.count()
    rows = list(qs[offset : offset + PAGE_SIZE])

    # Distinct facets for filter dropdowns — small cardinality so a
    # plain DISTINCT is cheap. If the catalog ever grows past ~200
    # concerns this should move to a cached denormalized list.
    categories = Evaluation.objects.values_list("category", flat=True).distinct()
    concerns = (
        Evaluation.objects
        .exclude(concern_id_slug="")
        .values_list("concern_id_slug", flat=True)
        .distinct()
    )
    target_names = (
        Evaluation.objects
        .values_list("target__name", flat=True)
        .distinct()
    )

    # Build querystring-preserving links for pagination. Strip page
    # so prev/next can set their own without stacking.
    from urllib.parse import urlencode
    preserved = {
        k: v for k, v in request.GET.items() if k != "page" and v
    }
    base_qs = urlencode(preserved)

    return render(request, "validator/runs_browser.html", {
        "rows": rows,
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
        "has_next": offset + PAGE_SIZE < total,
        "has_prev": page > 1,
        "next_page": page + 1,
        "prev_page": page - 1,
        "categories": sorted([c for c in categories if c]),
        "concerns": sorted([c for c in concerns if c]),
        "target_names": sorted([n for n in target_names if n]),
        "base_qs": base_qs,
        "q": {
            "target": q_target,
            "category": q_category,
            "concern": q_concern,
            "uid": q_uid,
            "min_severity": q_min_sev,
            "max_severity": q_max_sev,
            "only_findings": q_only_findings,
        },
        "nav_active": "runs",
    })


# --- Customer dashboard (stub views, implemented in task 8) -------------


@customer_required
def customer_dashboard(request: HttpRequest) -> HttpResponse:
    """Customer landing page: list of targets with safety posture summary."""
    targets = request.customer_profile.targets.all()
    return render(request, "validator/customer_dashboard.html", {"targets": targets})


@customer_required
def customer_target_detail(request: HttpRequest, name: str) -> HttpResponse:
    """Per-target vulnerability-outcome profile."""
    target = get_object_or_404(request.customer_profile.targets, name=name)
    return render(request, "validator/customer_target_detail.html", {"target": target})


@customer_required
def customer_findings(request: HttpRequest, name: str) -> HttpResponse:
    """Filterable findings list for a customer's target."""
    target = get_object_or_404(request.customer_profile.targets, name=name)
    from .models import Finding
    findings = Finding.objects.filter(evaluation__target=target).select_related("evaluation").order_by("-evaluation__timestamp")
    return render(request, "validator/customer_findings.html", {"target": target, "findings": findings})


@customer_required
def customer_finding_detail(request: HttpRequest, finding_id: int) -> HttpResponse:
    """Single finding with full transcript and curation status."""
    from .models import Finding
    customer_targets = request.customer_profile.targets.all()
    finding = get_object_or_404(
        Finding.objects.select_related("evaluation", "evaluation__target"),
        pk=finding_id,
        evaluation__target__in=customer_targets,
    )
    return render(request, "validator/customer_finding_detail.html", {"finding": finding})


# --- Curation (stub views, implemented in task 9) -----------------------


@staff_required
def curation_queue(request: HttpRequest) -> HttpResponse:
    """Pending critical findings for operator review PLUS the HITL queue.

    Sub-work A.2 — the curation page is the single operator view of
    "things humans need to touch". Two queues live here:

      1. Findings the operator curates manually via
         curation_action (confirm/downgrade/escalate).
      2. HitlCases routed to HITL miners. The operator cannot assign
         or reorder these (trust-minimization: uniform-random
         dispatch), but they can REMOVE cases from the pending queue
         with a reason via `hitl_case_remove`.

    Phase 7 additions:
      - Summary cards (queue depth, actions today/week, agreement delta,
        top concern in dispute, HITL miner availability)
      - Category filter (GET ?category=<name>) scopes the pending queues
      - Concern leaderboard: top 10 concerns by HITL case count
      - Miner leaderboard: top 10 miners by HITL case count
      - Curator contributions: last 7 days of actions by user
    """
    from django.db.models import Avg, Count, F, Q
    from django.db.models.functions import Abs
    from .models import CurationAction, Finding, HitlCase, MinerScore

    # --- Filter (GET ?category=...) --------------------------------------
    selected_category = (request.GET.get("category") or "").strip() or None

    def _apply_category(qs, field="category"):
        if selected_category:
            return qs.filter(**{field: selected_category})
        return qs

    # --- Pending / curated finding queues -------------------------------
    pending = (
        _apply_category(Finding.objects.filter(critical=True, curated=False))
        .select_related("evaluation", "evaluation__target")
        .prefetch_related("matched_cues")
        .order_by("-severity")
    )
    curated = (
        _apply_category(Finding.objects.filter(curated=True))
        .select_related("evaluation", "evaluation__target")
        .order_by("-curated_at")[:20]
    )

    # --- HITL queue (scoped by evaluation__category filter) -------------
    hitl_base = HitlCase.objects.select_related(
        "evaluation", "evaluation__target",
    )
    if selected_category:
        hitl_base = hitl_base.filter(evaluation__category=selected_category)

    hitl_pending = hitl_base.filter(status=HitlCase.STATUS_PENDING).order_by("routed_at")
    hitl_dispatched = hitl_base.filter(status=HitlCase.STATUS_DISPATCHED).order_by("-dispatched_at")
    hitl_recent_labeled = hitl_base.filter(status=HitlCase.STATUS_LABELED).order_by("-labeled_at")[:20]
    hitl_recent_removed = hitl_base.filter(status=HitlCase.STATUS_REMOVED).select_related("removed_by").order_by("-removed_at")[:20]

    # Global HITL status counts (NOT category-scoped — the counts summarize
    # the whole queue even when the user is filtering, so they know how
    # much the filter is hiding).
    hitl_counts = {
        "pending": HitlCase.objects.filter(status=HitlCase.STATUS_PENDING).count(),
        "dispatched": HitlCase.objects.filter(status=HitlCase.STATUS_DISPATCHED).count(),
        "labeled": HitlCase.objects.filter(status=HitlCase.STATUS_LABELED).count(),
        "removed": HitlCase.objects.filter(status=HitlCase.STATUS_REMOVED).count(),
        "timed_out": HitlCase.objects.filter(status=HitlCase.STATUS_TIMED_OUT).count(),
    }

    # --- Summary stats for the cards ------------------------------------
    now = djtz.now()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    actions_today = CurationAction.objects.filter(created_at__gte=day_ago).count()
    actions_week = CurationAction.objects.filter(created_at__gte=week_ago).count()

    # Average |miner_safety_score - audit_score| across HITL-routed evals.
    # HITL selection criterion is divergence, so this tells you how
    # divergent the current queue is on average.
    avg_delta_row = (
        HitlCase.objects
        .filter(evaluation__audit_score__isnull=False)
        .aggregate(avg_delta=Avg(Abs(F("evaluation__miner_safety_score") - F("evaluation__audit_score"))))
    )
    avg_claim_audit_delta = avg_delta_row["avg_delta"]

    # HITL miner availability — helps explain "why isn't my pending queue
    # moving?". Total comes from ValidatorStatus.n_hitl_miners (populated
    # by the loop's chain scan, since HITL-ness lives in the advertised
    # axon types, not in MinerScore). Cooldown count is any MinerScore
    # row whose hitl_cooldown_until is in the future — that field is
    # ONLY set by HITL dispatch, so every row with it set is definitionally
    # a HITL miner.
    vstatus = ValidatorStatus.get()
    hitl_miners_total = vstatus.n_hitl_miners if vstatus else 0
    hitl_miners_in_cooldown = MinerScore.objects.filter(
        hitl_cooldown_until__gt=now,
    ).count()
    hitl_miners_ready = max(0, hitl_miners_total - hitl_miners_in_cooldown)

    # --- Concern leaderboard: top 10 concerns by HITL case count --------
    concern_leaderboard = list(
        HitlCase.objects
        .exclude(evaluation__concern_id_slug="")
        .values("evaluation__concern_id_slug")
        .annotate(
            total=Count("id"),
            pending=Count("id", filter=Q(status=HitlCase.STATUS_PENDING)),
            dispatched=Count("id", filter=Q(status=HitlCase.STATUS_DISPATCHED)),
            labeled=Count("id", filter=Q(status=HitlCase.STATUS_LABELED)),
        )
        .order_by("-total")[:10]
    )

    top_concern_slug = concern_leaderboard[0]["evaluation__concern_id_slug"] if concern_leaderboard else None

    # --- Miner leaderboard: top 10 miners by HITL case count ------------
    miner_leaderboard = list(
        HitlCase.objects
        .values("evaluation__miner_uid")
        .annotate(
            total=Count("id"),
            pending=Count("id", filter=Q(status=HitlCase.STATUS_PENDING)),
            labeled=Count("id", filter=Q(status=HitlCase.STATUS_LABELED)),
            avg_delta=Avg(
                Abs(F("evaluation__miner_safety_score") - F("evaluation__audit_score")),
                filter=Q(evaluation__audit_score__isnull=False),
            ),
        )
        .order_by("-total")[:10]
    )

    # --- Curator contributions last 7 days ------------------------------
    curator_contributions = list(
        CurationAction.objects
        .filter(created_at__gte=week_ago)
        .values("curator__username")
        .annotate(
            total=Count("id"),
            confirms=Count("id", filter=Q(action="confirm")),
            downgrades=Count("id", filter=Q(action="downgrade")),
            escalates=Count("id", filter=Q(action="escalate")),
        )
        .order_by("-total")[:10]
    )

    # --- Available categories for the filter chips ----------------------
    available_categories = sorted(
        set(
            Finding.objects.filter(critical=True, curated=False)
            .values_list("category", flat=True).distinct()
        )
        | set(
            HitlCase.objects.filter(status__in=[
                HitlCase.STATUS_PENDING, HitlCase.STATUS_DISPATCHED,
            ]).values_list("evaluation__category", flat=True).distinct()
        )
    )

    summary = {
        "hitl_pending_count": hitl_counts["pending"],
        "findings_pending_count": Finding.objects.filter(
            critical=True, curated=False,
        ).count(),
        "actions_today": actions_today,
        "actions_week": actions_week,
        "avg_claim_audit_delta": avg_claim_audit_delta,
        "hitl_miners_ready": hitl_miners_ready,
        "hitl_miners_total": hitl_miners_total,
        "top_concern_slug": top_concern_slug,
    }

    return render(request, "validator/curation_queue.html", {
        "pending": pending,
        "curated": curated,
        "hitl_pending": hitl_pending,
        "hitl_dispatched": hitl_dispatched,
        "hitl_recent_labeled": hitl_recent_labeled,
        "hitl_recent_removed": hitl_recent_removed,
        "hitl_counts": hitl_counts,
        "summary": summary,
        "selected_category": selected_category,
        "available_categories": available_categories,
        "concern_leaderboard": concern_leaderboard,
        "miner_leaderboard": miner_leaderboard,
        "curator_contributions": curator_contributions,
        "nav_active": "curation",
    })


@csrf_exempt
@staff_required
@require_http_methods(["POST"])
def hitl_case_remove(request: HttpRequest, case_id: int) -> HttpResponse:
    """Remove a pending HitlCase from the dispatch queue.

    Sub-work A.2 — operator-controlled queue management. The operator
    can remove cases (with a required reason) but CANNOT reorder or
    assign them. Removal is non-destructive: status flips to `removed`
    and the row stays for audit trail. Only pending cases can be
    removed — dispatched / labeled / timed_out cases have already
    completed their dispatch lifecycle and removing them would
    silently undo work.
    """
    from django.db import transaction
    from .models import HitlCase

    reason = (request.POST.get("reason") or "").strip()
    if not reason:
        return HttpResponse("reason is required", status=400)

    case = get_object_or_404(HitlCase, pk=case_id)

    with transaction.atomic():
        if case.status != HitlCase.STATUS_PENDING:
            return HttpResponse(
                f"case is {case.status}, only pending cases can be removed",
                status=400,
            )
        case.status = HitlCase.STATUS_REMOVED
        case.removed_at = djtz.now()
        case.removed_by = request.user
        case.removed_reason = reason
        case.save(update_fields=[
            "status", "removed_at", "removed_by", "removed_reason",
        ])

    return redirect("curation_queue")


@staff_required
def curation_detail(request: HttpRequest, finding_id: int) -> HttpResponse:
    """Finding detail with evaluation context + curation form."""
    from .models import Concern, Finding
    finding = get_object_or_404(
        Finding.objects
        .select_related("evaluation", "evaluation__target")
        .prefetch_related("matched_cues__concern"),
        pk=finding_id,
    )
    actions = finding.curation_actions.select_related("curator").all()

    # Concerns v2 — human curators especially need to see WHAT the
    # probe was trying to elicit, so they can answer "did the AI
    # actually exhibit the concern the operator worried about?".
    eval_row = finding.evaluation
    concern = None
    if eval_row.concern_id_slug:
        concern = Concern.objects.filter(id_slug=eval_row.concern_id_slug).first()

    matched_cues = list(finding.matched_cues.all())
    # Trigger attribution — parallel workstream may or may not have
    # landed the FK. Use getattr so this renders as None if the
    # field doesn't exist yet.
    eval_trigger = getattr(eval_row, "trigger", None)

    return render(request, "validator/curation_detail.html", {
        "finding": finding,
        "actions": actions,
        "eval": eval_row,
        "concern": concern,
        "matched_cues": matched_cues,
        "eval_trigger": eval_trigger,
    })


@csrf_exempt
@staff_required
@require_http_methods(["POST"])
def curation_action(request: HttpRequest, finding_id: int) -> HttpResponse:
    """POST handler: create a CurationAction and update Finding cached fields."""
    from django.db import transaction
    from .models import CurationAction as CurationActionModel, Finding

    finding = get_object_or_404(Finding, pk=finding_id)

    action_type = request.POST.get("action", "").strip()
    reason = request.POST.get("reason", "").strip()
    if action_type not in ("confirm", "downgrade", "escalate"):
        return HttpResponse("Invalid action", status=400)
    if not reason:
        return HttpResponse("Reason is required", status=400)

    try:
        new_severity = float(request.POST.get("new_severity", finding.severity))
    except (ValueError, TypeError):
        new_severity = finding.severity

    with transaction.atomic():
        CurationActionModel.objects.create(
            finding=finding,
            action=action_type,
            reason=reason,
            original_severity=finding.severity,
            new_severity=new_severity,
            curator=request.user,
        )
        finding.curated = True
        finding.curated_severity = new_severity
        finding.curated_at = djtz.now()
        finding.save(update_fields=["curated", "curated_severity", "curated_at"])

    return redirect("curation_detail", finding_id=finding_id)


@staff_required
def curation_log(request: HttpRequest) -> HttpResponse:
    """Full audit trail of all curation actions."""
    from .models import CurationAction as CurationActionModel
    actions = CurationActionModel.objects.select_related("finding", "finding__evaluation__target", "curator").all()[:200]
    return render(request, "validator/curation_log.html", {"actions": actions})


# --- Concern management (operator curation UI) -------------------------
#
# Successor to the `/bait/*` views. DESIGN.md §2 "Concerns, curated by
# validators". Every edit bumps `version`, records the curator, and
# writes a ConcernRevision snapshot. Retirement is a separate POST
# action that flips `active` without requiring text edits, matching
# the DESIGN.md requirement for a non-destructive retirement path.


def _generate_unique_concern_slug(title: str) -> str:
    """Derive a URL-safe slug from the concern title, appending a
    numeric suffix if a concern with the base slug already exists.
    Operators enter the title and category; the slug is a system
    detail they should never have to think about."""
    from .models import Concern
    base = slugify(title)[:100] or "concern"
    slug = base
    n = 2
    while Concern.objects.filter(id_slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def _concern_snapshot(concern) -> dict:
    """Full content dict for ConcernRevision.snapshot. Everything the
    operator can edit via the curation form goes in here; audit
    metadata (created_at, version, etc.) is redundant on the
    revision row and is omitted.

    Includes the full current state of DetectionCue and
    UserTrigger child rows so revision history reflects what the
    concern "looked like" at the time of the version bump. Cue/
    trigger CRUD on its own does NOT bump version or write a
    snapshot — only a save of the Concern itself does, and that
    save captures the child rows as they then exist.
    """
    return {
        "id_slug": concern.id_slug,
        "version": concern.version,
        "title": concern.title,
        "concern_text": concern.concern_text,
        "category": concern.category,
        "severity_prior": concern.severity_prior,
        "active": concern.active,
        "related_concerns": list(
            concern.related_concerns.values_list("id_slug", flat=True)
        ),
        "cues": [
            {
                "id": c.id,
                "cue_text": c.cue_text,
                "kind": c.kind,
                "active": c.active,
            }
            for c in concern.cues.all()
        ],
        "triggers": [
            {
                "id": t.id,
                "trigger_text": t.trigger_text,
                "kind": t.kind,
                "active": t.active,
            }
            for t in concern.triggers.all()
        ],
    }


def _curator_hotkey_for(request: HttpRequest) -> str:
    """Resolve the logged-in operator's hotkey for curator_hotkey.
    TODO: hotkey linkage — Django username is a stand-in until we
    attach hotkeys to User accounts. DESIGN.md §2 expects a real
    validator hotkey here so miners can prove catalog provenance.
    """
    return request.user.username if request.user.is_authenticated else ""


@staff_required
def concern_library(request: HttpRequest) -> HttpResponse:
    """List all Concern rows grouped by category.

    Supports an optional ?filter=pending-customer query arg that
    restricts to customer-authored concerns still awaiting
    operator activation (active=False, curator_user is a
    customer-profile holder). DESIGN.md §2 "customer-authored
    concerns pass through validator curation before active".
    """
    from .models import Concern, CustomerProfile
    # Concerns v2 — annotate each concern with the counts an operator
    # needs at a glance: how many cues, how many triggers, and the
    # total cue-hit count across all cues. Operators use the last
    # number to tell "which concerns are actually producing findings"
    # without clicking into each one.
    qs = (
        Concern.objects
        .annotate(
            n_cues=Count("cues", distinct=True),
            n_triggers=Count("triggers", distinct=True),
            total_hits=Sum("cues__hit_count"),
        )
        .order_by("category", "id_slug")
    )
    filter_arg = request.GET.get("filter", "")
    if filter_arg == "pending-customer":
        customer_user_ids = CustomerProfile.objects.values_list(
            "user_id", flat=True,
        )
        qs = qs.filter(active=False, curator_user_id__in=list(customer_user_ids))

    categories: dict[str, list] = {}
    for c in qs:
        categories.setdefault(c.category, []).append(c)
    return render(request, "validator/concern_library.html", {
        "categories": categories,
        "filter_arg": filter_arg,
        "nav_active": "concerns",
    })


@staff_required
def concern_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """View a single concern plus its version history."""
    from .models import Concern, Finding
    concern = get_object_or_404(Concern, id_slug=slug)
    revisions = concern.revisions.select_related("editor").all()
    all_other = Concern.objects.filter(active=True).exclude(pk=concern.pk).order_by(
        "category", "id_slug"
    )
    related_ids = set(
        concern.related_concerns.values_list("pk", flat=True)
    )
    # Concerns v2 — last 20 findings tagged with this concern's slug.
    # Gives operators a direct answer to "what has this concern
    # actually caught?" at the bottom of its detail page.
    recent_findings = (
        Finding.objects
        .filter(evaluation__concern_id_slug=concern.id_slug)
        .select_related("evaluation", "evaluation__target")
        .prefetch_related("matched_cues")
        .order_by("-id")[:20]
    )
    return render(request, "validator/concern_detail.html", {
        "concern": concern,
        "revisions": revisions,
        "all_other": all_other,
        "related_ids": related_ids,
        "recent_findings": recent_findings,
    })


@staff_required
@require_http_methods(["POST"])
def concern_edit(request: HttpRequest, slug: str) -> HttpResponse:
    """Edit a concern. Bumps version and writes a ConcernRevision snapshot
    inside one transaction."""
    from django.db import transaction
    from .models import Concern, ConcernRevision

    concern = get_object_or_404(Concern, id_slug=slug)

    # --- Read form fields ---
    new_title = request.POST.get("title", concern.title)
    new_category = request.POST.get("category", concern.category)
    new_concern_text = request.POST.get("concern_text", concern.concern_text).strip()
    if not new_concern_text:
        return HttpResponse("concern_text is required", status=400)

    try:
        new_severity_prior = float(
            request.POST.get("severity_prior", concern.severity_prior)
        )
    except (ValueError, TypeError):
        new_severity_prior = concern.severity_prior
    new_severity_prior = max(0.0, min(1.0, new_severity_prior))

    new_active = request.POST.get("active") == "on"

    related_slugs = request.POST.getlist("related_concerns")
    related_qs = Concern.objects.filter(
        id_slug__in=related_slugs,
    ).exclude(pk=concern.pk)

    with transaction.atomic():
        concern.title = new_title
        concern.category = new_category
        concern.concern_text = new_concern_text
        concern.severity_prior = new_severity_prior
        concern.active = new_active
        concern.version = (concern.version or 0) + 1
        concern.curator_user = request.user
        concern.curator_hotkey = _curator_hotkey_for(request)
        concern.save()
        concern.related_concerns.set(related_qs)

        ConcernRevision.objects.create(
            concern=concern,
            version=concern.version,
            snapshot=_concern_snapshot(concern),
            editor=request.user,
        )

    return redirect("concern_detail", slug=slug)


@staff_required
@require_http_methods(["POST"])
def concern_retire(request: HttpRequest, slug: str) -> HttpResponse:
    """Retire a concern — set active=False without touching content.
    Bumps version and writes a revision so the retirement is
    attributable in version history."""
    from django.db import transaction
    from .models import Concern, ConcernRevision

    concern = get_object_or_404(Concern, id_slug=slug)
    if not concern.active:
        return redirect("concern_detail", slug=slug)

    with transaction.atomic():
        concern.active = False
        concern.version = (concern.version or 0) + 1
        concern.curator_user = request.user
        concern.curator_hotkey = _curator_hotkey_for(request)
        concern.save(update_fields=[
            "active", "version", "curator_user", "curator_hotkey", "updated_at",
        ])
        ConcernRevision.objects.create(
            concern=concern,
            version=concern.version,
            snapshot=_concern_snapshot(concern),
            editor=request.user,
        )
    return redirect("concern_detail", slug=slug)


@staff_required
@require_http_methods(["POST"])
def concern_activate(request: HttpRequest, slug: str) -> HttpResponse:
    """Activate a concern — set active=True. Counterpart to retire,
    primarily used to green-light customer-authored pending concerns."""
    from django.db import transaction
    from .models import Concern, ConcernRevision

    concern = get_object_or_404(Concern, id_slug=slug)
    if concern.active:
        return redirect("concern_detail", slug=slug)

    with transaction.atomic():
        concern.active = True
        concern.version = (concern.version or 0) + 1
        concern.curator_user = request.user
        concern.curator_hotkey = _curator_hotkey_for(request)
        concern.save(update_fields=[
            "active", "version", "curator_user", "curator_hotkey", "updated_at",
        ])
        ConcernRevision.objects.create(
            concern=concern,
            version=concern.version,
            snapshot=_concern_snapshot(concern),
            editor=request.user,
        )
    return redirect("concern_detail", slug=slug)


@staff_required
def concern_create(request: HttpRequest) -> HttpResponse:
    """Create a new concern row. Slug is auto-generated from the title —
    operators should never have to think about URL-safe strings."""
    from django.db import transaction
    from .models import Concern, ConcernRevision

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            return HttpResponse("title is required", status=400)
        concern_text = (request.POST.get("concern_text") or "").strip()
        if not concern_text:
            return HttpResponse("concern_text is required", status=400)
        try:
            severity_prior = float(request.POST.get("severity_prior", 0.5))
        except (ValueError, TypeError):
            severity_prior = 0.5
        severity_prior = max(0.0, min(1.0, severity_prior))
        slug = _generate_unique_concern_slug(title)
        with transaction.atomic():
            concern = Concern.objects.create(
                id_slug=slug,
                version=1,
                curator_user=request.user,
                curator_hotkey=_curator_hotkey_for(request),
                active=request.POST.get("active") == "on",
                title=title,
                concern_text=concern_text,
                category=request.POST.get("category", ""),
                severity_prior=severity_prior,
            )
            ConcernRevision.objects.create(
                concern=concern,
                version=1,
                snapshot=_concern_snapshot(concern),
                editor=request.user,
            )
        return redirect("concern_detail", slug=slug)
    return render(request, "validator/concern_create.html", {})


# --- DetectionCue CRUD (staff-gated, POST-only) -------------------------
#
# Cues are lightweight curation children of a Concern. They do NOT
# participate in Concern versioning — edits here do not bump
# concern.version or write a ConcernRevision (snapshotting every cue
# tweak would bloat history beyond usefulness). The next save of
# the parent concern through concern_edit captures the current cue
# state in its snapshot.
#
# Trust-minimization: DetectionCue rows are NEVER exposed through
# /api/concerns — the miner-facing serializer in serializers.py
# excludes them. Miners that see cues overfit their probes to the
# matcher. Curation lives entirely inside the operator UI.


@staff_required
@require_http_methods(["POST"])
def cue_create(request: HttpRequest, concern_slug: str) -> HttpResponse:
    """Create a DetectionCue tied to a concern. POST cue_text, kind."""
    from .models import Concern, DetectionCue

    concern = get_object_or_404(Concern, id_slug=concern_slug)
    cue_text = (request.POST.get("cue_text") or "").strip()
    if not cue_text:
        return HttpResponse("cue_text is required", status=400)
    kind = request.POST.get("kind") or DetectionCue.KIND_SUBSTRING
    if kind not in dict(DetectionCue.KIND_CHOICES):
        return HttpResponse(f"invalid cue kind: {kind}", status=400)
    DetectionCue.objects.create(
        concern=concern,
        cue_text=cue_text,
        kind=kind,
        active=True,
    )
    return redirect("concern_detail", slug=concern_slug)


@staff_required
@require_http_methods(["POST"])
def cue_edit(request: HttpRequest, cue_id: int) -> HttpResponse:
    """Edit cue_text, kind, active on an existing DetectionCue.
    Does NOT bump parent concern version or write a revision."""
    from .models import DetectionCue

    cue = get_object_or_404(DetectionCue, pk=cue_id)
    cue_text = (request.POST.get("cue_text") or "").strip()
    if not cue_text:
        return HttpResponse("cue_text is required", status=400)
    kind = request.POST.get("kind") or cue.kind
    if kind not in dict(DetectionCue.KIND_CHOICES):
        return HttpResponse(f"invalid cue kind: {kind}", status=400)
    cue.cue_text = cue_text
    cue.kind = kind
    cue.active = request.POST.get("active") == "on"
    cue.save(update_fields=["cue_text", "kind", "active", "updated_at"])
    return redirect("concern_detail", slug=cue.concern.id_slug)


@staff_required
@require_http_methods(["POST"])
def cue_retire(request: HttpRequest, cue_id: int) -> HttpResponse:
    """Soft-retire a cue by flipping active=False. Preserved for
    historical attribution on findings that already referenced it."""
    from .models import DetectionCue

    cue = get_object_or_404(DetectionCue, pk=cue_id)
    if cue.active:
        cue.active = False
        cue.save(update_fields=["active", "updated_at"])
    return redirect("concern_detail", slug=cue.concern.id_slug)


@staff_required
@require_http_methods(["POST"])
def cue_activate(request: HttpRequest, cue_id: int) -> HttpResponse:
    """Re-activate a previously retired cue."""
    from .models import DetectionCue

    cue = get_object_or_404(DetectionCue, pk=cue_id)
    if not cue.active:
        cue.active = True
        cue.save(update_fields=["active", "updated_at"])
    return redirect("concern_detail", slug=cue.concern.id_slug)


# --- UserTrigger CRUD (staff-gated, POST-only) --------------------------
#
# Triggers mirror cues structurally but represent the input-side
# risk factors (human prompting framings that might elicit the
# concerning AI behavior). Unlike cues, triggers ARE exposed to
# miners via /api/concerns and serve as seeds for adversarial probe
# generation, so curator wording matters to miner behavior.


@staff_required
@require_http_methods(["POST"])
def trigger_create(request: HttpRequest, concern_slug: str) -> HttpResponse:
    """Create a UserTrigger tied to a concern. POST trigger_text, kind."""
    from .models import Concern, UserTrigger

    concern = get_object_or_404(Concern, id_slug=concern_slug)
    trigger_text = (request.POST.get("trigger_text") or "").strip()
    if not trigger_text:
        return HttpResponse("trigger_text is required", status=400)
    kind = request.POST.get("kind") or UserTrigger.KIND_PROMPT
    if kind not in dict(UserTrigger.KIND_CHOICES):
        return HttpResponse(f"invalid trigger kind: {kind}", status=400)
    UserTrigger.objects.create(
        concern=concern,
        trigger_text=trigger_text,
        kind=kind,
        active=True,
    )
    return redirect("concern_detail", slug=concern_slug)


@staff_required
@require_http_methods(["POST"])
def trigger_edit(request: HttpRequest, trigger_id: int) -> HttpResponse:
    """Edit trigger_text, kind, active. Does NOT bump parent concern
    version or write a revision (same rationale as cue_edit)."""
    from .models import UserTrigger

    trigger = get_object_or_404(UserTrigger, pk=trigger_id)
    trigger_text = (request.POST.get("trigger_text") or "").strip()
    if not trigger_text:
        return HttpResponse("trigger_text is required", status=400)
    kind = request.POST.get("kind") or trigger.kind
    if kind not in dict(UserTrigger.KIND_CHOICES):
        return HttpResponse(f"invalid trigger kind: {kind}", status=400)
    trigger.trigger_text = trigger_text
    trigger.kind = kind
    trigger.active = request.POST.get("active") == "on"
    trigger.save(update_fields=["trigger_text", "kind", "active", "updated_at"])
    return redirect("concern_detail", slug=trigger.concern.id_slug)


@staff_required
@require_http_methods(["POST"])
def trigger_retire(request: HttpRequest, trigger_id: int) -> HttpResponse:
    """Soft-retire a trigger by flipping active=False. Retired
    triggers stop being served to miners via /api/concerns but
    retain their invocation/success counts for stats."""
    from .models import UserTrigger

    trigger = get_object_or_404(UserTrigger, pk=trigger_id)
    if trigger.active:
        trigger.active = False
        trigger.save(update_fields=["active", "updated_at"])
    return redirect("concern_detail", slug=trigger.concern.id_slug)


@staff_required
@require_http_methods(["POST"])
def trigger_activate(request: HttpRequest, trigger_id: int) -> HttpResponse:
    """Re-activate a previously retired trigger."""
    from .models import UserTrigger

    trigger = get_object_or_404(UserTrigger, pk=trigger_id)
    if not trigger.active:
        trigger.active = True
        trigger.save(update_fields=["active", "updated_at"])
    return redirect("concern_detail", slug=trigger.concern.id_slug)


# --- Concern catalog distribution (GET /concerns) -----------------------
#
# DESIGN.md §2 "Epistula-authed GET /concerns distribution". Miners
# poll this to pull the current active catalog and its version. The
# response carries an ETag; miners honor If-None-Match to avoid
# re-downloading when the catalog hasn't changed.


@csrf_exempt
@require_http_methods(["GET"])
@_epistula_required
def concerns_catalog(request: HttpRequest) -> JsonResponse:
    """Return the active concern catalog as JSON, Epistula-authed."""
    import hashlib
    from .models import Concern
    from .serializers import serialize_concern

    qs = Concern.objects.filter(active=True)
    category = request.GET.get("category", "")
    if category:
        qs = qs.filter(category=category)
    qs = qs.order_by("id_slug")

    # ETag over the (slug, version) tuple — cheap, stable, no body hash.
    etag_raw = ",".join(f"{c.id_slug}:{c.version}" for c in qs)
    etag = hashlib.sha256(etag_raw.encode()).hexdigest()
    quoted_etag = f'"{etag}"'

    if_none_match = request.headers.get("If-None-Match", "")
    if if_none_match and if_none_match.strip() in (etag, quoted_etag):
        resp = HttpResponse(status=304)
        resp["ETag"] = quoted_etag
        return resp

    concerns_payload = [serialize_concern(c) for c in qs]
    catalog_version = max((c.version for c in qs), default=0)
    body = {
        "concerns": concerns_payload,
        "catalog_version": catalog_version,
        "served_at": djtz.now().isoformat(),
    }
    resp = JsonResponse(body)
    resp["ETag"] = quoted_etag
    return resp


# --- Customer-authored concerns -----------------------------------------


@customer_required
@require_http_methods(["GET", "POST"])
def customer_concern_new(request: HttpRequest, name: str) -> HttpResponse:
    """Customer-facing form to author a new Concern against one of
    their targets. Creates the concern with active=False; an
    operator must flip it on via the /concerns/ UI before dispatch
    picks it up. DESIGN.md §2 "Customer-authored concerns still
    pass through validator curation before active".
    """
    from django.db import transaction
    from .models import Concern, ConcernRevision

    target = get_object_or_404(request.customer_profile.targets, name=name)

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            return HttpResponse("title is required", status=400)
        concern_text = (request.POST.get("concern_text") or "").strip()
        if not concern_text:
            return HttpResponse("concern_text is required", status=400)
        try:
            severity_prior = float(request.POST.get("severity_prior", 0.5))
        except (ValueError, TypeError):
            severity_prior = 0.5
        severity_prior = max(0.0, min(1.0, severity_prior))
        slug = _generate_unique_concern_slug(title)

        with transaction.atomic():
            concern = Concern.objects.create(
                id_slug=slug,
                version=1,
                curator_user=request.user,
                curator_hotkey="",
                active=False,  # pending operator curation
                title=title,
                concern_text=concern_text,
                category=request.POST.get("category", ""),
                severity_prior=severity_prior,
            )
            # Wire to the customer's target so the dispatch loop can
            # opt them in once the operator activates the concern.
            target.concerns.add(concern)
            ConcernRevision.objects.create(
                concern=concern,
                version=1,
                snapshot=_concern_snapshot(concern),
                editor=request.user,
            )
        return redirect("customer_target_detail", name=target.name)

    return render(request, "validator/customer_concern_new.html", {
        "target": target,
    })


# --- Legacy alias shims --------------------------------------------------
#
# Keep old `bait_*` symbols importable during the one-release back-compat
# window. External code (tests, management commands) that still imports
# these resolves to the corresponding Concern view transparently, and the
# /bait/* URL prefix 301-redirects to /concerns/* in urls.py.
bait_library = concern_library
bait_detail = concern_detail
bait_edit = concern_edit
bait_create = concern_create
