"""Shared test fixtures for Safeguard tests."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add safeguard root to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_wallet():
    """A mock wallet with a working hotkey for Epistula signing."""
    from bittensor_wallet.keypair import Keypair

    keypair = Keypair.create_from_mnemonic(Keypair.generate_mnemonic())

    # Keypair is a C extension with read-only attributes, so just use it directly
    # as the wallet.hotkey — wrap in a simple namespace
    class WalletLike:
        def __init__(self, kp):
            self.hotkey = kp
    return WalletLike(keypair)


