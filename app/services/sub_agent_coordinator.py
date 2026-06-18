"""Project 10: Multi Sub-Agent Coordination.

Shared channel for sub-agents to communicate, avoid duplication,
and negotiate conflicts.

Key mechanisms:
  - Claim channel: sub-agent claims a task → others skip it
  - Dedup: same task detected → merge into one
  - Conflict negotiation: two agents on same file → last-write-wins + notification
"""

import json
from datetime import datetime
from typing import Any


class SubAgentCoordinator:
    """Manages communication between sub-agents for one project."""

    def __init__(self):
        self.channel: list[dict] = []
        self.claims: dict[str, dict] = {}
        self.conflicts: list[dict] = []

    # ── shared channel ─────────────────────────────────────

    def broadcast(self, agent_id: str, message: str, msg_type: str = "info") -> int:
        msg = {
            "id": len(self.channel) + 1,
            "agent_id": agent_id,
            "type": msg_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        self.channel.append(msg)
        return msg["id"]

    def read_since(self, last_id: int) -> list[dict]:
        return [m for m in self.channel if m["id"] > last_id]

    # ── task claiming ──────────────────────────────────────

    def claim(self, agent_id: str, task_name: str) -> bool:
        """Attempt to claim a task. Returns True if claim succeeds."""
        if task_name in self.claims:
            existing = self.claims[task_name]
            if existing["agent_id"] != agent_id:
                return False
        self.claims[task_name] = {
            "agent_id": agent_id,
            "claimed_at": datetime.now().isoformat(),
            "status": "claimed",
        }
        self.broadcast(agent_id, f"Claimed task: {task_name}", "claim")
        return True

    def release(self, agent_id: str, task_name: str) -> bool:
        if task_name in self.claims and self.claims[task_name]["agent_id"] == agent_id:
            self.claims[task_name]["status"] = "released"
            self.broadcast(agent_id, f"Released task: {task_name}", "release")
            return True
        return False

    def complete_task(self, agent_id: str, task_name: str, result: str = "") -> bool:
        if task_name in self.claims:
            self.claims[task_name]["status"] = "completed"
            self.claims[task_name]["result"] = result
            self.claims[task_name]["completed_at"] = datetime.now().isoformat()
            self.broadcast(agent_id, f"Completed task: {task_name}", "complete")
            return True
        # Auto-claim if not claimed
        self.claim(agent_id, task_name)
        self.claims[task_name]["status"] = "completed"
        self.claims[task_name]["result"] = result
        return True

    def get_unclaimed(self) -> list[str]:
        return [name for name, c in self.claims.items()
                if c.get("status") == "released"]

    # ── dedup ──────────────────────────────────────────────

    def dedup_task(self, task_name: str) -> str | None:
        """Check if a similar task is already claimed/completed."""
        task_lower = task_name.lower().split()
        if not task_lower:
            task_lower = [task_name.lower()]
        for name, claim in self.claims.items():
            name_lower = name.lower().split()
            if not name_lower:
                name_lower = [name.lower()]
            overlap = len(set(task_lower) & set(name_lower))
            min_len = min(len(task_lower), len(name_lower)) or 1
            ratio = overlap / min_len
            if ratio >= 0.5 and claim["status"] in ("claimed", "completed"):
                return name
        return None

    # ── conflict negotiation ───────────────────────────────

    def report_conflict(self, agent_id: str, file_path: str, description: str):
        self.conflicts.append({
            "agent_id": agent_id,
            "file_path": file_path,
            "description": description,
            "timestamp": datetime.now().isoformat(),
            "resolution": "last_write_wins",
        })
        self.broadcast(agent_id,
                       f"Conflict on {file_path}: {description} (last-write-wins)",
                       "conflict")

    def get_summary(self) -> dict:
        return {
            "agents_registered": len(set(c.get("agent_id", "") for c in self.claims.values())),
            "tasks_claimed": len(self.claims),
            "tasks_completed": sum(1 for c in self.claims.values() if c.get("status") == "completed"),
            "conflicts": len(self.conflicts),
            "messages": len(self.channel),
        }


# ── singleton ─────────────────────────────────────────────

_coordinators: dict[int, SubAgentCoordinator] = {}


def get_coordinator(project_id: int) -> SubAgentCoordinator:
    if project_id not in _coordinators:
        _coordinators[project_id] = SubAgentCoordinator()
    return _coordinators[project_id]
