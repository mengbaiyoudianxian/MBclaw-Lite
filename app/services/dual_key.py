"""Project 5: Dual-Key Collaboration — Maker + Reviewer loop.

Key1 (Maker): generates content autonomously
Key2 (Reviewer): reviews, scores, suggests fixes
Loop: Maker → Reviewer → fix → re-review → approve or reject

Use case examples:
  - Code generation: Maker writes code, Reviewer checks quality
  - Skill extraction: Maker proposes skill, Reviewer validates
  - Memory consolidation: Maker consolidates entries, Reviewer checks budget
"""

from datetime import datetime
from enum import Enum
from typing import Any


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"
    REJECT = "reject"


class DualKey:
    """Maker + Reviewer orchestration for one review cycle."""

    def __init__(self, maker_key: str = "key1", reviewer_key: str = "key2"):
        self.maker_key = maker_key
        self.reviewer_key = reviewer_key
        self.cycles: list[dict] = []
        self.final_decision: str | None = None

    def maker_produce(self, content: str, artifact_type: str = "code") -> dict:
        """Maker generates content. Returns the artifact for review."""
        cycle = {
            "number": len(self.cycles) + 1,
            "maker_key": self.maker_key,
            "artifact_type": artifact_type,
            "content": content,
            "created_at": datetime.now().isoformat(),
            "review": None,
        }
        self.cycles.append(cycle)
        return cycle

    def reviewer_evaluate(self, cycle_number: int, decision: ReviewDecision,
                          score: int = 0, feedback: str = "",
                          suggested_fix: str = "") -> dict:
        """Reviewer evaluates the maker's output."""
        # Find the cycle
        for c in self.cycles:
            if c["number"] == cycle_number:
                c["review"] = {
                    "reviewer_key": self.reviewer_key,
                    "decision": decision.value,
                    "score": max(0, min(10, score)),
                    "feedback": feedback,
                    "suggested_fix": suggested_fix,
                    "reviewed_at": datetime.now().isoformat(),
                }
                self.final_decision = decision.value
                return c
        return {"error": "cycle_not_found", "cycle_number": cycle_number}

    def maker_revise(self, cycle_number: int, revised_content: str) -> dict:
        """Maker revises based on reviewer feedback."""
        cycle = {
            "number": len(self.cycles) + 1,
            "maker_key": self.maker_key,
            "artifact_type": self.cycles[cycle_number - 1].get("artifact_type", "code") if cycle_number <= len(self.cycles) else "code",
            "content": revised_content,
            "created_at": datetime.now().isoformat(),
            "review": None,
            "previous_cycle": cycle_number,
        }
        self.cycles.append(cycle)
        return cycle

    def get_summary(self) -> dict:
        total = len(self.cycles)
        approved = sum(1 for c in self.cycles
                       if c.get("review") and c["review"]["decision"] == "approve")
        rejected = sum(1 for c in self.cycles
                       if c.get("review") and c["review"]["decision"] == "reject")
        avg_score = sum(c["review"]["score"] for c in self.cycles if c.get("review")) / max(1, sum(1 for c in self.cycles if c.get("review")))

        return {
            "maker_key": self.maker_key,
            "reviewer_key": self.reviewer_key,
            "total_cycles": total,
            "approved": approved,
            "rejected": rejected,
            "average_score": round(avg_score, 1),
            "final_decision": self.final_decision,
            "cycles": self.cycles,
        }
