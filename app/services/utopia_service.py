"""Project 15: 乌托邦计划 — full pipeline service.

Pipeline:
  1. import_chat_logs → ChatImport
  2. extract_insights → UtopiaInsight (de-identify + categorize + score)
  3. prioritize_insights → merge duplicates, rank by priority
  4. generate_tasks → UtopiaTask queue
  5. evaluate_submission → user×0.80 + self×0.20 → accept/reject/contest
"""

import json
import re
import math
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session as DBSession

from app.models.utopia import ChatImport, UtopiaInsight, UtopiaTask, UtopiaSubmission
from app.models.user_profile import ChatAnalysisRequest


# ═══════════════════════════════════════════════════════════════
# Step 1: Chat Import
# ═══════════════════════════════════════════════════════════════

# Keywords that indicate agent-related content
AGENT_KEYWORDS = {
    "bug": ["bug", "报错", "错误", "崩溃", "闪退", "卡住", "不行", "没用", "坏了",
            "不好使", "出错", "异常", "故障", "失灵", "不能用了"],
    "praise": ["好用", "厉害", "牛", "不错", "挺好", "赞", "感谢", "方便", "完美",
               "太棒了", "聪明", "省事", "给力", "好评"],
    "complaint": ["难用", "垃圾", "失望", "烦", "麻烦", "太慢", "太复杂", "反人类",
                  "智障", "sb", "无语", "醉了", "坑", "差评"],
    "feature_request": ["希望", "建议", "要是能", "能不能", "加个", "增加", "支持",
                        "功能", "需要", "想要", "能不能做", "可不可以"],
    "skill_wish": ["学会", "教我", "帮我", "自动", "替我", "代劳", "帮忙",
                   "处理", "整理", "分析", "生成", "写", "改", "优化"],
}

# PII patterns for de-identification
PII_PATTERNS = [
    (re.compile(r'1[3-9]\d{9}'), '[手机号]'),                    # Chinese mobile
    (re.compile(r'\d{17}[\dXx]|\d{15}'), '[身份证号]'),           # Chinese ID
    (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), '[邮箱]'),  # Email
    (re.compile(r'(?:\d{3,4}-)?\d{7,8}'), '[座机号]'),            # Landline
    (re.compile(r'(?:https?://|www\.)[^\s]+'), '[链接]'),         # URLs
]


def _deidentify(text: str) -> str:
    """Strip PII from text, replacing with placeholders."""
    result = text
    for pattern, replacement in PII_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def _categorize_text(text: str) -> dict[str, Any]:
    """Categorize a single message: category + sentiment + keywords + scores."""
    text_lower = text.lower()
    matched_categories: dict[str, list[str]] = {}
    all_keywords: list[str] = []

    for category, keywords in AGENT_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in text_lower or kw in text]
        if hits:
            matched_categories[category] = hits
            all_keywords.extend(hits)

    if not matched_categories:
        return {"category": "other", "keywords": [], "sentiment": "neutral",
                "clarity_score": 0.0, "urgency_score": 0.0}

    # Primary category: most keyword hits
    primary = max(matched_categories, key=lambda c: len(matched_categories[c]))

    # Sentiment
    if primary in ("praise",):
        sentiment = "positive"
    elif primary in ("complaint", "bug"):
        sentiment = "negative"
    elif primary in ("feature_request", "skill_wish"):
        sentiment = "neutral"

    # Clarity: more keywords = clearer expression
    clarity = min(1.0, len(all_keywords) / 8.0)

    # Urgency: time-pressure words
    urgent_kws = ["急", "马上", "尽快", "立刻", "赶紧", "快", "urgent", "asap", "紧急"]
    urgency = min(1.0, sum(1 for kw in urgent_kws if kw in text_lower or kw in text) / 3.0)

    return {
        "category": primary,
        "keywords": all_keywords,
        "sentiment": sentiment,
        "clarity_score": round(clarity, 2),
        "urgency_score": round(urgency, 2),
    }


def import_chat_logs(db: DBSession, user_id: int, source_platform: str,
                     file_format: str, filename: str,
                     messages: list[str]) -> dict:
    """Import and parse chat messages."""
    import_row = ChatImport(
        user_id=user_id,
        source_platform=source_platform,
        file_format=file_format,
        original_filename=filename,
        message_count=len(messages),
        status="imported",
        created_at=datetime.now().isoformat(),
    )
    db.add(import_row)
    db.commit()
    db.refresh(import_row)
    return {"import_id": import_row.id, "message_count": len(messages),
            "source_platform": source_platform}


# ═══════════════════════════════════════════════════════════════
# Step 2: Insight Extraction + De-identification + Categorization
# ═══════════════════════════════════════════════════════════════

