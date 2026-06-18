"""Project 14: Collision Engine — combinatorial innovation.

Workflow:
  1. Gather ingredients: successful memories + praised skills + proven approaches
  2. Randomly select 2-4 ingredients from each category
  3. Generate a synthesis prompt for the LLM to think about
  4. Store the resulting ThoughtCollision
  5. Boost priority for future SessionBootstrap context
"""

import json
import random
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models.thought_collision import ThoughtCollision
from app.models.skill_card import SkillCard
from app.models.feedback import ApproachSuccessRate
from app.services.memory_store import get_memory_store

# ── Ingredient gathering ───────────────────────────────────


def gather_memory_ingredients() -> list[str]:
    """Collect successful/important memory entries from MemoryStore."""
    store = get_memory_store()
    if not store.memory_entries:
        store.load_from_disk()

    entries = store.memory_entries + store.user_entries
    # Filter: prefer entries that mention success, completion, or positive outcomes
    positive = [e for e in entries if any(kw in e for kw in
                ["成功", "完成", "有效", "好用", "推荐", "最佳", "success", "done", "works"])]
    if positive:
        return positive
    return entries


def gather_skill_ingredients(db: DBSession, project_id: int) -> list[dict]:
    """Collect user-praised or high-usage skills."""
    skills = db.query(SkillCard).filter(
        SkillCard.status.in_(["active", "stale"])
    ).order_by(SkillCard.usage_count.desc()).limit(20).all()

    # Prefer pinned and high-usage
    pinned = [s for s in skills if s.pinned]
    high_usage = [s for s in skills if s.usage_count >= 2]
    candidates = pinned + high_usage + skills
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for s in candidates:
        if s.id not in seen:
            seen.add(s.id)
            unique.append(s)
    return [{"id": s.id, "name": s.name, "trigger_condition": s.trigger_condition or "",
             "steps": s.steps or "[]", "usage_count": s.usage_count or 0}
            for s in unique[:10]]


def gather_approach_ingredients(db: DBSession, project_id: int) -> list[dict]:
    """Collect proven approaches with high success rates."""
    approaches = db.query(ApproachSuccessRate).filter(
        ApproachSuccessRate.project_id == project_id,
        ApproachSuccessRate.total_attempts >= 2,
    ).all()

    # Sort in Python since success_rate is a @property, not a column
    approaches.sort(key=lambda a: a.success_rate, reverse=True)

    return [{"name": a.approach_name, "success_rate": round(a.success_rate, 2),
             "total_attempts": a.total_attempts, "avg_rating": a.avg_rating}
            for a in approaches if a.success_rate >= 0.5]


# ── Collision generation ───────────────────────────────────


def generate_collision_prompt(memories: list[str], skills: list[dict],
                              approaches: list[dict]) -> dict:
    """Generate a synthesis prompt for the LLM.

    Returns a structured prompt that an LLM can use to think about combinations.
    """
    memory_text = "\n".join(f"- {m[:100]}" for m in memories[:5])
    skill_text = "\n".join(f"- {s['name']}: {s.get('trigger_condition', '')[:80]}"
                           for s in skills[:5])
    approach_text = "\n".join(f"- {a['name']} (成功率: {a.get('success_rate', 0):.0%})"
                              for a in approaches[:5])

    prompt = f"""## 思维碰撞：寻找组合创新

请思考以下成功经验能否组合出新的方案：

### 成功记忆片段
{memory_text if memory_text else '（暂无）'}

### 已验证的技能
{skill_text if skill_text else '（暂无）'}

### 高成功率方案
{approach_text if approach_text else '（暂无）'}

请回答：
1. 这些碎片之间有没有隐藏的联系？
2. 能否组合成一个新的方案？给它起个名字。
3. 预期会产生什么奇效？
4. 在什么场景下优先尝试这个组合？

返回 JSON 格式：
{{"combo_name": "...", "combo_description": "...", "expected_synergy": "...", "synergy_score": 0.0-1.0}}"""

    return {
        "prompt": prompt,
        "memory_count": len(memories),
        "skill_count": len(skills),
        "approach_count": len(approaches),
    }


# ── Collision session ──────────────────────────────────────


