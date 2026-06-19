"""Discord Bot adapter — gateway pattern.

Webhook: Discord uses Interaction Endpoint URL for slash commands.
For message events, uses Gateway Intents (websocket), but we bridge via HTTP webhook.

Setup:
  1. Create app at https://discord.com/developers/applications
  2. Add bot, enable MESSAGE CONTENT INTENT
  3. Set Interactions Endpoint URL to <MBclaw>/api/gateway/discord/{id}

Webhook: POST /api/gateway/discord/{integration_id}
"""

import hashlib
import hmac
import json
from typing import Any

import httpx

from app.services.gateway import MessageEvent, register_adapter


DISCORD_API = "https://discord.com/api/v10"


@register_adapter("discord")
class DiscordAdapter:
    """Discord Bot — HTTP interactions webhook + REST sender."""

    # ── Webhook parsing ───────────────────────────────────

    @staticmethod
    def parse_webhook(payload: dict, headers: dict | None = None) -> list[MessageEvent]:
        events: list[MessageEvent] = []

        # Discord sends Interaction or raw message event
        interaction_type = payload.get("type", 0)

        if interaction_type == 1:
            # PING — handled at HTTP level, not here
            return events

        # Slash command or message component
        if interaction_type in (2, 3):
            data = payload.get("data", {})
            member = payload.get("member", {}) or {}
            user = member.get("user", {}) or payload.get("user", {}) or {}

            text = ""
            if interaction_type == 2:
                # Slash command: resolve options
                options = data.get("options", [])
                for opt in options:
                    if opt.get("name") == "message" or opt.get("value"):
                        text += str(opt.get("value", "")) + " "
                text = text.strip() or data.get("name", "")

            events.append(MessageEvent(
                platform="discord",
                channel_id=payload.get("channel_id", ""),
                user_id=user.get("id", ""),
                user_name=user.get("username", user.get("global_name", "")),
                text=text.strip(),
                timestamp=payload.get("id", ""),  # snowflake ID
                message_type="interaction",
                raw_payload=payload,
            ))

        return events

    # ── Message sending ────────────────────────────────────

    @staticmethod
    async def send_message(target: str, text: str, bot_token: str = "", **kwargs) -> dict[str, Any]:
        """target = channel_id."""
        body: dict[str, Any] = {"content": text}
        if "embed" in kwargs:
            body["embeds"] = [kwargs["embed"]]

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{DISCORD_API}/channels/{target}/messages",
                json=body,
                headers={"Authorization": f"Bot {bot_token}"},
            )
            return resp.json() if resp.status_code in (200, 201) else {"error": resp.text}

    # ── Interaction response ───────────────────────────────

    @staticmethod
    async def respond_interaction(interaction_id: str, interaction_token: str,
                                  text: str, **kwargs) -> dict:
        """Respond to a Discord interaction (slash command etc)."""
        body = {"type": 4, "data": {"content": text}}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{DISCORD_API}/interactions/{interaction_id}/{interaction_token}/callback",
                json=body,
            )
            return {"status": resp.status_code}

    # ── Connectivity test ──────────────────────────────────

    @staticmethod
    def test_connectivity(api_key: str, base_url: str = "") -> bool:
        """api_key = bot_token."""
        try:
            resp = httpx.get(
                f"{DISCORD_API}/users/@me",
                headers={"Authorization": f"Bot {api_key}"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ── Signature verification ─────────────────────────────

    @staticmethod
    def verify_signature(payload: bytes, headers: dict, secret: str) -> bool:
        """Discord uses Ed25519 (X-Signature-Ed25519) + timestamp."""
        if not secret:
            return True
        sig = headers.get("x-signature-ed25519", "")
        timestamp = headers.get("x-signature-timestamp", "")
        if not sig or not timestamp:
            return True

        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            import base64

            key_bytes = bytes.fromhex(secret) if len(secret) == 64 else base64.b64decode(secret)
            public_key = Ed25519PublicKey.from_public_bytes(key_bytes)
            public_key.verify(bytes.fromhex(sig), timestamp.encode() + payload)
            return True
        except Exception:
            return False
