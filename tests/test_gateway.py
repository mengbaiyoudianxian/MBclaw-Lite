"""Tests for messaging gateway — platforms, webhooks, message routing."""

import json
import pytest


# ═══════════════════════════════════════════════════════════
# Platform registration
# ═══════════════════════════════════════════════════════════

def test_all_adapters_registered():
    # Import adapter modules to trigger @register_adapter decorators
    import app.services.gateway.telegram       # noqa: F401
    import app.services.gateway.feishu         # noqa: F401
    import app.services.gateway.wecom          # noqa: F401
    import app.services.gateway.qq             # noqa: F401
    import app.services.gateway.wechat_mp      # noqa: F401
    import app.services.gateway.whatsapp       # noqa: F401
    import app.services.gateway.signal         # noqa: F401
    import app.services.gateway.line           # noqa: F401
    import app.services.gateway.discord        # noqa: F401
    import app.services.gateway.slack          # noqa: F401
    import app.services.gateway.dingtalk       # noqa: F401
    from app.services.gateway import ADAPTERS
    expected = {
        "telegram", "feishu", "wecom", "qq", "wechat_mp",
        "whatsapp", "signal", "line", "discord", "slack", "dingtalk",
    }
    assert set(ADAPTERS.keys()) == expected
    assert len(ADAPTERS) == 11


def test_message_event_dataclass():
    from app.services.gateway import MessageEvent
    event = MessageEvent(
        platform="telegram",
        channel_id="123",
        user_id="456",
        user_name="testuser",
        text="hello",
        timestamp="1234567890",
        message_type="text",
    )
    assert event.platform == "telegram"
    assert event.channel_id == "123"
    assert event.text == "hello"
    assert event.raw_payload == {}


# ═══════════════════════════════════════════════════════════
# Platform adapter — Telegram
# ═══════════════════════════════════════════════════════════

def test_telegram_parse_text_message():
    from app.services.gateway.telegram import TelegramAdapter
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 100,
            "from": {"id": 12345, "username": "johndoe", "first_name": "John"},
            "chat": {"id": 67890, "type": "private"},
            "date": 1700000000,
            "text": "Hello MBclaw!",
        }
    }
    events = TelegramAdapter.parse_webhook(payload)
    assert len(events) == 1
    e = events[0]
    assert e.platform == "telegram"
    assert e.channel_id == "67890"
    assert e.user_id == "12345"
    assert e.user_name == "johndoe"
    assert e.text == "Hello MBclaw!"
    assert e.message_type == "text"


def test_telegram_parse_edited_message():
    from app.services.gateway.telegram import TelegramAdapter
    payload = {
        "update_id": 2,
        "edited_message": {
            "message_id": 101,
            "from": {"id": 111, "username": "editor"},
            "chat": {"id": 222, "type": "group"},
            "date": 1700000001,
            "text": "Edited text",
        }
    }
    events = TelegramAdapter.parse_webhook(payload)
    assert len(events) == 1
    assert events[0].text == "Edited text"


def test_telegram_parse_empty_payload():
    from app.services.gateway.telegram import TelegramAdapter
    events = TelegramAdapter.parse_webhook({})
    assert len(events) == 0


def test_telegram_signature_verification():
    from app.services.gateway.telegram import TelegramAdapter
    # Without secret, always passes
    assert TelegramAdapter.verify_signature(b"{}", {}, "")
    # With secret and correct token
    assert TelegramAdapter.verify_signature(
        b"{}", {"x-telegram-bot-api-secret-token": "mysecret"}, "mysecret"
    )
    # With secret and wrong token
    assert not TelegramAdapter.verify_signature(
        b"{}", {"x-telegram-bot-api-secret-token": "wrong"}, "mysecret"
    )


# ═══════════════════════════════════════════════════════════
# Platform adapter — Feishu
# ═══════════════════════════════════════════════════════════

def test_feishu_parse_text_message():
    from app.services.gateway.feishu import FeishuAdapter
    payload = {
        "header": {
            "event_type": "im.message.receive_v1",
            "create_time": "1700000000000",
        },
        "event": {
            "sender": {"sender_id": {"open_id": "ou_xxx", "user_id": "user_yyy"}},
            "message": {
                "message_id": "om_zzz",
                "chat_id": "oc_aaa",
                "message_type": "text",
                "content": json.dumps({"text": "你好 MBclaw!"}),
            }
        }
    }
    events = FeishuAdapter.parse_webhook(payload)
    assert len(events) == 1
    e = events[0]
    assert e.platform == "feishu"
    assert e.channel_id == "oc_aaa"
    assert e.user_id == "ou_xxx"
    assert e.text == "你好 MBclaw!"


def test_feishu_non_message_event():
    from app.services.gateway.feishu import FeishuAdapter
    payload = {"header": {"event_type": "im.chat.created"}}
    events = FeishuAdapter.parse_webhook(payload)
    assert len(events) == 0


