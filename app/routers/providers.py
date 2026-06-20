"""Provider management API — MiMo, OpenAI, Anthropic, etc.

Project 13: MiMo Code integration.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.services.llm_service import get_llm_config, configure_llm

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("")
def list_providers():
    """List all supported LLM providers with current config."""
    config = get_llm_config()
    providers = [
        {
            "name": "openai",
            "description": "OpenAI 兼容 API（支持 OpenAI / DeepSeek / Groq / vLLM）",
            "status": "available",
            "requires_key": True,
        },
        {
            "name": "ollama",
            "description": "本地 Ollama 模型",
            "status": "available",
            "requires_key": False,
        },
        {
            "name": "mimo",
            "description": "MiMo Code — 代码生成专用模型",
            "status": "available",
            "requires_key": True,
            "free_trial": "1 个月免费试用",
            "api_base": "https://api.mimo.run/v1",
        },
        {
            "name": "anthropic",
            "description": "Anthropic Claude API",
            "status": "available",
            "requires_key": True,
        },
    ]
    return {
        "providers": providers,
        "current": config,
    }


@router.get("/mimo/status")
def mimo_status():
    """Get MiMo trial status and connection info."""
    from app.services.llm.mimo_adapter import get_mimo
    try:
        adapter = get_mimo()
        return adapter.to_dict()
    except Exception as e:
        return {
            "provider": "mimo",
            "status": "error",
            "error": str(e),
        }


@router.post("/mimo/test")
async def test_mimo_connection(api_key: str = "", base_url: str = ""):
    """Test MiMo API connection.

    Send a minimal request to verify the API key and URL are correct.
    """
    from app.services.llm.mimo_adapter import MiMoAdapter
    adapter = MiMoAdapter(api_key=api_key, base_url=base_url)
    return await adapter.test_connection()


@router.post("/configure")
def configure_provider(
    provider: str = "",
    model: str = "",
    api_key: str = "",
    base_url: str = "",
    enabled: bool = True,
):
    """Reconfigure the active LLM provider at runtime."""
    configure_llm(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        enabled=enabled,
    )
    return {"success": True, "config": get_llm_config()}


@router.post("/mimo/configure")
def configure_mimo(
    api_key: str = "",
    model: str = "mimo-code-v1",
    base_url: str = "",
):
    """Configure MiMo as the active provider."""
    configure_llm(
        provider="mimo",
        model=model,
        api_key=api_key,
        base_url=base_url or "https://api.mimo.run/v1",
        enabled=True,
    )
    return {"success": True, "config": get_llm_config()}
