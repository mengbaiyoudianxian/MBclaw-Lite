"""QQ Bot adapter.

Two approaches:
  1. QQ Official Bot API (q.qq.com) — for public bots
  2. go-cqhttp / NapCat (self-hosted) — reverse websocket or HTTP webhook

This adapter targets the official QQ Bot API (WebSocket not needed for basic webhook).

Webhook: POST /api/gateway/qq/{integration_id}
"""

import hashlib
import hmac
import json
from typing import Any

import httpx

from app.services.gateway import MessageEvent, register_adapter


QQ_API = "https://api.sgroup.qq.com"


@register_adapter("qq")
class QQAdapter:
    """QQ Official Bot API — webhook receiver + sender."""

    # ── Access token ───────────────────────────────────────

    @staticmethod
    def _get_access_token(app_id: str, client_secret: str) -> str:
        resp = httpx.post(
            f"{QQ_API}/oauth2/token",
            json={
                "app_id": app_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        data = resp.json()
        return data.get("access_token", "")

    # ── Webhook parsing ───────────────────────────────────

    @staticmethod
    def parse_webhook(payload: dict, headers: dict | None = None) -> list[MessageEvent]:
        events: list[MessageEvent] = []
        op = payload.get("op", 0)

        if op == 0:  # Dispatch event
            d = payload.get("d", {})
            event_type = d.get("event_type", "")

            if "MESSAGE" in event_type:
                author = d.get("author", {})
                events.append(MessageEvent(
                    platform="qq",
                    channel_id=d.get("channel_id", ""),
                    user_id=author.get("id", ""),
                    user_name=author.get("username", ""),
                    text=d.get("content", ""),
                    timestamp=d.get("timestamp", ""),
                    message_type="text",
                    raw_payload=payload,
                ))

        elif op == 13:  # Validation callback
            pass

        return events

    # ── Message sending ────────────────────────────────────

    @staticmethod
    async def send_message(target: str, text: str, app_id: str = "",
                           client_secret: str = "", **kwargs) -> dict[str, Any]:
        """target = channel_id."""
        token = QQAdapter._get_access_token(app_id, client_secret)
        if not token:
            return {"code": -1, "msg": "failed to get access token"}

        body = {
            "content": text,
            "msg_type": 0,  # text
            "msg_id": kwargs.get("msg_id", ""),
        }
        if "image" in kwargs:
            body["msg_type"] = 2
            body["image"] = kwargs["image"]

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{QQ_API}/v2/channels/{target}/messages",
                json=body,
                headers={"Authorization": f"QQBot {token}"},
            )
            return resp.json()

    # ── Connectivity test ──────────────────────────────────

    @staticmethod
    def test_connectivity(api_key: str, base_url: str = "") -> bool:
        """api_key = "app_id:client_secret"."""
        parts = api_key.split(":", 1)
        if len(parts) != 2:
            return False
        token = QQAdapter._get_access_token(parts[0], parts[1])
        return bool(token)

    # ── Signature verification ─────────────────────────────

    @staticmethod
    def verify_signature(payload: bytes, headers: dict, secret: str) -> bool:
        """QQ Bot uses Ed25519 signature in X-Signature-Ed25519 header."""
        if not secret:
            return True
        sig = headers.get("x-signature-ed25519", "")
        timestamp = headers.get("x-signature-timestamp", "")
        if not sig or not timestamp:
            return True

        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            from cryptography.hazmat.primitives import serialization
            import base64

            key_bytes = base64.b64decode(secret)
            public_key = Ed25519PublicKey.from_public_bytes(key_bytes)
            public_key.verify(base64.b64decode(sig), timestamp.encode() + payload)
            return True
        except Exception:
            return False
