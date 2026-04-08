"""
Wallet loading. The user said: "just read the effing file bro."

VALIDATOR_WALLET=<coldkey-name> and VALIDATOR_HOTKEY=<hotkey-name> point at
~/.bittensor/wallets/<wallet>/hotkeys/<hotkey>. We resolve the path
ourselves and hand it to bittensor_wallet.Wallet — no env-var indirection
inside the bittensor library, no surprises about which wallet got loaded.
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger("vali.wallet")

WALLETS_DIR = Path.home() / ".bittensor" / "wallets"


class WalletLoadError(RuntimeError):
    pass


def wallet_path(wallet_name: str, hotkey_name: str) -> Path:
    return WALLETS_DIR / wallet_name / "hotkeys" / hotkey_name


def load_wallet():
    """Resolve and instantiate the configured wallet. Raises WalletLoadError
    with a clear message if the file isn't where we expect."""
    wallet_name = settings.VALIDATOR_WALLET
    hotkey_name = settings.VALIDATOR_HOTKEY
    if not wallet_name or not hotkey_name:
        raise WalletLoadError(
            "VALIDATOR_WALLET and VALIDATOR_HOTKEY must both be set"
        )

    hotkey_file = wallet_path(wallet_name, hotkey_name)
    if not hotkey_file.exists():
        raise WalletLoadError(f"Hotkey file not found: {hotkey_file}")

    from bittensor_wallet import Wallet
    wallet = Wallet(name=wallet_name, hotkey=hotkey_name)
    # Touch the hotkey to force-load it; raises if the file is malformed.
    _ = wallet.hotkey.ss58_address
    logger.info(
        f"Loaded wallet {wallet_name}/{hotkey_name} → {wallet.hotkey.ss58_address}"
    )
    return wallet
