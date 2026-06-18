"""F1: Active Feedback Solicitation — user rates agent performance.

Three uses:
  1. Breakthrough snapshots (high ratings → trigger snapshot)
  2. Success rate tracking (per approach / ClassificationNode)
  3. AI self-improvement (aggregate feedback → behavior adjustment)
"""

from sqlalchemy import Column, Integer, String, Text, Float
from app.database import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False)
    session_id = Column(Integer, nullable=True)
    task_id = Column(Integer, nullable=True)

    # Rating
    overall_rating = Column(Integer, default=0)    # 1-5
    helpfulness = Column(Integer, default=0)       # 1-5
    accuracy = Column(Integer, default=0)          # 1-5
    speed = Column(Integer, default=0)             # 1-5
    clarity = Column(Integer, default=0)           # 1-5

    # Free text
    what_went_well = Column(Text, default="")
    what_to_improve = Column(Text, default="")
    free_text = Column(Text, default="")

    # Metadata
    solicited = Column(String, default="auto")    # auto / manual
    created_at = Column(String, default="")

    @property
    def avg_score(self) -> float:
        scores = [s for s in [self.helpfulness, self.accuracy, self.speed, self.clarity] if s > 0]
        return sum(scores) / len(scores) if scores else 0


class ApproachSuccessRate(Base):
    """Track success/failure rates per approach for ClassificationNode linking."""
    __tablename__ = "approach_success_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False)
    approach_name = Column(String, default="")
    total_attempts = Column(Integer, default=0)
    successes = Column(Integer, default=0)
    failures = Column(Integer, default=0)
    avg_rating = Column(Float, default=0.0)
    updated_at = Column(String, default="")

    @property
    def success_rate(self) -> float:
        return self.successes / self.total_attempts if self.total_attempts > 0 else 0.0
