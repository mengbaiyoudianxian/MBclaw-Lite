"""Telegram Bot API adapter.

Webhook: POST /api/gateway/telegram/{integration_id}
Setup:   1. Create bot via @BotFather → get token
         2. Set webhook: https://api.telegram.org/bot<TOKEN>/setWebhook?url=<MBclaw>/api/gateway/telegram/<id>
"""

import hashlib
import hmac
import json
from typing import Any

import httpx

from app.services.gateway import MessageEvent, register_adapter


TELEGRAM_API = "https://api.telegram.org"


@register_adapter("telegram")
class TelegramAdapter:
    """Telegram Bot API — grammY-style webhook receiver + sender."""

    @staticmethod
    def _api_url(token: str, method: str) -> str:
        return f"{TELEGRAM_API}/bot{token}/{method}"

    # ── Webhook parsing ───────────────────────────────────

    @staticmethod
    def parse_webhook(payload: dict, headers: dict | None = None) -> list[MessageEvent]:
        events: list[MessageEvent] = []
        message = payload.get("message") or payload.get("edited_message") or {}
        if not message:
            return events

        chat = message.get("chat", {})
        from_user = message.get("from", {})
        text = message.get("text") or message.get("caption") or ""

        events.append(MessageEvent(
            platform="telegram",
            channel_id=str(chat.get("id", "")),
            user_id=str(from_user.get("id", "")),
            user_name=from_user.get("username") or f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip(),
            text=text,
            timestamp=str(message.get("date", "")),
            message_type="text" if "text" in message else "photo" if "photo" in message else "other",
            raw_payload=payload,
        ))
        return events

    # ── Message sending ────────────────────────────────────

    @staticmethod
    async def send_message(target: str, text: str, token: str = "", **kwargs) -> dict[str, Any]:
        """target = chat_id."""
        body: dict[str, Any] = {"chat_id": target, "text": text, "parse_mode": "HTML"}
        body.update({k: v for k, v in kwargs.items() if k in ("reply_markup", "disable_web_page_preview", "reply_to_message_id")})

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(TelegramAdapter._api_url(token, "sendMessage"), json=body)
            return resp.json()

    # ── Connectivity test ──────────────────────────────────

    @staticmethod
    def test_connectivity(api_key: str, base_url: str = "") -> bool:
        try:
            resp = httpx.get(TelegramAdapter._api_url(api_key, "getMe"), timeout=10)
            return resp.status_code == 200 and resp.json().get("ok", False)
        except Exception:
            return False

    # ── Signature verification ─────────────────────────────

    @staticmethod
    def verify_signature(payload: bytes, headers: dict, secret: str) -> bool:
        """Telegram doesn't sign webhooks by default. Use secret_token from setWebhook."""
        if not secret:
            return True  # no secret configured → skip verification
        received = headers.get("x-telegram-bot-api-secret-token", "")
        return hmac.compare_digest(received, secret)
