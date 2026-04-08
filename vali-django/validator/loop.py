"""
Background validator loop. Runs as a single asyncio task started by the
ASGI lifespan handler in valiproject/asgi.py.

This is a STUB. The real chain logic — discover miners, dispatch probes,
audit transcripts, set weights — gets ported from safeguard/validator.py in
a follow-up. For now the loop:

  1. Loads the wallet from VALIDATOR_WALLET/VALIDATOR_HOTKEY env vars
  2. Updates ValidatorStatus.last_tick_at every iteration
  3. Logs a heartbeat
  4. Catches its own exceptions, records them on ValidatorStatus, and
     keeps ticking — the loop itself does not crash the pod. The pod
     dies only if the asyncio task is cancelled or the process exits.

Crash-recovery philosophy: this loop does NOT self-restart with os.execv
or threads-with-watchdog. If the loop catches an unrecoverable error it
re-raises and the lifespan task dies, which closes the ASGI app, which
makes /healthz fail, which makes k8s restart the pod. That's the only
restart path. One owner of restarts: k8s.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timezone

from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone as djtz

from .models import ValidatorStatus
from .wallet import load_wallet, WalletLoadError
from .wallet_lock import acquire as acquire_wallet_lock, WalletLockError

logger = logging.getLogger("vali.loop")


@sync_to_async
def _update_status(**fields) -> None:
    status = ValidatorStatus.get()
    for k, v in fields.items():
        setattr(status, k, v)
    status.save()


@sync_to_async
def _bump_tick() -> int:
    status = ValidatorStatus.get()
    status.loop_iteration += 1
    status.last_tick_at = djtz.now()
    status.save(update_fields=["loop_iteration", "last_tick_at"])
    return status.loop_iteration


async def acquire_resources():
    """Take the wallet lock and load the wallet. Called from the ASGI
    lifespan startup BEFORE the background loop task is created.

    On failure, raises and writes NOTHING to the DB. This is critical:
    multiple processes share the same sqlite/postgres DB, and the
    ValidatorStatus row belongs to whichever process currently holds the
    wallet lock. A process that failed to acquire the lock has no business
    touching that row — it would clobber the healthy holder's status. The
    lockfile is the gate: pass it, then you can write status.
    """
    # Layer 1 of double-submit protection: flock a sentinel file next to
    # the hotkey. Catches another vali-django on this host. Does NOT catch
    # safeguard/validator.py or remote processes — see the layer-2 on-chain
    # check at the future set_weights call site below.
    acquire_wallet_lock(settings.VALIDATOR_WALLET, settings.VALIDATOR_HOTKEY)

    # Wallet load. If the lock succeeded but wallet load fails, we still
    # release nothing (lock is held for process lifetime); the process
    # will exit on the raised exception and the OS will release the lock.
    wallet = load_wallet()

    # Only NOW write to DB. We hold the lock, the status row is ours.
    await _update_status(
        wallet_loaded=True,
        wallet_hotkey_ss58=wallet.hotkey.ss58_address,
        last_chain_error="",
        last_chain_error_at=None,
    )
    return wallet


async def run_validator_loop(wallet) -> None:
    interval = settings.LOOP_INTERVAL_S
    logger.info(f"Validator loop starting (interval={interval}s)")

    while True:
        try:
            iteration = await _bump_tick()
            if iteration % 25 == 0:
                logger.info(f"Validator loop heartbeat (iter={iteration})")

            # TODO: port from safeguard/validator.py
            #   - discover miners (commitments + metagraph sync)
            #   - dispatch probes against RegisteredTarget rows
            #   - audit returned transcripts
            #   - update MinerScore
            #   - set_weights, then update last_set_weights_{at,block}
            #
            # Each chain RPC must go through a per-call timeout wrapper
            # (see safeguard/validator.py:72-86 for the pattern). Inside
            # an async loop the equivalent is asyncio.wait_for() around
            # asyncio.to_thread(...).
            #
            # Note on double-submit: the chain enforces a one-set_weights-
            # per-tempo rate limit per (hotkey, netuid). If another process
            # using the same hotkey beats us to it, our extrinsic just gets
            # rejected — atomic, no state corruption, no emissions impact.
            # The wallet_lock.py layer-1 lockfile catches the friendly case
            # of another vali-django on the same host with a clean error.
            #
            # Optional ergonomic improvement: before calling set_weights,
            # query the chain for the most recent weight-set from our
            # hotkey on this netuid; if it's within the current tempo and
            # wasn't us, skip our submission and save the wasted compute.
            # NOT required for correctness — the chain handles that — just
            # avoids spending a tempo's worth of probing on an extrinsic
            # that will be rejected. Defer until we actually see this
            # happen in practice.

        except asyncio.CancelledError:
            logger.info("Validator loop cancelled")
            raise
        except Exception as e:  # noqa: BLE001
            logger.exception("Validator loop iteration error")
            await _update_status(
                last_chain_error=f"{type(e).__name__}: {e}",
                last_chain_error_at=djtz.now(),
            )

        await asyncio.sleep(interval)
