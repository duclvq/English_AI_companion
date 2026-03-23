from datetime import datetime, timedelta
from sqlalchemy import select, and_, not_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.question import Question
from app.models.progress import UserProgress
from app.models.user import User


async def get_next_question(user: User, db: AsyncSession) -> Question | None:
    # IDs the user answered correctly in last 30 days (suppress)
    cutoff_correct = datetime.utcnow() - timedelta(days=30)
    suppress_result = await db.execute(
        select(UserProgress.question_id).where(
            and_(
                UserProgress.user_id == user.id,
                UserProgress.is_correct == True,
                UserProgress.answered_at >= cutoff_correct,
            )
        )
    )
    suppress_ids = [r[0] for r in suppress_result.all()]

    # IDs answered incorrectly within last 7 days (also suppress for now)
    cutoff_wrong = datetime.utcnow() - timedelta(days=7)
    wrong_result = await db.execute(
        select(UserProgress.question_id).where(
            and_(
                UserProgress.user_id == user.id,
                UserProgress.is_correct == False,
                UserProgress.answered_at >= cutoff_wrong,
            )
        )
    )
    suppress_ids += [r[0] for r in wrong_result.all()]

    difficulty_map = {"beginner": 1, "intermediate": 2, "advanced": 3}
    difficulty = difficulty_map.get(user.level, 2)

    # Build the suppression filter
    suppress_filter = not_(Question.id.in_(suppress_ids)) if suppress_ids else True

    # 1. Try agent-generated questions first
    result = await db.execute(
        select(Question).where(
            and_(
                Question.generated_by == "agent",
                Question.difficulty == difficulty,
                suppress_filter,
            )
        ).order_by(Question.created_at).limit(1)
    )
    q = result.scalar_one_or_none()
    if q:
        return q

    # 2. Fall back to seed questions matching user level
    result = await db.execute(
        select(Question).where(
            and_(
                Question.generated_by == "seed",
                Question.difficulty == difficulty,
                suppress_filter,
            )
        ).order_by(Question.created_at).limit(1)
    )
    return result.scalar_one_or_none()
