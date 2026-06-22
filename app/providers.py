"""Multi-provider LLM dispatch — R0 extension, derived from model_service.py."""

import os
from app.models import ModelProfile
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.llm import LLMClient



class ProviderInfo(BaseModel):
    key_alias: str
    provider: str
    model_name: str
    active: bool
    priority: int


# ── built-in defaults ───────────────────────────────────────

BUILTIN_PROVIDERS = [
    {"key_alias": "openai-gpt4o", "provider": "openai", "model_name": "gpt-4o",
     "api_base": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY", "priority": 10},
    {"key_alias": "openai-gpt4o-mini", "provider": "openai", "model_name": "gpt-4o-mini",
     "api_base": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY", "priority": 5},
    {"key_alias": "local-ollama", "provider": "local", "model_name": "llama3",
     "api_base": "http://localhost:11434/v1", "api_key_env": "", "priority": 0},
]


def seed_default_providers(db: Session):
    """Ensure built-in providers exist."""
    for cfg in BUILTIN_PROVIDERS:
        existing = db.query(ModelProfile).filter(ModelProfile.key_alias == cfg["key_alias"]).first()
        if not existing:
            db.add(ModelProfile(**cfg))
    db.commit()


def list_providers(db: Session) -> list[ProviderInfo]:
    """Return all registered providers with status."""
    seed_default_providers(db)
    profiles = db.query(ModelProfile).order_by(ModelProfile.priority.desc()).all()
    result = []
    for p in profiles:
        key = os.getenv(p.api_key_env) if p.api_key_env else None
        active = p.is_active and (bool(key) or p.provider == "local")
        result.append(ProviderInfo(
            key_alias=p.key_alias, provider=p.provider,
            model_name=p.model_name, active=active, priority=p.priority,
        ))
    return result


def get_best_client(db: Session) -> LLMClient:
    """Return the best available LLM client with automatic failover."""
    seed_default_providers(db)
    profiles = db.query(ModelProfile).filter(
        ModelProfile.is_active == True
    ).order_by(ModelProfile.priority.desc()).all()

    # Try env-configured key first
    env_key = os.getenv("MBCLAW_LLM_API_KEY")
    if env_key:
        return LLMClient()

    for p in profiles:
        key = os.getenv(p.api_key_env) if p.api_key_env else None
        if key or p.provider == "local":
            return LLMClient(base_url=p.api_base, api_key=key or "", model=p.model_name)

    return LLMClient()
