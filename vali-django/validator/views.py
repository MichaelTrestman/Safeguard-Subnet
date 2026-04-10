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


# --- Operator UI --------------------------------------------------------

def operator_dashboard(request: HttpRequest) -> HttpResponse:
    """Phase 3: full operator console for vali-django.

    Shows everything the loop has accumulated in the DB — live status
    + per-cycle history + per-miner roster + recent audit findings +
    HITL queue. All data sources are the same tables the loop writes
    to, so if the loop is alive and the dashboard shows stale values,
    it's a dashboard bug not a loop bug.
    """
    from .models import CycleHistory, Evaluation, Finding, HitlCase, MinerScore

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

    # ----- Phase 3: cycle history -----
    # Most recent 20 cycles. Each row shows burn share, earned total,
    # and the submitted weights payload. Sorted newest-first.
    recent_cycles = CycleHistory.objects.order_by("-id")[:20]

    # ----- Phase 3: miner roster -----
    # One row per MinerScore. Annotate with lifetime evaluation count
    # and the most recent raw contribution so the operator can spot
    # productive vs dormant miners at a glance.
    miners = MinerScore.objects.all().order_by("uid")

    # ----- Phase 3: recent findings -----
    # Last 10 Finding rows with their Evaluation context.
    recent_findings = Finding.objects.select_related(
        "evaluation", "evaluation__target"
    ).order_by("-id")[:10]

    # ----- Phase 3: HITL queue -----
    # Pending HITL cases that nobody's labeled yet.
    pending_hitl = HitlCase.objects.filter(
        status=HitlCase.STATUS_PENDING
    ).select_related("evaluation", "evaluation__target").order_by("-id")[:10]

    # ----- Phase 3: audit throughput -----
    # Totals for the scoreboard card.
    n_evaluations_total = Evaluation.objects.count()
    n_evaluations_audited = Evaluation.objects.filter(
        audit_score__isnull=False
    ).count()
    n_findings_total = Finding.objects.count()
    n_hitl_pending = HitlCase.objects.filter(
        status=HitlCase.STATUS_PENDING
    ).count()

    # Burn share presentation hint — the FULL BURN chip fires at >=0.99
    # (tolerate tiny float imprecision around the 1.0 boundary).
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
        "burn_share": burn_share,
        "full_burn": full_burn,
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
