"""LLM configuration and status endpoints."""

from fastapi import APIRouter, HTTPException
from app.services.llm_service import get_llm_config, configure_llm

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/status")
def llm_status():
    """Get current LLM configuration."""
    return get_llm_config()


@router.post("/configure")
def llm_configure(
    provider: str = "",
    model: str = "",
    api_key: str = "",
    base_url: str = "",
    enabled: bool = True,
):
    """Configure LLM at runtime.

    Supported providers: openai (OpenAI-compatible API), ollama (localhost:11434).

    Examples:
      # OpenAI
      provider=openai&model=gpt-4o-mini&api_key=sk-xxx

      # DeepSeek
      provider=openai&model=deepseek-chat&base_url=https://api.deepseek.com/v1&api_key=sk-xxx

      # Ollama (local)
      provider=ollama&model=qwen2.5:7b&base_url=http://localhost:11434
    """
    try:
        configure_llm(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            enabled=enabled,
        )
        return {"status": "ok", "config": get_llm_config()}
    except Exception as e:
        raise HTTPException(400, str(e))
