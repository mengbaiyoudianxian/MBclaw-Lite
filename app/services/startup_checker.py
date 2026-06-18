"""Project 9: Startup Checker + Self-Healer.

Five-phase startup validation:
  1. Dependencies (Python version, packages, DB connection)
  2. LLM API Key connectivity (ping each configured key)
  3. External integration connectivity
  4. Filesystem permissions (data/, memory/, snapshots/ writable)
  5. Config completeness (required fields present)

Conflict handling:
  - Non-fatal → warning log → continue boot
  - Fatal     → bypass if possible → ensure core startup → notify user

Self-healing:
  - Auto-fix: create missing dirs, set defaults
  - Need user: generate fix plan → notify
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from typing import Any

from app.config import DATA_DIR, OLLAMA_BASE_URL

REQUIRED_DIRS = [
    os.path.join(DATA_DIR, "memory"),
    os.path.join(DATA_DIR, "transcripts"),
    os.path.join(DATA_DIR, "snapshots"),
    os.path.join(DATA_DIR, "chroma"),
]

REQUIRED_CONFIGS = {
    "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
    "OLLAMA_MODEL": os.environ.get("OLLAMA_MODEL", ""),
}

CheckResult = dict[str, Any]


class StartupChecker:
    def __init__(self):
        self.results: list[CheckResult] = []
        self.auto_fixes: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.passed = True

    # ── public API ─────────────────────────────────────────

    async def run_all(self) -> dict:
        """Run all 5 phases. Returns full report."""
        self._phase1_dependencies()
        await self._phase2_llm_keys()
        await self._phase3_integrations()
        self._phase4_filesystem()
        self._phase5_config()

        return {
            "status": "healthy" if self.passed else "degraded",
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version,
            "phases": self.results,
            "auto_fixes_applied": self.auto_fixes,
            "warnings": self.warnings,
            "errors": self.errors,
            "passed": self.passed,
        }

    # ── phase 1: dependencies ─────────────────────────────

    def _phase1_dependencies(self):
        report = {"phase": "dependencies", "checks": [], "passed": True}

        # Python version
        py_ok = sys.version_info >= (3, 10)
        report["checks"].append({
            "name": "python_version",
            "status": "ok" if py_ok else "error",
            "detail": f"Python {sys.version.split()[0]}",
            "required": ">=3.10",
        })
        if not py_ok:
            self.errors.append("Python >=3.10 required")
            report["passed"] = False

        # Packages
        try:
            import fastapi, sqlalchemy, chromadb
            pkg_ok = True
            pkg_detail = "fastapi, sqlalchemy, chromadb available"
        except ImportError as e:
            pkg_ok = False
            pkg_detail = f"Missing: {e}"
            self.errors.append(f"Missing package: {e}")
            report["passed"] = False

        report["checks"].append({
            "name": "packages", "status": "ok" if pkg_ok else "error",
            "detail": pkg_detail,
        })

        # DB connection
        try:
            from app.database import engine
            with engine.connect() as conn:
                conn.execute(conn.default_schema_name)
            db_ok = True
        except Exception as e:
            db_ok = False
            self.errors.append(f"DB connection failed: {e}")
            report["passed"] = False

        report["checks"].append({
            "name": "database", "status": "ok" if db_ok else "error",
            "detail": "SQLite connected" if db_ok else str(e if 'e' in dir() else "unknown"),
        })

        self.results.append(report)
        if not report["passed"]:
            self.passed = False

    # ── phase 2: LLM keys ─────────────────────────────────

    async def _phase2_llm_keys(self):
        report = {"phase": "llm_keys", "checks": [], "passed": True}

        # Check Ollama connectivity
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    ollama_ok = True
                    ollama_detail = f"{len(models)} models available"
                    model = os.environ.get("OLLAMA_MODEL", "")
                    if model and model not in " ".join(models):
                        self.warnings.append(f"Model '{model}' not found in Ollama")
                else:
                    ollama_ok = False
                    ollama_detail = f"HTTP {resp.status_code}"
        except Exception as e:
            ollama_ok = False
            ollama_detail = str(e)
            self.warnings.append(f"Ollama not reachable: {e}")

        report["checks"].append({
            "name": "ollama", "status": "ok" if ollama_ok else "warning",
            "detail": ollama_detail, "base_url": OLLAMA_BASE_URL,
        })
        # Ollama being down is non-fatal for MBclaw-Lite core

        self.results.append(report)

    # ── phase 3: external integrations ────────────────────

    async def _phase3_integrations(self):
        report = {"phase": "integrations", "checks": [], "passed": True}
        try:
            from app.database import SessionLocal
            from app.models.external_integration import ExternalIntegration
            db = SessionLocal()
            integrations = db.query(ExternalIntegration).filter(
                ExternalIntegration.status == "active"
            ).all()
            report["checks"].append({
                "name": "active_integrations",
                "status": "ok",
                "detail": f"{len(integrations)} active",
            })
            db.close()
        except Exception as e:
            report["checks"].append({
                "name": "integrations", "status": "warning",
                "detail": f"Could not query: {e}",
            })
        self.results.append(report)

    # ── phase 4: filesystem ───────────────────────────────

    def _phase4_filesystem(self):
        report = {"phase": "filesystem", "checks": [], "passed": True}

        for d in REQUIRED_DIRS:
            try:
                os.makedirs(d, exist_ok=True)
                # Test writability
                test_file = os.path.join(d, ".write_test")
                with open(test_file, "w") as f:
                    f.write("ok")
                os.remove(test_file)
                report["checks"].append({
                    "name": f"dir_{os.path.basename(d)}",
                    "status": "ok", "detail": f"{d} writable",
                })
            except PermissionError:
                report["checks"].append({
                    "name": f"dir_{os.path.basename(d)}",
                    "status": "error", "detail": f"{d} NOT writable",
                })
                self.errors.append(f"Directory not writable: {d}")
                report["passed"] = False
            except Exception as e:
                report["checks"].append({
                    "name": f"dir_{os.path.basename(d)}",
                    "status": "error", "detail": str(e),
                })
                self.errors.append(f"Directory error {d}: {e}")
                report["passed"] = False

        self.results.append(report)
        if not report["passed"]:
            self.passed = False

    # ── phase 5: config ───────────────────────────────────

    def _phase5_config(self):
        report = {"phase": "config", "checks": [], "passed": True}

        for key, value in REQUIRED_CONFIGS.items():
            if value:
                report["checks"].append({
                    "name": key, "status": "ok",
                    "detail": value[:50] + ("..." if len(str(value)) > 50 else ""),
                })
            else:
                report["checks"].append({
                    "name": key, "status": "warning",
                    "detail": "not set",
                })
                self.warnings.append(f"Config '{key}' is not set")

        self.results.append(report)

    # ── self-healer ───────────────────────────────────────

    def self_heal(self) -> list[str]:
        """Auto-fix non-fatal issues. Returns list of fixes applied."""
        fixes = []

        # Create missing directories
        for d in REQUIRED_DIRS:
            if not os.path.exists(d):
                try:
                    os.makedirs(d, exist_ok=True)
                    fixes.append(f"Created directory: {d}")
                except Exception as e:
                    fixes.append(f"Failed to create {d}: {e}")

        # Create default config file if missing
        config_path = os.path.join(DATA_DIR, "config.json")
        if not os.path.exists(config_path):
            try:
                with open(config_path, "w") as f:
                    json.dump({"initialized": True, "created_at": datetime.now().isoformat()}, f)
                fixes.append(f"Created default config: {config_path}")
            except Exception:
                pass

        self.auto_fixes = fixes
        return fixes


# ── singleton ─────────────────────────────────────────────

_checker: StartupChecker | None = None


async def run_startup_checks() -> dict:
    global _checker
    _checker = StartupChecker()
    _checker.self_heal()
    return await _checker.run_all()


def get_health_report() -> dict | None:
    if _checker is None:
        return None
    return {
        "status": "healthy" if _checker.passed else "degraded",
        "passed": _checker.passed,
        "auto_fixes": _checker.auto_fixes,
        "warnings": _checker.warnings,
        "errors": _checker.errors,
    }
