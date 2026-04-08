"""
Wallet lock — refuses to start if another vali-django process on this host
is already running against the same wallet/hotkey.

This is layer 1 of two-layer protection against double-submitting set_weights
extrinsics. It catches the friendly case: an operator forgot to shut down a
prior vali-django container before starting a new one. It does NOT catch:

  - safeguard/validator.py running against the same wallet (no shared
    lockfile convention)
  - a vali-django instance on a different host using the same wallet
    (lockfile is local-fs only)
  - any third-party validator software using the same hotkey

For those cases see layer 2 in loop.py: an on-chain check that the most
recent set_weights extrinsic from our hotkey was actually ours, run
*before* every set_weights call. Layer 2 is the universal defense; layer 1
just gives a faster, friendlier error in the common single-host case.

Mechanism: fcntl.flock(LOCK_EX | LOCK_NB) on a sentinel file next to the
hotkey. The lock is held for the lifetime of the process and released by
the OS on process death — no stale-lock cleanup logic needed.
"""
from __future__ import annotations

import fcntl
import logging
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

from .wallet import wallet_path

logger = logging.getLogger("vali.lock")


class WalletLockError(RuntimeError):
    pass


_held_fd: int | None = None  # module-level so the fd survives function return


def lock_path(wallet_name: str, hotkey_name: str) -> Path:
    return wallet_path(wallet_name, hotkey_name).parent / f"{hotkey_name}.vali-django.lock"


def acquire(wallet_name: str, hotkey_name: str) -> Path:
    """Take an exclusive non-blocking flock on the sentinel file. Raises
    WalletLockError if another process holds it. The fd is intentionally
    leaked into module scope so the lock survives function return — it is
    released only when this process exits."""
    global _held_fd

    path = lock_path(wallet_name, hotkey_name)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        # Read whatever the holder wrote into the file for a useful error.
        try:
            holder_info = path.read_text(errors="replace").strip() or "(empty)"
        except OSError:
            holder_info = "(unreadable)"
        raise WalletLockError(
            f"Wallet {wallet_name}/{hotkey_name} is locked by another process "
            f"on this host. Holder info: {holder_info}\n"
            f"Lockfile: {path}\n"
            f"If you are sure no other vali-django is running, the OS will "
            f"release the lock automatically when the holding process dies. "
            f"This lock does NOT detect safeguard/validator.py or remote "
            f"processes — see loop.py layer-2 chain check for those."
        )

    # Overwrite contents with our identity for human debugging.
    holder = (
        f"pid={os.getpid()} "
        f"host={socket.gethostname()} "
        f"started={datetime.now(timezone.utc).isoformat()}\n"
    )
    os.ftruncate(fd, 0)
    os.write(fd, holder.encode())
    os.fsync(fd)

    _held_fd = fd
    logger.info(f"Acquired wallet lock: {path}")
    return path
