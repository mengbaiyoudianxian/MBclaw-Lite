"""T2.1 — LLM client for session summarisation.

Single-responsibility: call OpenAI-compatible /chat/completions,
parse the result into a validated LLMOutput.
"""

import json
import os

import httpx
from pydantic import BaseModel, Field


# ── exceptions ───────────────────────────────────────────────

class LLMError(Exception):
    """Raised when the LLM call fails after retries."""


# ── output model ─────────────────────────────────────────────

class _Experience(BaseModel):
    kind: str = Field(default="lesson")
    title: str = Field(max_length=80, default="")
    content: str = Field(max_length=500, default="")


class LLMOutput(BaseModel):
    summary: str = Field(max_length=400, default="")
    keywords: list[str] = Field(max_length=10, default_factory=list)
    experiences: list[_Experience] = Field(max_length=5, default_factory=list)


# ── prompt template (hardcoded, single) ──────────────────────

_SUMMARISE_PROMPT = """\
分析以下对话，严格输出 JSON：
{{
  "summary": "≤300字概括用户目标/达成结论/未决问题",
  "keywords": ["最多10个"],
  "experiences": [{{"kind":"success|failure|lesson","title":"≤80字","content":"≤500字"}}]
}}
experiences 最多 5 条。没有则空数组。
对话：
{messages_text}"""


# ── client ───────────────────────────────────────────────────

class LLMClient:
    """OpenAI-compatible chat-completions client.

    Reads credentials from env vars unless explicitly passed.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        self.base_url = (base_url or os.getenv("MBCLAW_LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("MBCLAW_LLM_API_KEY", "")
        self.model = model or os.getenv("MBCLAW_LLM_MODEL", "gpt-4o-mini")

    def summarize_session(self, messages: list[dict]) -> LLMOutput:
        """Send conversation messages to LLM, return structured output.

        Retries once on transient failure; raises LLMError if both attempts fail.
        """
        if os.getenv("MBCLAW_LLM_MOCK") == "1":
            return LLMOutput(
                summary="[MOCK] 对话摘要。",
                keywords=["mock"],
                experiences=[],
            )

        if not self.api_key:
            raise LLMError("LLM API key not configured. Set MBCLAW_LLM_API_KEY.")

        text = "\n".join(
            f"[{m.get('role', 'unknown')}]: {m.get('content', '')}" for m in messages
        )
        prompt = _SUMMARISE_PROMPT.format(messages_text=text)

        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        last_error: Exception | None = None
        for attempt in (1, 2):
            try:
                resp = httpx.post(url, headers=headers, json=body, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                raw = data["choices"][0]["message"]["content"]
                parsed = json.loads(raw)
                return LLMOutput(**parsed)
            except Exception as exc:
                last_error = exc
                if attempt == 2:
                    raise LLMError(f"LLM summarisation failed after 2 attempts: {last_error}") from last_error
        # unreachable — kept for type checker
        raise LLMError("unreachable")


# ── DI helper ────────────────────────────────────────────────

def get_llm() -> LLMClient:
    """FastAPI dependency: return a default-configured LLMClient."""
    return LLMClient()
