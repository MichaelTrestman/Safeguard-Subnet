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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

USE_TZ = True
TIME_ZONE = "UTC"

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
