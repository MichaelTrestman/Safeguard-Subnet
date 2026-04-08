"""
ASGI entrypoint with a lifespan handler that owns the background validator
loop. The loop is started in the lifespan startup event and cancelled on
shutdown — one process, one event loop, no threads.

This is the entrypoint k8s + uvicorn use in production. `manage.py runserver`
uses WSGI and will NOT start the background loop, which is intentional: dev
server is for poking views, not for running the validator.
"""
import asyncio
import logging
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "valiproject.settings")

logger = logging.getLogger("vali.asgi")

_django_app = get_asgi_application()
_loop_task: asyncio.Task | None = None


async def application(scope, receive, send):
    global _loop_task

    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                from validator.loop import acquire_resources, run_validator_loop
                try:
                    # Acquire wallet lock + load wallet SYNCHRONOUSLY in
                    # startup. If this fails (e.g. another vali-django on
                    # this host already holds the wallet) we send
                    # lifespan.startup.failed and the process exits without
                    # ever serving an HTTP request. This is what guarantees
                    # that a failed-to-start instance does not run a zombie
                    # web server against a DB it does not own.
                    wallet = await acquire_resources()
                except Exception as e:
                    logger.error(f"Startup failed: {e}")
                    await send({
                        "type": "lifespan.startup.failed",
                        "message": str(e),
                    })
                    return
                logger.info("Starting background validator loop")
                _loop_task = asyncio.create_task(run_validator_loop(wallet))
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                if _loop_task is not None:
                    logger.info("Cancelling background validator loop")
                    _loop_task.cancel()
                    try:
                        await _loop_task
                    except (asyncio.CancelledError, Exception):
                        pass
                await send({"type": "lifespan.shutdown.complete"})
                return
    else:
        await _django_app(scope, receive, send)
