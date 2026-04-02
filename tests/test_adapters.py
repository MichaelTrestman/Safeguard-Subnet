"""Tests for the generic relay adapter."""

import json
import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock
from adapters.generic import GenericRelayAdapter


class TestGenericRelayAdapter:
    def test_creates_epistula_headers(self, mock_wallet):
        adapter = GenericRelayAdapter(mock_wallet)
        body = b'{"test": true}'
        headers = adapter._create_epistula_headers(body)
        assert "X-Epistula-Timestamp" in headers
        assert "X-Epistula-Signature" in headers
        assert "X-Epistula-Hotkey" in headers
        assert headers["X-Epistula-Hotkey"] == mock_wallet.hotkey.ss58_address

    @pytest.mark.asyncio
    async def test_send_turn_makes_correct_request(self, mock_wallet):
        adapter = GenericRelayAdapter(mock_wallet)

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "I'm an AI assistant.", "session_id": "s1"}
        mock_response.raise_for_status = MagicMock()

        with patch("adapters.generic.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await adapter.send_turn(
                target_validator_endpoint="http://target:9000",
                prompt="Hello",
                session_id="s1",
            )

            assert result == "I'm an AI assistant."
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://target:9000/relay"
            # Verify body contains prompt and session_id
            sent_body = json.loads(call_args[1]["content"])
            assert sent_body["prompt"] == "Hello"
            assert sent_body["session_id"] == "s1"

    @pytest.mark.asyncio
    async def test_send_turn_http_error_propagates(self, mock_wallet):
        adapter = GenericRelayAdapter(mock_wallet)

        with patch("adapters.generic.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            with pytest.raises(httpx.ConnectError):
                await adapter.send_turn(
                    target_validator_endpoint="http://target:9000",
                    prompt="Hello",
                    session_id="s1",
                )
