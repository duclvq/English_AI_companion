import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PracticePrompt(Base):
    __tablename__ = "practice_prompts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario: Mapped[str] = mapped_column(String(1000), nullable=False)
    hint: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PracticeSession(Base):
    __tablename__ = "practice_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    prompt_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    user_text: Mapped[str] = mapped_column(String(5000), nullable=False)
    feedback_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
