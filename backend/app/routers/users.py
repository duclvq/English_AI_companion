from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.user import GoalUpdateRequest
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


@router.patch("/me/goal")
async def set_goal(
    body: GoalUpdateRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    user.goal = body.goal
    user.daily_goal = body.daily_goal
    await db.commit()
    return {"success": True}
