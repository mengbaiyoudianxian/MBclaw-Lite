"""F2: Psychology Engine — analyze user feedback to build profile.

Extracts psychological traits from:
  1. Rating patterns (what they rate highly → what they value)
  2. Free-text feedback (emotional words, decision language)
  3. Praised patterns (language, behaviors, thinking styles)
  4. Chat analysis (with permission)

Output: CompanionArchetype + behavioral adaptation instructions.
"""

import json
import re
from datetime import datetime
from typing import Any

from app.models.user_profile import UserProfile, PositivePattern


# ── Trait analysis from feedback text ──────────────────────

EMOTIONAL_WORDS = {
    "温暖": ("social_energy", 0.1), "亲切": ("social_energy", 0.1),
    "耐心": ("social_energy", 0.05), "热情": ("social_energy", 0.15),
    "直接": ("communication", 0.2), "干脆": ("communication", 0.15),
    "委婉": ("communication", -0.2), "温和": ("communication", -0.1),
    "仔细": ("structure_pref", 0.1), "严谨": ("structure_pref", 0.15),
    "灵活": ("structure_pref", -0.15), "自由": ("structure_pref", -0.1),
    "理性": ("decision_style", 0.2), "逻辑": ("decision_style", 0.15),
    "感性": ("decision_style", -0.2), "共情": ("decision_style", -0.1),
    "体贴": ("social_energy", -0.05), "关心": ("social_energy", -0.05),
    "专业": ("communication", 0.1), "靠谱": ("communication", 0.05),
    "幽默": ("social_energy", 0.1), "有趣": ("social_energy", 0.1),
    "细心": ("structure_pref", 0.1), "周到": ("structure_pref", 0.1),
    "快速": ("communication", 0.05), "高效": ("communication", 0.1),
    "懂我": ("decision_style", -0.1), "理解": ("decision_style", -0.05),
}

PRAISE_PATTERNS = {
    "language": ["用词", "语气", "表达", "说话", "措辞", "称呼", "沟通方式"],
    "behavior": ["做法", "行动", "处理", "方式", "方法", "步骤", "流程"],
    "thinking": ["思路", "思考", "想法", "逻辑", "分析", "角度", "创意"],
}


def extract_traits_from_feedback(feedback_text: str) -> dict[str, float]:
    """Extract trait adjustments from a single feedback text."""
    adjustments = {"social_energy": 0, "decision_style": 0,
                   "communication": 0, "structure_pref": 0}
    text_lower = feedback_text.lower()

    for word, (trait, delta) in EMOTIONAL_WORDS.items():
        if word in text_lower or word in feedback_text:
            adjustments[trait] += delta

    # Normalize: cap at ±0.3 per feedback
    for k in adjustments:
        adjustments[k] = max(-0.3, min(0.3, adjustments[k]))

    return adjustments


def extract_praised_patterns(feedback_text: str) -> list[dict]:
    """Extract specific praised patterns from feedback."""
    patterns = []
    for category, keywords in PRAISE_PATTERNS.items():
        for kw in keywords:
            if kw in feedback_text:
                # Extract surrounding context (20 chars on each side)
                idx = feedback_text.find(kw)
                start = max(0, idx - 20)
                end = min(len(feedback_text), idx + len(kw) + 30)
                context = feedback_text[start:end].strip()
                patterns.append({
                    "category": category,
                    "pattern": context,
                    "keyword": kw,
                })
    return patterns


# ── Companion Archetype System ─────────────────────────────

