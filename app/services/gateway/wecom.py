"""WeCom / 企业微信 Bot adapter.

Two modes:
  1. Webhook bot (simplest): incoming via group bot webhook, outgoing via webhook URL
  2. Application bot (full): OAuth + message push via corp API

Webhook: POST /api/gateway/wecom/{integration_id}
"""

import hashlib
import json
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from app.services.gateway import MessageEvent, register_adapter


WECOM_API = "https://qyapi.weixin.qq.com"


@register_adapter("wecom")
class WeComAdapter:
    """WeCom Bot — webhook receiver + sender."""

    # ── Access token (for application mode) ────────────────

    @staticmethod
    def _get_access_token(corp_id: str, corp_secret: str) -> str:
        resp = httpx.get(
            f"{WECOM_API}/cgi-bin/gettoken",
            params={"corpid": corp_id, "corpsecret": corp_secret},
            timeout=10,
        )
        data = resp.json()
        return data.get("access_token", "")

    # ── Webhook parsing ───────────────────────────────────

    @staticmethod
    def parse_webhook(payload: dict, headers: dict | None = None) -> list[MessageEvent]:
        events: list[MessageEvent] = []

        # Group bot webhook format (plain callback)
        msg = payload.get("msg", payload)  # may be nested or flat

        msg_type = msg.get("msgtype", msg.get("MsgType", "text"))
        chat_id = msg.get("chatid", msg.get("ChatId", ""))
        from_user = msg.get("from", {}).get("userid", msg.get("From", {}).get("UserId", ""))
        from_name = msg.get("from", {}).get("name", "")

        if msg_type == "text":
            text_content = msg.get("text", {})
            text = text_content.get("content", "") if isinstance(text_content, dict) else str(text_content)
        else:
            text = json.dumps(msg, ensure_ascii=False)

        if chat_id:
            events.append(MessageEvent(
                platform="wecom",
                channel_id=chat_id,
                user_id=from_user if isinstance(from_user, str) else "",
                user_name=from_name,
                text=text,
                timestamp=msg.get("CreateTime", ""),
                message_type=msg_type,
                raw_payload=payload,
            ))

        return events

    # ── Message sending ────────────────────────────────────

    @staticmethod
    async def send_message(target: str, text: str, webhook_url: str = "", **kwargs) -> dict[str, Any]:
        """target = chat_id or webhook_key. Uses webhook URL for simplicity."""
        url = webhook_url or f"{WECOM_API}/cgi-bin/webhook/send?key={target}"
        body = {"msgtype": "text", "text": {"content": text}}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=body)
            return resp.json()

    # ── Connectivity test ──────────────────────────────────

    @staticmethod
    def test_connectivity(api_key: str, base_url: str = "") -> bool:
        """api_key can be webhook key or "corp_id:corp_secret"."""
        if ":" in api_key:
            parts = api_key.split(":", 1)
            token = WeComAdapter._get_access_token(parts[0], parts[1])
            return bool(token)
        # Test webhook key
        try:
            resp = httpx.post(
                f"{WECOM_API}/cgi-bin/webhook/send?key={api_key}",
                json={"msgtype": "text", "text": {"content": "MBclaw connectivity test"}},
                timeout=10,
            )
            data = resp.json()
            return data.get("errcode") == 0
        except Exception:
            return False

    # ── Signature verification ─────────────────────────────

    @staticmethod
    def verify_signature(payload: bytes, headers: dict, secret: str) -> bool:
        """WeCom URL verification: echostr + signature check.
        For msg_signature, use SHA1(sort(token, timestamp, nonce, echostr))."""
        msg_signature = headers.get("x-wework-msg-signature", "")
        timestamp = headers.get("x-wework-timestamp", "")
        nonce = headers.get("x-wework-nonce", "")
        if not all([msg_signature, timestamp, nonce]):
            return True

        import hashlib as hl
        parts = sorted([secret, timestamp, nonce, payload.decode()])
        expected = hl.sha1("".join(parts).encode()).hexdigest()
        return expected == msg_signature
