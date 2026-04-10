"""
ASGI entrypoint with a lifespan handler that owns the background validator
loop AND the module-level httpx.AsyncClient used by the v2 /probe/relay
view. The loop is started in lifespan startup and cancelled on shutdown —
one process, one event loop, no threads.

This is the entrypoint k8s + uvicorn use in production. `manage.py runserver`
uses WSGI and will NOT start the background loop or initialize the relay
httpx client, which is intentional: dev server is for poking views, not for
running the validator.

## Module-level mutables

Two pieces of state live on this module so the /probe/relay view can
reach them without dragging them through every request:

  - `RELAY_HTTPX`: an `httpx.AsyncClient` configured with the forward
    timeouts in settings. Constructed once in lifespan startup, closed
    in lifespan shutdown. The view imports this module and reads
    `valiproject.asgi.RELAY_HTTPX`. None until startup completes; the
    view checks for None and 503s if the lifespan didn't run.

  - `WALLET`: the validator wallet, used to sign the Epistula headers
    on the forward POST to the client v1 relay. Same lifecycle —
    populated by lifespan startup, available to the view from then on.
"""
import asyncio
import logging
import os

import httpx
from django.conf import settings
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "valiproject.settings")

logger = logging.getLogger("vali.asgi")

_django_app = get_asgi_application()
_loop_task: asyncio.Task | None = None

# Module-level state for the v2 /probe/relay view (sub-phase 2.9).
# Set in lifespan startup, cleared in shutdown. The view reads these
# via `from valiproject import asgi; asgi.RELAY_HTTPX` so it always
# sees the live values, not a stale import-time copy.
RELAY_HTTPX: httpx.AsyncClient | None = None
WALLET = None  # bittensor_wallet.Wallet — typed loosely to avoid the import here


def _build_relay_httpx_client() -> httpx.AsyncClient:
    """Construct the shared httpx.AsyncClient for /probe/relay forwards."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=settings.RELAY_FORWARD_CONNECT_S,
            read=settings.RELAY_FORWARD_READ_S,
            write=5.0,
            pool=5.0,
        ),
    )


async def application(scope, receive, send):
    global _loop_task, RELAY_HTTPX, WALLET

    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                from validator.loop import acquire_resources, run_validator_loop
                try:
                    # Acquire wallet lock + load wallet + connect to chain +
                    # fetch metagraph + resolve owner UID + fetch tempo
                    # SYNCHRONOUSLY in startup. If any of these fail (e.g.
                    # another vali-django on this host already holds the
                    # wallet, or the chain is unreachable past the retry
                    # budget), we send lifespan.startup.failed and the
                    # process exits without ever serving an HTTP request.
                    # This is what guarantees that a failed-to-start
                    # instance does not run a zombie web server against a
                    # DB it does not own.
                    wallet, subtensor, metagraph, owner_uid, tempo = await acquire_resources()
                except Exception as e:
                    logger.error(f"Startup failed: {e}")
                    await send({
                        "type": "lifespan.startup.failed",
                        "message": str(e),
                    })
                    return

                # Stash the wallet + build the relay httpx client. Both
                # are needed by the v2 /probe/relay view; both fail
                # quietly to None if the lifespan didn't run, and the
                # view returns 503 in that case.
                WALLET = wallet
                RELAY_HTTPX = _build_relay_httpx_client()
                logger.info("Built RELAY_HTTPX (timeouts from settings)")

                logger.info("Starting background validator loop")
                _loop_task = asyncio.create_task(
                    run_validator_loop(wallet, subtensor, metagraph, owner_uid, tempo)
                )
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                if _loop_task is not None:
                    logger.info("Cancelling background validator loop")
                    _loop_task.cancel()
                    try:
                        await _loop_task
                    except (asyncio.CancelledError, Exception):
                        pass
                if RELAY_HTTPX is not None:
                    logger.info("Closing RELAY_HTTPX")
                    try:
                        await RELAY_HTTPX.aclose()
                    except Exception:
                        pass
                    RELAY_HTTPX = None
                WALLET = None
                await send({"type": "lifespan.shutdown.complete"})
                return
    else:
        await _django_app(scope, receive, send)
