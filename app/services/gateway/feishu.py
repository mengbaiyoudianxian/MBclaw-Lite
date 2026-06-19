"""Feishu / Lark Bot adapter.

Feishu (飞书) and Lark share the same API with different base URLs:
  - Feishu:  https://open.feishu.cn
  - Lark:    https://open.larksuite.com

Webhook: POST /api/gateway/feishu/{integration_id}
"""

import hashlib
import hmac
import json
from typing import Any

import httpx

from app.services.gateway import MessageEvent, register_adapter


FEISHU_API = "https://open.feishu.cn"
LARK_API = "https://open.larksuite.com"


@register_adapter("feishu")
class FeishuAdapter:
    """Feishu/Lark Bot — webhook receiver + message sender."""

    # ── Access token ───────────────────────────────────────

    @staticmethod
    def _get_tenant_access_token(app_id: str, app_secret: str, base_url: str = FEISHU_API) -> str:
        resp = httpx.post(
            f"{base_url}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
        data = resp.json()
        return data.get("tenant_access_token", "")

    # ── Webhook parsing ───────────────────────────────────

    @staticmethod
    def parse_webhook(payload: dict, headers: dict | None = None) -> list[MessageEvent]:
        events: list[MessageEvent] = []
        header = payload.get("header", {})
        event_type = header.get("event_type", "")

        if event_type == "im.message.receive_v1":
            event = payload.get("event", {})
            msg = event.get("message", {})
            sender = event.get("sender", {}).get("sender_id", {}) or {}
            chat_id = msg.get("chat_id", "")

            # Extract text content
            content = json.loads(msg.get("content", "{}"))
            text = content.get("text", "")

            events.append(MessageEvent(
                platform="feishu",
                channel_id=chat_id,
                user_id=sender.get("open_id", sender.get("user_id", "")),
                user_name="",
                text=text,
                timestamp=header.get("create_time", ""),
                message_type=msg.get("message_type", "text"),
                raw_payload=payload,
            ))

        return events

    # ── Message sending ────────────────────────────────────

    @staticmethod
    async def send_message(target: str, text: str, app_id: str = "",
                           app_secret: str = "", base_url: str = FEISHU_API, **kwargs) -> dict[str, Any]:
        """target = chat_id (receive_id)."""
        token = FeishuAdapter._get_tenant_access_token(app_id, app_secret, base_url)
        if not token:
            return {"code": -1, "msg": "failed to get access token"}

        content = json.dumps({"text": text})
        body = {
            "receive_id": target,
            "msg_type": "text",
            "content": content,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{base_url}/open-apis/im/v1/messages",
                params={"receive_id_type": "chat_id"},
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.json()

    # ── Connectivity test ──────────────────────────────────

    @staticmethod
    def test_connectivity(api_key: str, base_url: str = "") -> bool:
        """api_key = "app_id:app_secret"."""
        parts = api_key.split(":", 1)
        if len(parts) != 2:
            return False
        app_id, app_secret = parts
        token = FeishuAdapter._get_tenant_access_token(app_id, app_secret, base_url or FEISHU_API)
        return bool(token)

    # ── Signature verification ─────────────────────────────

    @staticmethod
    def verify_signature(payload: bytes, headers: dict, secret: str) -> bool:
        """Feishu uses SHA256 challenge on URL verification, HMAC-SHA256 on events."""
        if not secret:
            return True
        timestamp = headers.get("x-lark-request-timestamp", "")
        nonce = headers.get("x-lark-request-nonce", "")
        signature = headers.get("x-lark-signature", "")
        if not all([timestamp, nonce, signature]):
            return True  # skip if headers missing

        body = f"{timestamp}{nonce}{secret}{payload.decode()}"
        expected = hashlib.sha256(body.encode()).hexdigest()
        return hmac.compare_digest(signature, expected)
