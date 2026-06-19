"""Signal messenger adapter.

Uses signal-cli REST API (https://github.com/bbernhard/signal-cli-rest-api)
as a bridge. Requires a running signal-cli-rest-api instance with a registered
phone number.

Alternatively, can use Twilio Signal API (deprecated) or callsocket.

Webhook: POST /api/gateway/signal/{integration_id}
"""

import json
from typing import Any

import httpx

from app.services.gateway import MessageEvent, register_adapter


@register_adapter("signal")
class SignalAdapter:
    """Signal — via signal-cli-rest-api bridge."""

    # ── Webhook parsing ───────────────────────────────────

    @staticmethod
    def parse_webhook(payload: dict, headers: dict | None = None) -> list[MessageEvent]:
        """Parse signal-cli-rest-api JSON webhook format."""
        events: list[MessageEvent] = []

        envelope = payload.get("envelope", {})
        source = envelope.get("source", "")
        source_name = envelope.get("sourceName", source)
        data_message = envelope.get("dataMessage", {})
        message = data_message.get("message", "")

        if message:
            events.append(MessageEvent(
                platform="signal",
                channel_id=source,
                user_id=source,
                user_name=source_name,
                text=message,
                timestamp=str(envelope.get("timestamp", "")),
                message_type="text",
                raw_payload=payload,
            ))

        return events

    # ── Message sending ────────────────────────────────────

    @staticmethod
    async def send_message(target: str, text: str, base_url: str = "",
                           sender: str = "", **kwargs) -> dict[str, Any]:
        """target = recipient phone number. sender = registered signal number."""
        body = {
            "number": sender or target,
            "recipients": [target],
            "message": text,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{base_url}/v2/send", json=body)
            return resp.json() if resp.status_code == 201 else {"error": resp.text}

    # ── Connectivity test ──────────────────────────────────

    @staticmethod
    def test_connectivity(api_key: str, base_url: str = "") -> bool:
        """Test connection to signal-cli-rest-api."""
        if not base_url:
            return False
        try:
            resp = httpx.get(f"{base_url}/v1/about", timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    # ── Signature verification ─────────────────────────────

    @staticmethod
    def verify_signature(payload: bytes, headers: dict, secret: str) -> bool:
        """signal-cli-rest-api doesn't sign webhooks by default."""
        return True
