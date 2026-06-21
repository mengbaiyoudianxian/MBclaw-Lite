"""Classification Engine — categorize conversation content into topics.

Uses LLM + jieba keyword matching to assign categories.
Supports: 技术选型, 问题排查, 功能开发, 代码审查, 项目规划, 学习研究, 闲聊
"""

from app.llm import LLMClient
import os

CATEGORIES = [
    "技术选型", "问题排查", "功能开发", "代码审查",
    "项目规划", "学习研究", "闲聊", "其它",
]

CLASSIFY_PROMPT = """分析以下对话内容，从下面分类中选择最合适的一个:

可选分类: {categories}

只回复分类名称，不要解释。

对话:
{content}

分类:"""


def classify_content(llm: LLMClient, content: str) -> str:
    """Classify conversation content into a category."""
    if os.getenv("MBCLAW_LLM_MOCK") == "1":
        # Simple keyword-based mock classification
        content_lower = content.lower()
        if any(kw in content_lower for kw in ["选型", "用哪个", "技术", "sqlite", "postgres", "方案"]):
            return "技术选型"
        if any(kw in content_lower for kw in ["bug", "报错", "错误", "error", "不行", "失败"]):
            return "问题排查"
        if any(kw in content_lower for kw in ["开发", "实现", "写", "代码", "功能"]):
            return "功能开发"
        if any(kw in content_lower for kw in ["review", "审查", "看下代码", "检查"]):
            return "代码审查"
        if any(kw in content_lower for kw in ["计划", "规划", "方案", "设计"]):
            return "项目规划"
        if any(kw in content_lower for kw in ["学习", "了解", "教程", "怎么", "什么是"]):
            return "学习研究"
        if any(kw in content_lower for kw in ["你好", "谢谢", "哈哈", "再见"]):
            return "闲聊"
        return "其它"

    prompt = CLASSIFY_PROMPT.format(
        categories=", ".join(CATEGORIES),
        content=content[:1000],
    )

    try:
        import httpx
        url = f"{llm.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if llm.api_key:
            headers["Authorization"] = f"Bearer {llm.api_key}"
        resp = httpx.post(url, headers=headers, json={
            "model": llm.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 20,
        }, timeout=30)
        resp.raise_for_status()
        result = resp.json()["choices"][0]["message"]["content"].strip()
        for cat in CATEGORIES:
            if cat in result:
                return cat
        return "其它"
    except Exception:
        return "其它"
