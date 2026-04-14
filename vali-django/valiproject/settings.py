"""
Django settings for vali-django.

Lean by design — no auth middleware on the customer API (Epistula handles
that per-view), no sessions, no CSRF on the API endpoints. The operator UI
is read-only and runs on the same port; lock it down at the network layer
(k8s NetworkPolicy / GCP firewall) rather than in Django.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["*"]  # k8s ingress / firewall handles host filtering

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "validator.apps.ValidatorConfig",
    "public.apps.PublicConfig",
]

MIDDLEWARE = [
    # SecurityMiddleware enforces SECURE_SSL_REDIRECT, SECURE_HSTS_*, and
    # SECURE_PROXY_SSL_HEADER. Default-inert; only acts when those settings
    # are non-default (see BEHIND_CLOUDFLARE block below). Must sit first
    # so HTTPS redirects happen before any other handler runs.
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # WhiteNoise serves /static/ for the public landing. Must sit above
    # SessionMiddleware so anon asset fetches don't touch the session.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "valiproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.request",
                "validator.context_processors.validator_identity",
            ],
        },
    },
]

ASGI_APPLICATION = "valiproject.asgi.application"

LOGIN_URL = "/accounts/login/"
# After login, route to /app/ (the role-dispatching view) instead of /
# (which is now the public landing page, not the authed dashboard).
LOGIN_REDIRECT_URL = "/app/"
WSGI_APPLICATION = "valiproject.wsgi.application"


def _database_from_url(url: str) -> dict:
    # Tiny parser to avoid pulling dj-database-url for one feature.
    from urllib.parse import urlparse
    p = urlparse(url)
    if p.scheme.startswith("postgres"):
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": p.path.lstrip("/"),
            "USER": p.username or "",
            "PASSWORD": p.password or "",
            "HOST": p.hostname or "",
            "PORT": str(p.port or ""),
        }
    raise ValueError(f"Unsupported DATABASE_URL scheme: {p.scheme}")


if os.environ.get("DATABASE_URL"):
    DATABASES = {"default": _database_from_url(os.environ["DATABASE_URL"])}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# PgBouncer hop. When USE_PGBOUNCER=1 is set in the pod env, rewrite the
# DATABASE_URL's host:port to the in-pod pgbouncer sidecar. Keeps the
# user/pass from the secret intact — pgbouncer runs auth_type=trust and
# forwards creds upstream to the Cloud SQL Auth Proxy, which still
# validates against Cloud SQL. Decouples the "turn pooling on" decision
# from the database-url secret rotation. Stability sweep 2.x-4.
if os.environ.get("USE_PGBOUNCER", "").lower() in ("1", "true", "yes"):
    for _db in DATABASES.values():
        _db["HOST"] = "127.0.0.1"
        _db["PORT"] = os.environ.get("PGBOUNCER_PORT", "6432")

# Persistent connection pooling. Default 0 means every request opens+closes
# a fresh Postgres connection — under async load with sync_to_async hops,
# 20 concurrent experiment dispatches saturated Cloud SQL's ~25-connection
# ceiling in seconds (stress test 2026-04-14). 60s reuse cuts churn 5-10x.
# Django 4.2+ CONN_HEALTH_CHECKS silently replaces a stale connection at
# the start of a request rather than raising OperationalError mid-query.
for _db in DATABASES.values():
    _db.setdefault("CONN_MAX_AGE", int(os.environ.get("DB_CONN_MAX_AGE", "60")))
    _db.setdefault("CONN_HEALTH_CHECKS", True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

USE_TZ = True
TIME_ZONE = "UTC"

# ---------------------------------------------------------------------------
# HTTPS hardening. Only activates when BEHIND_CLOUDFLARE=1 is set in the pod
# env. Test stack (direct HTTP LB at 34.135.204.42) leaves this off.
#
# Threat: operator dashboard was served over plain HTTP at the raw prod LB IP
# (136.116.237.112:9090). Session cookies + login passwords traveled in
# cleartext. Only the project-safeguard.ai domain had TLS (via Cloudflare).
# See claude-brainstormz/safeguard-security-review-2026-04-14.md Critical #2.
#
# Fix: trust Cloudflare's X-Forwarded-Proto so Django knows the request was
# HTTPS end-to-end, then mark cookies Secure and 301-redirect any HTTP
# request to HTTPS. /healthz is exempt so kubelet's in-cluster probes keep
# working (they hit http://<pod-ip>:9090/healthz with no forwarding header).
#
# NOT yet enabled: HSTS (needs testing first — once you set HSTS-preload
# clients refuse HTTP for a year, hard to revert). Cloudflare-only firewall
# (blocks raw LB IP access from non-Cloudflare sources; deferred to a
# separate careful ship with dynamic IP-range refresh).
if os.environ.get("BEHIND_CLOUDFLARE", "").lower() in ("1", "true", "yes"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True  # no-op today (no CsrfViewMiddleware) but
    # belt-and-suspenders in case CSRF gets turned on later.
    SECURE_SSL_REDIRECT = True
    # Exempt paths that are legitimately hit over HTTP by internal/
    # programmatic traffic that doesn't follow POST redirects:
    #   - /healthz: kubelet probes via pod IP (no X-Forwarded-Proto)
    #   - /probe/relay: miner POSTs probe turns; httpx doesn't auto-
    #     follow 301 on POST (2026-04-14 discovered when stress test
    #     on prod produced empty transcripts)
    #   - /register, /evaluate, /status/<hk>, /registry, /api/concerns:
    #     Epistula-authed API endpoints hit by miners and target AIs;
    #     chain-signature auth at the body/header layer means HTTPS
    #     adds nothing security-wise, and redirect breaks them the
    #     same way /probe/relay broke.
    # Human-facing paths (/, /app/, /operator/, /experiments/, etc.)
    # still redirect to HTTPS.
    SECURE_REDIRECT_EXEMPT = [
        r"^healthz$",
        r"^probe/",
        r"^register$",
        r"^evaluate$",
        r"^status/",
        r"^registry$",
        r"^api/",
    ]

# --- Validator-specific config ---
VALIDATOR_WALLET = os.environ.get("VALIDATOR_WALLET", "")
VALIDATOR_HOTKEY = os.environ.get("VALIDATOR_HOTKEY", "")
SUBTENSOR_NETWORK = os.environ.get("SUBTENSOR_NETWORK", "test")
NETUID = int(os.environ.get("NETUID", "444"))

VALIDATOR_DISPLAY_NAME = os.environ.get("VALIDATOR_DISPLAY_NAME", "")

LOOP_INTERVAL_S = float(os.environ.get("LOOP_INTERVAL_S", "12"))
HEALTH_MAX_WEIGHT_AGE_S = float(os.environ.get("HEALTH_MAX_WEIGHT_AGE_S", "1800"))
HEALTH_MAX_TICK_AGE_S = float(os.environ.get("HEALTH_MAX_TICK_AGE_S", "120"))

# --- Provenance v2 (sub-phase 2.9) ---
# The externally-reachable URL the loop stamps into each dispatched
# task body so v2-aware miners know where to POST their probes.
# Required for v2 dispatch; if unset the loop falls back to v1-style
# dispatch (target_validator_endpoint only) and miners use the v1 path.
SAFEGUARD_RELAY_ENDPOINT = os.environ.get("SAFEGUARD_RELAY_ENDPOINT", "")

# Per-call timeouts for the /probe/relay forward to the client v1 relay.
# Strictly nested below the miner's overall probe timeout
# (~600s in loop.py) so that if the client hangs, our forward fails
# with 504 long before the miner gives up on us.
RELAY_FORWARD_READ_S = float(os.environ.get("RELAY_FORWARD_READ_S", "65"))
RELAY_FORWARD_CONNECT_S = float(os.environ.get("RELAY_FORWARD_CONNECT_S", "5"))

# Retention window for RelayCommitment rows. The retention loop deletes
# commitments older than this AND whose Evaluation has already been
# audited. Unaudited commitments are kept regardless of age — losing
# them breaks audit-time re-verification.
RELAY_COMMITMENT_RETENTION_HOURS = int(
    os.environ.get("RELAY_COMMITMENT_RETENTION_HOURS", "48")
)

# Structured-ish stdout logging. k8s captures stdout; never write log files.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {
            "format": "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "plain",
        },
    },
    "root": {"handlers": ["stdout"], "level": "INFO"},
    "loggers": {
        "django.server": {"handlers": ["stdout"], "level": "WARNING", "propagate": False},
    },
}
