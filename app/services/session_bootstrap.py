"""Session bootstrap: auto-retrieve relevant history when a new session starts.

When a user creates a new session, this service:
1. Extracts keywords from the session title
2. Searches the ClassificationNode tree for matching nodes
3. Retrieves failed_approaches and successful_approaches
4. Formats a context block injected into the session

This enables the "remember 3-month-old failure → suggest alternative" behavior.
"""

import json
from sqlalchemy.orm import Session as DBSession

from app.models.classification_node import ClassificationNode
from app.models.project_dna import ProjectDNA
from app.models.keyword import Keyword


def bootstrap_session_context(db: DBSession, session, title: str = "") -> str:
    """Generate a context block from project history. Returns formatted string."""
    project_id = session.project_id
    parts = []

    # ── 1. Extract search terms from title ──
    terms = _tokenize(title)
    if not terms:
        return ""

    # ── 2. Search ClassificationNode tree ──
    matched_nodes = _search_classification_nodes(db, project_id, terms)
    if matched_nodes:
        parts.append("## 历史相关话题\n")
        for node in matched_nodes[:5]:
            parts.append(f"### {node.category_name}")
            if node.summary_short:
                parts.append(f"摘要: {node.summary_short}")
            if node.keywords:
                try:
                    kws = json.loads(node.keywords)
                    if kws:
                        parts.append(f"关键词: {', '.join(kws[:5])}")
                except (json.JSONDecodeError, TypeError):
                    pass
            parts.append("")

        # ── 3. Extract failed_approaches ──
        failed = _collect_failed_approaches(matched_nodes)
        if failed:
            parts.append("## ⚠️ 之前尝试过的失败方案\n")
            for fa in failed:
                parts.append(f"- **方案**: {fa.get('approach', '未知')}")
                if fa.get("reason"):
                    parts.append(f"  **失败原因**: {fa['reason']}")
                parts.append("")

        # ── 4. Extract successful_approaches ──
        successful = _collect_successful_approaches(matched_nodes)
        if successful:
            parts.append("## ✅ 之前验证过的成功方案\n")
            for sa in successful:
                parts.append(f"- **方案**: {sa.get('approach', '未知')}")
                if sa.get("result"):
                    parts.append(f"  **结果**: {sa['result']}")
                parts.append("")

    # ── 5. Add Project DNA summary ──
    dna = db.query(ProjectDNA).filter(ProjectDNA.project_id == project_id).first()
    if dna:
        dna_parts = []
        if dna.goals and dna.goals != "[]":
            try:
                goals = json.loads(dna.goals)
                if goals:
                    dna_parts.append(f"项目目标: {', '.join(goals[:3])}")
            except (json.JSONDecodeError, TypeError):
                pass
        if dna.tools and dna.tools != "[]":
            try:
                tools = json.loads(dna.tools)
                if tools:
                    dna_parts.append(f"常用工具: {', '.join(tools[:5])}")
            except (json.JSONDecodeError, TypeError):
                pass
        if dna_parts:
            if not parts:
                parts.append("## 项目背景\n")
            else:
                parts.append("## 项目背景\n")
            parts.extend(f"- {p}" for p in dna_parts)
            parts.append("")

    # ── 6. Add recent keyword correlations ──
    recent_kws = _find_related_keywords(db, project_id, terms)
    if recent_kws:
        parts.append("## 相关高频关键词\n")
        parts.append(", ".join(recent_kws[:15]))
        parts.append("")

    context = "\n".join(parts) if parts else ""

    # P14: Inject top thought collisions
    try:
        from app.services.collision_engine import get_collision_context_for_bootstrap
        collision_lines = get_collision_context_for_bootstrap(project_id)
        if collision_lines:
            context = context + "\n" + "\n".join(collision_lines) if context else "\n".join(collision_lines)
    except Exception:
        pass

    return context


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: split on whitespace + punctuation, min 2 chars."""
    import re
    tokens = re.findall(r"[\w\u4e00-\u9fff]{2,}", text.lower())
    # Deduplicate, keep order
    seen = set()
    result = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _search_classification_nodes(db: DBSession, project_id: int, terms: list[str]) -> list[ClassificationNode]:
    """Find ClassificationNodes whose keywords or category_name match the search terms."""
    all_nodes = db.query(ClassificationNode).filter(
        ClassificationNode.project_id == project_id
    ).all()

    if not all_nodes:
        return []

    scored = []
    for node in all_nodes:
        score = 0
        search_text = f"{node.category_name} {node.keywords} {node.summary_short}".lower()
        for term in terms:
            if term in search_text:
                score += 1
        # Bonus: deeper nodes (level >= 2) are more specific
        if node.level and node.level >= 2:
            score += 2
        if score > 0:
            scored.append((score, node))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in scored[:10]]


def _collect_failed_approaches(nodes: list[ClassificationNode]) -> list[dict]:
    """Extract failed_approaches from matched nodes, deduplicated."""
    seen = set()
    results = []
    for node in nodes:
        if not node.failed_approaches or node.failed_approaches == "[]":
            continue
        try:
            items = json.loads(node.failed_approaches)
            for item in items:
                if isinstance(item, str):
                    key = item[:80]
                elif isinstance(item, dict):
                    key = item.get("approach", "")[:80]
                    approach = item
                else:
                    continue
                if key and key not in seen:
                    seen.add(key)
                    if isinstance(item, dict):
                        results.append(item)
                    else:
                        results.append({"approach": item})
        except (json.JSONDecodeError, TypeError):
            pass
    return results


def _collect_successful_approaches(nodes: list[ClassificationNode]) -> list[dict]:
    """Extract successful approaches from DNA and nodes."""
    results = []
    seen = set()
    for node in nodes:
        # Check summary_detailed for success indicators
        pass

    return results


def _find_related_keywords(db: DBSession, project_id: int, terms: list[str]) -> list[str]:
    """Find top keywords that frequently co-occur with search terms."""
    all_kws = db.query(Keyword).filter(Keyword.project_id == project_id).all()
    if not all_kws:
        return []

    # Terms that appear in any keyword
    related = set()
    for kw in all_kws:
        kw_lower = kw.keyword.lower()
        for term in terms:
            if term in kw_lower and len(kw_lower) > len(term):
                related.add(kw.keyword)

    return sorted(related, key=lambda k: len(k), reverse=True)[:15]


def bootstrap_and_store(db: DBSession, session) -> None:
    """Generate context and store it on the session. Call after session create."""
    context = bootstrap_session_context(db, session, session.title)
    if context:
        session.context = context
        db.commit()
