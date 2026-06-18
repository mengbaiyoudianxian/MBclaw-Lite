import json
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models.project import Project
from app.models.project_dna import ProjectDNA
from app.models.summary import Summary
from app.schemas.dna import DNAUpdate


def get_or_create_dna(db: DBSession, project: Project) -> ProjectDNA:
    dna = db.query(ProjectDNA).filter(ProjectDNA.project_id == project.id).first()
    if not dna:
        dna = ProjectDNA(project_id=project.id)
        db.add(dna)
        db.flush()
    return dna


def _parse_json_field(value: str) -> list:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def _dump_json_field(value: list) -> str:
    return json.dumps(value, ensure_ascii=False)


def update_dna(db: DBSession, project: Project, data: DNAUpdate) -> ProjectDNA:
    dna = get_or_create_dna(db, project)

    field_map = {
        "goals": "goals",
        "successful_approaches": "successful_approaches",
        "failed_approaches": "failed_approaches",
        "tools": "tools",
        "models": "models",
        "next_plans": "next_plans",
    }

    for key, attr in field_map.items():
        new_items = getattr(data, key, None)
        if new_items is not None:
            current = _parse_json_field(getattr(dna, attr))
            merged = list(dict.fromkeys(current + new_items))
            setattr(dna, attr, _dump_json_field(merged))

    dna.updated_at = datetime.now().isoformat()
    db.flush()
    return dna


def update_dna_from_session(db: DBSession, project: Project) -> ProjectDNA:
    dna = get_or_create_dna(db, project)
    summaries = (
        db.query(Summary)
        .join(Summary.session)
        .filter(Summary.session.has(project_id=project.id))
        .all()
    )

    decisions = []
    next_steps = []
    for s in summaries:
        if s.decisions:
            decisions.append(s.decisions)
        if s.next_steps:
            next_steps.append(s.next_steps)

    if decisions:
        current = _parse_json_field(dna.successful_approaches)
        merged = list(dict.fromkeys(current + decisions))
        dna.successful_approaches = _dump_json_field(merged)

    if next_steps:
        current = _parse_json_field(dna.next_plans)
        merged = list(dict.fromkeys(current + next_steps))
        dna.next_plans = _dump_json_field(merged)

    dna.updated_at = datetime.now().isoformat()
    db.flush()
    return dna
