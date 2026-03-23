from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.models.progress import UserStats
from app.schemas.progress import StatsOut
from app.services.auth_service import get_current_user

router = APIRouter()
bearer = HTTPBearer()


async def current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        return await get_current_user(creds.credentials, db)
    except ValueError:
        raise HTTPException(401, "Invalid token")


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserStats).where(UserStats.user_id == user.id))
    stats = result.scalar_one_or_none()
    if not stats:
        return StatsOut(
            total_answered=0, correct_count=0, streak=0,
            weak_topics={}, strong_topics={},
        )
    return StatsOut(
        total_answered=stats.total_answered,
        correct_count=stats.correct_count,
        streak=stats.current_streak,
        weak_topics=stats.weak_topics or {},
        strong_topics=stats.strong_topics or {},
    )