COMPANION_ARCHETYPES = {
    "collaborator": {
        "name": "合作者",
        "description": "平等、理性、一起解决问题",
        "tone": "professional but warm",
        "communication": "直接给出分析和建议，邀请用户一起决策",
        "suitable_for": "balanced traits, high structure_pref",
        "style_rules": [
            "用'我们'而不是'你'",
            "给选项让用户选，不替用户做决定",
            "分享推理过程",
        ],
    },
    "mentor": {
        "name": "导师",
        "description": "引导、耐心、培养能力",
        "tone": "encouraging and instructive",
        "communication": "先问用户的想法，再补充引导，夸奖进步",
        "suitable_for": "low structure_pref, high social_energy",
        "style_rules": [
            "先肯定再建议",
            "解释背后的原理",
            "鼓励用户自己尝试",
        ],
    },
    "caregiver": {
        "name": "照顾者",
        "description": "温暖、体贴、优先情感需求",
        "tone": "gentle and nurturing",
        "communication": "先关注情绪，再处理任务，多用肯定和安慰",
        "suitable_for": "low social_energy, negative decision_style (feeling)",
        "style_rules": [
            "先回应情绪再解决问题",
            "多用温暖词语：没关系、慢慢来、已经很好了",
            "记住并主动提起用户之前说过的话",
        ],
    },
    "challenger": {
        "name": "挑战者",
        "description": "犀利、推动成长、不满足于现状",
        "tone": "direct and motivating",
        "communication": "指出不足，推动做得更好，用高标准要求",
        "suitable_for": "high decision_style (thinking), high communication (direct)",
        "style_rules": [
            "直接指出问题",
            "提出更高的标准",
            "用数据和逻辑说话",
        ],
    },
    "companion": {
        "name": "陪伴者",
        "description": "轻松、有趣、像朋友一样聊天",
        "tone": "casual and playful",
        "communication": "像朋友一样聊天，偶尔开玩笑，分享趣事",
        "suitable_for": "high social_energy, low structure_pref",
        "style_rules": [
            "用轻松的语气",
            "适当使用表情和语气词",
            "主动分享类似经历",
        ],
    },
    "butler": {
        "name": "管家",
        "description": "高效、精准、不多废话",
        "tone": "concise and efficient",
        "communication": "直接给结果，不解释不啰嗦，精准执行",
        "suitable_for": "high communication (direct), high structure_pref",
        "style_rules": [
            "一句话说清楚",
            "不主动展开",
            "完成后简短汇报",
        ],
    },
}


def determine_archetype(profile: UserProfile) -> tuple[str, float, str]:
    """Determine the best companion archetype based on psychological traits.

    Returns (archetype_key, confidence, reason).
    """
    scores = {}
    reasons = {}

    # Collaborator: balanced, structured
    balance = 1.0 - max(abs(profile.social_energy), abs(profile.decision_style),
                         abs(profile.communication)) / 2.0
    scores["collaborator"] = balance * 0.6 + (1.0 - abs(profile.structure_pref)) * 0.4
    reasons["collaborator"] = f"平衡型用户，结构偏好={profile.structure_pref:.2f}"

    # Mentor: low structure, high social
    scores["mentor"] = ((1.0 - profile.structure_pref) / 2.0 + profile.social_energy / 2.0) * 0.8
    reasons["mentor"] = "偏好灵活互动，社交能量较高"

    # Caregiver: low social energy, feeling-leaning
    caregiver_score = ((1.0 - profile.social_energy) / 2.0 + (-profile.decision_style) / 2.0) * 0.9
    scores["caregiver"] = caregiver_score
    reasons["caregiver"] = "社交能量偏低，偏感性决策"

    # Challenger: high thinking, high directness
    scores["challenger"] = (profile.decision_style / 2.0 + profile.communication / 2.0) * 0.9
    reasons["challenger"] = "理性直接，追求高标准"

    # Companion: high social, low structure
    scores["companion"] = (profile.social_energy / 2.0 + (1.0 - profile.structure_pref) / 2.0) * 0.8
    reasons["companion"] = "社交能量高，偏好轻松互动"

    # Butler: high directness, high structure
    scores["butler"] = (profile.communication / 2.0 + profile.structure_pref / 2.0) * 0.9
    reasons["butler"] = "直接高效，偏好结构化"

    best = max(scores, key=scores.get)
    return best, round(scores[best], 2), reasons[best]


def get_archetype_style_rules(archetype: str) -> dict:
    """Get the communication style rules for an archetype."""
    info = COMPANION_ARCHETYPES.get(archetype, COMPANION_ARCHETYPES["collaborator"])
    return {
        "archetype": archetype,
        "name": info["name"],
        "description": info["description"],
        "tone": info["tone"],
        "communication": info["communication"],
        "style_rules": info["style_rules"],
    }


# ── Profile update engine ──────────────────────────────────