def extract_insights(db: DBSession, import_id: int) -> dict:
    """Extract agent-related insights from imported messages."""
    import_row = db.query(ChatImport).filter(ChatImport.id == import_id).first()
    if not import_row:
        return {"error": "import_not_found"}

    # We need the actual messages. In Phase 1, messages are passed directly.
    # In Phase 2, they'd be stored in a messages table.
    # For now, mark as processing — caller passes messages to extract_from_messages
    import_row.status = "processing"
    db.commit()
    return {"import_id": import_id, "status": "processing"}


def extract_from_messages(db: DBSession, import_id: int, user_id: int,
                          messages: list[str], source_platform: str = "") -> dict:
    """Process messages: de-identify → categorize → store as insights."""
    import_row = db.query(ChatImport).filter(ChatImport.id == import_id).first()
    if not import_row:
        return {"error": "import_not_found"}

    insights_created = 0
    for msg in messages:
        cat_result = _categorize_text(msg)
        if cat_result["category"] == "other":
            continue

        deidentified = _deidentify(msg)

        insight = UtopiaInsight(
            import_id=import_id,
            user_id=user_id,
            raw_text=msg,
            deidentified_text=deidentified,
            category=cat_result["category"],
            sentiment=cat_result["sentiment"],
            keywords_matched=json.dumps(cat_result["keywords"], ensure_ascii=False),
            clarity_score=cat_result["clarity_score"],
            urgency_score=cat_result["urgency_score"],
            source_platform=source_platform or import_row.source_platform,
            source_date=datetime.now().isoformat()[:10],
            created_at=datetime.now().isoformat(),
        )
        db.add(insight)
        insights_created += 1

    import_row.status = "analyzed"
    import_row.extracted_insights = insights_created
    db.commit()

    return {"import_id": import_id, "insights_created": insights_created}


# ═══════════════════════════════════════════════════════════════
# Step 3: Prioritization
# ═══════════════════════════════════════════════════════════════

def prioritize_insights(db: DBSession, user_id: int) -> dict:
    """Compute priority scores for all insights and merge duplicates."""
    insights = db.query(UtopiaInsight).filter(
        UtopiaInsight.user_id == user_id,
        UtopiaInsight.priority == 0.0,  # not yet scored
    ).all()

    if not insights:
        return {"scored": 0}

    # Group by category + similar deidentified_text for frequency counting
    groups: dict[str, list[UtopiaInsight]] = {}
    for ins in insights:
        key = f"{ins.category}:{ins.deidentified_text[:60]}"
        groups.setdefault(key, []).append(ins)

    max_count = max(len(g) for g in groups.values()) if groups else 1

    scored = 0
    for key, group in groups.items():
        mention_count = len(group)
        freq_score = math.log(mention_count + 1) / math.log(max_count + 2)

        for ins in group:
            ins.mention_count = mention_count
            urgency = ins.urgency_score or 0.0
            clarity = ins.clarity_score or 0.0
            ins.priority = round(0.40 * urgency + 0.35 * freq_score + 0.25 * clarity, 3)
            scored += 1

    db.commit()
    return {"scored": scored, "groups": len(groups)}


# ═══════════════════════════════════════════════════════════════
# Step 4: Task Generation
# ═══════════════════════════════════════════════════════════════

def generate_tasks(db: DBSession, user_id: int, min_priority: float = 0.15,
                   max_tasks: int = 10) -> dict:
    """Generate UtopiaTasks from high-priority insights."""
    insights = db.query(UtopiaInsight).filter(
        UtopiaInsight.user_id == user_id,
        UtopiaInsight.priority >= min_priority,
    ).order_by(UtopiaInsight.priority.desc()).limit(max_tasks * 3).all()

    if not insights:
        return {"tasks_created": 0}

    # Group by category and merge
    merged: dict[str, dict] = {}
    for ins in insights:
        cat = ins.category
        if cat not in merged:
            merged[cat] = {
                "insight_ids": [],
                "texts": [],
                "max_priority": 0.0,
                "total_urgency": 0.0,
                "count": 0,
            }
        m = merged[cat]
        m["insight_ids"].append(ins.id)
        m["texts"].append(ins.deidentified_text[:200])
        m["max_priority"] = max(m["max_priority"], ins.priority)
        m["total_urgency"] += ins.urgency_score or 0
        m["count"] += 1

    # Create tasks for top categories
    sorted_cats = sorted(merged.items(), key=lambda x: x[1]["max_priority"], reverse=True)
    tasks_created = 0

    category_labels = {
        "bug": "修复问题",
        "feature_request": "新增功能",
        "skill_wish": "学习能力",
        "complaint": "改善体验",
        "praise": "巩固优势",
    }

    for cat, data in sorted_cats[:max_tasks]:
        label = category_labels.get(cat, cat)
        best_text = data["texts"][0] if data["texts"] else ""
        title = f"[{label}] {best_text[:80]}"
        description = f"从 {data['count']} 条相关反馈中提取。\n" + "\n".join(
            f"- {t}" for t in data["texts"][:5]
        )

        task = UtopiaTask(
            user_id=user_id,
            source_insight_ids=json.dumps(data["insight_ids"], ensure_ascii=False),
            title=title,
            description=description,
            category=cat,
            priority=round(data["max_priority"], 3),
            status="pending",
            created_at=datetime.now().isoformat(),
        )
        db.add(task)
        tasks_created += 1

    db.commit()
    return {"tasks_created": tasks_created, "categories": list(merged.keys())}


