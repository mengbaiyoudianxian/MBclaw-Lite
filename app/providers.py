"""Multi-provider LLM dispatch — supports OpenAI, Anthropic, local models."""

import os
from app.llm import LLMClient


_PROVIDERS = {
    "openai": {"base_url": "https://api.openai.com/v1", "env_key": "OPENAI_API_KEY"},
    "anthropic": {"base_url": "https://api.anthropic.com/v1", "env_key": "ANTHROPIC_API_KEY"},
    "local": {"base_url": "http://localhost:11434/v1", "env_key": None},
}


def get_available_providers() -> list[dict]:
    """List all configured providers with status."""
    result = []
    for name, cfg in _PROVIDERS.items():
        key = os.getenv(cfg["env_key"]) if cfg["env_key"] else None
        active = bool(key) or name == "local"
        result.append({"name": name, "base_url": cfg["base_url"], "active": active, "configured": bool(key)})
    return result


def get_best_provider() -> LLMClient:
    """Return the best available LLM client with automatic failover."""
    env_key = os.getenv("MBCLAW_LLM_API_KEY")
    if env_key:
        return LLMClient()

    for name in ("openai", "anthropic", "local"):
        cfg = _PROVIDERS[name]
        key = os.getenv(cfg["env_key"]) if cfg["env_key"] else None
        if key or name == "local":
            return LLMClient(base_url=cfg["base_url"], api_key=key or "", model=os.getenv("MBCLAW_LLM_MODEL", "gpt-4o-mini"))
    return LLMClient()
