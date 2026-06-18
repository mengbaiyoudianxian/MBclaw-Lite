from typing import Optional
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import or_

from app.models.project import Project
from app.models.session import Session
from app.models.message import Message
from app.models.summary import Summary
from app.models.keyword import Keyword
from app.schemas.search import SearchResult


def search(db: DBSession, query: str, project_id: Optional[int] = None) -> list[SearchResult]:
    results = []

    project_filter = [Project.id == project_id] if project_id else []

    # search projects by name/description
    proj_query = db.query(Project).filter(
        or_(Project.name.contains(query), Project.description.contains(query))
    )
    if project_id:
        proj_query = proj_query.filter(Project.id == project_id)
    for p in proj_query.limit(5):
        results.append(SearchResult(type="project", id=p.id, project_name=p.name, snippet=p.description[:200]))

    # search sessions by title
    sess_query = db.query(Session).join(Project).filter(Session.title.contains(query))
    if project_id:
        sess_query = sess_query.filter(Session.project_id == project_id)
    for s in sess_query.limit(5):
        results.append(SearchResult(
            type="session", id=s.id,
            project_name=s.project.name,
            snippet=f"[Session #{s.session_number}] {s.title}",
        ))

    # search messages by content
    msg_query = db.query(Message).join(Session).join(Project).filter(Message.content.contains(query))
    if project_id:
        msg_query = msg_query.filter(Session.project_id == project_id)
    for m in msg_query.limit(5):
        pos = m.content.lower().find(query.lower())
        start = max(0, pos - 40)
        end = min(len(m.content), pos + len(query) + 80)
        snippet = m.content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(m.content):
            snippet = snippet + "..."
        results.append(SearchResult(
            type="message", id=m.id,
            project_name=m.session.project.name,
            snippet=snippet,
        ))

    # search summaries
    sum_query = db.query(Summary).join(Session).join(Project).filter(
        or_(
            Summary.topic.contains(query),
            Summary.conclusions.contains(query),
            Summary.decisions.contains(query),
            Summary.next_steps.contains(query),
        )
    )
    if project_id:
        sum_query = sum_query.filter(Session.project_id == project_id)
    for s in sum_query.limit(5):
        results.append(SearchResult(
            type="summary", id=s.id,
            project_name=s.session.project.name,
            snippet=f"[{s.topic[:100]}] {s.conclusions[:100]}",
        ))

    # search keywords
    kw_query = db.query(Keyword).join(Project).filter(Keyword.keyword.contains(query))
    if project_id:
        kw_query = kw_query.filter(Keyword.project_id == project_id)
    for k in kw_query.limit(5):
        results.append(SearchResult(
            type="keyword", id=k.id,
            project_name=k.project.name,
            snippet=f"Keyword: {k.keyword} (weight: {k.weight})",
        ))

    return results