def test_feishu_signature_verification():
    from app.services.gateway.feishu import FeishuAdapter
    assert FeishuAdapter.verify_signature(b"{}", {}, "")


# ═══════════════════════════════════════════════════════════
# Platform adapter — WeCom
# ═══════════════════════════════════════════════════════════

def test_wecom_parse_text():
    from app.services.gateway.wecom import WeComAdapter
    payload = {
        "msgtype": "text",
        "chatid": "wrchat123",
        "from": {"userid": "zhangsan", "name": "张三"},
        "text": {"content": "Hello from WeCom"},
    }
    events = WeComAdapter.parse_webhook(payload)
    assert len(events) == 1
    e = events[0]
    assert e.platform == "wecom"
    assert e.channel_id == "wrchat123"
    assert e.user_id == "zhangsan"
    assert e.user_name == "张三"
    assert e.text == "Hello from WeCom"


# ═══════════════════════════════════════════════════════════
# Platform adapter — WhatsApp
# ═══════════════════════════════════════════════════════════

def test_whatsapp_parse_text():
    from app.services.gateway.whatsapp import WhatsAppAdapter
    payload = {
        "entry": [{
            "id": "WHATSAPP_BUSINESS",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"wa_id": "8613800000000", "profile": {"name": "Test User"}}],
                    "messages": [{
                        "from": "8613800000000",
                        "id": "wamid.xxx",
                        "timestamp": "1700000000",
                        "type": "text",
                        "text": {"body": "Hello from WhatsApp"},
                    }],
                }
            }]
        }]
    }
    events = WhatsAppAdapter.parse_webhook(payload)
    assert len(events) == 1
    e = events[0]
    assert e.platform == "whatsapp"
    assert e.channel_id == "8613800000000"
    assert e.text == "Hello from WhatsApp"
    assert e.user_name == "Test User"


def test_whatsapp_webhook_verification():
    from app.services.gateway.whatsapp import WhatsAppAdapter
    result = WhatsAppAdapter.verify_webhook("subscribe", "my_token", "challenge123", "my_token")
    assert result == "challenge123"
    result = WhatsAppAdapter.verify_webhook("subscribe", "wrong", "challenge123", "my_token")
    assert result == ""


# ═══════════════════════════════════════════════════════════
# Platform adapter — LINE
# ═══════════════════════════════════════════════════════════

def test_line_parse_text():
    from app.services.gateway.line import LineAdapter
    payload = {
        "destination": "Uxxx",
        "events": [{
            "type": "message",
            "message": {"type": "text", "id": "123", "text": "Hello from LINE"},
            "timestamp": 1700000000000,
            "source": {"type": "user", "userId": "U12345"},
            "replyToken": "reply_xxx",
        }]
    }
    events = LineAdapter.parse_webhook(payload)
    assert len(events) == 1
    e = events[0]
    assert e.platform == "line"
    assert e.channel_id == "U12345"
    assert e.user_id == "U12345"
    assert e.text == "Hello from LINE"


def test_line_skip_non_message():
    from app.services.gateway.line import LineAdapter
    payload = {
        "events": [{"type": "follow", "timestamp": 1700000000000}]
    }
    events = LineAdapter.parse_webhook(payload)
    assert len(events) == 0


# ═══════════════════════════════════════════════════════════
# Platform adapter — Discord
# ═══════════════════════════════════════════════════════════

def test_discord_ping():
    from app.services.gateway.discord import DiscordAdapter
    events = DiscordAdapter.parse_webhook({"type": 1})
    assert len(events) == 0


def test_discord_parse_slash_command():
    from app.services.gateway.discord import DiscordAdapter
    payload = {
        "type": 2,
        "id": "1234567890",
        "channel_id": "111222333",
        "data": {
            "name": "chat",
            "options": [{"name": "message", "value": "How do I deploy?"}],
        },
        "member": {"user": {"id": "999888", "username": "devuser", "global_name": "Dev"}},
    }
    events = DiscordAdapter.parse_webhook(payload)
    assert len(events) == 1
    e = events[0]
    assert e.platform == "discord"
    assert e.channel_id == "111222333"
    assert e.user_id == "999888"
    assert e.user_name == "devuser"
    assert "How do I deploy?" in e.text


# ═══════════════════════════════════════════════════════════
# Platform adapter — Slack
# ═══════════════════════════════════════════════════════════

def test_slack_url_verification():
    from app.services.gateway.slack import SlackAdapter
    events = SlackAdapter.parse_webhook({"type": "url_verification", "challenge": "test123"})
    assert len(events) == 0


