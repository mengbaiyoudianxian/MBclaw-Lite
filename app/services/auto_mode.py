"""Project 4: Full Auto Mode — autonomous decision + parallel product generation.

When user says "全自动", the agent:
  1. Generates multiple parallel solutions
  2. Auto-selects the best one based on heuristics
  3. Executes without step-by-step user confirmation
"""

import json
from datetime import datetime
from typing import Any


AUTO_TRIGGER_KEYWORDS = [
    "全自动", "auto", "自动完成", "不用问我", "直接做", "放手做",
    "full auto", "autonomous", "go ahead",
]

PARALLEL_BRANCH_LIMIT = 5

DecisionResult = dict[str, Any]


class AutoMode:
    """Manages full-auto session state and parallel product tracking."""

    def __init__(self):
        self.branches: list[dict] = []
        self.selected_branch: int | None = None
        self.started_at: str | None = None

    def is_auto_trigger(self, message: str) -> bool:
        """Check if a message triggers auto mode."""
        msg_lower = message.lower()
        return any(kw in msg_lower for kw in AUTO_TRIGGER_KEYWORDS)

    def start(self) -> dict:
        self.started_at = datetime.now().isoformat()
        self.branches = []
        self.selected_branch = None
        return {"mode": "auto", "started_at": self.started_at,
                "branches": 0, "status": "collecting_approaches"}

    def add_branch(self, name: str, approach: str, estimated_steps: int = 0) -> int:
        n = len(self.branches) + 1
        if n > PARALLEL_BRANCH_LIMIT:
            return -1
        self.branches.append({
            "id": n, "name": name, "approach": approach,
            "estimated_steps": estimated_steps,
            "status": "generating",
            "error_count": 0,
            "result": None,
        })
        return n

    def update_branch(self, branch_id: int, status: str = "",
                      error_count: int = 0, result: str | None = None) -> bool:
        for b in self.branches:
            if b["id"] == branch_id:
                if status:
                    b["status"] = status
                if error_count:
                    b["error_count"] = error_count
                if result is not None:
                    b["result"] = result
                return True
        return False

    def select_best(self) -> int | None:
        """Auto-select the best branch by lowest error count."""
        if not self.branches:
            return None
        # Prefer branches with results and zero errors
        viable = [b for b in self.branches
                  if b["status"] in ("generated", "tested") and b["error_count"] == 0]
        if viable:
            self.selected_branch = viable[0]["id"]
            return self.selected_branch
        # Fallback: lowest error count
        best = min(self.branches, key=lambda b: b["error_count"])
        self.selected_branch = best["id"]
        return self.selected_branch

    def summary(self) -> dict:
        return {
            "mode": "auto",
            "started_at": self.started_at,
            "total_branches": len(self.branches),
            "selected_branch": self.selected_branch,
            "branches": self.branches,
        }


# ── singleton ─────────────────────────────────────────────

_auto_modes: dict[int, AutoMode] = {}  # project_id → AutoMode


def get_auto_mode(project_id: int) -> AutoMode:
    if project_id not in _auto_modes:
        _auto_modes[project_id] = AutoMode()
    return _auto_modes[project_id]
