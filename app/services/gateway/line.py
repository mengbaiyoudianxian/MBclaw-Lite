"""LINE Messaging API adapter.

LINE Official Account → Messaging API.
Requires: channel_access_token, channel_secret from LINE Developers Console.

Webhook: POST /api/gateway/line/{integration_id}
"""

import hashlib
import hmac
import json
from typing import Any

import httpx

from app.services.gateway import MessageEvent, register_adapter


LINE_API = "https://api.line.me"


@register_adapter("line")
class LineAdapter:
    """LINE Messaging API — webhook receiver + sender."""

    # ── Webhook parsing ───────────────────────────────────

    @staticmethod
    def parse_webhook(payload: dict, headers: dict | None = None) -> list[MessageEvent]:
        events: list[MessageEvent] = []

        for event in payload.get("events", []):
            if event.get("type") != "message":
                continue

            msg = event.get("message", {})
            msg_type = msg.get("type", "text")
            text = msg.get("text", "")

            source = event.get("source", {})
            src_type = source.get("type", "user")
            if src_type == "group":
                channel_id = source.get("groupId", "")
            elif src_type == "room":
                channel_id = source.get("roomId", "")
            else:
                channel_id = source.get("userId", "")

            events.append(MessageEvent(
                platform="line",
                channel_id=channel_id,
                user_id=source.get("userId", ""),
                user_name="",
                text=text,
                timestamp=str(event.get("timestamp", "")),
                message_type=msg_type,
                raw_payload=event,
            ))

        return events

    # ── Message sending ────────────────────────────────────

    @staticmethod
    async def send_message(target: str, text: str, channel_token: str = "", **kwargs) -> dict[str, Any]:
        """target = user_id/group_id/room_id."""
        body = {
            "to": target,
            "messages": [{"type": "text", "text": text}],
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{LINE_API}/v2/bot/message/push",
                json=body,
                headers={"Authorization": f"Bearer {channel_token}"},
            )
            return resp.json()

    # ── Reply (within webhook context) ─────────────────────

    @staticmethod
    async def reply_message(reply_token: str, text: str, channel_token: str = "") -> dict:
        """Reply directly to a webhook event using replyToken."""
        body = {
            "replyToken": reply_token,
            "messages": [{"type": "text", "text": text}],
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{LINE_API}/v2/bot/message/reply",
                json=body,
                headers={"Authorization": f"Bearer {channel_token}"},
            )
            return resp.json()

    # ── Connectivity test ──────────────────────────────────

    @staticmethod
    def test_connectivity(api_key: str, base_url: str = "") -> bool:
        """api_key = channel_access_token."""
        try:
            resp = httpx.get(
                f"{LINE_API}/v2/bot/info",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ── Signature verification ─────────────────────────────

    @staticmethod
    def verify_signature(payload: bytes, headers: dict, secret: str) -> bool:
        """LINE uses HMAC-SHA256 with channel_secret on raw body."""
        if not secret:
            return True
        received = headers.get("x-line-signature", "")
        if not received:
            return True
        expected = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).digest()
        return hmac.compare_digest(
            received.encode(), expected.hex().encode()
        )