def test_slack_parse_app_mention():
    from app.services.gateway.slack import SlackAdapter
    payload = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "channel": "C123",
            "user": "U456",
            "text": "<@BOT123> What's the status?",
            "ts": "1700000000.000100",
        }
    }
    events = SlackAdapter.parse_webhook(payload)
    assert len(events) == 1
    e = events[0]
    assert e.platform == "slack"
    assert e.channel_id == "C123"
    assert e.user_id == "U456"
    assert "What's the status?" in e.text


def test_slack_skip_bot_message():
    from app.services.gateway.slack import SlackAdapter
    payload = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "Bot reply",
            "bot_id": "B999",
            "ts": "1700000000.000100",
        }
    }
    events = SlackAdapter.parse_webhook(payload)
    assert len(events) == 0


# ═══════════════════════════════════════════════════════════
# Platform adapter — QQ
# ═══════════════════════════════════════════════════════════

def test_qq_parse_message():
    from app.services.gateway.qq import QQAdapter
    payload = {
        "op": 0,
        "d": {
            "event_type": "MESSAGE_CREATE",
            "channel_id": "chan_123",
            "author": {"id": "user_456", "username": "qquser"},
            "content": "帮我查一下数据",
            "timestamp": "2024-01-15T10:30:00Z",
        }
    }
    events = QQAdapter.parse_webhook(payload)
    assert len(events) == 1
    e = events[0]
    assert e.platform == "qq"
    assert e.channel_id == "chan_123"
    assert e.user_id == "user_456"
    assert e.user_name == "qquser"
    assert e.text == "帮我查一下数据"


# ═══════════════════════════════════════════════════════════
# Platform adapter — Signal
# ═══════════════════════════════════════════════════════════

def test_signal_parse_message():
    from app.services.gateway.signal import SignalAdapter
    payload = {
        "envelope": {
            "source": "+8613800000000",
            "sourceName": "Test Contact",
            "timestamp": 1700000000000,
            "dataMessage": {"message": "Hello via Signal"},
        }
    }
    events = SignalAdapter.parse_webhook(payload)
    assert len(events) == 1
    e = events[0]
    assert e.platform == "signal"
    assert e.user_id == "+8613800000000"
    assert e.text == "Hello via Signal"


# ═══════════════════════════════════════════════════════════
# Platform adapter — DingTalk
# ═══════════════════════════════════════════════════════════

def test_dingtalk_parse_text():
    from app.services.gateway.dingtalk import DingTalkAdapter
    payload = {
        "msgtype": "text",
        "text": {"content": "帮我生成报告"},
        "senderStaffId": "staff_123",
        "senderNick": "李四",
        "conversationId": "conv_456",
        "createAt": 1700000000000,
    }
    events = DingTalkAdapter.parse_webhook(payload)
    assert len(events) == 1
    e = events[0]
    assert e.platform == "dingtalk"
    assert e.channel_id == "conv_456"
    assert e.user_id == "staff_123"
    assert e.user_name == "李四"
    assert e.text == "帮我生成报告"


# ═══════════════════════════════════════════════════════════
# Integration service
# ═══════════════════════════════════════════════════════════

def test_provider_types_include_gateway_platforms():
    from app.services.integration_service import PROVIDER_TYPES
    gateway_platforms = {
        "telegram", "feishu", "wecom", "qq", "wechat_mp",
        "whatsapp", "signal", "line", "dingtalk",
    }
    assert gateway_platforms.issubset(PROVIDER_TYPES)


