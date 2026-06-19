"""Slack Bot adapter — gateway pattern.

Uses Slack Bolt-style event subscriptions.
Setup: Slack App → Event Subscriptions → Request URL = <MBclaw>/api/gateway/slack/{id}

Webhook: POST /api/gateway/slack/{integration_id}
"""

import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from app.services.gateway import MessageEvent, register_adapter


SLACK_API = "https://slack.com/api"


@register_adapter("slack")
class SlackAdapter:
    """Slack Bot — Events API webhook + sender."""

    # ── Webhook parsing ───────────────────────────────────

    @staticmethod
    def parse_webhook(payload: dict, headers: dict | None = None) -> list[MessageEvent]:
        events: list[MessageEvent] = []

        # URL verification challenge
        if payload.get("type") == "url_verification":
            return events

        # Event callback
        event = payload.get("event", {})
        event_type = event.get("type", "")

        if event_type == "app_mention":
            text = event.get("text", "")
            # Strip bot mention from text
            if text.startswith("<@"):
                idx = text.find(">")
                if idx > 0:
                    text = text[idx + 1:].strip()

            events.append(MessageEvent(
                platform="slack",
                channel_id=event.get("channel", ""),
                user_id=event.get("user", ""),
                user_name="",
                text=text,
                timestamp=event.get("ts", ""),
                message_type="app_mention",
                raw_payload=payload,
            ))

        elif event_type == "message":
            # Skip bot's own messages, subtypes like message_changed
            if event.get("subtype"):
                return events
            if event.get("bot_id"):
                return events

            events.append(MessageEvent(
                platform="slack",
                channel_id=event.get("channel", ""),
                user_id=event.get("user", ""),
                user_name="",
                text=event.get("text", ""),
                timestamp=event.get("ts", ""),
                message_type="message",
                raw_payload=payload,
            ))

        return events

    # ── Message sending ────────────────────────────────────

    @staticmethod
    async def send_message(target: str, text: str, bot_token: str = "", **kwargs) -> dict[str, Any]:
        """target = channel_id."""
        body: dict[str, Any] = {"channel": target, "text": text}
        if "thread_ts" in kwargs:
            body["thread_ts"] = kwargs["thread_ts"]

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{SLACK_API}/chat.postMessage",
                json=body,
                headers={"Authorization": f"Bearer {bot_token}"},
            )
            return resp.json()

    # ── Connectivity test ──────────────────────────────────

    @staticmethod
    def test_connectivity(api_key: str, base_url: str = "") -> bool:
        """api_key = bot_token."""
        try:
            resp = httpx.post(
                f"{SLACK_API}/auth.test",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            return resp.json().get("ok", False)
        except Exception:
            return False

    # ── Signature verification ─────────────────────────────

    @staticmethod
    def verify_signature(payload: bytes, headers: dict, secret: str) -> bool:
        """Slack Signing Secret — HMAC-SHA256 of 'v0:ts:body'."""
        if not secret:
            return True
        received = headers.get("x-slack-signature", "")
        timestamp = headers.get("x-slack-request-timestamp", "")
        if not received or not timestamp:
            return True

        # Prevent replay attacks
        if abs(time.time() - int(timestamp)) > 300:
            return False

        sig_basestring = f"v0:{timestamp}:{payload.decode()}"
        expected = "v0=" + hmac.new(
            secret.encode(), sig_basestring.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(received, expected)
