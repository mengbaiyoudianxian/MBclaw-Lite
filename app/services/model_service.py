import json
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models.model_profile import ModelProfile


def register_model(db: DBSession, data: dict) -> ModelProfile:
    profile = ModelProfile(
        key_alias=data["key_alias"],
        model_name=data["model_name"],
        api_base=data.get("api_base", ""),
        capabilities=json.dumps(data.get("capabilities", {}), ensure_ascii=False),
        strengths=json.dumps(data.get("strengths", []), ensure_ascii=False),
        tool_compatibility=json.dumps(data.get("tool_compatibility", {}), ensure_ascii=False),
        cost_per_1k_tokens=data.get("cost_per_1k_tokens", 0.0),
        context_window=data.get("context_window", 8192),
        created_at=datetime.now().isoformat(),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def recommend_models(db: DBSession, task_type: str, task_complexity: str = "medium",
                     budget: float = 1.0, required_tools: list[str] | None = None) -> list[dict]:
    """Score all registered models for the given task and return sorted recommendations."""
    required_tools = required_tools or []
    profiles = db.query(ModelProfile).all()
    if not profiles:
        return []

    scored = []
    for p in profiles:
        caps = json.loads(p.capabilities) if p.capabilities else {}
        comp = json.loads(p.tool_compatibility) if p.tool_compatibility else {}

        # Capability scores
        reasoning = caps.get("reasoning", 0.5)
        coding = caps.get("coding", 0.5)
        speed = caps.get("speed", 0.5)
        cost_efficiency = max(0, 1.0 - p.cost_per_1k_tokens * 100)

        # Task-type weighting
        task_weights = {
            "coding": {"coding": 0.5, "reasoning": 0.3, "speed": 0.2},
            "writing": {"creativity": 0.4, "reasoning": 0.4, "speed": 0.2},
            "analysis": {"reasoning": 0.5, "coding": 0.2, "speed": 0.3},
            "chat": {"speed": 0.5, "reasoning": 0.3, "creativity": 0.2},
            "vision": {"vision": 0.6, "reasoning": 0.4},
        }
        w = task_weights.get(task_type, task_weights["chat"])
        score = sum(caps.get(k, 0.5) * v for k, v in w.items()) / max(sum(w.values()), 0.01)

        # Tool compatibility bonus
        tool_bonus = 0.0
        for tool in required_tools:
            tool_bonus += comp.get(tool, 0.0)
        if required_tools and tool_bonus > 0:
            score += tool_bonus * 0.2

        # Cost-aware scaling
        if budget < 0.05 and p.cost_per_1k_tokens > 0.001:
            score *= 0.3  # heavy penalty for expensive models on tight budget
        elif budget < 0.2 and p.cost_per_1k_tokens > 0.005:
            score *= 0.7

        scored.append({
            "id": p.id, "key_alias": p.key_alias, "model_name": p.model_name,
            "score": round(score, 3),
            "cost_per_1k_tokens": p.cost_per_1k_tokens,
            "context_window": p.context_window,
            "capabilities": caps,
            "strengths": json.loads(p.strengths) if p.strengths else [],
            "reason": _explain_recommendation(caps, task_type, score),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _explain_recommendation(caps: dict, task_type: str, score: float) -> str:
    reasons = []
    if task_type == "coding" and caps.get("coding", 0) > 0.7:
        reasons.append("编码能力强")
    if task_type == "analysis" and caps.get("reasoning", 0) > 0.7:
        reasons.append("推理能力强")
    if caps.get("speed", 0) > 0.8:
        reasons.append("响应快速")
    if score < 0.3:
        reasons.append("综合评分较低")
    return "；".join(reasons) if reasons else "综合匹配"
