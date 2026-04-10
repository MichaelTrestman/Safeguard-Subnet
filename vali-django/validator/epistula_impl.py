"""
Epistula: HTTP authentication for Bittensor subnet communication.

Uses 3 headers to authenticate requests between validators and miners:
- X-Epistula-Timestamp: nanosecond unix timestamp (nonce)
- X-Epistula-Signature: hotkey signature of "{timestamp}.{sha256(body).hex()}"
- X-Epistula-Hotkey: SS58 address of the signing hotkey
"""

import time
import hashlib
from bittensor_wallet.keypair import Keypair

MAX_REQUEST_AGE = 60  # seconds


def create_epistula_headers(wallet, body: bytes) -> dict:
    """
    Create Epistula authentication headers for an HTTP request.

    Args:
        wallet: Bittensor wallet with hotkey
        body: Request body as bytes (use b'' for GET requests)

    Returns:
        Dictionary of authentication headers.
    """
    nonce = str(int(time.time() * 1e9))
    body_hash = hashlib.sha256(body).hexdigest()
    message = f"{nonce}.{body_hash}"
    signature = wallet.hotkey.sign(message.encode()).hex()

    return {
        "X-Epistula-Timestamp": nonce,
        "X-Epistula-Signature": signature,
        "X-Epistula-Hotkey": wallet.hotkey.ss58_address,
    }


def verify_epistula(
    timestamp: str,
    signature: str,
    hotkey: str,
    body: bytes,
) -> str:
    """
    Verify Epistula authentication headers.

    Args:
        timestamp: X-Epistula-Timestamp header value
        signature: X-Epistula-Signature header value
        hotkey: X-Epistula-Hotkey header value
        body: Request body as bytes

    Returns:
        The verified hotkey SS58 address.

    Raises:
        ValueError: If verification fails (stale timestamp, bad signature).
    """
    request_time = int(timestamp) / 1e9
    if abs(time.time() - request_time) > MAX_REQUEST_AGE:
        raise ValueError(
            f"Request timestamp too old: {abs(time.time() - request_time):.1f}s"
        )

    body_hash = hashlib.sha256(body).hexdigest()
    message = f"{timestamp}.{body_hash}"

    keypair = Keypair(ss58_address=hotkey)
    if not keypair.verify(message.encode(), bytes.fromhex(signature)):
        raise ValueError("Invalid signature")

    return hotkey
