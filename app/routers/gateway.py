"""Unified messaging gateway router — OpenClaw-style multi-platform webhook receiver.

Each platform sends webhooks to: POST /api/gateway/{platform}/{integration_id}

Supported platforms (mirrors OpenClaw's 16+ channels + Chinese platforms):
  telegram, feishu, wecom, qq, wechat_mp, whatsapp, signal, line,
  discord, slack, dingtalk

Each webhook is:
  1. Signature-verified (when applicable)
  2. Parsed into MessageEvent
  3. Routed to MBclaw Agent Runtime for processing
  4. Response sent back to the platform
"""

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.external_integration import ExternalIntegration
from app.services.gateway import ADAPTERS, MessageEvent
from app.services.gateway_service import process_gateway_message

logger = logging.getLogger("mbclaw.gateway")

router = APIRouter(prefix="/api/gateway", tags=["gateway"])


# ═══════════════════════════════════════════════════════════
# Platform webhook receivers
# ═══════════════════════════════════════════════════════════

async def _handle_webhook(
    platform: str,
    integration_id: int,
    request: Request,
    db: DBSession,
) -> dict[str, Any]:
    """Generic webhook handler for all platforms."""

    # Look up integration
    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.id == integration_id,
        ExternalIntegration.provider == platform,
    ).first()

    if not integration:
        raise HTTPException(404, f"集成不存在: {platform}#{integration_id}")

    # Get adapter
    adapter_cls = ADAPTERS.get(platform)
    if not adapter_cls:
        raise HTTPException(400, f"不支持的平台: {platform}")

    adapter = adapter_cls()

    # Read raw body
    raw_body = await request.body()
    headers = dict(request.headers)

    # Special handling — URL verification challenges
    if request.method == "GET":
        return _handle_url_verification(request, adapter, platform)

    # Verify signature — webhook secret from config (not api_key, which is for API calls)
    integration_config = json.loads(integration.config) if integration.config else {}
    webhook_secret = integration_config.get("webhook_secret", "")
    if not adapter.verify_signature(raw_body, headers, webhook_secret):
        logger.warning(f"Gateway signature verification failed for {platform}#{integration_id}")
        raise HTTPException(401, "签名验证失败")

    # Parse webhook
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        payload = {"xml_raw": raw_body.decode("utf-8", errors="replace")}

    events = adapter.parse_webhook(payload, headers)

    if not events:
        return {"status": "ok", "events": 0, "message": "no actionable events"}

    # Process each event through MBclaw Agent Runtime
    results = []
    for event in events:
        result = await process_gateway_message(
            db=db,
            event=event,
            integration=integration,
        )
        results.append(result)

    return {
        "status": "ok",
        "events": len(results),
        "results": results,
    }


def _handle_url_verification(request: Request, adapter, platform: str) -> Response:
    """Handle platform URL verification (GET requests)."""
    params = request.query_params

    # Discord PING
    if platform == "discord":
        return Response(content=json.dumps({"type": 1}), media_type="application/json")

    # Slack URL verification
    challenge = params.get("challenge", "")
    if challenge:
        return Response(content=challenge, media_type="text/plain")

    # WeChat MP
    echostr = params.get("echostr", "")
    if echostr:
        sig = params.get("signature", "")
        ts = params.get("timestamp", "")
        nonce = params.get("nonce", "")
        result = adapter.verify_url(echostr, sig, ts, nonce, "")
        return Response(content=result or "", media_type="text/plain")

    # WhatsApp / Meta
    mode = params.get("hub.mode", "")
    verify_token = params.get("hub.verify_token", "")
    challenge_val = params.get("hub.challenge", "")
    if mode == "subscribe":
        result = adapter.verify_webhook(mode, verify_token, challenge_val, "")
        return Response(content=result or challenge_val, media_type="text/plain")

    return Response(content="ok")


# ═══════════════════════════════════════════════════════════
# Platform-specific routes
# ═══════════════════════════════════════════════════════════

@router.api_route("/telegram/{integration_id}", methods=["GET", "POST"])
async def telegram_webhook(integration_id: int, request: Request,
                           db: DBSession = Depends(get_db)):
    return await _handle_webhook("telegram", integration_id, request, db)


@router.api_route("/feishu/{integration_id}", methods=["GET", "POST"])
async def feishu_webhook(integration_id: int, request: Request,
                         db: DBSession = Depends(get_db)):
    return await _handle_webhook("feishu", integration_id, request, db)


@router.api_route("/wecom/{integration_id}", methods=["GET", "POST"])
async def wecom_webhook(integration_id: int, request: Request,
                        db: DBSession = Depends(get_db)):
    return await _handle_webhook("wecom", integration_id, request, db)


@router.api_route("/qq/{integration_id}", methods=["GET", "POST"])
async def qq_webhook(integration_id: int, request: Request,
                     db: DBSession = Depends(get_db)):
    return await _handle_webhook("qq", integration_id, request, db)


