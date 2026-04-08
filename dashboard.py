"""
Safeguard Safety Intel Dashboard + Cross-Subnet Portal.

A single web app on port 9080 that serves both:

  1. The dashboard UI + read-only data API for inspecting safety findings
     (everything under /api/* and the inline HTML at /).
  2. The public-facing client-integration API: /register, /evaluate, /status,
     /registry — what cross_subnet_api.py used to do.

The /evaluate endpoint is **async-query**: it returns aggregated safety stats
from validator.py's accumulated state, NOT a synchronous probe dispatch. This
unifies scoring math (the discovery market in validator.py is the only source
of truth) and removes the parallel evaluation path that cross_subnet_api.py
used to maintain. See DESIGN.md § Validator design for the underlying model.

Usage:
    python dashboard.py
"""

from dotenv import load_dotenv
load_dotenv()

import os
import json
import time
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Query, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from epistula import verify_epistula
from report_data import (
    load_evaluation_data,
    load_jsonl,
    get_finding_detail,
    get_hitl_cases,
    aggregate_target_safety,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | SG-DASHBOARD | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
PORT = int(os.getenv("DASHBOARD_PORT", "9080"))
REGISTRY_FILE = os.getenv("TARGET_REGISTRY_FILE", "target_registry.json")
MAX_REQUEST_AGE = 60  # seconds — for Epistula timestamp freshness check

# Default categories that any newly registered target is probed against unless
# the client provides a custom subset. Mirrors validator.py DEFAULT_SCENARIO_CATEGORIES.
DEFAULT_SCENARIO_CATEGORIES = [
    "self-harm", "illegal-activity", "fraud",
    "harassment", "pii-generation", "unauthorized-access",
]

app = FastAPI(title="Safeguard Safety Intel Portal")

# Cache with short TTL to avoid re-reading files on every request
_cache: dict = {}
_cache_ts: float = 0
CACHE_TTL = 30  # seconds

# Target registry — keyed by client hotkey. Persisted to REGISTRY_FILE.
# validator.py reads this same file each cycle to know what to probe.
_registry: dict[str, dict] = {}


def _save_registry():
    try:
        with open(REGISTRY_FILE, "w") as f:
            json.dump(_registry, f, indent=2)
    except OSError as e:
        logger.error(f"Failed to save registry: {e}")


def _load_registry_into_memory():
    global _registry
    try:
        with open(REGISTRY_FILE) as f:
            _registry = json.load(f)
        logger.info(f"Loaded {len(_registry)} registered target(s) from {REGISTRY_FILE}")
    except FileNotFoundError:
        _registry = {}
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load registry: {e}")
        _registry = {}


async def _get_body_bytes(request: Request) -> bytes:
    return await request.body()


async def verify_caller(
    request: Request,
    body: bytes = Depends(_get_body_bytes),
) -> str:
    """Verify Epistula auth headers on an inbound request. Returns the caller hotkey.

    For MVP we accept any valid Epistula-signed request — i.e. any wallet that
    can prove possession of its hotkey. In production, the caller's hotkey
    should also be checked against a known set of registered target subnets.
    """
    try:
        hotkey = verify_epistula(
            timestamp=request.headers["X-Epistula-Timestamp"],
            signature=request.headers["X-Epistula-Signature"],
            hotkey=request.headers["X-Epistula-Hotkey"],
            body=body,
        )
    except KeyError as e:
        raise HTTPException(400, f"Missing header: {e}")
    except ValueError as e:
        raise HTTPException(401, str(e))
    return hotkey


def _get_data(filter_target: str = "") -> dict:
    """Get report data, cached for CACHE_TTL seconds."""
    global _cache, _cache_ts
    cache_key = f"data:{filter_target}"
    now = time.time()
    if cache_key in _cache and now - _cache_ts < CACHE_TTL:
        return _cache[cache_key]

    data = load_evaluation_data(filter_target=filter_target)
    _cache[cache_key] = data
    _cache_ts = now
    return data


# -- Cross-subnet portal endpoints (replaces cross_subnet_api.py) --

@app.post("/register")
async def register(
    request: Request,
    caller_hotkey: str = Depends(verify_caller),
):
    """Register a target relay for ongoing safety evaluation.

    Body: {
        "relay_endpoint": "http://...",
        "name": "human-readable name",
        "subnet_type": "llm-chat",  # optional, default llm-chat
        "categories": ["self-harm", ...]  # optional subset of DEFAULT_SCENARIO_CATEGORIES
    }
    """
    body = await request.json()
    relay_endpoint = body.get("relay_endpoint", "")
    name = body.get("name", f"client-{caller_hotkey[:8]}")
    if not relay_endpoint:
        raise HTTPException(400, "Missing relay_endpoint")

    categories = body.get("categories") or DEFAULT_SCENARIO_CATEGORIES

    _registry[caller_hotkey] = {
        "relay_endpoint": relay_endpoint,
        "name": name,
        "subnet_type": body.get("subnet_type", "llm-chat"),
        "categories": categories,
        "registered_at": time.time(),
        "last_probed": None,
        "evaluations_completed": 0,
        "last_evaluation": None,
    }
    _save_registry()
    logger.info(
        f"Registered target: {name} at {relay_endpoint} (client={caller_hotkey[:8]}...)"
    )
    return {
        "status": "registered",
        "client_hotkey": caller_hotkey,
        "name": name,
    }


@app.delete("/register")
async def deregister(
    request: Request,
    caller_hotkey: str = Depends(verify_caller),
):
    """Deregister a target (stop being probed)."""
    if caller_hotkey in _registry:
        name = _registry[caller_hotkey].get("name", "unknown")
        del _registry[caller_hotkey]
        _save_registry()
        logger.info(f"Deregistered target: {name} (client={caller_hotkey[:8]}...)")
        return {"status": "deregistered"}
    raise HTTPException(404, "Client not registered")


@app.get("/status/{client_hotkey}")
async def client_status(client_hotkey: str):
    """Check evaluation status for a registered client (public, no auth)."""
    entry = _registry.get(client_hotkey)
    if not entry:
        raise HTTPException(404, "Client not registered")
    return {
        "registered": True,
        "relay_endpoint": entry["relay_endpoint"],
        "name": entry["name"],
        "evaluations_completed": entry.get("evaluations_completed", 0),
        "last_evaluation": entry.get("last_evaluation"),
        "registered_at": entry.get("registered_at"),
    }


@app.get("/registry")
async def list_registry():
    """List all registered targets (public, no auth)."""
    return {
        "count": len(_registry),
        "targets": [
            {
                "client_hotkey": hk[:12] + "...",
                "name": entry.get("name", "unknown"),
                "relay_endpoint": entry.get("relay_endpoint", ""),
                "evaluations_completed": entry.get("evaluations_completed", 0),
            }
            for hk, entry in _registry.items()
        ],
    }


@app.post("/evaluate")
async def evaluate(
    request: Request,
    caller_hotkey: str = Depends(verify_caller),
):
    """Async-query safety evaluation: returns aggregated stats from validator.py's
    accumulated state, NOT a synchronous probe dispatch.

    The validator.py main loop continuously dispatches probes against registered
    targets and accumulates per-finding contributions under the discovery market.
    This endpoint is a thin read-only window over that accumulated state.

    Body (legacy + new shapes both accepted):
        Legacy:  {"subnet_type": "...", "target_validator_endpoint": "...", "context": {...}}
        New:     {"target": "<name|hotkey>", "category": "<optional category filter>"}

    Response:
        {
            "safety_score": float in [0, 1] — 1 = safe, 0 = unsafe (multiplier-friendly)
            "based_on_evaluations": int,
            "categories_observed": [str],
            "n_findings": int,
            "n_bait_only": int,
            "n_null": int,
            "total_accepted_severity": float,
            "time_range": {"start": float, "end": float},
            "fallback": bool  — true if no accumulated data was available yet
        }
    """
    body = await request.json()

    # Resolve target name from one of: explicit "target", legacy
    # "target_validator_endpoint" lookup against registry, or fall back to
    # the caller's own registered name.
    target_name = body.get("target", "")
    if not target_name:
        # Legacy: caller passed target_validator_endpoint; look it up by relay match
        endpoint = body.get("target_validator_endpoint", "")
        if endpoint:
            for hk, entry in _registry.items():
                if entry.get("relay_endpoint") == endpoint:
                    target_name = entry.get("name", "")
                    break
        # Last resort: caller's own registration
        if not target_name and caller_hotkey in _registry:
            target_name = _registry[caller_hotkey].get("name", "")

    if not target_name:
        raise HTTPException(
            400,
            "Could not resolve target. Pass 'target' (registered name) or "
            "'target_validator_endpoint' that matches a registered relay, "
            "or register first via POST /register."
        )

    category_filter = body.get("category", "")
    agg = aggregate_target_safety(target_name, category=category_filter)

    # Update registry stats so the dashboard shows recent activity
    if caller_hotkey in _registry:
        _registry[caller_hotkey]["evaluations_completed"] = (
            _registry[caller_hotkey].get("evaluations_completed", 0) + 1
        )
        _registry[caller_hotkey]["last_evaluation"] = {
            "timestamp": time.time(),
            "target": target_name,
            "safety_score": agg["safety_score"],
        }
        _save_registry()

    logger.info(
        f"Evaluate query from {caller_hotkey[:8]}... target={target_name} "
        f"category={category_filter or 'any'} → safety_score={agg['safety_score']:.3f} "
        f"based_on={agg['based_on_evaluations']}"
    )
    return agg


# -- Public dashboard data API (no auth) --

@app.get("/api/targets")
async def api_targets():
    """List registered targets with evaluation counts (UI use)."""
    targets = []
    for hk, entry in _registry.items():
        targets.append({
            "client_hotkey": hk[:12] + "...",
            "name": entry.get("name", "unknown"),
            "relay_endpoint": entry.get("relay_endpoint", ""),
            "evaluations_completed": entry.get("evaluations_completed", 0),
            "last_probed": entry.get("last_probed"),
            "registered_at": entry.get("registered_at"),
        })
    return {"count": len(targets), "targets": targets}


@app.get("/api/summary")
async def api_summary():
    """Aggregate safety stats — no transcripts, public."""
    data = _get_data()
    return {
        "summary": data["summary"],
        "time_range": data["time_range"],
        "targets": data["targets"],
        "per_target": data["per_target"],
        "category_breakdown": data["category_breakdown"],
    }


@app.get("/api/report/{target_name}")
async def api_report(target_name: str):
    """Full safety report for a specific target."""
    data = _get_data(filter_target=target_name)
    if not data["summary"]["total_probes"]:
        raise HTTPException(404, f"No data for target '{target_name}'")

    return {
        "target_name": target_name,
        "summary": data["summary"],
        "time_range": data["time_range"],
        "category_breakdown": data["category_breakdown"],
        "findings_count": data["summary"]["findings_count"],
        "critical_count": data["summary"]["critical_count"],
        "findings": data["findings"][:50],
        "critical_findings": data["critical_findings"][:20],
        "hitl_cases": data["hitl_cases"],
        "hitl_labels": data["hitl_labels"],
    }


@app.get("/api/findings/{target_name}")
async def api_findings(
    target_name: str,
    category: str = Query(default="", description="Filter by category"),
    min_score: float = Query(default=0.3, description="Minimum score threshold"),
    limit: int = Query(default=50, description="Max results"),
):
    """Findings with transcript previews for a specific target."""
    data = _get_data(filter_target=target_name)

    findings = data["findings"]
    if category:
        findings = [f for f in findings if f["category"] == category]
    findings = [f for f in findings if max(f["miner_safety_score"], f["validator_score"]) >= min_score]

    return {
        "target_name": target_name,
        "total": len(findings),
        "findings": findings[:limit],
    }


@app.get("/api/finding/{task_id}")
async def api_finding_detail(task_id: str):
    """Full finding detail with complete transcript."""
    finding = get_finding_detail(task_id)
    if not finding:
        raise HTTPException(404, f"Finding '{task_id}' not found")
    return finding


@app.get("/api/hitl")
async def api_hitl(status: str = Query(default="", description="Filter: pending, labeled, or all")):
    """HITL cases with labels and status."""
    data = get_hitl_cases()
    if status:
        data["cases"] = [c for c in data["cases"] if c["status"] == status]
        data["total"] = len(data["cases"])
    return data


@app.get("/api/comparison")
async def api_comparison():
    """Side-by-side comparison of all targets."""
    data = _get_data()
    comparison = []
    for target, stats in data["per_target"].items():
        comparison.append({
            "target": target,
            **stats,
            "finding_rate": round(stats["findings"] / stats["probes"], 2) if stats["probes"] else 0,
            "critical_rate": round(stats["critical"] / stats["probes"], 2) if stats["probes"] else 0,
        })
    comparison.sort(key=lambda x: x.get("critical_rate", 0), reverse=True)
    return {"comparison": comparison}


@app.get("/health")
async def health():
    data = _get_data()
    return {
        "status": "ok",
        "service": "safeguard-dashboard",
        "total_entries": data["summary"]["total_entries"],
        "targets": data["targets"],
    }


# -- Static UI --

# Serve static files if directory exists
dashboard_static = Path(__file__).parent / "dashboard_static"
if dashboard_static.exists():
    app.mount("/static", StaticFiles(directory=str(dashboard_static)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the dashboard UI."""
    static_index = dashboard_static / "index.html"
    if static_index.exists():
        return static_index.read_text()

    # Inline fallback if no static files
    return """<!DOCTYPE html>
<html>
<head>
    <title>Safeguard Safety Intel</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #e0e0e0; padding: 2rem; max-width: 1200px; margin: 0 auto; }
        a { color: #88f; text-decoration: none; }
        a:hover { text-decoration: underline; }
        h1 { color: #fff; margin-bottom: 0.5rem; }
        h2 { color: #aaa; font-size: 1rem; font-weight: normal; margin-bottom: 1.5rem; }
        h3 { color: #fff; margin: 2rem 0 1rem; }
        .nav { display: flex; gap: 1rem; margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid #222; }
        .nav a { color: #aaa; padding: 0.4rem 0.8rem; border-radius: 4px; }
        .nav a.active, .nav a:hover { color: #fff; background: #222; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .card { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 1.25rem; }
        .card h4 { color: #888; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 0.4rem; }
        .card .value { font-size: 1.8rem; font-weight: bold; color: #fff; }
        .card .sub { font-size: 0.8rem; color: #666; margin-top: 0.2rem; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        th, td { text-align: left; padding: 0.6rem 0.75rem; border-bottom: 1px solid #222; }
        th { color: #888; font-size: 0.8rem; text-transform: uppercase; }
        tr:hover { background: #111; }
        .finding { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; cursor: pointer; transition: border-color 0.15s; }
        .finding:hover { border-color: #555; }
        .finding .meta { color: #888; font-size: 0.85rem; margin-bottom: 0.5rem; }
        .finding .preview { color: #ccc; font-size: 0.9rem; line-height: 1.4; }
        .score { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: bold; font-size: 0.8rem; }
        .score.critical { background: #4a1111; color: #ff4444; }
        .score.high { background: #4a2a11; color: #ff8844; }
        .score.medium { background: #4a4a11; color: #ffcc44; }
        .score.low { background: #1a3a1a; color: #44cc44; }
        .status { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; }
        .status.pending { background: #4a4a11; color: #ffcc44; }
        .status.labeled { background: #1a3a1a; color: #44cc44; }
        .transcript { background: #111; border: 1px solid #222; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
        .turn { margin-bottom: 1rem; }
        .turn .role { font-size: 0.8rem; text-transform: uppercase; font-weight: bold; margin-bottom: 0.3rem; }
        .turn .role.user { color: #ff8844; }
        .turn .role.assistant { color: #44aaff; }
        .turn .content { color: #ccc; line-height: 1.5; white-space: pre-wrap; word-break: break-word; font-size: 0.9rem; }
        .turn .think { color: #666; font-style: italic; font-size: 0.85rem; margin-top: 0.3rem; }
        .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 1rem 0; }
        .detail-item { }
        .detail-item .label { color: #888; font-size: 0.8rem; text-transform: uppercase; }
        .detail-item .val { color: #fff; font-size: 1.1rem; margin-top: 0.2rem; }
        .hitl-label { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; }
        .hitl-label .header { display: flex; justify-content: space-between; margin-bottom: 0.5rem; }
        .hitl-label .reasoning { color: #aaa; font-style: italic; margin-top: 0.5rem; }
        .loading { color: #666; padding: 2rem; text-align: center; }
        .back { margin-bottom: 1rem; }
    </style>
</head>
<body>
    <h1>Safeguard Safety Intel</h1>
    <h2>AI Safety Red-Teaming Subnet</h2>
    <div class="nav">
        <a href="#" onclick="loadOverview()" class="active" id="nav-overview">Overview</a>
        <a href="#" onclick="loadHITL()" id="nav-hitl">HITL Cases</a>
    </div>
    <div id="app"><div class="loading">Loading...</div></div>
    <script>
    const API = '';
    function setNav(id) { document.querySelectorAll('.nav a').forEach(a => a.classList.remove('active')); document.getElementById(id)?.classList.add('active'); }

    async function loadOverview() {
        setNav('nav-overview');
        const [summary, comparison, targets] = await Promise.all([
            fetch(API + '/api/summary').then(r => r.json()),
            fetch(API + '/api/comparison').then(r => r.json()),
            fetch(API + '/api/targets').then(r => r.json()),
        ]);
        const s = summary.summary;
        let html = '<div class="grid">';
        html += card('Total Probes', s.total_probes, (s.total_canaries || 0) + ' legacy canary entries');
        html += card('Findings', s.findings_count, s.critical_count + ' critical');
        html += card('Bait-only Nulls', s.bait_only_count || 0, 'informative nulls');
        html += card('Empty Nulls', s.null_count || 0, 'no findings, no bait');
        html += card('HITL Cases', s.hitl_routed_count, (s.hitl_labels_count||0) + ' labeled');
        html += card('Targets', s.targets_count, summary.targets.join(', '));
        html += '</div>';

        if (comparison.comparison.length) {
            html += '<h3>Model Comparison</h3><table><tr><th>Target</th><th>Probes</th><th>Findings</th><th>Critical</th><th>Safety</th><th>Avg Severity</th><th>Contribution</th></tr>';
            for (const c of comparison.comparison) {
                const safety = (c.safety_score != null ? c.safety_score : (1 - (c.avg_accepted_severity || 0)));
                const sev = (c.avg_accepted_severity != null ? c.avg_accepted_severity : (c.avg_validator_score || 0));
                const contrib = (c.total_contribution != null ? c.total_contribution : 0);
                html += '<tr><td><a href="#" onclick="showTarget(\\'' + c.target + '\\')">' + c.target + '</a></td>';
                html += '<td>' + c.probes + '</td><td>' + c.findings + '</td><td>' + c.critical + '</td>';
                html += '<td>' + safetyTag(safety) + '</td>';
                html += '<td>' + sev.toFixed(2) + '</td>';
                html += '<td>' + contrib.toFixed(3) + '</td></tr>';
            }
            html += '</table>';
        }

        html += '<h3>Category Breakdown</h3><table><tr><th>Category</th><th>Probes</th><th>Findings</th><th>Avg Severity</th></tr>';
        for (const [cat, st] of Object.entries(summary.category_breakdown).sort((a,b) => b[1].findings - a[1].findings)) {
            const sev = (st.avg_accepted_severity != null ? st.avg_accepted_severity : (st.avg_validator_score || 0));
            html += '<tr><td>' + cat + '</td><td>' + st.count + '</td><td>' + st.findings + '</td><td>' + sev.toFixed(2) + '</td></tr>';
        }
        html += '</table>';
        document.getElementById('app').innerHTML = html;
    }

    async function showTarget(name) {
        setNav('');
        const report = await fetch(API + '/api/report/' + encodeURIComponent(name)).then(r => r.json());
        let html = '<div class="back"><a href="#" onclick="loadOverview()">← Back to overview</a></div>';
        html += '<h3>' + esc(name) + '</h3>';
        const s = report.summary;
        html += '<div class="grid">';
        html += card('Probes', s.total_probes);
        html += card('Findings', s.findings_count, s.critical_count + ' critical');
        html += card('Bait-only Nulls', s.bait_only_count || 0);
        html += card('Empty Nulls', s.null_count || 0);
        html += card('HITL', s.hitl_routed_count);
        html += '</div>';

        if (report.critical_findings.length) {
            html += '<h3>Critical Findings</h3>';
            for (const f of report.critical_findings.slice(0, 15)) { html += findingCard(f); }
        }
        if (report.findings.length) {
            html += '<h3>All Findings (' + report.findings.length + ')</h3>';
            for (const f of report.findings.slice(0, 30)) { html += findingCard(f); }
        }
        document.getElementById('app').innerHTML = html;
    }

    async function showFinding(taskId) {
        setNav('');
        const f = await fetch(API + '/api/finding/' + encodeURIComponent(taskId)).then(r => r.json());
        let html = '<div class="back"><a href="#" onclick="history.back ? loadOverview() : loadOverview()">← Back</a></div>';
        html += '<h3>Finding Detail</h3>';

        html += '<div class="detail-grid">';
        html += detailItem('Target', f.target_name);
        html += detailItem('Category', f.category);
        html += detailItem('Miner UID', f.miner_uid);
        html += detailItem('Time', new Date(f.timestamp * 1000).toLocaleString());
        html += detailItem('Miner claimed severity', scoreTag(f.miner_safety_score));
        html += detailItem('Audit score', scoreTag(f.audit_score != null ? f.audit_score : f.validator_score));
        html += detailItem('Confidence in claim', (f.confidence_in_claim != null ? Number(f.confidence_in_claim).toFixed(2) : '—'));
        html += detailItem('Accepted severity', scoreTag(f.accepted_severity != null ? f.accepted_severity : 0));
        html += detailItem('Findings reward', (f.findings_reward != null ? Number(f.findings_reward).toFixed(3) : '—'));
        html += detailItem('Bait detected', (f.n_bait_detected != null ? f.n_bait_detected : 0) + ' patterns');
        html += detailItem('Bait modifier', (f.bait_modifier != null ? Number(f.bait_modifier).toFixed(3) : '0.000'));
        html += detailItem('Total contribution', (f.contribution != null ? Number(f.contribution).toFixed(3) : '—'));
        html += '</div>';

        if (f.miner_categories && f.miner_categories.length) {
            html += '<p style="color:#888;margin:0.5rem 0">Miner categories: ' + f.miner_categories.join(', ') + '</p>';
        }

        html += '<h3>Transcript</h3><div class="transcript">';
        for (const turn of f.transcript || []) {
            html += '<div class="turn"><div class="role ' + turn.role + '">' + (turn.role === 'user' ? 'Red-Team Probe' : 'Target Response') + '</div>';
            html += '<div class="content">' + esc(turn.content) + '</div>';
            if (turn.think_summary) { html += '<div class="think">Model reasoning: ' + esc(turn.think_summary) + '</div>'; }
            html += '</div>';
        }
        html += '</div>';
        document.getElementById('app').innerHTML = html;
    }

    async function loadHITL() {
        setNav('nav-hitl');
        const data = await fetch(API + '/api/hitl').then(r => r.json());
        let html = '<h3>HITL Cases</h3>';
        html += '<div class="grid">';
        html += card('Total', data.total);
        html += card('Pending', data.pending);
        html += card('Labeled', data.labeled);
        html += '</div>';

        if (!data.cases.length) {
            html += '<p style="color:#666">No HITL cases yet.</p>';
        } else {
            for (const c of data.cases) {
                const minerScore = (c.miner_safety_score != null ? c.miner_safety_score : 0);
                const auditScore = (c.tier2_score != null ? c.tier2_score : (c.audit_score || 0));
                html += '<div class="finding" onclick="showFinding(\\'' + c.task_id + '\\')">';
                html += '<div class="meta"><span class="status ' + c.status + '">' + c.status + '</span> ';
                html += 'miner ' + scoreTag(minerScore) + ' vs audit ' + scoreTag(auditScore);
                html += ' — ' + new Date(c.timestamp * 1000).toLocaleDateString() + '</div>';
                if (c.probe_preview) { html += '<div class="preview"><strong>Probe:</strong> ' + esc(c.probe_preview) + '</div>'; }
                if (c.response_preview) { html += '<div class="preview" style="margin-top:0.3rem"><strong>Response:</strong> ' + esc(c.response_preview) + '</div>'; }
                if (c.labels.length) {
                    for (const l of c.labels) {
                        html += '<div class="hitl-label" style="margin-top:0.75rem"><div class="header"><span>' + scoreTag(l.safety_score) + ' ' + (l.severity||'') + '</span><span style="color:#666">' + (l.categories||[]).join(', ') + '</span></div>';
                        if (l.reasoning) { html += '<div class="reasoning">"' + esc(l.reasoning) + '"</div>'; }
                        html += '</div>';
                    }
                }
                html += '</div>';
            }
        }
        document.getElementById('app').innerHTML = html;
    }

    function findingCard(f) {
        // Prefer the discovery-market accepted_severity; fall back to legacy max(miner, validator).
        const accepted = (f.accepted_severity != null ? f.accepted_severity : Math.max(f.miner_safety_score||0, f.validator_score||0));
        const baitInfo = (f.n_bait_detected ? ' [' + f.n_bait_detected + ' bait]' : '');
        const contribInfo = (f.contribution != null ? ' contrib:' + Number(f.contribution).toFixed(3) : '');
        return '<div class="finding" onclick="showFinding(\\'' + f.task_id + '\\')">' +
            '<div class="meta">' + scoreTag(accepted) + ' ' + esc(f.category) + ' — accepted:' + accepted.toFixed(2) + contribInfo + baitInfo +
            (f.hitl_routed ? ' [HITL]' : '') + ' <span style="color:#444">' + (f.target_name||'') + '</span></div>' +
            '<div class="preview">' + esc(f.transcript_preview || '(no preview)') + '</div></div>';
    }

    function card(t, v, sub) { return '<div class="card"><h4>'+t+'</h4><div class="value">'+v+'</div>'+(sub?'<div class="sub">'+sub+'</div>':'')+'</div>'; }
    function detailItem(label, val) { return '<div class="detail-item"><div class="label">' + label + '</div><div class="val">' + val + '</div></div>'; }
    // Severity tag: higher = more unsafe (red). For accepted_severity, miner claims, audit scores.
    function scoreTag(score) { const s = Number(score)||0; const c = s >= 0.7 ? 'critical' : s >= 0.4 ? 'high' : s >= 0.3 ? 'medium' : 'low'; return '<span class="score '+c+'">'+s.toFixed(2)+'</span>'; }
    // Safety tag: higher = SAFER (green). For target safety_score from /evaluate aggregation.
    function safetyTag(score) { const s = Number(score)||0; const c = s >= 0.7 ? 'low' : s >= 0.4 ? 'medium' : s >= 0.3 ? 'high' : 'critical'; return '<span class="score '+c+'">'+s.toFixed(2)+'</span>'; }
    function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = String(s); return d.innerHTML; }

    loadOverview();
    </script>
</body>
</html>"""


@app.on_event("startup")
async def _startup():
    """Load registry from disk before serving requests."""
    _load_registry_into_memory()
    logger.info(f"Safeguard portal listening on {HOST}:{PORT}")


if __name__ == "__main__":
    logger.info(f"Starting Safeguard portal on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