def run_collision(db: DBSession, project_id: int) -> dict:
    """Run a full collision session: gather ingredients → generate prompt.

    Returns the collision prompt + pre-created ThoughtCollision placeholder.
    """
    # 1. Gather ingredients
    memories = gather_memory_ingredients()
    skills = gather_skill_ingredients(db, project_id)
    approaches = gather_approach_ingredients(db, project_id)

    # 2. Randomly select 2-4 from each
    if memories:
        memories = random.sample(memories, min(len(memories), random.randint(2, 4)))
    if skills:
        skills = random.sample(skills, min(len(skills), random.randint(2, 4)))
    if approaches:
        approaches = random.sample(approaches, min(len(approaches), random.randint(2, 4)))

    # 3. Generate collision prompt
    prompt_data = generate_collision_prompt(memories, skills, approaches)

    # 4. Create placeholder collision
    collision = ThoughtCollision(
        project_id=project_id,
        memory_snippets=json.dumps(memories, ensure_ascii=False),
        skill_ids=json.dumps([s["id"] for s in skills], ensure_ascii=False),
        approach_names=json.dumps([a["name"] for a in approaches], ensure_ascii=False),
        status="proposed",
        created_at=datetime.now().isoformat(),
    )
    db.add(collision)
    db.commit()
    db.refresh(collision)

    return {
        "collision_id": collision.id,
        "ingredients": {
            "memories": len(memories),
            "skills": len(skills),
            "approaches": len(approaches),
        },
        "prompt": prompt_data["prompt"],
    }


def save_collision_result(db: DBSession, collision_id: int,
                          combo_name: str, combo_description: str,
                          expected_synergy: str, synergy_score: float) -> dict:
    """Save the LLM's synthesis result back to the collision."""
    c = db.query(ThoughtCollision).filter(ThoughtCollision.id == collision_id).first()
    if not c:
        return {"error": "not_found"}

    c.combo_name = combo_name
    c.combo_description = combo_description
    c.expected_synergy = expected_synergy
    c.synergy_score = max(0.0, min(1.0, synergy_score))
    c.status = "proposed"
    c.priority_boost = c.synergy_score * 0.3  # higher synergy = higher priority boost

    db.commit()
    db.refresh(c)
    return {
        "collision_id": c.id,
        "combo_name": c.combo_name,
        "synergy_score": c.synergy_score,
        "priority_boost": c.priority_boost,
    }


def mark_collision_tested(db: DBSession, collision_id: int,
                          success: bool, result: str = "") -> dict:
    """Mark a collision as tested, recording the outcome."""
    c = db.query(ThoughtCollision).filter(ThoughtCollision.id == collision_id).first()
    if not c:
        return {"error": "not_found"}

    c.tested_count = (c.tested_count or 0) + 1
    if success:
        c.success_count = (c.success_count or 0) + 1
        c.priority_boost = min(1.0, (c.priority_boost or 0) + 0.1)
    else:
        c.priority_boost = max(0.0, (c.priority_boost or 0) - 0.05)

    c.last_tested_at = datetime.now().isoformat()
    c.last_result = result
    c.status = "proven" if (c.success_rate >= 0.6 and c.tested_count >= 2) else \
               "discarded" if (c.success_rate < 0.3 and c.tested_count >= 3) else "tested"

    db.commit()
    db.refresh(c)
    return {
        "collision_id": c.id, "status": c.status,
        "success_rate": round(c.success_rate, 2),
        "tested_count": c.tested_count,
    }


# ── Retrieval ──────────────────────────────────────────────


def get_top_collisions(db: DBSession, project_id: int, limit: int = 10) -> list[dict]:
    """Get top collisions ordered by priority_boost + synergy_score."""
    collisions = db.query(ThoughtCollision).filter(
        ThoughtCollision.project_id == project_id,
        ThoughtCollision.status.in_(["proposed", "tested", "proven"]),
    ).all()

    # Sort by (priority_boost + synergy_score) descending
    collisions.sort(key=lambda c: (c.priority_boost or 0) + (c.synergy_score or 0),
                    reverse=True)

    return [{
        "id": c.id, "combo_name": c.combo_name,
        "combo_description": c.combo_description,
        "expected_synergy": c.expected_synergy,
        "synergy_score": c.synergy_score,
        "priority_boost": c.priority_boost,
        "status": c.status,
        "success_rate": round(c.success_rate, 2),
        "tested_count": c.tested_count,
    } for c in collisions[:limit]]


def get_collision_context_for_bootstrap(project_id: int) -> list[str]:
    """Get collision summaries for injection into SessionBootstrap context.

    Returns a list of formatted strings ready to inject.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        top = get_top_collisions(db, project_id, limit=3)
        if not top:
            return []

        lines = ["## 思维碰撞：待验证的组合方案"]
        for c in top:
            if c["combo_name"]:
                status_icon = {"proposed": "💡", "tested": "🧪", "proven": "✅"}.get(c["status"], "")
                lines.append(f"- {status_icon} **{c['combo_name']}** (奇效指数: {c['synergy_score']:.0%})")
                if c["combo_description"]:
                    lines.append(f"  {c['combo_description'][:120]}")
                if c["expected_synergy"]:
                    lines.append(f"  预期奇效: {c['expected_synergy'][:120]}")
        return lines
    finally:
        db.close()
