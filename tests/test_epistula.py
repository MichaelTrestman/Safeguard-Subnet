"""Tests for Epistula HTTP authentication module."""

import time
import pytest
from epistula import create_epistula_headers, verify_epistula


class TestCreateEpistulaHeaders:
    def test_returns_three_headers(self, mock_wallet):
        headers = create_epistula_headers(mock_wallet, b"test body")
        assert "X-Epistula-Timestamp" in headers
        assert "X-Epistula-Signature" in headers
        assert "X-Epistula-Hotkey" in headers

    def test_hotkey_matches_wallet(self, mock_wallet):
        headers = create_epistula_headers(mock_wallet, b"test")
        assert headers["X-Epistula-Hotkey"] == mock_wallet.hotkey.ss58_address

    def test_timestamp_is_recent_nanoseconds(self, mock_wallet):
        headers = create_epistula_headers(mock_wallet, b"test")
        ts = int(headers["X-Epistula-Timestamp"])
        now_ns = int(time.time() * 1e9)
        assert abs(now_ns - ts) < 2e9  # within 2 seconds

    def test_empty_body_works(self, mock_wallet):
        headers = create_epistula_headers(mock_wallet, b"")
        assert len(headers["X-Epistula-Signature"]) > 0


class TestVerifyEpistula:
    def test_roundtrip_sign_verify(self, mock_wallet):
        body = b'{"prompt": "hello"}'
        headers = create_epistula_headers(mock_wallet, body)
        result = verify_epistula(
            timestamp=headers["X-Epistula-Timestamp"],
            signature=headers["X-Epistula-Signature"],
            hotkey=headers["X-Epistula-Hotkey"],
            body=body,
        )
        assert result == mock_wallet.hotkey.ss58_address

    def test_tampered_body_fails(self, mock_wallet):
        body = b"original"
        headers = create_epistula_headers(mock_wallet, body)
        with pytest.raises(ValueError, match="Invalid signature"):
            verify_epistula(
                timestamp=headers["X-Epistula-Timestamp"],
                signature=headers["X-Epistula-Signature"],
                hotkey=headers["X-Epistula-Hotkey"],
                body=b"tampered",
            )

    def test_stale_timestamp_fails(self, mock_wallet):
        body = b"test"
        headers = create_epistula_headers(mock_wallet, body)
        # Make timestamp 120 seconds old
        old_ts = str(int(time.time() * 1e9) - int(120e9))
        with pytest.raises(ValueError, match="too old"):
            verify_epistula(
                timestamp=old_ts,
                signature=headers["X-Epistula-Signature"],
                hotkey=headers["X-Epistula-Hotkey"],
                body=body,
            )

    def test_wrong_hotkey_fails(self, mock_wallet):
        from bittensor_wallet.keypair import Keypair

        body = b"test"
        headers = create_epistula_headers(mock_wallet, body)
        other_keypair = Keypair.create_from_mnemonic(Keypair.generate_mnemonic())
        with pytest.raises(ValueError, match="Invalid signature"):
            verify_epistula(
                timestamp=headers["X-Epistula-Timestamp"],
                signature=headers["X-Epistula-Signature"],
                hotkey=other_keypair.ss58_address,
                body=body,
            )

    def test_empty_body_roundtrip(self, mock_wallet):
        body = b""
        headers = create_epistula_headers(mock_wallet, body)
        result = verify_epistula(
            timestamp=headers["X-Epistula-Timestamp"],
            signature=headers["X-Epistula-Signature"],
            hotkey=headers["X-Epistula-Hotkey"],
            body=body,
        )
        assert result == mock_wallet.hotkey.ss58_address
