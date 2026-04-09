"""
Recovery from the bittensor-import logging hijack.

`import bittensor` (10.2.0 at time of writing) installs bittensor's own
`LoggingMachine`, which by default sets every non-bittensor logger to
CRITICAL so third-party libraries don't pollute its console output. Our
`vali.*` stdlib loggers are "third-party" from bittensor's perspective,
so after the import any `vali.loop.info(...)` call gets filtered out
before it ever reaches Django's root StreamHandler.

Recovery is two lines:

1. Set the `vali` parent logger to INFO so children inherit a sane level.
2. Walk existing `vali.*` loggers and reset their explicit level to
   NOTSET — bittensor set them to CRITICAL one-by-one, and an explicit
   level on a child overrides parent inheritance, so we have to undo
   that explicit setting.

We do NOT call `bt.logging.enable_third_party_loggers()` even though it
also fixes the levels — that call additionally installs a bittensor
QueueHandler on every third-party logger, which causes our log lines to
emit twice (once via Django's root StreamHandler in our format, once via
bittensor's color-coded console handler reading from the queue). Single
output via our format only is the goal.

Brand-new `vali.*` loggers created AFTER recovery do not need any
treatment — they default to NOTSET and inherit INFO from the `vali`
parent. Verified via `tmp-scripts/probe_logging_recovery_minimal.py`.

The "Enabling default logging (Warning level)" line that bittensor emits
once at import time is harmless announcement noise from bittensor itself
and is the only bittensor log line we surface.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("vali.logging_setup")
_recovered = False


def recover_after_bittensor_import() -> None:
    """Restore visibility of vali.* log lines after `import bittensor`.

    Idempotent — safe to call multiple times. Returns silently if
    bittensor is not installed (e.g. in a unit test environment that
    stubs out chain code).
    """
    global _recovered
    if _recovered:
        return

    # Sanity check: if bittensor isn't installed, no recovery is needed.
    try:
        import bittensor  # noqa: F401
    except ImportError:
        _recovered = True
        return

    # Step 1: parent gets a real level.
    parent = logging.getLogger("vali")
    parent.setLevel(logging.INFO)

    # Step 2: walk existing children and undo bittensor's explicit
    # per-logger level setting so they inherit from parent.
    for name in list(logging.root.manager.loggerDict.keys()):
        if name.startswith("vali."):
            logging.getLogger(name).setLevel(logging.NOTSET)

    _recovered = True
    logger.info(
        "Bittensor logging hijack recovered: vali.* loggers reset to inherit INFO"
    )
