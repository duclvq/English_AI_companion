import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.models.practice import PracticePrompt
from app.schemas.practice import PracticePromptOut, PracticeSubmitRequest, PracticeFeedbackResponse
from app.services.auth_service import get_current_user
from app.services import practice_service

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


@router.get("/prompt", response_model=PracticePromptOut)
async def get_prompt(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    prompt = await practice_service.get_prompt_for_user(user.id, user.level, db)
    if not prompt:
        raise HTTPException(404, "No practice prompts available")
    return prompt


@router.post("/submit", response_model=PracticeFeedbackResponse)
async def submit_practice(
    body: PracticeSubmitRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if len(body.user_text.strip()) < 20:
        raise HTTPException(400, detail="Please write a bit more for Beary to help you!")

    result = await db.execute(select(PracticePrompt).where(PracticePrompt.id == body.prompt_id))
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(404, "Prompt not found")

    try:
        feedback = await practice_service.validate_writing(
            prompt, body.user_text, user.level, user.id, db
        )
    except (ValueError, Exception):
        raise HTTPException(503, detail="Beary is thinking... try again in a moment.")

    return feedback
