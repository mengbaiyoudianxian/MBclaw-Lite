"""H3: Auto Skill Extraction — extract reusable SkillCards from agent execution history.

Triggers (H3a):
  1. tool_call_count >= 5  →  extract from tool usage patterns
  2. error_correction_count >= 2  →  extract from fix patterns
  3. user_correction_success  →  user said "不对/应该..." then agent fixed it
  4. user_explicitly_said "记住/学会/记住这个做法"  →  forced extraction

Pipeline (H3b):
  conversation_history → classify trigger type → build LLM prompt →
  LLM extracts: name, trigger_condition, steps[], known_pitfalls[], category

Dedup (H3c):
  SHA256(trigger_condition) → check existing SkillCards → update if exists, else create
"""

import hashlib
import json
from typing import Any
from sqlalchemy.orm import Session as DBSession

from app.models.skill_card import SkillCard


# ═══════════════════════════════════════════════════════════
# Trigger detection
# ═══════════════════════════════════════════════════════════

TRIGGER_PHRASES = [
    "记住", "记住这个", "记住这个做法", "学会", "学会这个",
    "以后都这样", "下次用这个", "把这个记下来", "记住这个方案",
    "remember this", "learn this", "save this pattern",
]


def detect_triggers(messages: list[dict]) -> dict:
    """Analyze session messages for skill extraction triggers.

    Each message: {role: "user"|"assistant"|"tool", content: str}
    Returns trigger info or empty dict.
    """
    tool_count = sum(1 for m in messages if m.get("role") == "tool")
    error_count = _count_errors(messages)
    user_corrections = _detect_user_corrections(messages)
    explicit_trigger = _detect_explicit_trigger(messages)

    triggers = {
        "tool_count": tool_count,
        "error_count": error_count,
        "user_corrections": user_corrections,
        "explicit_trigger": explicit_trigger,
    }

    # Determine primary trigger type
    if explicit_trigger:
        triggers["trigger_type"] = "explicit"
        triggers["should_extract"] = True
        triggers["priority"] = "high"
    elif tool_count >= 5:
        triggers["trigger_type"] = "tool_heavy"
        triggers["should_extract"] = True
        triggers["priority"] = "normal"
    elif error_count >= 2:
        triggers["trigger_type"] = "error_fix"
        triggers["should_extract"] = True
        triggers["priority"] = "high"
    elif user_corrections > 0:
        triggers["trigger_type"] = "user_correction"
        triggers["should_extract"] = True
        triggers["priority"] = "high"
    else:
        triggers["trigger_type"] = "none"
        triggers["should_extract"] = False
        triggers["priority"] = "none"

    return triggers


def _count_errors(messages: list[dict]) -> int:
    """Count error-correction cycles."""
    count = 0
    for i, m in enumerate(messages):
        if m.get("role") != "assistant":
            continue
        content = m.get("content", "")
        # Check if message mentions errors
        if any(kw in content.lower() for kw in
               ["error", "错误", "报错", "失败", "traceback", "exception"]):
            # Check if next user message corrects it
            if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                next_content = messages[i + 1].get("content", "")
                if any(kw in next_content for kw in
                       ["不对", "应该", "改成", "不是", "换个", "试试", "wrong", "should", "instead"]):
                    count += 1
    return count


def _detect_user_corrections(messages: list[dict]) -> int:
    """Count 'user corrected agent → agent fixed it' cycles."""
    count = 0
    for i, m in enumerate(messages):
        if m.get("role") != "user":
            continue
        content = m.get("content", "")
        if any(kw in content for kw in
               ["不对", "应该", "改成", "不是这样", "换个方式", "试试这个"]):
            # Check if next agent message acknowledges and fixes
            if i + 1 < len(messages) and messages[i + 1].get("role") == "assistant":
                next_content = messages[i + 1].get("content", "")
                if any(kw in next_content for kw in
                       ["好的", "明白", "改好", "修好", "完成", "done", "fixed", "updated", "corrected"]):
                    count += 1
    return count


def _detect_explicit_trigger(messages: list[dict]) -> bool:
    """Check if user explicitly asked to remember a pattern."""
    for m in messages:
        if m.get("role") != "user":
            continue
        content = m.get("content", "")
        if any(phrase in content for phrase in TRIGGER_PHRASES):
            return True
    return False


# ═══════════════════════════════════════════════════════════
# Skill extraction via LLM
# ═══════════════════════════════════════════════════════════

EXTRACTION_PROMPT = """你是一个技能提取器。分析以下对话历史，提取可复用的操作流程。

对话历史：
{conversation}

请提取为一个技能卡，JSON格式：
{{
  "name": "技能名称（简洁，5-15字）",
  "trigger_condition": "什么时候使用这个技能（描述触发场景）",
  "steps": ["步骤1", "步骤2", "步骤3"],
  "known_pitfalls": ["已知坑1", "已知坑2"],
  "category": "分类（coding/debugging/configuration/data/communication/other）"
}}

要求：
- name 用中文
- steps 是可执行的步骤，不是抽象描述
- known_pitfalls 是实际踩过的坑，没有就空数组
- 只输出 JSON，不要其他内容"""


async def extract_skill_from_conversation(
    messages: list[dict],
    trigger_info: dict,
    llm_call: Any = None,  # async callable: llm_call(prompt) -> str
) -> dict | None:
    """Extract a SkillCard from conversation using LLM.

    llm_call: async function that takes a prompt string and returns LLM response.
               If None, returns None (LLM not configured).
    """
    if not llm_call:
        return None

    # Build conversation summary for the prompt
    conversation_text = []
    for m in messages[-40:]:  # last 40 messages for context
        role = m.get("role", "unknown")
        content = m.get("content", "")[:500]  # truncate per message
        conversation_text.append(f"[{role}]: {content}")

    prompt = EXTRACTION_PROMPT.format(
        conversation="\n".join(conversation_text),
    )

    try:
        response = await llm_call(prompt)
        # Extract JSON from response
        json_str = response.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        extracted = json.loads(json_str)
        return extracted
    except (json.JSONDecodeError, Exception):
        return None


