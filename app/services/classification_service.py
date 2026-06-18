import json
import os
import httpx
from sqlalchemy.orm import Session as DBSession

from app.models.session import Session
from app.models.summary import Summary
from app.models.project import Project
from app.models.classification_node import ClassificationNode
from app.services.vector_store import index_text, search_similar
from app.config import OLLAMA_BASE_URL as DEFAULT_OLLAMA_URL

COLLECTION_NAME = "classification_nodes"


def _get_llm_category(text: str) -> dict | None:
    """Best-effort LLM categorization. Falls back to keyword-based if LLM unavailable."""
    prompt = f"""分析以下对话总结，输出 JSON 格式的分类结果（只输出 JSON，不要其他内容）：
{{
  "level1": "一级分类（如：后端/前端/运维/设计/其他）",
  "level2": "二级分类（如：数据库/API/UI/部署）",
  "level3": "具体话题（≤20字）",
  "summary_short": "200字以内粗略总结",
  "summary_detailed": "完整详细总结",
  "failed_approaches": ["失败方案1", "失败方案2"],
  "keywords": ["关键词1", "关键词2"]
}}

对话内容：
{text[:3000]}"""

    try:
        base_url = os.environ.get("LLM_API_BASE", DEFAULT_OLLAMA_URL)
        api_key = os.environ.get("LLM_API_KEY", "")
        model = os.environ.get("LLM_MODEL", "qwen2.5:7b")

        if not base_url:
            return None

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        resp = httpx.post(
            f"{base_url}/chat/completions",
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 800},
            headers=headers,
            timeout=60,
        )
        if resp.status_code == 200:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            # Try to extract JSON from markdown code blocks
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
    except Exception:
        pass
    return None


def _keyword_fallback(text: str) -> dict:
    """Simple keyword-based classification when LLM is unavailable."""
    text_lower = text.lower()
    cats = {
        "后端": ["api", "数据库", "sql", "接口", "服务", "server", "后端", "fastapi", "http"],
        "前端": ["ui", "界面", "页面", "前端", "html", "css", "react", "组件"],
        "运维": ["部署", "docker", "容器", "服务器", "nginx", "配置"],
        "设计": ["架构", "设计", "方案", "模式", "pattern"],
    }
    scores = {k: sum(1 for kw in v if kw in text_lower) for k, v in cats.items()}
    best = max(scores, key=scores.get) if any(scores.values()) else "通用"

    return {
        "level1": best,
        "level2": "未分类",
        "level3": "自动分类",
        "summary_short": text[:200],
        "summary_detailed": text[:1000],
        "failed_approaches": [],
        "keywords": [w for w in text[:500].split() if len(w) > 1][:10],
    }


def classify_session(db: DBSession, session: Session):
    """Classify a completed session into the topic tree."""
    summary = db.query(Summary).filter(Summary.session_id == session.id).first()
    combined_text = (
        (summary.topic or "") + " "
        + (summary.conclusions or "") + " "
        + (summary.decisions or "")
    ).strip()

    if not combined_text:
        combined_text = " ".join(m.content[:200] for m in session.messages[:3])

    if not combined_text.strip():
        return

    result = _get_llm_category(combined_text) or _keyword_fallback(combined_text)

    keywords = json.dumps(result.get("keywords", []))
    failed = result.get("failed_approaches", [])
    if isinstance(failed, str):
        failed = [failed]
    failed_json = json.dumps(failed, ensure_ascii=False)

    # Find or create parent node at level1
    level1_name = result.get("level1", "未分类")
    parent = _find_or_create_node(db, session.project_id, None, level1_name, 1)

    # Find or create level2 node
    level2_name = result.get("level2", "未分类")
    parent = _find_or_create_node(db, session.project_id, parent.id, f"{level1_name}/{level2_name}", 2)

    # Create level3 node (leaf for this session)
    level3_name = result.get("level3", "具体话题")
    node = ClassificationNode(
        parent_id=parent.id,
        project_id=session.project_id,
        session_id=session.id,
        level=3,
        category_name=f"{level1_name}/{level2_name}/{level3_name}",
        summary_short=result.get("summary_short", combined_text[:200]),
        summary_detailed=result.get("summary_detailed", combined_text),
        failed_approaches=failed_json,
        keywords=keywords,
    )
    db.add(node)
    db.commit()
    db.refresh(node)

    # Index into ChromaDB for semantic search (best-effort)
    try:
        index_text(
            COLLECTION_NAME,
            f"node_{node.id}",
            f"{level3_name}: {node.summary_short}",
            {"project_id": str(session.project_id), "level": "3"},
        )
    except Exception:
        pass  # ChromaDB may not be available

    # If there are failed approaches, also store in ProjectDNA
    if failed:
        project = db.query(Project).filter(Project.id == session.project_id).first()
        if project:
            from app.models.project_dna import ProjectDNA
            dna = db.query(ProjectDNA).filter(ProjectDNA.project_id == session.project_id).first()
            if dna:
                existing = json.loads(dna.failed_approaches_detail) if dna.failed_approaches_detail else []
                for f in failed:
                    if f not in existing:
                        existing.append(f)
                dna.failed_approaches_detail = json.dumps(existing, ensure_ascii=False)
                db.commit()

    return node


def _find_or_create_node(db: DBSession, project_id: int, parent_id: int | None, name: str, level: int) -> ClassificationNode:
    existing = (
        db.query(ClassificationNode)
        .filter(
            ClassificationNode.project_id == project_id,
            ClassificationNode.category_name == name,
            ClassificationNode.level == level,
        )
        .first()
    )
    if existing:
        return existing
    node = ClassificationNode(
        parent_id=parent_id,
        project_id=project_id,
        level=level,
        category_name=name,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def get_failed_approaches(db: DBSession, project_id: int) -> list[str]:
    """Retrieve all failed approaches for a project as a flat list."""
    nodes = (
        db.query(ClassificationNode)
        .filter(ClassificationNode.project_id == project_id)
        .all()
    )
    all_failed = []
    for n in nodes:
        if n.failed_approaches:
            try:
                arr = json.loads(n.failed_approaches)
                if isinstance(arr, list):
                    all_failed.extend(arr)
            except (json.JSONDecodeError, TypeError):
                pass
    return list(dict.fromkeys(all_failed))
