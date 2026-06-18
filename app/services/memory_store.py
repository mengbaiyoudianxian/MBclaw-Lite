"""MemoryStore: dual-state memory with frozen snapshots, char budgets, and batch ops.

Design (inspired by Hermes-Agent):
  - _live_entries: mutable, written to disk immediately (durable)
  - _system_prompt_snapshot: frozen at session start, returned by format_for_system_prompt()
  - Mid-session writes hit _live_entries + disk but NOT the snapshot
    → prefix-cache stable for entire session
  - Hard char budget; on overflow, return entries + error → LLM consolidates
  - Batch API: [remove, replace, add] applied atomically, budget check on final state only
"""

import hashlib
import os
from datetime import datetime
from typing import Optional

from app.config import DATA_DIR

MEMORY_CHAR_LIMIT = 2200
USER_CHAR_LIMIT = 1375
MEMORY_DIR = os.path.join(DATA_DIR, "memory")

# Sentinel marker: entries are §-delimited paragraphs
DELIMITER = "\n\n"


class MemoryStore:
    """Per-session memory manager with frozen system-prompt snapshot."""

    def __init__(self, memory_path: str | None = None, user_path: str | None = None,
                 memory_char_limit: int = MEMORY_CHAR_LIMIT,
                 user_char_limit: int = USER_CHAR_LIMIT):
        self._memory_path = memory_path or os.path.join(MEMORY_DIR, "MEMORY.md")
        self._user_path = user_path or os.path.join(MEMORY_DIR, "USER.md")
        self.memory_char_limit = memory_char_limit
        self.user_char_limit = user_char_limit

        # Live state – mutated by tool calls
        self.memory_entries: list[str] = []
        self.user_entries: list[str] = []

        # Frozen snapshot – loaded once at session start, never changes mid-session
        self._system_prompt_snapshot: dict[str, str] = {"memory": "", "user": ""}

        # Drift detection: SHA256 of disk files at load time
        self._memory_hash: str = ""
        self._user_hash: str = ""

    # ── disk I/O ──────────────────────────────────────────────

    def load_from_disk(self) -> None:
        """Load entries from disk into live state + freeze snapshot. Call once at session start."""
        os.makedirs(MEMORY_DIR, exist_ok=True)
        self.memory_entries = self._read_entries(self._memory_path)
        self.user_entries = self._read_entries(self._user_path)
        self._memory_hash = self._file_hash(self._memory_path)
        self._user_hash = self._file_hash(self._user_path)
        self._freeze_snapshot()

    def _read_entries(self, path: str) -> list[str]:
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return []
        # §-delimited: split on double-newline, strip § markers
        entries = []
        for block in raw.split(DELIMITER):
            block = block.strip()
            if block.startswith("§ "):
                block = block[2:]
            if block:
                entries.append(block)
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for e in entries:
            if e not in seen:
                seen.add(e)
                deduped.append(e)
        return deduped

    def _save_to_disk(self, path: str, entries: list[str]) -> None:
        """Atomic write via tempfile + os.replace."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = DELIMITER.join(f"§ {e}" for e in entries) + "\n" if entries else ""
        tmp_path = path + f".tmp.{os.getpid()}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)

    def save(self) -> None:
        """Persist live entries to disk for both memory and user files."""
        self._save_to_disk(self._memory_path, self.memory_entries)
        self._save_to_disk(self._user_path, self.user_entries)
        self._memory_hash = self._file_hash(self._memory_path)
        self._user_hash = self._file_hash(self._user_path)

    # ── snapshot management ───────────────────────────────────

    def _freeze_snapshot(self) -> None:
        self._system_prompt_snapshot["memory"] = self._render_block(self.memory_entries)
        self._system_prompt_snapshot["user"] = self._render_block(self.user_entries)

    def _render_block(self, entries: list[str]) -> str:
        return DELIMITER.join(f"§ {e}" for e in entries) if entries else ""

    def format_for_system_prompt(self, target: str) -> str | None:
        """Return frozen snapshot block. Always returns the session-start snapshot."""
        block = self._system_prompt_snapshot.get(target, "")
        return block if block else None

    # ── char budget helpers ──────────────────────────────────

    def _total_chars(self, entries: list[str]) -> int:
        return len(self._render_block(entries))

    def _check_budget(self, entries: list[str], limit: int) -> bool:
        return self._total_chars(entries) <= limit

    def _budget_error(self, entries: list[str], limit: int) -> dict:
        return {
            "error": "char_limit_exceeded",
            "limit": limit,
            "current": self._total_chars(entries),
            "current_entries": entries,
            "hint": "合并重叠条目用 replace，删过期条目用 remove，缩短冗长条目用 replace，然后重新调用 batch",
        }

    # ── single-entry mutations (delegate to batch) ──────────

    def add(self, target: str, entry: str) -> dict:
        """Add an entry. On overflow, return error with current entries for LLM consolidation."""
        entries = self._get_entries(target)
        limit = self._get_limit(target)
        entries.append(entry)
        if not self._check_budget(entries, limit):
            entries.pop()
            return self._budget_error(entries, limit)
        entries.pop()  # undo preview
        return self.apply_batch(target, [{"action": "add", "entry": entry}])

    def replace(self, target: str, old: str, new: str) -> dict:
        """Replace an entry. On overflow, return error."""
        entries = self._get_entries(target)
        if old not in entries:
            return {"error": "entry_not_found", "old": old[:80]}
        idx = entries.index(old)
        preview = list(entries)
        preview[idx] = new
        if not self._check_budget(preview, self._get_limit(target)):
            return self._budget_error(entries, self._get_limit(target))
        return self.apply_batch(target, [{"action": "replace", "old": old, "new": new}])

    def remove(self, target: str, entry: str) -> dict:
        """Remove an entry."""
        entries = self._get_entries(target)
        if entry not in entries:
            return {"error": "entry_not_found", "entry": entry[:80]}
        return self.apply_batch(target, [{"action": "remove", "entry": entry}])

    # ── batch atomic operations ──────────────────────────────

    def apply_batch(self, target: str, operations: list[dict]) -> dict:
        """Apply [remove, replace, add] atomically. Budget check only on final state."""
        entries = list(self._get_entries(target))
        limit = self._get_limit(target)
        added = 0
        removed = 0
        replaced = 0

        for op in operations:
            action = op.get("action")
            if action == "remove":
                entry = op["entry"]
                if entry in entries:
                    entries.remove(entry)
                    removed += 1
            elif action == "replace":
                old, new = op["old"], op["new"]
                if old in entries:
                    idx = entries.index(old)
                    entries[idx] = new
                    replaced += 1
            elif action == "add":
                entry = op["entry"]
                if entry not in entries:
                    entries.append(entry)
                    added += 1

        # Budget check on FINAL state only
        if not self._check_budget(entries, limit):
            return self._budget_error(list(self._get_entries(target)), limit)

        # Commit
        self._set_entries(target, entries)
        self.save()
        return self._success_response(target, added, removed, replaced)

    def _success_response(self, target: str, added: int, removed: int, replaced: int) -> dict:
        """Return summary only — deliberately omit full entries to prevent LLM thrashing."""
        entries = self._get_entries(target)
        total = self._total_chars(entries)
        limit = self._get_limit(target)
        return {
            "ok": True,
            "target": target,
            "entries_count": len(entries),
            "char_usage": f"{total}/{limit}",
            "percent": round(total / limit * 100, 1),
            "added": added,
            "removed": removed,
            "replaced": replaced,
        }

    # ── query ─────────────────────────────────────────────────

    def get_entries(self, target: str) -> list[str]:
        """Return current entries as a list (for API responses)."""
        return list(self._get_entries(target))

    def get_full_state(self) -> dict:
        return {
            "memory": {
                "entries": list(self.memory_entries),
                "total_chars": self._total_chars(self.memory_entries),
                "limit": self.memory_char_limit,
                "snapshot": self._system_prompt_snapshot["memory"],
            },
            "user": {
                "entries": list(self.user_entries),
                "total_chars": self._total_chars(self.user_entries),
                "limit": self.user_char_limit,
                "snapshot": self._system_prompt_snapshot["user"],
            },
        }

    # ── drift detection ──────────────────────────────────────

    def detect_drift(self) -> dict | None:
        """Check if disk files were modified externally. Returns drift report or None."""
        mem_hash = self._file_hash(self._memory_path)
        usr_hash = self._file_hash(self._user_path)
        drifted = []
        if self._memory_hash and mem_hash != self._memory_hash:
            drifted.append({"target": "memory", "expected_hash": self._memory_hash, "disk_hash": mem_hash})
        if self._user_hash and usr_hash != self._user_hash:
            drifted.append({"target": "user", "expected_hash": self._user_hash, "disk_hash": usr_hash})
        if not drifted:
            return None

        # Create .bak files
        for d in drifted:
            path = self._memory_path if d["target"] == "memory" else self._user_path
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            bak_path = f"{path}.bak.{ts}"
            if os.path.exists(path):
                os.rename(path, bak_path)
                d["backup_path"] = bak_path

        return {
            "error": "external_drift_detected",
            "message": "磁盘文件被外部工具修改，已创建备份，请检查后重试",
            "drifted_files": drifted,
        }

    def _pre_mutation_check(self) -> dict | None:
        """Run drift check before any mutation. Returns error dict or None."""
        drift = self.detect_drift()
        if drift:
            return drift
        return None

    # ── internal helpers ─────────────────────────────────────

    def _get_entries(self, target: str) -> list[str]:
        if target == "memory":
            return self.memory_entries
        if target == "user":
            return self.user_entries
        raise ValueError(f"Unknown target: {target}")

    def _set_entries(self, target: str, entries: list[str]) -> None:
        if target == "memory":
            self.memory_entries = entries
        elif target == "user":
            self.user_entries = entries
        else:
            raise ValueError(f"Unknown target: {target}")

    def _get_limit(self, target: str) -> int:
        return self.memory_char_limit if target == "memory" else self.user_char_limit

    @staticmethod
    def _file_hash(path: str) -> str:
        if not os.path.exists(path):
            return ""
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()


# ── module-level singleton ─────────────────────────────────

_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


def reset_memory_store() -> None:
    global _store
    _store = None
