import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
from app.models.question import Question
from app.models.progress import UserProgress
from app.schemas.question import QuestionOut
from app.services.auth_service import get_current_user
from app.services import question_router as qr, stats_service

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


class AnswerRequest(BaseModel):
    chosen_index: int
    time_spent_ms: int = 0


@router.get("/next", response_model=QuestionOut)
async def next_question(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.onboarding_complete:
        raise HTTPException(403, "Complete onboarding first")
    q = await qr.get_next_question(user, db)
    if not q:
        raise HTTPException(404, "No questions available")
    return q


@router.post("/{question_id}/answer")
async def answer_question(
    question_id: uuid.UUID,
    body: AnswerRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Question).where(Question.id == question_id))
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")
    if body.chosen_index not in range(5):
        raise HTTPException(400, "chosen_index must be 0-4")
    stats = await stats_service.record_answer(
        user.id, q, body.chosen_index, body.time_spent_ms, db
    )
    return {
        "is_correct": body.chosen_index == q.correct_index,
        "correct_index": q.correct_index,
        "streak": stats.current_streak,
    }


@router.get("/{question_id}/explain")
async def explain_question(
    question_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserProgress)
        .where(
            UserProgress.user_id == user.id,
            UserProgress.question_id == question_id,
        )
        .order_by(UserProgress.answered_at.desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    if not last or last.is_correct:
        raise HTTPException(403, "Explanation only available after a wrong answer")

    q_result = await db.execute(select(Question).where(Question.id == question_id))
    q = q_result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")

    from app.services.ollama_client import stream_explanation

    return StreamingResponse(
        stream_explanation(q, last.chosen_index, user.level),
        media_type="text/event-stream",
    )


class FollowupRequest(BaseModel):
    question: str
    history: list[dict] = []


@router.get("/{question_id}/suggestions")
async def get_suggestions(
    question_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    q_result = await db.execute(select(Question).where(Question.id == question_id))
    q = q_result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")
    from app.services.ollama_client import suggest_followups
    return {"suggestions": suggest_followups(q, user.level)}


@router.post("/{question_id}/followup")
async def followup_question(
    question_id: uuid.UUID,
    body: FollowupRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserProgress)
        .where(
            UserProgress.user_id == user.id,
            UserProgress.question_id == question_id,
        )
        .order_by(UserProgress.answered_at.desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    if not last or last.is_correct:
        raise HTTPException(403, "Follow-up only available after a wrong answer")

    q_result = await db.execute(select(Question).where(Question.id == question_id))
    q = q_result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")

    from app.services.ollama_client import stream_followup

    return StreamingResponse(
        stream_followup(q, last.chosen_index, user.level, body.history, body.question),
        media_type="text/event-stream",
    )
