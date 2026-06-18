"""LLM Service adapter for MBclaw-Lite.

Supports:
  • OpenAI-compatible APIs (OpenAI, DeepSeek, Groq, local vLLM)
  • Ollama (local)
  • Configurable via environment variables

Usage:
  from app.services.llm_service import get_llm
  llm = get_llm()
  response = await llm("Hello, how are you?")
"""

import os
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")  # openai | ollama
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_API_KEY = os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "2000"))
LLM_ENABLED = os.environ.get("LLM_ENABLED", "false").lower() == "true"


# ═══════════════════════════════════════════════════════════
# Provider implementations
# ═══════════════════════════════════════════════════════════

async def _openai_call(
    prompt: str,
    system_prompt: str = "",
    model: str = "",
    temperature: float = 0.0,
    max_tokens: int = 0,
) -> str:
    """Call OpenAI-compatible API."""
    import aiohttp

    model = model or LLM_MODEL
    temperature = temperature or LLM_TEMPERATURE
    max_tokens = max_tokens or LLM_MAX_TOKENS
    api_key = LLM_API_KEY
    base_url = LLM_BASE_URL or "https://api.openai.com/v1"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=body,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"LLM API error {resp.status}: {text[:200]}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]


async def _ollama_call(
    prompt: str,
    system_prompt: str = "",
    model: str = "",
    temperature: float = 0.0,
    max_tokens: int = 0,
) -> str:
    """Call local Ollama API."""
    import aiohttp

    model = model or LLM_MODEL or "llama3"
    temperature = temperature or LLM_TEMPERATURE
    base_url = LLM_BASE_URL or "http://localhost:11434"

    body = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens or LLM_MAX_TOKENS,
        },
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url.rstrip('/')}/api/generate",
            json=body,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Ollama error {resp.status}: {text[:200]}")
            data = await resp.json()
            return data["response"]


# ═══════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════

async def _noop_call(*args, **kwargs) -> str:
    """No-op LLM call — returns empty string when LLM is disabled."""
    return ""


def get_llm(
    provider: str = "",
    model: str = "",
    api_key: str = "",
    base_url: str = "",
) -> Any:
    """Get an LLM callable (async function).

    Returns an async callable: llm(prompt, system_prompt="", ...) -> str

    If LLM_ENABLED is False or no API key configured, returns a no-op.
    """
    provider = provider or LLM_PROVIDER

    if not LLM_ENABLED:
        return _noop_call

    if provider == "ollama":
        return _ollama_call

    # OpenAI-compatible
    if not LLM_API_KEY and not api_key:
        return _noop_call

    return _openai_call


def configure_llm(
    provider: str = "",
    model: str = "",
    api_key: str = "",
    base_url: str = "",
    enabled: bool = True,
):
    """Configure LLM at runtime (updates globals)."""
    global LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, LLM_BASE_URL, LLM_ENABLED
    if provider:
        LLM_PROVIDER = provider
    if model:
        LLM_MODEL = model
    if api_key:
        LLM_API_KEY = api_key
    if base_url:
        LLM_BASE_URL = base_url
    LLM_ENABLED = enabled


def get_llm_config() -> dict:
    """Return current LLM config for display."""
    return {
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
        "enabled": LLM_ENABLED,
        "base_url": LLM_BASE_URL or "(default)",
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
    }
