"""Tests for LLM judge module."""

import pytest
import httpx
from unittest.mock import patch, MagicMock
from llm_judge import _format_transcript, classify_transcript, judge_transcript


class TestFormatTranscript:
    def test_formats_roles(self):
        transcript = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = _format_transcript(transcript)
        assert "[USER]: Hello" in result
        assert "[ASSISTANT]: Hi there" in result

    def test_handles_empty_transcript(self):
        assert _format_transcript([]) == ""

    def test_handles_missing_fields(self):
        transcript = [{"role": "user"}, {"content": "orphan"}]
        result = _format_transcript(transcript)
        assert "[USER]:" in result
        assert "[UNKNOWN]: orphan" in result


class TestClassifyTranscript:
    @patch("llm_judge.os.getenv", return_value="")
    def test_no_api_key_returns_placeholder(self, mock_env):
        score, conf = classify_transcript([{"role": "user", "content": "hi"}])
        assert score == 0.5
        assert conf == 0.0

    @patch("llm_judge.httpx.post")
    @patch("llm_judge.os.getenv")
    def test_parses_valid_response(self, mock_env, mock_post):
        mock_env.side_effect = lambda k, default="": {
            "CHUTES_API_KEY": "test-key",
            "CHUTES_MODEL_TIER2": "test-model",
        }.get(k, default)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"unsafe_prob": 0.8, "confidence": 0.9}'}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        score, conf = classify_transcript([{"role": "assistant", "content": "bad stuff"}])
        assert score == 0.8
        assert conf == 0.9

    @patch("llm_judge.httpx.post")
    @patch("llm_judge.os.getenv")
    def test_handles_markdown_fenced_json(self, mock_env, mock_post):
        mock_env.side_effect = lambda k, default="": {
            "CHUTES_API_KEY": "test-key",
            "CHUTES_MODEL_TIER2": "test-model",
        }.get(k, default)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '```json\n{"unsafe_prob": 0.6, "confidence": 0.85}\n```'}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        score, conf = classify_transcript([{"role": "assistant", "content": "stuff"}])
        assert score == 0.6
        assert conf == 0.85

    @patch("llm_judge.httpx.post", side_effect=httpx.ConnectError("network error"))
    @patch("llm_judge.os.getenv")
    def test_network_error_returns_placeholder(self, mock_env, mock_post):
        mock_env.side_effect = lambda k, default="": {
            "CHUTES_API_KEY": "test-key",
            "CHUTES_MODEL_TIER2": "test-model",
        }.get(k, default)
        score, conf = classify_transcript([])
        assert score == 0.5
        assert conf == 0.0


class TestJudgeTranscript:
    @patch("llm_judge.os.getenv", return_value="")
    def test_no_api_key_returns_placeholder(self, mock_env):
        score, conf = judge_transcript([{"role": "user", "content": "hi"}])
        assert score == 0.5
        assert conf == 0.0
