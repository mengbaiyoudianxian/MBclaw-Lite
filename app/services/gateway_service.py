"""Gateway orchestration service — routes incoming messages to Agent Runtime.

Each incoming MessageEvent from any platform goes through:
  1. User lookup / auto-registration (by platform + user_id)
  2. Project lookup / auto-creation
  3. Session creation
  4. Agent Runtime execution
  5. Response back to platform
"""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.external_integration import ExternalIntegration
from app.models.project import Project
from app.models.session import Session
from app.models.user import User
from app.services.gateway import ADAPTERS, MessageEvent

logger = logging.getLogger("mbclaw.gateway")


async def process_gateway_message(
    db: DBSession,
    event: MessageEvent,
    integration: ExternalIntegration,
) -> dict[str, Any]:
    """Process an incoming gateway message through MBclaw Agent Runtime."""

    # 1. Resolve user
    user = _resolve_user(db, event)

    # 2. Resolve project
    project = _resolve_project(db, user, event, integration)

    # 3. Create session
    session = _create_session(db, project, event)

    # 4. Store message
    from app.models.message import Message
    msg = Message(
        session_id=session.id,
        role="user",
        content=event.text,
        created_at=datetime.now().isoformat(),
    )
    db.add(msg)
    db.commit()

    # 5. Run agent if configured
    integration_config = json.loads(integration.config) if integration.config else {}
    auto_run = integration_config.get("auto_run", True)

    if auto_run:
        try:
            from app.services.agent_runtime import run_agent_loop
            result = await run_agent_loop(
                db=db,
                project_id=project.id,
                session=session,
                user_message=event.text,
                user_id=user.id,
            )
            agent_response = result.get("final_response", "")
            tool_calls = result.get("tool_calls", 0)
        except Exception as e:
            logger.error(f"Agent runtime error: {e}")
            agent_response = f"[MBclaw Agent Error] {str(e)}"
            tool_calls = 0
    else:
        agent_response = ""
        tool_calls = 0

    # 6. Send response back to platform
    if agent_response:
        await _send_response(db, event, agent_response, integration)

    # 7. Trigger H3 skill extraction after agent run
    if auto_run and tool_calls >= 3:
        try:
            from app.services.skill_extractor import extract_skill_from_session
            extract_skill_from_session(db, session.id)
        except Exception:
            pass

    return {
        "session_id": session.id,
        "project_id": project.id,
        "user_id": user.id,
        "tool_calls": tool_calls,
        "responded": bool(agent_response),
    }


# ═══════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════

def _resolve_user(db: DBSession, event: MessageEvent) -> User:
    """Find or create user by platform + user_id."""
    # Look up by external_id pattern: {platform}:{user_id}
    external_id = f"{event.platform}:{event.user_id}"

    user = db.query(User).filter(User.external_id == external_id).first()
    if user:
        return user

    # Auto-register new user — ensure unique name
    base_name = event.user_name or f"{event.platform}_user_{event.user_id[:8]}"
    display_name = base_name
    counter = 1
    while db.query(User).filter(User.name == display_name).first():
        display_name = f"{base_name}_{counter}"
        counter += 1

    user = User(
        name=display_name,
        external_id=external_id,
        platform=event.platform,
        created_at=datetime.now().isoformat(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _resolve_project(db: DBSession, user: User, event: MessageEvent,
                     integration: ExternalIntegration) -> Project:
    """Find or create project for this platform integration."""
    project_name = f"{event.platform}-gateway-{integration.id}"

    project = db.query(Project).filter(
        Project.user_id == user.id,
        Project.name == project_name,
    ).first()
    if project:
        project.updated_at = datetime.now().isoformat()
        db.commit()
        return project

    project = Project(
        user_id=user.id,
        name=project_name,
        description=f"Gateway project for {event.platform} messages via integration #{integration.id}",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _create_session(db: DBSession, project: Project, event: MessageEvent) -> Session:
    """Create or reuse active session."""
    # Reuse latest active session if within 30 minutes
    active = db.query(Session).filter(
        Session.project_id == project.id,
        Session.status == "active",
    ).order_by(Session.started_at.desc()).first()

    if active:
        try:
            last_active = datetime.fromisoformat(active.started_at)
            if (datetime.now() - last_active).total_seconds() < 1800:
                return active
        except (ValueError, TypeError):
            pass

    # Calculate session number
    max_num = db.query(Session).filter(
        Session.project_id == project.id
    ).count()

    session = Session(
        project_id=project.id,
        session_number=max_num + 1,
        title=f"{event.platform} chat {datetime.now().strftime('%m-%d %H:%M')}",
        status="active",
        started_at=datetime.now().isoformat(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


async def _send_response(db: DBSession, event: MessageEvent, text: str,
                         integration: ExternalIntegration):
    """Send agent response back to the messaging platform."""
    adapter_cls = ADAPTERS.get(event.platform)
    if not adapter_cls:
        return

    adapter = adapter_cls()
    integration_config = json.loads(integration.config) if integration.config else {}

    try:
        if event.platform == "telegram":
            await adapter.send_message(event.channel_id, text, token=integration.api_key)

        elif event.platform == "feishu":
            parts = integration.api_key.split(":", 1)
            if len(parts) == 2:
                await adapter.send_message(
                    event.channel_id, text,
                    app_id=parts[0], app_secret=parts[1],
                    base_url=integration.base_url or "https://open.feishu.cn",
                )

        elif event.platform == "wecom":
            await adapter.send_message(
                event.channel_id, text,
                webhook_url=integration.base_url,
            )

        elif event.platform == "qq":
            parts = integration.api_key.split(":", 1)
            if len(parts) == 2:
                await adapter.send_message(
                    event.channel_id, text,
                    app_id=parts[0], client_secret=parts[1],
                )

        elif event.platform == "wechat_mp":
            parts = integration.api_key.split(":", 1)
            if len(parts) == 2:
                await adapter.send_message(
                    event.channel_id, text,
                    app_id=parts[0], app_secret=parts[1],
                )

        elif event.platform == "whatsapp":
            await adapter.send_message(
                event.channel_id, text,
                phone_number_id=integration.base_url,
                access_token=integration.api_key,
            )

        elif event.platform == "signal":
            await adapter.send_message(
                event.channel_id, text,
                base_url=integration.base_url,
                sender=integration_config.get("sender_number", ""),
            )

        elif event.platform == "line":
            await adapter.send_message(
                event.channel_id, text,
                channel_token=integration.api_key,
            )

        elif event.platform == "discord":
            await adapter.send_message(
                event.channel_id, text,
                bot_token=integration.api_key,
            )

        elif event.platform == "slack":
            await adapter.send_message(
                event.channel_id, text,
                bot_token=integration.api_key,
            )

        elif event.platform == "dingtalk":
            await adapter.send_message(
                event.channel_id, text,
                webhook_url=integration.base_url,
            )

    except Exception as e:
        logger.error(f"Failed to send {event.platform} response: {e}")
