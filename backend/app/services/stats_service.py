import uuid
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.progress import UserStats, UserProgress
from app.models.question import Question


async def apply_daily_reset(user_id: uuid.UUID, db: AsyncSession) -> None:
    """Reset daily counters if calendar day (UTC) has changed since last_active_at."""
    result = await db.execute(
        select(UserStats).where(UserStats.user_id == user_id).with_for_update()
    )
    stats = result.scalar_one_or_none()
    if not stats:
        return
    today_utc = datetime.utcnow().date()
    last_active_date = stats.last_active_at.date() if stats.last_active_at else None
    if last_active_date is None or last_active_date < today_utc:
        stats.daily_answered_count = 0
        stats.daily_correct_count = 0
        stats.daily_xp = 0
        stats.daily_goal_completed_at = None
        await db.commit()


async def record_answer(
    user_id: uuid.UUID,
    question: Question,
    chosen_index: int,
    time_spent_ms: int,
    daily_goal: int,
    db: AsyncSession,
) -> UserStats:
    is_correct = chosen_index == question.correct_index
    xp_earned = 10 if is_correct else 0

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

    # Streak reset: 24h inactivity only (no reset on wrong answer per v2 spec)
    if stats.last_active_at and datetime.utcnow() - stats.last_active_at > timedelta(hours=24):
        stats.current_streak = 0

    stats.total_answered += 1
    stats.daily_answered_count += 1

    if is_correct:
        stats.correct_count += 1
        stats.daily_correct_count += 1
        stats.current_streak += 1
        stats.xp_total += xp_earned
        stats.daily_xp += xp_earned

    # Topic accuracy (rolling EMA)
    topic = question.topic
    weak = dict(stats.weak_topics or {})
    strong = dict(stats.strong_topics or {})
    prev = weak.get(topic, strong.get(topic, 0.5))
    updated = round(prev * 0.8 + (1.0 if is_correct else 0.0) * 0.2, 3)
    if updated < 0.6:
        weak[topic] = updated
        strong.pop(topic, None)
    else:
        strong[topic] = updated
        weak.pop(topic, None)
    stats.weak_topics = weak
    stats.strong_topics = strong

    # Daily goal completion
    daily_goal_complete = False
    if stats.daily_answered_count >= daily_goal and stats.daily_goal_completed_at is None:
        stats.daily_goal_completed_at = datetime.utcnow()
        daily_goal_complete = True

    stats.last_active_at = datetime.utcnow()

    await db.commit()
    await db.refresh(stats)

    # Attach transient fields for caller
    stats._xp_earned = xp_earned
    stats._daily_goal_complete = daily_goal_complete
    return stats
