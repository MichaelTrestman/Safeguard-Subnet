"""
Challenge-response authentication using polkadot.js browser extension.

Flow:
1. Client requests a nonce for their SS58 address
2. Client signs the nonce with their hotkey via polkadot.js extension
3. Server verifies the signature using bittensor_wallet.Keypair
4. Server issues a session JWT

Adapted from taoapp/api/auth.py, simplified for local single-operator use.
"""

import re
import secrets
from datetime import datetime, timezone, timedelta

import jwt
from bittensor_wallet.keypair import Keypair

# Random secret per server lifetime — sessions don't survive restarts.
# Acceptable for a local tool.
_JWT_SECRET = secrets.token_hex(32)
_JWT_ALGORITHMS = ["HS256"]

NONCE_EXPIRY_MINUTES = 5
SESSION_EXPIRY_HOURS = 1

WALLET_ADDRESS_PATTERN = re.compile(r"^5[1-9A-HJ-NP-Za-km-z]{47}$")


def validate_address(address: str) -> bool:
    """Validate SS58 wallet address format."""
    return bool(WALLET_ADDRESS_PATTERN.match(address))


def generate_nonce() -> str:
    """Generate cryptographically secure nonce (32 bytes hex)."""
    return secrets.token_hex(32)


def create_nonce_token(nonce: str, address: str) -> str:
    """Create short-lived JWT containing nonce and address for verification."""
    now = datetime.now(timezone.utc)
    payload = {
        "nonce": nonce,
        "address": address,
        "purpose": "nonce",
        "iat": now,
        "exp": now + timedelta(minutes=NONCE_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def verify_nonce_token(token: str) -> dict | None:
    """Verify nonce token and return payload if valid."""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=_JWT_ALGORITHMS)
        if payload.get("purpose") != "nonce":
            return None
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def verify_signature(address: str, nonce: str, signature: str) -> bool:
    """
    Verify an SR25519 signature from the polkadot.js extension.

    The extension wraps payloads in <Bytes>...</Bytes> before signing
    when using type: 'bytes'. Keypair.verify handles this transparently.
    """
    try:
        keypair = Keypair(ss58_address=address)
        sig_hex = signature.removeprefix("0x")
        sig_bytes = bytes.fromhex(sig_hex)
        return keypair.verify(nonce.encode(), sig_bytes)
    except Exception:
        return False


def create_session_token(address: str) -> str:
    """Create a session JWT for an authenticated address."""
    now = datetime.now(timezone.utc)
    payload = {
        "address": address,
        "purpose": "session",
        "iat": now,
        "exp": now + timedelta(hours=SESSION_EXPIRY_HOURS),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def verify_session_token(token: str) -> str | None:
    """Verify session JWT, return address if valid."""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=_JWT_ALGORITHMS)
        if payload.get("purpose") != "session":
            return None
        address = payload.get("address")
        if not isinstance(address, str) or not WALLET_ADDRESS_PATTERN.match(address):
            return None
        return address
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
