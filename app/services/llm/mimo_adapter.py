"""MiMo Code API adapter.

MiMo (MiMo Code) is a coding-focused LLM provider.
API: https://api.mimo.run/v1/chat/completions (OpenAI-compatible)
Free trial: 1 month, then paid.

This adapter:
  - Wraps MiMo's OpenAI-compatible endpoint
  - Tracks trial status, token usage, and expiry
  - Supports regression detection (checking if MiMo reverted our changes)
"""

import json
import os
import time
from datetime import datetime
from typing import Any, Optional

MIMO_BASE_URL = os.environ.get("MIMO_BASE_URL", "https://api.mimo.run/v1")
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_DEFAULT_MODEL = os.environ.get("MIMO_MODEL", "mimo-code-v1")


class MiMoAdapter:
    """Adapter for the MiMo Code API (OpenAI-compatible)."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ):
        self.api_key = api_key or MIMO_API_KEY
        self.base_url = (base_url or MIMO_BASE_URL).rstrip("/")
        self.model = model or MIMO_DEFAULT_MODEL
        self._trial_start = None
        self._token_usage = 0

    # ── trial tracking ──────────────────────────────

    @property
    def trial_started_at(self) -> Optional[str]:
        return self._trial_start

    def start_trial(self) -> str:
        """Record trial start and return expiry (1 month)."""
        self._trial_start = datetime.now().isoformat()
        expiry = datetime.now().replace(month=datetime.now().month % 12 + 1)
        return expiry.isoformat()

    def trial_days_remaining(self) -> int:
        """Days left in the 1-month trial, or -1 if not started."""
        if not self._trial_start:
            return -1
        start = datetime.fromisoformat(self._trial_start)
        elapsed = (datetime.now() - start).days
        return max(0, 30 - elapsed)

    @property
    def token_usage(self) -> int:
        return self._token_usage

    # ── core call ──────────────────────────────────

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        model: str = "",
    ) -> dict[str, Any]:
        """Send chat completion request to MiMo.

        Returns: {"content": str, "usage": {"input": int, "output": int}, "model": str}
        Raises RuntimeError on API error.
        """
        import aiohttp

        model = model or self.model
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
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
                url,
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status == 401:
                    raise RuntimeError("MiMo API Key 无效或已过期，请检查配置")
                if resp.status == 402:
                    raise RuntimeError("MiMo 试用期已结束，请升级套餐")
                if resp.status == 429:
                    raise RuntimeError("MiMo API 请求频率过高，请稍后重试")
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"MiMo API 错误 {resp.status}: {text[:200]}")

                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                self._token_usage += usage.get("total_tokens", 0)

                return {
                    "content": content,
                    "usage": {
                        "input": usage.get("prompt_tokens", 0),
                        "output": usage.get("completion_tokens", 0),
                    },
                    "model": data.get("model", model),
                }

    async def chat_simple(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """Convenience wrapper — returns just the text content."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        result = await self.chat(messages, temperature, max_tokens)
        return result["content"]

    # ── health check ───────────────────────────────

    async def test_connection(self) -> dict[str, Any]:
        """Test MiMo API connectivity with a minimal request."""
        try:
            result = await self.chat(
                [{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return {
                "success": True,
                "model": result["model"],
                "status": "active",
                "trial_days_remaining": self.trial_days_remaining(),
                "message": "MiMo 连接正常",
            }
        except RuntimeError as e:
            return {
                "success": False,
                "status": "error",
                "error": str(e),
            }

    # ── helpers ────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "provider": "mimo",
            "model": self.model,
            "base_url": self.base_url,
            "has_key": bool(self.api_key),
            "trial_days_remaining": self.trial_days_remaining(),
            "token_usage": self._token_usage,
        }


# ── singleton ─────────────────────────────────

_mimo_instance: Optional[MiMoAdapter] = None


def get_mimo(
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> MiMoAdapter:
    """Get or create MiMo adapter singleton."""
    global _mimo_instance
    if api_key or base_url or model:
        # Recreate with new config
        _mimo_instance = MiMoAdapter(api_key=api_key, base_url=base_url, model=model)
    elif _mimo_instance is None:
        _mimo_instance = MiMoAdapter()
    return _mimo_instance
