"""F2: User Psychology Profile — understand the user through feedback.

Builds a psychological profile from:
  1. Direct feedback (what they praise / criticize)
  2. Language patterns (formality, emotional words, decision style)
  3. Chat history analysis (with permission)
  4. Behavioral patterns (when they interrupt, what they prioritize)

Output: CompanionArchetype — how the agent should adapt its communication.
"""

from sqlalchemy import Column, Integer, String, Text, Float
from app.database import Base


class UserProfile(Base):
    """Psychological profile for a user. Updated continuously."""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, unique=True)

    # Core traits (MBTI-inspired, simplified to 4 axes)
    # Each axis: -1.0 to 1.0 (e.g., -1=introvert, +1=extrovert)
    social_energy = Column(Float, default=0.0)       # introvert ↔ extrovert
    decision_style = Column(Float, default=0.0)      # feeling ↔ thinking
    communication = Column(Float, default=0.0)       # indirect ↔ direct
    structure_pref = Column(Float, default=0.0)      # flexible ↔ structured

    # Companion archetype
    companion_archetype = Column(String, default="collaborator")
    archetype_confidence = Column(Float, default=0.0)

    # Positive reinforcement patterns
    praised_language = Column(Text, default="[]")    # JSON: words/phrases they like
    praised_behaviors = Column(Text, default="[]")   # JSON: behaviors they appreciate
    praised_thinking = Column(Text, default="[]")    # JSON: thinking styles they value

    # Communication preferences
    formality_level = Column(String, default="casual")  # casual / neutral / formal
    humor_tolerance = Column(Float, default=0.5)
    detail_preference = Column(String, default="balanced")  # concise / balanced / exhaustive

    # Meta
    feedback_count = Column(Integer, default=0)
    confidence_score = Column(Float, default=0.0)    # how confident we are in this profile
    updated_at = Column(String, default="")


class PositivePattern(Base):
    """Stores specific positive feedback patterns for reinforcement."""
    __tablename__ = "positive_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    category = Column(String, default="")         # language / behavior / thinking
    pattern = Column(Text, default="")            # the specific pattern observed
    source = Column(String, default="feedback")   # feedback / chat_analysis / inferred
    strength = Column(Float, default=1.0)         # how strongly this pattern is confirmed (0-5)
    occurrences = Column(Integer, default=1)
    created_at = Column(String, default="")


class ChatAnalysisRequest(Base):
    """Permission-gated request to analyze user's chats with others."""
    __tablename__ = "chat_analysis_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    status = Column(String, default="pending")    # pending / approved / denied / completed
    chat_source = Column(String, default="")       # description of chat source
    analysis_result = Column(Text, default="")
    permission_granted_at = Column(String, default="")
    analyzed_at = Column(String, default="")
    created_at = Column(String, default="")
