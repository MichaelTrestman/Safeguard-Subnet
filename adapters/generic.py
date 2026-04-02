"""
Generic relay adapter.

Sends prompts to a target validator's /relay endpoint using Epistula
authentication. This works for any subnet that implements the standard
Safeguard relay protocol (see RELAY_PROTOCOL.md).

For subnets with non-standard relay interfaces, create a subnet-specific
adapter that inherits from or replaces this one.
"""

import time
import hashlib
import json
import logging

import httpx
from bittensor_wallet import Wallet

logger = logging.getLogger(__name__)


class GenericRelayAdapter:
    """
    Adapter for subnets implementing the standard /relay protocol.

    Usage:
        adapter = GenericRelayAdapter(wallet)
        response = await adapter.send_turn(
            target_validator_endpoint="http://target-validator:9000",
            prompt="Hello, can you help me with something?",
            session_id="some-uuid",
        )
    """

    def __init__(self, wallet: Wallet, timeout: float = 30.0):
        self.wallet = wallet
        self.timeout = timeout

    def _create_epistula_headers(self, body: bytes) -> dict:
        nonce = str(int(time.time() * 1e9))
        body_hash = hashlib.sha256(body).hexdigest()
        message = f"{nonce}.{body_hash}"
        signature = self.wallet.hotkey.sign(message.encode()).hex()
        return {
            "X-Epistula-Timestamp": nonce,
            "X-Epistula-Signature": signature,
            "X-Epistula-Hotkey": self.wallet.hotkey.ss58_address,
        }

    async def send_turn(
        self,
        target_validator_endpoint: str,
        prompt: str,
        session_id: str,
    ) -> str:
        """
        Send a single conversation turn through the target validator's relay.

        Args:
            target_validator_endpoint: URL of the target subnet validator
            prompt: The prompt to forward to the target miner
            session_id: UUID grouping this conversation's turns

        Returns:
            The target miner's response text.

        Raises:
            httpx.HTTPError: On network or HTTP errors.
            ValueError: On malformed response.
        """
        relay_body = {"prompt": prompt, "session_id": session_id}
        body_bytes = json.dumps(relay_body).encode()
        headers = self._create_epistula_headers(body_bytes)
        headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{target_validator_endpoint}/relay",
                content=body_bytes,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
