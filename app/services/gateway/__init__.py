"""Multi-platform messaging gateway — OpenClaw-style unified adapter pattern.

Each platform adapter implements:
  - parse_webhook(payload, headers) -> list[MessageEvent]
  - send_message(target, text, **kwargs) -> dict
  - test_connectivity(api_key, base_url) -> bool
  - verify_signature(payload, headers, secret) -> bool
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class MessageEvent:
    platform: str
    channel_id: str = ""
    user_id: str = ""
    user_name: str = ""
    text: str = ""
    timestamp: str = ""
    message_type: str = "text"  # text, image, file, voice, video
    raw_payload: dict = field(default_factory=dict)


class GatewayAdapter(Protocol):
    """Protocol for platform-specific adapters."""

    async def send_message(self, target: str, text: str, **kwargs) -> dict[str, Any]: ...
    def parse_webhook(self, payload: dict, headers: dict) -> list[MessageEvent]: ...
    def test_connectivity(self, api_key: str, base_url: str = "") -> bool: ...
    def verify_signature(self, payload: bytes, headers: dict, secret: str) -> bool: ...


# Registry of all supported messaging platforms
ADAPTERS: dict[str, type] = {}


def register_adapter(name: str):
    """Decorator to register a gateway adapter class."""
    def decorator(cls):
        ADAPTERS[name] = cls
        return cls
    return decorator