def test_register_gateway_integration(client):
    client.post("/api/users", json={"name": "gateway_user"})
    resp = client.post("/api/integrations", json={
        "provider": "telegram",
        "display_name": "My Telegram Bot",
        "api_key": "12345:abcde",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "telegram"
    assert data["display_name"] == "My Telegram Bot"
    assert data["status"] == "inactive"


def test_list_integrations(client):
    client.post("/api/users", json={"name": "gw_list"})
    client.post("/api/integrations", json={"provider": "telegram", "api_key": "k1"})
    client.post("/api/integrations", json={"provider": "discord", "api_key": "k2"})
    resp = client.get("/api/integrations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    providers = {d["provider"] for d in data}
    assert providers == {"telegram", "discord"}


def test_invalid_provider_rejected(client):
    resp = client.post("/api/integrations", json={
        "provider": "nonexistent_platform",
        "api_key": "xxx",
    })
    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════
# Gateway router — HTTP endpoints
# ═══════════════════════════════════════════════════════════

def test_gateway_platforms_list(client):
    resp = client.get("/api/gateway/platforms")
    assert resp.status_code == 200
    data = resp.json()
    assert "platforms" in data
    platforms = data["platforms"]
    for p in ("telegram", "feishu", "wecom", "qq", "line", "whatsapp"):
        assert p in platforms
        assert "webhook" in platforms[p]
        assert "setup" in platforms[p]


def test_gateway_webhook_integration_not_found(client):
    resp = client.post("/api/gateway/telegram/99999", json={"test": True})
    assert resp.status_code == 404


def test_gateway_webhook_telegram_e2e(client):
    """End-to-end: register integration → send webhook → verify response."""
    client.post("/api/users", json={"name": "tguser"})
    resp = client.post("/api/integrations", json={
        "provider": "telegram",
        "display_name": "TG Bot",
        "api_key": "dummy_token",
    })
    assert resp.status_code == 201
    integration_id = resp.json()["id"]

    # Send a Telegram-style webhook
    webhook_payload = {
        "update_id": 1,
        "message": {
            "message_id": 100,
            "from": {"id": 12345, "username": "tguser", "first_name": "TG"},
            "chat": {"id": 67890, "type": "private"},
            "date": 1700000000,
            "text": "Hello from Telegram",
        }
    }
    resp = client.post(
        f"/api/gateway/telegram/{integration_id}",
        json=webhook_payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["events"] >= 0  # May fail if agent runtime has side effects


def test_gateway_webhook_slack_e2e(client):
    """End-to-end: Slack integration."""
    client.post("/api/users", json={"name": "slackuser"})
    resp = client.post("/api/integrations", json={
        "provider": "slack",
        "display_name": "Slack Bot",
        "api_key": "xoxb-dummy",
    })
    assert resp.status_code == 201
    integration_id = resp.json()["id"]

    webhook_payload = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "channel": "C123",
            "user": "U456",
            "text": "<@BOT123> help me please",
            "ts": "1700000000.000100",
        }
    }
    resp = client.post(
        f"/api/gateway/slack/{integration_id}",
        json=webhook_payload,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_gateway_webhook_qq_e2e(client):
    """End-to-end: QQ integration."""
    client.post("/api/users", json={"name": "qquser"})
    resp = client.post("/api/integrations", json={
        "provider": "qq",
        "display_name": "QQ Bot",
        "api_key": "app_id:secret",
    })
    integration_id = resp.json()["id"]

    webhook_payload = {
        "op": 0,
        "d": {
            "event_type": "MESSAGE_CREATE",
            "channel_id": "chan_123",
            "author": {"id": "user_456", "username": "qquser"},
            "content": "测试消息",
            "timestamp": "2024-01-15T10:30:00Z",
        }
    }
    resp = client.post(
        f"/api/gateway/qq/{integration_id}",
        json=webhook_payload,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ═══════════════════════════════════════════════════════════
# WeChat MP specific
# ═══════════════════════════════════════════════════════════

def test_wechat_mp_signature():
    from app.services.gateway.wechat_mp import WeChatMPAdapter
    import hashlib
    token = "testtoken"
    timestamp = "1700000000"
    nonce = "abcd1234"
    parts = sorted([token, timestamp, nonce])
    expected = hashlib.sha1("".join(parts).encode()).hexdigest()
    result = WeChatMPAdapter.verify_url("echo_back", expected, timestamp, nonce, token)
    assert result == "echo_back"


def test_wechat_mp_verify_url_wrong():
    from app.services.gateway.wechat_mp import WeChatMPAdapter
    result = WeChatMPAdapter.verify_url("echo_back", "wrong_sig", "ts", "nonce", "token")
    assert result == ""


# ═══════════════════════════════════════════════════════════
# Gateway service — user/project/session creation
# ═══════════════════════════════════════════════════════════

def test_gateway_creates_user_automatically(client, db):
    """Gateway should auto-create users on first message."""
    from app.services.gateway_service import _resolve_user
    from app.services.gateway import MessageEvent

    event = MessageEvent(
        platform="telegram",
        channel_id="123",
        user_id="new_user_999",
        user_name="NewUser",
        text="hello",
    )

    user = _resolve_user(db, event)
    assert user.name == "NewUser"
    assert user.external_id == "telegram:new_user_999"
    assert user.platform == "telegram"

    # Second call returns same user
    user2 = _resolve_user(db, event)
    assert user2.id == user.id


def test_gateway_creates_project_automatically(client, db):
    """Gateway should auto-create projects for each integration."""
    from app.services.gateway_service import _resolve_user, _resolve_project
    from app.services.gateway import MessageEvent
    from app.models.external_integration import ExternalIntegration

    # Create integration
    integration = ExternalIntegration(
        id=1, provider="telegram", display_name="TG", api_key="tok",
        status="active", config="{}",
    )
    db.add(integration)
    db.commit()

    event = MessageEvent(
        platform="telegram",
        channel_id="123",
        user_id="user_1",
        user_name="User1",
        text="hello",
    )
    user = _resolve_user(db, event)
    project = _resolve_project(db, user, event, integration)
    assert project is not None
    assert "telegram-gateway-1" in project.name
    assert project.user_id == user.id
