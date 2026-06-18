"""Unified external tool gateway with provider adapter pattern."""

import json
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session as DBSession

from app.models.external_integration import ExternalIntegration

PROVIDER_TYPES = {
    "openhands", "mimo", "image_recognition", "tts", "stt",
    "smart_home", "router", "slack", "discord", "github_app",
    "linear", "datadog", "gitlab", "vercel", "notion",
}


def register_integration(db: DBSession, data: dict) -> ExternalIntegration:
    now = datetime.now().isoformat()
    integration = ExternalIntegration(
        provider=data["provider"],
        display_name=data.get("display_name", data["provider"]),
        api_key=data.get("api_key", ""),
        base_url=data.get("base_url", ""),
        config=json.dumps(data.get("config", {}), ensure_ascii=False),
        status="inactive",
        created_at=now,
        updated_at=now,
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


def test_connectivity(db: DBSession, integration_id: int) -> dict[str, Any]:
    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.id == integration_id
    ).first()
    if not integration:
        return {"success": False, "error": "集成不存在"}

    provider = integration.provider
    base_url = integration.base_url
    api_key = integration.api_key

    # Provider-specific connectivity tests
    if provider in ("openhands",):
        # Quick API ping
        import httpx
        try:
            resp = httpx.get(f"{base_url}/api/health", timeout=5)
            ok = resp.status_code < 500
        except Exception as e:
            ok = False

    elif provider == "github_app":
        import httpx
        try:
            resp = httpx.get("https://api.github.com/rate_limit",
                             headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
            ok = resp.status_code == 200
        except Exception:
            ok = False

    elif provider == "slack":
        import httpx
        try:
            resp = httpx.post("https://slack.com/api/auth.test",
                              headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
            data = resp.json()
            ok = data.get("ok", False)
        except Exception:
            ok = False

    elif provider == "discord":
        import httpx
        try:
            resp = httpx.get("https://discord.com/api/v10/users/@me",
                             headers={"Authorization": f"Bot {api_key}"}, timeout=5)
            ok = resp.status_code == 200
        except Exception:
            ok = False

    else:
        # Generic: try base_url health check
        if base_url:
            import httpx
            try:
                resp = httpx.get(f"{base_url}/health", timeout=5)
                ok = resp.status_code < 500
            except Exception:
                ok = False
        else:
            ok = True  # can't test without URL

    # Update status
    integration.status = "active" if ok else "error"
    integration.updated_at = datetime.now().isoformat()
    db.commit()

    return {"success": ok, "status": integration.status,
            "provider": provider, "message": "连通" if ok else "连接失败"}


async def call_provider(db: DBSession, integration_id: int, action: str,
                        params: dict | None = None) -> dict[str, Any]:
    """Unified gateway: call any registered provider."""
    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.id == integration_id
    ).first()
    if not integration:
        return {"success": False, "error": "集成不存在"}

    config = json.loads(integration.config) if integration.config else {}
    params = params or {}

    # Route to appropriate adapter
    provider = integration.provider

    if provider == "openhands":
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{integration.base_url}/api/v1/{action}",
                json=params,
                headers={"Authorization": f"Bearer {integration.api_key}"},
            )
            return resp.json()

    if provider == "slack":
        import httpx
        channel = params.get("channel", config.get("default_channel", ""))
        text = params.get("text", "")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://slack.com/api/chat.postMessage",
                json={"channel": channel, "text": text},
                headers={"Authorization": f"Bearer {integration.api_key}"},
            )
            return resp.json()

    if provider == "discord":
        import httpx
        channel_id = params.get("channel_id", config.get("default_channel_id", ""))
        content = params.get("content", "")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                json={"content": content},
                headers={"Authorization": f"Bot {integration.api_key}"},
            )
            return resp.json()

    return {"success": False, "error": f"不支持的 provider: {provider}"}
