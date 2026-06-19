"""WhatsApp Cloud API adapter (Meta).

Uses WhatsApp Business Platform Cloud API via Meta developer account.
Requires: phone_number_id, access_token (from Meta developer dashboard).

Webhook: POST /api/gateway/whatsapp/{integration_id}
"""

import hashlib
import hmac
import json
from typing import Any

import httpx

from app.services.gateway import MessageEvent, register_adapter


WHATSAPP_API = "https://graph.facebook.com/v21.0"


@register_adapter("whatsapp")
class WhatsAppAdapter:
    """WhatsApp Cloud API — webhook receiver + sender."""

    # ── Webhook parsing ───────────────────────────────────

    @staticmethod
    def parse_webhook(payload: dict, headers: dict | None = None) -> list[MessageEvent]:
        events: list[MessageEvent] = []

        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                contacts = {c["wa_id"]: c.get("profile", {}).get("name", "")
                           for c in value.get("contacts", [])}

                for msg in messages:
                    msg_type = msg.get("type", "text")
                    text = ""
                    if msg_type == "text":
                        text = msg.get("text", {}).get("body", "")
                    elif msg_type == "interactive":
                        interactive = msg.get("interactive", {})
                        text = interactive.get("button_reply", {}).get("id", "")
                        if not text:
                            text = interactive.get("list_reply", {}).get("id", "")

                    events.append(MessageEvent(
                        platform="whatsapp",
                        channel_id=msg.get("from", ""),
                        user_id=msg.get("from", ""),
                        user_name=contacts.get(msg.get("from", ""), ""),
                        text=text,
                        timestamp=msg.get("timestamp", ""),
                        message_type=msg_type,
                        raw_payload=msg,
                    ))

        return events

    # ── Message sending ────────────────────────────────────

    @staticmethod
    async def send_message(target: str, text: str, phone_number_id: str = "",
                           access_token: str = "", **kwargs) -> dict[str, Any]:
        """target = recipient phone number (wa_id)."""
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": target,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{WHATSAPP_API}/{phone_number_id}/messages",
                json=body,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return resp.json()

    # ── Connectivity test ──────────────────────────────────

    @staticmethod
    def test_connectivity(api_key: str, base_url: str = "") -> bool:
        """api_key = access_token. base_url should be phone_number_id."""
        if not base_url:
            return False
        try:
            resp = httpx.get(
                f"{WHATSAPP_API}/{base_url}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ── Signature verification ─────────────────────────────

    @staticmethod
    def verify_signature(payload: bytes, headers: dict, secret: str) -> bool:
        """WhatsApp uses HMAC-SHA256 with app secret."""
        if not secret:
            return True
        received = headers.get("x-hub-signature-256", "")
        if not received:
            return True
        expected = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(received, expected)

    # ── Webhook verification (GET) ─────────────────────────

    @staticmethod
    def verify_webhook(mode: str, token: str, challenge: str, verify_token: str) -> str:
        """Meta webhook verification: hub.mode=subscribe&hub.verify_token=X&hub.challenge=Y."""
        if mode == "subscribe" and token == verify_token:
            return challenge
        return ""