def update_profile_from_feedback(profile: UserProfile,
                                 feedback_text: str,
                                 ratings: dict[str, int]) -> dict[str, Any]:
    """Update user profile based on a single feedback entry.

    Returns summary of changes made.
    """
    changes = []

    # 1. Extract trait adjustments from feedback text
    trait_deltas = extract_traits_from_feedback(feedback_text)
    for trait, delta in trait_deltas.items():
        if delta != 0:
            old = getattr(profile, trait, 0)
            new = max(-1.0, min(1.0, old + delta * 0.1))  # smooth update
            setattr(profile, trait, round(new, 3))
            changes.append(f"{trait}: {old:.2f} → {new:.2f}")

    # 2. Extract praised patterns
    praised = extract_praised_patterns(feedback_text)
    new_patterns = 0
    if praised:
        existing_lang = _parse_json_list(profile.praised_language)
        existing_behav = _parse_json_list(profile.praised_behaviors)
        existing_think = _parse_json_list(profile.praised_thinking)

        for p in praised:
            if p["category"] == "language" and p["pattern"] not in existing_lang:
                existing_lang.append(p["pattern"])
                new_patterns += 1
            elif p["category"] == "behavior" and p["pattern"] not in existing_behav:
                existing_behav.append(p["pattern"])
                new_patterns += 1
            elif p["category"] == "thinking" and p["pattern"] not in existing_think:
                existing_think.append(p["pattern"])
                new_patterns += 1

        profile.praised_language = json.dumps(existing_lang[-20:], ensure_ascii=False)
        profile.praised_behaviors = json.dumps(existing_behav[-20:], ensure_ascii=False)
        profile.praised_thinking = json.dumps(existing_think[-20:], ensure_ascii=False)
        changes.append(f"新增 {new_patterns} 个赞许模式")

    # 3. Update meta
    profile.feedback_count += 1
    profile.confidence_score = min(1.0, profile.feedback_count * 0.05)
    profile.updated_at = datetime.now().isoformat()

    # 4. Re-determine archetype
    archetype, confidence, reason = determine_archetype(profile)
    old_archetype = profile.companion_archetype
    profile.companion_archetype = archetype
    profile.archetype_confidence = confidence

    if old_archetype != archetype:
        changes.append(f"伴侣形象切换: {old_archetype} → {archetype} (置信度: {confidence})")

    return {
        "changes": changes,
        "traits": {
            "social_energy": profile.social_energy,
            "decision_style": profile.decision_style,
            "communication": profile.communication,
            "structure_pref": profile.structure_pref,
        },
        "archetype": get_archetype_style_rules(archetype),
        "archetype_reason": reason,
        "confidence": profile.confidence_score,
    }


def _parse_json_list(s: str) -> list:
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return []


# ── System prompt injection ────────────────────────────────

def generate_persona_block(profile: UserProfile) -> str:
    """Generate a persona block for injection into the system prompt.

    This is what makes MBclaw '哄' the user — adapting communication style
    based on psychological profile.
    """
    if not profile or profile.feedback_count < 1:
        return ""

    archetype_info = get_archetype_style_rules(profile.companion_archetype)
    praised_lang = _parse_json_list(profile.praised_language)[:5]
    praised_behav = _parse_json_list(profile.praised_behaviors)[:5]

    lines = [
        "## 用户画像（心理学分析）",
        f"- 伴侣形象: {archetype_info['name']} ({archetype_info['description']})",
        f"- 沟通风格: {archetype_info['tone']}",
        f"- 沟通策略: {archetype_info['communication']}",
        "",
        "### 行为准则",
    ]
    for rule in archetype_info["style_rules"]:
        lines.append(f"- {rule}")

    if praised_lang:
        lines.append("")
        lines.append("### 用户喜欢的表达方式")
        for p in praised_lang[:3]:
            lines.append(f"- \"{p}\"")

    if praised_behav:
        lines.append("")
        lines.append("### 用户喜欢的做法")
        for p in praised_behav[:3]:
            lines.append(f"- \"{p}\"")

    lines.append("")
    lines.append(f"画像置信度: {profile.confidence_score:.0%} (基于 {profile.feedback_count} 次反馈)")

    return "\n".join(lines)