@router.api_route("/wechat_mp/{integration_id}", methods=["GET", "POST"])
async def wechat_mp_webhook(integration_id: int, request: Request,
                            db: DBSession = Depends(get_db)):
    return await _handle_webhook("wechat_mp", integration_id, request, db)


@router.api_route("/whatsapp/{integration_id}", methods=["GET", "POST"])
async def whatsapp_webhook(integration_id: int, request: Request,
                           db: DBSession = Depends(get_db)):
    return await _handle_webhook("whatsapp", integration_id, request, db)


@router.api_route("/signal/{integration_id}", methods=["GET", "POST"])
async def signal_webhook(integration_id: int, request: Request,
                         db: DBSession = Depends(get_db)):
    return await _handle_webhook("signal", integration_id, request, db)


@router.api_route("/line/{integration_id}", methods=["GET", "POST"])
async def line_webhook(integration_id: int, request: Request,
                       db: DBSession = Depends(get_db)):
    return await _handle_webhook("line", integration_id, request, db)


@router.api_route("/discord/{integration_id}", methods=["GET", "POST"])
async def discord_webhook(integration_id: int, request: Request,
                          db: DBSession = Depends(get_db)):
    return await _handle_webhook("discord", integration_id, request, db)


@router.api_route("/slack/{integration_id}", methods=["GET", "POST"])
async def slack_webhook(integration_id: int, request: Request,
                        db: DBSession = Depends(get_db)):
    return await _handle_webhook("slack", integration_id, request, db)


@router.api_route("/dingtalk/{integration_id}", methods=["GET", "POST"])
async def dingtalk_webhook(integration_id: int, request: Request,
                           db: DBSession = Depends(get_db)):
    return await _handle_webhook("dingtalk", integration_id, request, db)


# ═══════════════════════════════════════════════════════════
# Gateway management
# ═══════════════════════════════════════════════════════════

@router.get("/platforms")
def list_platforms():
    """List all supported messaging platforms with setup instructions."""
    return {
        "platforms": {
            "telegram": {
                "name": "Telegram Bot",
                "setup": "Create bot via @BotFather, get token, set webhook URL",
                "webhook": "/api/gateway/telegram/{integration_id}",
                "api_key_label": "Bot Token",
            },
            "feishu": {
                "name": "飞书 / Lark Bot",
                "setup": "Create app in Feishu Developer Console, enable bot, get App ID + App Secret",
                "webhook": "/api/gateway/feishu/{integration_id}",
                "api_key_label": "App ID:App Secret",
            },
            "wecom": {
                "name": "企业微信 Bot",
                "setup": "Create group bot or corp app, get webhook key or Corp ID:Secret",
                "webhook": "/api/gateway/wecom/{integration_id}",
                "api_key_label": "Webhook Key or Corp ID:Corp Secret",
            },
            "qq": {
                "name": "QQ Bot",
                "setup": "Register at q.qq.com, create bot, get App ID + Client Secret",
                "webhook": "/api/gateway/qq/{integration_id}",
                "api_key_label": "App ID:Client Secret",
            },
            "wechat_mp": {
                "name": "微信公众号",
                "setup": "Register WeChat Official Account, enable developer mode, get App ID + App Secret",
                "webhook": "/api/gateway/wechat_mp/{integration_id}",
                "api_key_label": "App ID:App Secret",
            },
            "whatsapp": {
                "name": "WhatsApp Cloud API",
                "setup": "Create Meta App, configure WhatsApp, get Phone Number ID + Access Token",
                "webhook": "/api/gateway/whatsapp/{integration_id}",
                "api_key_label": "Access Token",
                "base_url_label": "Phone Number ID",
            },
            "signal": {
                "name": "Signal",
                "setup": "Run signal-cli-rest-api Docker container, register phone number",
                "webhook": "/api/gateway/signal/{integration_id}",
                "api_key_label": "(optional) Phone Number",
                "base_url_label": "signal-cli-rest-api URL",
            },
            "line": {
                "name": "LINE Bot",
                "setup": "Create LINE Official Account, enable Messaging API, get Channel Access Token + Secret",
                "webhook": "/api/gateway/line/{integration_id}",
                "api_key_label": "Channel Access Token",
            },
            "discord": {
                "name": "Discord Bot",
                "setup": "Create app at discord.com/developers, add bot, set Interactions Endpoint URL",
                "webhook": "/api/gateway/discord/{integration_id}",
                "api_key_label": "Bot Token",
            },
            "slack": {
                "name": "Slack Bot",
                "setup": "Create Slack App, enable Event Subscriptions, set Request URL",
                "webhook": "/api/gateway/slack/{integration_id}",
                "api_key_label": "Bot Token (xoxb-...)",
            },
            "dingtalk": {
                "name": "钉钉 Bot",
                "setup": "Create DingTalk app or group bot, get webhook URL or App Key:App Secret",
                "webhook": "/api/gateway/dingtalk/{integration_id}",
                "api_key_label": "Webhook Key or App Key:App Secret",
            },
        }
    }
