"""Project 15: 乌托邦计划 — chat analysis → insight → task → evaluation pipeline.

Phase 1 (now): file import pipeline (user exports chat logs as txt/csv/json)
Phase 2 (future): real-time via client agent

Flow:
  ChatImport → InsightExtract → Deidentify → Categorize → Prioritize →
  UtopiaTask queue → User completes → DualEval (user 80% + agent 20%) →
  composite > 50% → Server Inbox
"""

from sqlalchemy import Column, Integer, String, Text, Float
from app.database import Base


class ChatImport(Base):
    """Metadata for an imported chat log file."""
    __tablename__ = "utopia_chat_imports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    source_platform = Column(String, default="")      # wechat / qq / feishu / wecom / other
    file_format = Column(String, default="")           # txt / csv / json
    original_filename = Column(String, default="")
    message_count = Column(Integer, default=0)
    extracted_insights = Column(Integer, default=0)    # how many agent-related insights found
    status = Column(String, default="imported")        # imported / processing / analyzed / error
    created_at = Column(String, default="")


class UtopiaInsight(Base):
    """A single de-identified insight extracted from chat analysis."""
    __tablename__ = "utopia_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    import_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)

    # De-identified raw text
    raw_text = Column(Text, default="")               # original (may contain PII, not exposed)
    deidentified_text = Column(Text, default="")       # sanitized version

    # Categorization
    category = Column(String, default="")              # bug / praise / complaint / feature_request / skill_wish / other
    sub_category = Column(String, default="")          # e.g., "timing", "code_quality", "ux", "speed"
    sentiment = Column(String, default="neutral")      # positive / negative / neutral / mixed

    # Agent-relevant keywords found
    keywords_matched = Column(Text, default="[]")      # JSON list

    # Priority dimensions
    mention_count = Column(Integer, default=1)         # how many times this topic appears
    clarity_score = Column(Float, default=0.0)         # 0-1: how clearly the need is expressed
    urgency_score = Column(Float, default=0.0)         # 0-1: derived from "急"/"马上"/"尽快" etc
    priority = Column(Float, default=0.0)              # composite: 0.40*urgency + 0.35*freq + 0.25*clarity

    # Source trace (de-identified)
    source_platform = Column(String, default="")
    source_date = Column(String, default="")

    created_at = Column(String, default="")


class UtopiaTask(Base):
    """A prioritized task generated from insights, for user/client to work on."""
    __tablename__ = "utopia_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)

    # Derived from insight(s)
    source_insight_ids = Column(Text, default="[]")    # JSON list of insight IDs that spawned this
    title = Column(String, default="")
    description = Column(Text, default="")
    category = Column(String, default="")

    # Priority
    priority = Column(Float, default=0.0)

    # Status
    status = Column(String, default="pending")         # pending / claimed / in_progress / submitted / evaluating / accepted / rejected

    # Assignment
    claimed_by = Column(String, default="")            # client_id or user_id
    claimed_at = Column(String, default="")

    # Deadline
    suggested_deadline_hours = Column(Integer, default=72)

    created_at = Column(String, default="")


class UtopiaSubmission(Base):
    """A user/client's creative work responding to a UtopiaTask."""
    __tablename__ = "utopia_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)

    # The creative output
    solution_text = Column(Text, default="")           # description of the solution
    solution_artifacts = Column(Text, default="[]")    # JSON: file paths, code snippets, etc

    # Dual evaluation
    self_score = Column(Float, default=0.0)            # agent self-evaluation (0-1)
    self_rationale = Column(Text, default="")          # why agent thinks it's good
    user_score = Column(Float, default=0.0)            # user evaluation (0-1)
    user_feedback = Column(Text, default="")           # user's comments
    composite_score = Column(Float, default=0.0)       # user*0.80 + self*0.20

    # Decision
    status = Column(String, default="draft")           # draft / submitted / evaluating / accepted / rejected / contested
    contested_reason = Column(Text, default="")        # if user-score and self-score gap > 0.60

    submitted_at = Column(String, default="")
    evaluated_at = Column(String, default="")
    accepted_at = Column(String, default="")
    created_at = Column(String, default="")
