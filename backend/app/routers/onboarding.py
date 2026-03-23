from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.question import Question
from app.models.user import User
from app.models.progress import UserStats
from app.schemas.question import QuestionOut, OnboardingSubmit
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


def _score_to_level(correct: int) -> str:
    if correct <= 1:
        return "beginner"
    if correct <= 3:
        return "intermediate"
    return "advanced"


@router.get("/questions", response_model=list[QuestionOut])
async def get_onboarding_questions(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    results = []
    for difficulty, count in [(1, 2), (2, 2), (3, 1)]:
        r = await db.execute(
            select(Question)
            .where(Question.difficulty == difficulty)
            .order_by(func.random())
            .limit(count)
        )
        results.extend(r.scalars().all())
    return results


@router.post("/submit")
async def submit_onboarding(
    body: OnboardingSubmit,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    question_ids = [a.question_id for a in body.answers]
    r = await db.execute(select(Question).where(Question.id.in_(question_ids)))
    questions = {q.id: q for q in r.scalars().all()}

    correct = sum(
        1
        for a in body.answers
        if questions.get(a.question_id)
        and questions[a.question_id].correct_index == a.chosen_index
    )
    level = _score_to_level(correct)

    user.level = level
    user.onboarding_complete = True

    stats = UserStats(user_id=user.id)
    db.add(stats)
    await db.commit()

    return {"level": level}