# ═══════════════════════════════════════════════════════════════
# Step 5: Dual Evaluation
# ═══════════════════════════════════════════════════════════════

def submit_solution(db: DBSession, task_id: int, user_id: int,
                    solution_text: str, solution_artifacts: str = "[]",
                    self_score: float = 0.0, self_rationale: str = "") -> dict:
    """Submit a creative solution for evaluation."""
    task = db.query(UtopiaTask).filter(UtopiaTask.id == task_id).first()
    if not task:
        return {"error": "task_not_found"}

    sub = UtopiaSubmission(
        task_id=task_id,
        user_id=user_id,
        solution_text=solution_text,
        solution_artifacts=solution_artifacts,
        self_score=max(0.0, min(1.0, self_score)),
        self_rationale=self_rationale,
        status="submitted",
        submitted_at=datetime.now().isoformat(),
        created_at=datetime.now().isoformat(),
    )
    db.add(sub)
    task.status = "submitted"
    db.commit()
    db.refresh(sub)
    return {"submission_id": sub.id, "status": "submitted"}


def evaluate_submission(db: DBSession, submission_id: int,
                        user_score: float, user_feedback: str = "") -> dict:
    """User evaluates + compute composite. Decision: accept/reject/contest."""
    sub = db.query(UtopiaSubmission).filter(UtopiaSubmission.id == submission_id).first()
    if not sub:
        return {"error": "submission_not_found"}

    sub.user_score = max(0.0, min(1.0, user_score))
    sub.user_feedback = user_feedback
    sub.composite_score = round(sub.user_score * 0.80 + sub.self_score * 0.20, 3)
    sub.evaluated_at = datetime.now().isoformat()

    gap = abs(sub.user_score - sub.self_score)

    if sub.composite_score > 0.50 and gap <= 0.60:
        sub.status = "accepted"
        sub.accepted_at = datetime.now().isoformat()
        decision = "accepted"
        reason = f"综合评分 {sub.composite_score:.0%} > 50%，用户与自评差距 {gap:.0%} ≤ 60%，收录。"
    elif sub.composite_score > 0.50 and gap > 0.60:
        sub.status = "contested"
        sub.contested_reason = f"用户({sub.user_score:.0%})与自评({sub.self_score:.0%})差距 {gap:.0%} > 60%，需第三人审核。"
        decision = "contested"
        reason = sub.contested_reason
    else:
        sub.status = "rejected"
        decision = "rejected"
        reason = f"综合评分 {sub.composite_score:.0%} ≤ 50%，驳回。"

    # Update task status
    task = db.query(UtopiaTask).filter(UtopiaTask.id == sub.task_id).first()
    if task:
        task.status = f"evaluating_{decision}"

    db.commit()
    return {
        "submission_id": sub.id,
        "decision": decision,
        "composite_score": sub.composite_score,
        "reason": reason,
    }


def get_server_inbox(db: DBSession, user_id: int | None = None) -> list[dict]:
    """Server collects accepted submissions for next-phase planning."""
    query = db.query(UtopiaSubmission).filter(UtopiaSubmission.status == "accepted")
    if user_id:
        query = query.filter(UtopiaSubmission.user_id == user_id)

    subs = query.order_by(UtopiaSubmission.composite_score.desc()).all()

    results = []
    for s in subs:
        task = db.query(UtopiaTask).filter(UtopiaTask.id == s.task_id).first()
        results.append({
            "submission_id": s.id,
            "task_title": task.title if task else "",
            "category": task.category if task else "",
            "solution_text": s.solution_text[:200],
            "composite_score": s.composite_score,
            "user_score": s.user_score,
            "self_score": s.self_score,
            "user_feedback": s.user_feedback[:100],
        })
    return results
