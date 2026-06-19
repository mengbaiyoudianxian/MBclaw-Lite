"""DingTalk / 钉钉 Bot adapter.

DingTalk supports:
  1. Group bot webhook (outgoing only) — simplest
  2. Enterprise app with message callback — full two-way

This adapter supports both modes.

Webhook: POST /api/gateway/dingtalk/{integration_id}
"""

import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from app.services.gateway import MessageEvent, register_adapter


DINGTALK_API = "https://api.dingtalk.com"


@register_adapter("dingtalk")
class DingTalkAdapter:
    """DingTalk Bot — webhook receiver + sender."""

    # ── Access token ───────────────────────────────────────

    @staticmethod
    def _get_access_token(app_key: str, app_secret: str) -> str:
        resp = httpx.post(
            f"{DINGTALK_API}/v1.0/oauth2/accessToken",
            json={"appKey": app_key, "appSecret": app_secret},
            timeout=10,
        )
        data = resp.json()
        return data.get("accessToken", "")

    # ── Webhook parsing ───────────────────────────────────

    @staticmethod
    def parse_webhook(payload: dict, headers: dict | None = None) -> list[MessageEvent]:
        events: list[MessageEvent] = []

        msg_type = payload.get("msgtype", payload.get("MsgType", "text"))

        if msg_type == "text":
            text_content = payload.get("text", {})
            text = text_content.get("content", "") if isinstance(text_content, dict) else str(text_content)
        else:
            text = json.dumps(payload, ensure_ascii=False)

        sender_id = payload.get("senderStaffId", payload.get("senderId", ""))
        conversation_id = payload.get("conversationId", payload.get("chatbotUserId", ""))

        if conversation_id:
            events.append(MessageEvent(
                platform="dingtalk",
                channel_id=conversation_id,
                user_id=sender_id,
                user_name=payload.get("senderNick", ""),
                text=text,
                timestamp=str(payload.get("createAt", int(time.time() * 1000))),
                message_type=msg_type,
                raw_payload=payload,
            ))

        return events

    # ── Message sending ────────────────────────────────────

    @staticmethod
    async def send_message(target: str, text: str, webhook_url: str = "",
                           access_token: str = "", **kwargs) -> dict[str, Any]:
        """target = conversation_id or webhook access_token.
        Uses webhook URL for simplicity.
        """
        if not webhook_url and access_token:
            body = {
                "msgtype": "text",
                "text": {"content": text},
            }

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{DINGTALK_API}/v1.0/robot/oToMessages/batchSend",
                    json={
                        "robotCode": kwargs.get("robot_code", ""),
                        "userIds": [target],
                        "msgKey": "sampleText",
                        "msgParam": json.dumps(body),
                    },
                    headers={"x-acs-dingtalk-access-token": access_token},
                )
                return resp.json()

        # Webhook mode
        url = webhook_url or f"{DINGTALK_API}/robot/send?access_token={target}"
        body = {"msgtype": "text", "text": {"content": text}}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=body)
            return resp.json()

    # ── Connectivity test ──────────────────────────────────

    @staticmethod
    def test_connectivity(api_key: str, base_url: str = "") -> bool:
        """api_key can be webhook access_token or "app_key:app_secret"."""
        if ":" in api_key:
            parts = api_key.split(":", 1)
            token = DingTalkAdapter._get_access_token(parts[0], parts[1])
            return bool(token)
        # Test webhook
        try:
            resp = httpx.post(
                f"{DINGTALK_API}/robot/send?access_token={api_key}",
                json={"msgtype": "text", "text": {"content": "MBclaw connectivity test"}},
                timeout=10,
            )
            return resp.json().get("errcode") == 0
        except Exception:
            return False

    # ── Signature verification ─────────────────────────────

    @staticmethod
    def verify_signature(payload: bytes, headers: dict, secret: str) -> bool:
        """DingTalk uses HMAC-SHA256 with timestamp + secret for outgoing webhooks."""
        if not secret:
            return True
        timestamp = headers.get("timestamp", "")
        sign = headers.get("sign", "")
        if not all([timestamp, sign]):
            return True

        string_to_sign = f"{timestamp}\n{secret}"
        expected = hmac.new(
            secret.encode(), string_to_sign.encode(), hashlib.sha256
        ).digest()
        expected_b64 = __import__("base64").b64encode(expected).decode()
        return hmac.compare_digest(sign, expected_b64)
