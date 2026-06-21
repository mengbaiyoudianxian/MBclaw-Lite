"""Skill Extraction — detect reusable patterns from conversations.

Triggered after session close. Uses LLM to extract:
- trigger_condition: what user said/did that triggered this
- skill_name: short name
- steps: ordered list of steps taken
- outcome: what was achieved
"""

import json
import os

from app.llm import LLMClient

SKILL_EXTRACT_PROMPT = """分析以下对话，判断是否包含可复用的操作模式。

如果包含，提取为技能卡片，输出 JSON:
{{
  "has_skill": true,
  "trigger_condition": "≤30字描述触发条件",
  "skill_name": "≤20字技能名称",
  "steps": ["步骤1", "步骤2", ...],
  "outcome": "≤50字描述结果",
  "category": "技术选型|问题排查|功能开发|代码审查|其它"
}}

如果不包含可复用模式，输出: {{"has_skill": false}}

对话:
{content}"""


def extract_skill(llm: LLMClient, messages_text: str) -> dict | None:
    """Try to extract a reusable skill from conversation.

    Returns skill dict or None if no skill detected.
    """
    if os.getenv("MBCLAW_LLM_MOCK") == "1":
        # Simple heuristic mock detection
        text_lower = messages_text.lower()
        if "sqlite" in text_lower and "fts5" in text_lower:
            return {
                "trigger_condition": "用户询问全文检索方案",
                "skill_name": "SQLite FTS5 选型",
                "steps": ["分析需求", "对比方案", "确定技术栈"],
                "outcome": "选择 SQLite FTS5 + jieba 作为检索方案",
                "category": "技术选型",
            }
        if "bug" in text_lower or "报错" in text_lower or "error" in text_lower:
            return {
                "trigger_condition": "用户报告错误",
                "skill_name": "错误排查流程",
                "steps": ["复现错误", "查看日志", "定位根因", "修复验证"],
                "outcome": "定位并修复了错误",
                "category": "问题排查",
            }
        return None

    prompt = SKILL_EXTRACT_PROMPT.format(content=messages_text[:3000])

    try:
        import httpx
        url = f"{llm.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if llm.api_key:
            headers["Authorization"] = f"Bearer {llm.api_key}"
        resp = httpx.post(url, headers=headers, json={
            "model": llm.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]
        result = json.loads(raw)
        if result.get("has_skill"):
            return {
                "trigger_condition": result.get("trigger_condition", ""),
                "skill_name": result.get("skill_name", ""),
                "steps": result.get("steps", []),
                "outcome": result.get("outcome", ""),
                "category": result.get("category", "其它"),
            }
        return None
    except Exception:
        return None
