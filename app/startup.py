"""Startup checker — validate environment before gateway launch."""

import os, sys


def run_startup_checks() -> list[str]:
    """Run all startup checks, return list of warnings."""
    warnings = []

    db_path = os.getenv("MBCLAW_DB_PATH", "data/mbclaw.db")
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.isdir(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
        except Exception:
            warnings.append(f"Cannot create DB directory: {db_dir}")

    api_key = os.getenv("MBCLAW_LLM_API_KEY", "")
    mock = os.getenv("MBCLAW_LLM_MOCK", "")
    if not api_key and mock != "1":
        warnings.append("No LLM API key set. Agent will return 503 on close. Set MBCLAW_LLM_API_KEY or MBCLAW_LLM_MOCK=1.")

    try:
        import fastapi, uvicorn, sqlalchemy, jieba, httpx
    except ImportError as e:
        warnings.append(f"Missing dependency: {e}")

    return warnings


def print_startup_banner():
    print("🦞 MBclaw v0.1.0")
    for w in run_startup_checks():
        print(f"  ⚠ {w}")
    print("  Ready.")