# ═══════════════════════════════════════════════════════════
# Rule-based extraction (fallback when LLM unavailable)
# ═══════════════════════════════════════════════════════════

def extract_skill_rules(messages: list[dict], trigger_info: dict) -> dict | None:
    """Rule-based skill extraction as LLM fallback.

    Analyzes tool calls and user corrections to derive skill card.
    """
    if not trigger_info.get("should_extract"):
        return None

    # Collect tool names
    tools_used: list[str] = []
    for m in messages:
        if m.get("role") == "tool":
            tool_name = m.get("tool_name", m.get("name", ""))
            if tool_name:
                tools_used.append(tool_name)

    # Collect user corrections
    corrections: list[str] = []
    for m in messages:
        if m.get("role") == "user":
            content = m.get("content", "")
            if any(kw in content for kw in ["不对", "应该", "改成"]):
                corrections.append(content[:200])

    # Build skill from patterns
    trigger_type = trigger_info.get("trigger_type", "")

    if trigger_type == "explicit":
        name = "用户指定技能"
        trigger = "用户明确要求时"
    elif trigger_type == "tool_heavy" and tools_used:
        name = f"{tools_used[0]} 操作流程"
        trigger = f"需要使用 {', '.join(tools_used[:3])} 时"
    elif trigger_type == "error_fix":
        name = "错误修复流程"
        trigger = "遇到类似错误时"
    elif trigger_type == "user_correction":
        name = "用户纠正方案"
        trigger = "用户纠正方向后"
    else:
        return None

    steps = [f"使用工具: {t}" for t in tools_used[:5]]
    pitfalls = [c for c in corrections[:3]]

    return {
        "name": name,
        "trigger_condition": trigger,
        "steps": steps or ["分析需求", "执行操作", "验证结果"],
        "known_pitfalls": pitfalls,
        "category": "debugging" if trigger_type in ("error_fix",) else "coding",
    }


# ═══════════════════════════════════════════════════════════
# Dedup + storage
# ═══════════════════════════════════════════════════════════

def _hash_trigger(trigger_condition: str) -> str:
    return hashlib.sha256(trigger_condition.encode()).hexdigest()[:16]


def save_extracted_skill(db: DBSession, skill_data: dict,
                         project_id: int = 0) -> dict:
    """Save or update extracted SkillCard with dedup check.

    Dedup: SHA256(trigger_condition) → check existing → update if found.
    """
    trigger = skill_data.get("trigger_condition", "")
    trigger_hash = _hash_trigger(trigger)

    # Check existing by name similarity first
    existing = db.query(SkillCard).filter(
        SkillCard.name == skill_data.get("name", "")
    ).first()

    if existing:
        # Update existing
        existing.trigger_condition = trigger
        existing.steps = json.dumps(skill_data.get("steps", []), ensure_ascii=False)
        existing.known_pitfalls = json.dumps(skill_data.get("known_pitfalls", []), ensure_ascii=False)
        existing.category = skill_data.get("category", "")
        db.commit()
        return {"action": "updated", "skill_id": existing.id, "name": existing.name}

    # Check by trigger hash for near-duplicates
    all_skills = db.query(SkillCard).all()
    for s in all_skills:
        if s.trigger_condition and _hash_trigger(s.trigger_condition) == trigger_hash:
            s.steps = json.dumps(skill_data.get("steps", []), ensure_ascii=False)
            s.known_pitfalls = json.dumps(skill_data.get("known_pitfalls", []), ensure_ascii=False)
            s.category = skill_data.get("category", "")
            db.commit()
            return {"action": "updated_by_hash", "skill_id": s.id, "name": s.name}

    # Create new
    card = SkillCard(
        name=skill_data.get("name", "未命名技能"),
        trigger_condition=trigger,
        steps=json.dumps(skill_data.get("steps", []), ensure_ascii=False),
        known_pitfalls=json.dumps(skill_data.get("known_pitfalls", []), ensure_ascii=False),
        category=skill_data.get("category", ""),
        created_by="agent",
        status="active",
        created_at=None,  # let DB default
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return {"action": "created", "skill_id": card.id, "name": card.name}


# ═══════════════════════════════════════════════════════════
# Entry point: run full extraction cycle
# ═══════════════════════════════════════════════════════════

async def run_skill_extraction(
    db: DBSession,
    messages: list[dict],
    project_id: int = 0,
    llm_call: Any = None,
) -> dict:
    """Full H3 cycle: detect triggers → extract skill → dedup → save.

    Returns: {triggered, trigger_type, skill_data, save_result}
    """
    triggers = detect_triggers(messages)

    if not triggers["should_extract"]:
        return {"triggered": False, "trigger_type": triggers["trigger_type"],
                "reason": "no_trigger"}

    # Try LLM extraction first
    skill_data = None
    if llm_call:
        skill_data = await extract_skill_from_conversation(messages, triggers, llm_call)

    # Fall back to rules-based extraction
    if not skill_data:
        skill_data = extract_skill_rules(messages, triggers)

    if not skill_data:
        return {"triggered": True, "trigger_type": triggers["trigger_type"],
                "success": False, "reason": "extraction_failed"}

    # Save with dedup
    save_result = save_extracted_skill(db, skill_data, project_id)

    return {
        "triggered": True,
        "trigger_type": triggers["trigger_type"],
        "success": True,
        "skill_data": skill_data,
        "save_result": save_result,
    }
