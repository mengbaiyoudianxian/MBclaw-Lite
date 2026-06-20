"""Regression / rollback detection service (Project 13).

Compares git state before and after a task to detect:
  - Large deletions (potential rollback)
  - Core MBclaw file modifications
  - Accidental reversions of previous fixes
"""

import json
import os
import subprocess
from datetime import datetime
from typing import Any

from app.config import DATA_DIR

# Files considered "core" — modifications to these trigger critical alerts
CORE_FILES = [
    "app/services/memory_service.py",
    "app/services/memory_store.py",
    "app/services/transcript_service.py",
    "app/services/curator.py",
    "app/services/skill_extractor.py",
    "app/services/agent_runtime.py",
    "app/services/classification_service.py",
    "app/services/snapshot_service.py",
    "app/models/action_memory.py",
    "app/models/skill_card.py",
    "app/routers/memory.py",
    "app/database.py",
    "app/main.py",
]

CHANGE_LOG_PATH = os.path.join(DATA_DIR, "change_log.jsonl")


def _run_git_diff(project_root: str, before: str, after: str = "HEAD") -> str:
    """Run git diff between two refs."""
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", before, after],
            cwd=project_root,
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout
    except Exception:
        return ""


def _run_git_diff_files(project_root: str, before: str, after: str = "HEAD") -> list[dict]:
    """Get per-file diff stats."""
    try:
        result = subprocess.run(
            ["git", "diff", "--numstat", before, after],
            cwd=project_root,
            capture_output=True, text=True, timeout=10,
        )
        files = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) == 3:
                added, removed, path = parts
                files.append({
                    "path": path,
                    "added_lines": int(added) if added != "-" else 0,
                    "removed_lines": int(removed) if removed != "-" else 0,
                })
        return files
    except Exception:
        return []


def _run_git_log(project_root: str, count: int = 5) -> list[dict]:
    """Get recent commits."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{count}", "--format=%H||%s||%ai"],
            cwd=project_root,
            capture_output=True, text=True, timeout=10,
        )
        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("||")
            if len(parts) == 3:
                commits.append({
                    "hash": parts[0],
                    "message": parts[1],
                    "date": parts[2],
                })
        return commits
    except Exception:
        return []


def detect_regression(
    project_root: str,
    before_ref: str = "HEAD~1",
    after_ref: str = "HEAD",
) -> dict[str, Any]:
    """Detect potential regressions between two git refs.

    Returns: {
        "has_regressions": bool,
        "severity": "none" | "warning" | "critical",
        "findings": [...],
        "summary": str,
    }
    """
    diff_files = _run_git_diff_files(project_root, before_ref, after_ref)
    findings = []
    critical_count = 0
    warning_count = 0

    for f in diff_files:
        path = f["path"]
        added = f["added_lines"]
        removed = f["removed_lines"]

        finding = {"path": path, "added": added, "removed": removed, "level": "info"}

        # Rule 1: Massive deletion without replacement
        if removed > added * 3 and removed > 20:
            finding["level"] = "warning"
            finding["reason"] = f"大量删除 ({removed} 行删除 vs {added} 行新增)"
            warning_count += 1

        # Rule 2: Core file modified
        if path in CORE_FILES and removed > 0:
            finding["level"] = "critical"
            finding["reason"] = f"核心文件 {path} 被修改，删除了 {removed} 行"
            critical_count += 1

        # Rule 3: Core file deleted entirely
        if path in CORE_FILES and added == 0 and removed > 100:
            finding["level"] = "critical"
            finding["reason"] = f"核心文件 {path} 可能被完全删除"
            critical_count += 1

        if finding["level"] != "info":
            findings.append(finding)

    # Determine overall severity
    if critical_count > 0:
        severity = "critical"
    elif warning_count > 0:
        severity = "warning"
    else:
        severity = "none"

    # Generate summary
    if severity == "critical":
        summary = f"检测到 {critical_count} 个严重回滚 + {warning_count} 个警告，建议立即审查"
    elif severity == "warning":
        summary = f"检测到 {warning_count} 个可能回滚，建议审查后再继续"
    else:
        summary = "未检测到回滚，代码变更正常"

    return {
        "has_regressions": severity != "none",
        "severity": severity,
        "findings": findings,
        "summary": summary,
        "files_changed": len(diff_files),
        "checked_at": datetime.now().isoformat(),
    }


def log_change(db, session_id: int, change_type: str, detail: dict):
    """Append a change log entry."""
    os.makedirs(os.path.dirname(CHANGE_LOG_PATH), exist_ok=True)
    entry = {
        "session_id": session_id,
        "type": change_type,
        "detail": detail,
        "timestamp": datetime.now().isoformat(),
    }
    with open(CHANGE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def check_and_log_regression(
    db,
    session_id: int,
    project_root: str,
    before_ref: str = "HEAD~1",
    after_ref: str = "HEAD",
) -> dict:
    """Check for regressions and log the result."""
    result = detect_regression(project_root, before_ref, after_ref)

    # Log to change_log
    log_change(db, session_id, "regression_check", {
        "before": before_ref,
        "after": after_ref,
        "severity": result["severity"],
        "findings_count": len(result["findings"]),
    })

    # Also append to session transcript if critical
    if result["severity"] == "critical":
        from app.models.message import Message
        log_msg = Message(
            session_id=session_id,
            role="system",
            content=f"[回滚检测] {result['summary']}",
            message_type="code_change",
            metadata=json.dumps(result, ensure_ascii=False, default=str),
        )
        db.add(log_msg)
        db.commit()

    return result


def rollback_if_needed(
    project_root: str,
    before_ref: str = "HEAD~1",
    auto_rollback: bool = False,
) -> dict:
    """Optionally auto-rollback if critical regression detected."""
    result = detect_regression(project_root, before_ref)
    if result["severity"] == "critical" and auto_rollback:
        try:
            subprocess.run(
                ["git", "reset", "--hard", before_ref],
                cwd=project_root,
                capture_output=True, text=True, timeout=10,
            )
            result["rolled_back"] = True
            result["summary"] += " （已自动回滚）"
        except Exception as e:
            result["rolled_back"] = False
            result["summary"] += f" （自动回滚失败: {e}）"
    return result
