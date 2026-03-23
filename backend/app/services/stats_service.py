import uuid
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.progress import UserStats, UserProgress
from app.models.question import Question


async def record_answer(
    user_id: uuid.UUID,
    question: Question,
    chosen_index: int,
    time_spent_ms: int,
    db: AsyncSession,
) -> UserStats:
    is_correct = chosen_index == question.correct_index

    db.add(UserProgress(
        user_id=user_id,
        question_id=question.id,
        chosen_index=chosen_index,
        is_correct=is_correct,
        time_spent_ms=time_spent_ms,
    ))

    result = await db.execute(
        select(UserStats).where(UserStats.user_id == user_id).with_for_update()
    )
    stats = result.scalar_one()

    # Check 24h inactivity streak reset
    if stats.last_active_at and datetime.utcnow() - stats.last_active_at > timedelta(hours=24):
        stats.current_streak = 0

    stats.total_answered += 1
    if is_correct:
        stats.correct_count += 1
        stats.current_streak += 1
    else:
        stats.current_streak = 0

    # Update topic accuracy (exponential moving average)
    topic = question.topic
    weak = dict(stats.weak_topics or {})
    strong = dict(stats.strong_topics or {})

    prev = weak.get(topic, strong.get(topic, 0.5))
    updated = prev * 0.8 + (1.0 if is_correct else 0.0) * 0.2
    if updated < 0.6:
        weak[topic] = round(updated, 3)
        strong.pop(topic, None)
    else:
        strong[topic] = round(updated, 3)
        weak.pop(topic, None)

    stats.weak_topics = weak
    stats.strong_topics = strong
    stats.last_active_at = datetime.utcnow()

    await db.commit()
    await db.refresh(stats)
    return stats
