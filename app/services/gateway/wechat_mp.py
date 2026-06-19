"""WeChat Official Account / 微信公众号 adapter.

WeChat MP uses XML-based message exchange (not JSON).
Message push from WeChat servers → our webhook → parse XML → reply XML.

Webhook: POST /api/gateway/wechat_mp/{integration_id}
"""

import hashlib
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from app.services.gateway import MessageEvent, register_adapter


WECHAT_MP_API = "https://api.weixin.qq.com"


@register_adapter("wechat_mp")
class WeChatMPAdapter:
    """WeChat Official Account — XML webhook + message sender."""

    # ── Access token ───────────────────────────────────────

    @staticmethod
    def _get_access_token(app_id: str, app_secret: str) -> str:
        resp = httpx.get(
            f"{WECHAT_MP_API}/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": app_id, "secret": app_secret},
            timeout=10,
        )
        data = resp.json()
        return data.get("access_token", "")

    # ── Webhook parsing (XML) ──────────────────────────────

    @staticmethod
    def parse_webhook(payload: dict, headers: dict | None = None) -> list[MessageEvent]:
        """payload['xml_raw'] should contain the raw XML string."""
        events: list[MessageEvent] = []

        xml_raw = payload.get("xml_raw", "")
        if not xml_raw:
            return events

        try:
            root = ET.fromstring(xml_raw)
        except ET.ParseError:
            return events

        msg_type = root.findtext("MsgType", "text")
        if msg_type not in ("text", "voice"):
            return events

        events.append(MessageEvent(
            platform="wechat_mp",
            channel_id=f"mp:{root.findtext('ToUserName', '')}",
            user_id=root.findtext("FromUserName", ""),
            user_name="",
            text=root.findtext("Content", ""),
            timestamp=root.findtext("CreateTime", ""),
            message_type=msg_type,
            raw_payload={"xml": xml_raw},
        ))
        return events

    # ── Message sending ────────────────────────────────────

    @staticmethod
    async def send_message(target: str, text: str, app_id: str = "",
                           app_secret: str = "", **kwargs) -> dict[str, Any]:
        """target = openid. Sends customer service message."""
        token = WeChatMPAdapter._get_access_token(app_id, app_secret)
        if not token:
            return {"errcode": -1, "errmsg": "failed to get access token"}

        body = {
            "touser": target,
            "msgtype": "text",
            "text": {"content": text},
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{WECHAT_MP_API}/cgi-bin/message/custom/send",
                params={"access_token": token},
                json=body,
            )
            return resp.json()

    # ── Connectivity test ──────────────────────────────────

    @staticmethod
    def test_connectivity(api_key: str, base_url: str = "") -> bool:
        """api_key = "app_id:app_secret"."""
        parts = api_key.split(":", 1)
        if len(parts) != 2:
            return False
        token = WeChatMPAdapter._get_access_token(parts[0], parts[1])
        return bool(token)

    # ── Signature verification ─────────────────────────────

    @staticmethod
    def verify_signature(payload: bytes, headers: dict, secret: str) -> bool:
        """WeChat MP signature: SHA1(sort(token, timestamp, nonce))."""
        signature = headers.get("x-wx-signature", headers.get("signature", ""))
        timestamp = headers.get("x-wx-timestamp", headers.get("timestamp", ""))
        nonce = headers.get("x-wx-nonce", headers.get("nonce", ""))
        if not all([signature, timestamp, nonce]):
            return True

        parts = sorted([secret, timestamp, nonce])
        expected = hashlib.sha1("".join(parts).encode()).hexdigest()
        return expected == signature

    # ── URL verification echo ──────────────────────────────

    @staticmethod
    def verify_url(echostr: str, signature: str, timestamp: str, nonce: str, token: str) -> str:
        """WeChat MP URL verification: return echostr if signature matches."""
        parts = sorted([token, timestamp, nonce])
        expected = hashlib.sha1("".join(parts).encode()).hexdigest()
        return echostr if expected == signature else ""
