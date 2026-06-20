"""OpenAI-compatible adapter (generic, shared by DeepSeek/Groq/local vLLM)."""

import os
from typing import Any

OPENAI_DEFAULT_MODEL = os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")


class OpenAIAdapter:
    """Generic OpenAI-compatible API adapter."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ):
        self.api_key = api_key or os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "")).rstrip("/") or "https://api.openai.com/v1"
        self.model = model or OPENAI_DEFAULT_MODEL
        self._token_usage = 0

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        model: str = "",
    ) -> dict[str, Any]:
        import aiohttp

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=body,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"OpenAI API 错误 {resp.status}: {text[:200]}")
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                self._token_usage += usage.get("total_tokens", 0)
                return {
                    "content": content,
                    "usage": {"input": usage.get("prompt_tokens", 0), "output": usage.get("completion_tokens", 0)},
                    "model": data.get("model", model or self.model),
                }

    async def chat_simple(self, prompt: str, system_prompt: str = "", **kw) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        result = await self.chat(messages, **kw)
        return result["content"]

    def to_dict(self) -> dict:
        return {
            "provider": "openai",
            "model": self.model,
            "base_url": self.base_url,
            "has_key": bool(self.api_key),
            "token_usage": self._token_usage,
        }
