"""T6.1 — Unit tests for app.llm (T2.1)."""

import importlib
import json
import os

import httpx
import pytest
from unittest.mock import patch, MagicMock


def _fresh_llm():
    """Reload app.llm so test-isolation across other test files is clean."""
    os.environ.pop("MBCLAW_LLM_MOCK", None)
    """Reload app.llm so test-isolation across other test files is clean."""
    importlib.reload(importlib.import_module("app.llm"))
    from app.llm import LLMOutput, LLMClient, LLMError, _Experience
    return LLMOutput, LLMClient, LLMError, _Experience


# ── LLMOutput validation ────────────────────────────────────

def test_llm_output_valid():
    LLMOutput, _, _, _ = _fresh_llm()
    out = LLMOutput(summary="done", keywords=["a", "b"], experiences=[])
    assert out.summary == "done"


def test_llm_output_rejects_overlong_summary():
    LLMOutput, _, _, _ = _fresh_llm()
    with pytest.raises(Exception):
        LLMOutput(summary="x" * 401, keywords=[], experiences=[])


def test_llm_output_rejects_too_many_keywords():
    LLMOutput, _, _, _ = _fresh_llm()
    with pytest.raises(Exception):
        LLMOutput(summary="ok", keywords=["k"] * 11, experiences=[])


# ── LLMClient config ────────────────────────────────────────

def test_client_reads_env_vars():
    _, LLMClient, _, _ = _fresh_llm()
    os.environ["MBCLAW_LLM_BASE_URL"] = "http://localhost:9999/v1"
    os.environ["MBCLAW_LLM_API_KEY"] = "test-key"
    os.environ["MBCLAW_LLM_MODEL"] = "test-model"
    c = LLMClient()
    assert c.base_url == "http://localhost:9999/v1"
    assert c.api_key == "test-key"
    assert c.model == "test-model"


def test_client_prefers_explicit_args():
    _, LLMClient, _, _ = _fresh_llm()
    os.environ["MBCLAW_LLM_MODEL"] = "env-model"
    c = LLMClient(model="explicit-model")
    assert c.model == "explicit-model"


# ── summarise_session (mocked httpx) ────────────────────────

def test_summarize_session_returns_valid_output():
    LLMOutput, LLMClient, LLMError, _ = _fresh_llm()
    fake_response = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "summary": "User chose SQLite FTS5.",
                    "keywords": ["sqlite", "fts5"],
                    "experiences": [
                        {"kind": "success", "title": "Picked FTS5", "content": "FTS5 works well."}
                    ]
                })
            }
        }]
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = fake_response
    with patch.object(httpx, "post", return_value=mock_resp):
        c = LLMClient(base_url="http://fake", api_key="k", model="m")
        out = c.summarize_session([
            {"role": "user", "content": "Let us use FTS5."},
            {"role": "assistant", "content": "Agreed."}
        ])
    assert isinstance(out, LLMOutput)
    assert "FTS5" in out.summary


def test_summarize_session_raises_after_two_failures():
    _, LLMClient, LLMError, _ = _fresh_llm()
    with patch.object(httpx, "post", side_effect=httpx.ConnectError("down")):
        c = LLMClient(base_url="http://fake", api_key="k", model="m")
        with pytest.raises(LLMError):
            c.summarize_session([{"role": "user", "content": "hi"}])

def test_summarize_session_rejects_empty_api_key():
    """Empty API key → LLMError with clear message, no HTTP call."""
    _, LLMClient, LLMError, _ = _fresh_llm()
    c = LLMClient(base_url="http://fake", api_key="", model="m")
    with pytest.raises(LLMError, match="MBCLAW_LLM_API_KEY"):
        c.summarize_session([{"role": "user", "content": "hi"}])
