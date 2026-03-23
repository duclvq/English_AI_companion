# Backend UX Additions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Phase 1 FastAPI backend with new DB fields for gamification, updated stats/streak logic, a goal-setting endpoint, and a full Practice tab API (prompt selection + Qwen3:8b writing validation).

**Architecture:** Additive changes to the existing Phase 1 monolith. New models and services follow the same patterns already in place. A seed script inserts practice prompts. Stats service is updated in-place to change streak and daily reset behavior.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x (async), Alembic, PostgreSQL 15+, httpx (Qwen3:8b calls), pytest + pytest-asyncio

---

## File Structure

```
backend/
  alembic/versions/
    xxxx_ux_additions.py            # Alembic migration: new columns + practice tables
  app/
    models/
      user.py                       # Modify: add goal, daily_goal fields
      progress.py                   # Modify: add xp_total, daily_xp, daily_correct_count,
                                    #         daily_answered_count, daily_goal_completed_at
      practice.py                   # Create: PracticePrompt, PracticeSession ORM models
    routers/
      questions.py                  # Modify: extend answer response with XP/daily fields
      users.py                      # Create: PATCH /users/me/goal endpoint
      practice.py                   # Create: GET /practice/prompt, POST /practice/submit
    services/
      stats_service.py              # Modify: new streak rule, calendar-day reset, daily counters
      practice_service.py           # Create: prompt selection, Qwen3:8b call, weak_topics update
    schemas/
      question.py                   # Modify: extend AnswerResponse
      user.py                       # Create: GoalUpdateRequest schema
      practice.py                   # Create: PracticePromptOut, SubmitRequest, FeedbackResponse
    main.py                         # Modify: register users + practice routers
  scripts/
    seed_practice_prompts.py        # Create: insert practice_prompts seed data
  tests/
    test_stats.py                   # Create: daily reset, streak, XP, daily counters
    test_practice.py                # Create: prompt selection, submit, feedback, validation
    test_users.py                   # Create: PATCH /users/me/goal
```

---

## Task 1: DB Migration — New Columns + Practice Tables

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/progress.py`
- Create: `backend/app/models/practice.py`
- Create: `backend/alembic/versions/xxxx_ux_additions.py` (auto-generated)

- [ ] **Step 1: Add `goal` and `daily_goal` fields to `app/models/user.py`**

Open `app/models/user.py` and add two fields to the `User` class after `onboarding_complete`:

```python
goal: Mapped[str | None] = mapped_column(String(20), nullable=True)       # travel/exam/work/general
daily_goal: Mapped[int | None] = mapped_column(Integer, nullable=True)    # 5/10/20/30
```

Add `from sqlalchemy import Integer` to imports if not already present.

- [ ] **Step 2: Add new gamification fields to `UserStats` in `app/models/progress.py`**

Add these fields to the `UserStats` class after `agent_last_trigger_count`:

```python
xp_total: Mapped[int] = mapped_column(Integer, default=0)
daily_xp: Mapped[int] = mapped_column(Integer, default=0)
daily_answered_count: Mapped[int] = mapped_column(Integer, default=0)
daily_correct_count: Mapped[int] = mapped_column(Integer, default=0)
daily_goal_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 3: Create `app/models/practice.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PracticePrompt(Base):
    __tablename__ = "practice_prompts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–3
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
```

- [ ] **Step 4: Import new models in `alembic/env.py`**

Add to the imports section in `alembic/env.py`:

```python
from app.models import user, question, progress, practice  # add practice
```

- [ ] **Step 5: Generate and apply migration**

```bash
cd backend
alembic revision --autogenerate -m "ux additions: gamification fields and practice tables"
alembic upgrade head
```

- [ ] **Step 6: Verify new tables and columns**

```bash
psql english_companion -c "\dt"
# Expected: practice_prompts, practice_sessions appear in list

psql english_companion -c "\d users"
# Expected: goal, daily_goal columns present

psql english_companion -c "\d user_stats"
# Expected: xp_total, daily_xp, daily_answered_count, daily_correct_count, daily_goal_completed_at present
```

- [ ] **Step 7: Commit**

```bash
git add app/models/user.py app/models/progress.py app/models/practice.py alembic/
git commit -m "feat: DB migration for gamification fields and practice tables"
```

---

## Task 2: Updated Stats Service (Streak + Daily Counters)

**Files:**
- Modify: `backend/app/services/stats_service.py`
- Create: `backend/tests/test_stats.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_stats.py`:

```python
import pytest
from datetime import datetime, timedelta
from app.models.question import Question
from app.models.progress import UserStats


async def _setup_user_with_stats(client, db_session):
    r = await client.post("/auth/register", json={"email": "s@test.com", "password": "pass123"})
    token = r.json()["access_token"]
    from app.models.user import User
    from sqlalchemy import select
    result = await db_session.execute(select(User).where(User.email == "s@test.com"))
    user = result.scalar_one()
    user.onboarding_complete = True
    user.daily_goal = 10
    stats = UserStats(user_id=user.id)
    db_session.add(stats)
    await db_session.commit()
    return token, user


@pytest.mark.asyncio
async def test_correct_answer_increments_xp(client, db_session):
    token, user = await _setup_user_with_stats(client, db_session)
    q = Question(type="vocabulary", difficulty=2, topic="synonyms",
                 question_text="Q", choices=["a","b","c","d","e"], correct_index=0)
    db_session.add(q)
    await db_session.commit()

    r = await client.post(f"/questions/{q.id}/answer",
                          json={"chosen_index": 0},
                          headers={"Authorization": f"Bearer {token}"})
    data = r.json()
    assert data["xp_earned"] == 10
    assert data["daily_xp"] == 10
    assert data["daily_answered_count"] == 1
    assert data["daily_correct_count"] == 1


@pytest.mark.asyncio
async def test_wrong_answer_does_not_reset_streak(client, db_session):
    token, user = await _setup_user_with_stats(client, db_session)
    # Build streak of 3
    for i in range(3):
        q = Question(type="vocabulary", difficulty=2, topic="synonyms",
                     question_text=f"Q{i}", choices=["a","b","c","d","e"], correct_index=0)
        db_session.add(q)
    await db_session.commit()
    from sqlalchemy import select
    from app.models.question import Question as Q
    qs = (await db_session.execute(select(Q))).scalars().all()
    for q in qs:
        await client.post(f"/questions/{q.id}/answer",
                          json={"chosen_index": 0},
                          headers={"Authorization": f"Bearer {token}"})

    # Now answer wrong — streak must NOT reset
    q_wrong = Question(type="vocabulary", difficulty=2, topic="synonyms",
                       question_text="Qwrong", choices=["a","b","c","d","e"], correct_index=0)
    db_session.add(q_wrong)
    await db_session.commit()
    r = await client.post(f"/questions/{q_wrong.id}/answer",
                          json={"chosen_index": 1},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.json()["streak"] == 3  # unchanged


@pytest.mark.asyncio
async def test_wrong_answer_increments_daily_answered_not_correct(client, db_session):
    token, user = await _setup_user_with_stats(client, db_session)
    q = Question(type="vocabulary", difficulty=2, topic="synonyms",
                 question_text="Q", choices=["a","b","c","d","e"], correct_index=0)
    db_session.add(q)
    await db_session.commit()

    r = await client.post(f"/questions/{q.id}/answer",
                          json={"chosen_index": 1},  # wrong
                          headers={"Authorization": f"Bearer {token}"})
    data = r.json()
    assert data["xp_earned"] == 0
    assert data["daily_answered_count"] == 1
    assert data["daily_correct_count"] == 0


@pytest.mark.asyncio
async def test_daily_goal_complete_flag_set(client, db_session):
    token, user = await _setup_user_with_stats(client, db_session)
    user.daily_goal = 2
    await db_session.commit()

    for i in range(2):
        q = Question(type="vocabulary", difficulty=2, topic="synonyms",
                     question_text=f"Q{i}", choices=["a","b","c","d","e"], correct_index=0)
        db_session.add(q)
    await db_session.commit()
    from sqlalchemy import select
    qs = (await db_session.execute(select(Question))).scalars().all()

    responses = []
    for q in qs:
        r = await client.post(f"/questions/{q.id}/answer",
                              json={"chosen_index": 0},
                              headers={"Authorization": f"Bearer {token}"})
        responses.append(r.json())

    assert responses[-1]["daily_goal_complete"] is True
    assert responses[0]["daily_goal_complete"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_stats.py -v
# Expected: FAIL — new fields not in response yet
```

- [ ] **Step 3: Update `app/services/stats_service.py`**

Replace the full `record_answer` function:

```python
from datetime import datetime, timedelta, date
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.progress import UserStats, UserProgress
from app.models.question import Question


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

    # --- Daily reset: calendar-day boundary (UTC) ---
    today_utc = datetime.utcnow().date()  # UTC date — do NOT use date.today() (uses local server time)
    last_active_date = stats.last_active_at.date() if stats.last_active_at else None
    if last_active_date is None or last_active_date < today_utc:
        stats.daily_answered_count = 0
        stats.daily_correct_count = 0
        stats.daily_xp = 0
        stats.daily_goal_completed_at = None

    # --- Streak reset: 24h inactivity only (no reset on wrong answer) ---
    if stats.last_active_at and datetime.utcnow() - stats.last_active_at > timedelta(hours=24):
        stats.current_streak = 0

    # --- Update counters ---
    stats.total_answered += 1
    stats.daily_answered_count += 1

    if is_correct:
        stats.correct_count += 1
        stats.daily_correct_count += 1
        stats.current_streak += 1
        stats.xp_total += xp_earned
        stats.daily_xp += xp_earned

    # --- Topic accuracy (rolling EMA) ---
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

    # --- Daily goal completion ---
    daily_goal_complete = False
    if (
        stats.daily_answered_count >= daily_goal
        and stats.daily_goal_completed_at is None
    ):
        stats.daily_goal_completed_at = datetime.utcnow()
        daily_goal_complete = True

    stats.last_active_at = datetime.utcnow()

    await db.commit()
    await db.refresh(stats)

    # Attach transient fields for caller
    stats._xp_earned = xp_earned
    stats._daily_goal_complete = daily_goal_complete
    return stats
```

- [ ] **Step 4: Update `app/routers/questions.py` — daily reset on `/next`, extend answer response**

The spec requires the daily reset to fire on `GET /questions/next` (not inside `record_answer`). Add a reset call at the top of `next_question`, and extend the answer response:

```python
# Add to imports
from app.services.stats_service import apply_daily_reset

@router.get("/next", response_model=QuestionOut)
async def next_question(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if not user.onboarding_complete:
        raise HTTPException(403, "Complete onboarding first")
    # Daily reset fires here per spec
    await apply_daily_reset(user.id, db)
    q = await qr.get_next_question(user, db)
    if not q:
        raise HTTPException(404, "No questions available")
    return q
```

Add `apply_daily_reset` to `stats_service.py` (extracted from `record_answer`):

```python
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
```

Remove the daily-reset block from `record_answer` (keep only streak reset + counter updates).

In `answer_question`, pass `daily_goal` and extend the return dict:

```python
daily_goal = user.daily_goal or 10
stats = await stats_service.record_answer(
    user.id, q, body.chosen_index, body.time_spent_ms, daily_goal, db
)
return {
    "is_correct": body.chosen_index == q.correct_index,
    "correct_index": q.correct_index,
    "streak": stats.current_streak,
    "xp_earned": stats._xp_earned,
    "daily_xp": stats.daily_xp,
    "daily_answered_count": stats.daily_answered_count,
    "daily_correct_count": stats.daily_correct_count,
    "daily_goal": daily_goal,
    "daily_goal_complete": stats._daily_goal_complete,
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_stats.py -v
# Expected: 4 PASSED
```

- [ ] **Step 6: Commit**

```bash
git add app/services/stats_service.py app/routers/questions.py tests/test_stats.py
git commit -m "feat: gamification stats — XP, daily counters, streak only resets on inactivity"
```

---

## Task 3: Goal-Setting Endpoint

**Files:**
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/routers/users.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_users.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_users.py`:

```python
import pytest


async def _register(client):
    r = await client.post("/auth/register", json={"email": "u@test.com", "password": "pass123"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_set_goal_saves_fields(client, db_session):
    token = await _register(client)
    r = await client.patch("/users/me/goal",
                           json={"goal": "exam", "daily_goal": 10},
                           headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["success"] is True

    from app.models.user import User
    from sqlalchemy import select
    result = await db_session.execute(select(User).where(User.email == "u@test.com"))
    user = result.scalar_one()
    assert user.goal == "exam"
    assert user.daily_goal == 10


@pytest.mark.asyncio
async def test_set_goal_requires_both_fields(client, db_session):
    token = await _register(client)
    r = await client.patch("/users/me/goal",
                           json={"goal": "travel"},
                           headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422  # missing daily_goal


@pytest.mark.asyncio
async def test_set_goal_requires_auth(client):
    r = await client.patch("/users/me/goal", json={"goal": "exam", "daily_goal": 10})
    assert r.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_users.py -v
# Expected: FAIL — endpoint not yet implemented
```

- [ ] **Step 3: Create `app/schemas/user.py`**

```python
from pydantic import BaseModel
from typing import Literal


class GoalUpdateRequest(BaseModel):
    goal: Literal["travel", "exam", "work", "general"]
    daily_goal: Literal[5, 10, 20, 30]
```

- [ ] **Step 4: Create `app/routers/users.py`**

```python
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
```

- [ ] **Step 5: Register router in `app/main.py`**

Add to imports and registrations:

```python
from app.routers import auth, onboarding, questions, progress, users  # add users

app.include_router(users.router, prefix="/users", tags=["users"])
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_users.py -v
# Expected: 3 PASSED
```

- [ ] **Step 7: Commit**

```bash
git add app/schemas/user.py app/routers/users.py app/main.py tests/test_users.py
git commit -m "feat: PATCH /users/me/goal endpoint for onboarding goal + daily goal"
```

---

## Task 4: Practice Prompts Seed Data

**Files:**
- Create: `backend/scripts/seed_practice_prompts.py`

- [ ] **Step 1: Create `scripts/seed_practice_prompts.py`**

```python
"""
Seed practice_prompts table with scenario-based writing prompts.
Run once: python -m scripts.seed_practice_prompts
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models.practice import PracticePrompt

PROMPTS = [
    # past_perfect
    dict(topic="past_perfect", difficulty=2,
         scenario="You just returned from a trip. Tell Beary about something interesting that happened before you arrived at your destination.",
         hint='Try to use "had" in your answer'),
    dict(topic="past_perfect", difficulty=2,
         scenario="You missed an important event. Tell Beary what had already happened by the time you arrived.",
         hint='Use "had already" to describe something completed before another past event'),
    dict(topic="past_perfect", difficulty=3,
         scenario="Describe a time when you realized you had made a mistake. What had you done, and what happened next?",
         hint=None),
    # present_perfect
    dict(topic="present_perfect", difficulty=2,
         scenario="Tell Beary about something you have never done but would like to try.",
         hint='Use "have never" or "have always wanted to"'),
    dict(topic="present_perfect", difficulty=2,
         scenario="Describe your experience with learning a new skill. Have you ever struggled with something before getting better?",
         hint='Use "have + past participle" (e.g. have tried, have learned)'),
    # past_tense
    dict(topic="past_tense", difficulty=1,
         scenario="Describe what you did last weekend. Where did you go and who did you meet?",
         hint='Use past tense verbs: went, saw, ate, talked...'),
    dict(topic="past_tense", difficulty=1,
         scenario="Tell Beary about a memorable meal you had. What did you eat and where were you?",
         hint=None),
    # conditionals
    dict(topic="conditionals", difficulty=3,
         scenario="If you could live anywhere in the world, where would you choose and why?",
         hint='Use "would" and "if I could..." or "if I were..."'),
    dict(topic="conditionals", difficulty=2,
         scenario="What would you do if you found a large amount of money on the street?",
         hint='Use "I would..." to describe your choices'),
    # articles
    dict(topic="articles", difficulty=2,
         scenario="Describe your favourite place in your city to a friend visiting for the first time.",
         hint='Pay attention to when to use "a", "an", or "the"'),
    # prepositions
    dict(topic="prepositions", difficulty=2,
         scenario="Describe how to get from your home to the nearest supermarket.",
         hint='Use prepositions of place and movement: at, on, in, next to, turn left...'),
    # idioms
    dict(topic="idioms", difficulty=3,
         scenario="Tell Beary about a time when you felt completely overwhelmed. Try to use at least one idiom.",
         hint='Try phrases like "bite off more than you can chew" or "in over my head"'),
    # synonyms (vocabulary)
    dict(topic="synonyms", difficulty=2,
         scenario="Describe a beautiful place you have visited. Try to use varied and descriptive vocabulary instead of simple words like 'nice' or 'good'.",
         hint='Replace simple words with richer alternatives: stunning, breathtaking, serene...'),
    # phrasal_verbs
    dict(topic="phrasal_verbs", difficulty=2,
         scenario="Tell Beary about a problem you had to deal with recently. How did you handle it?",
         hint='Try phrasal verbs: deal with, figure out, give up, look into...'),
    # present_simple
    dict(topic="present_simple", difficulty=1,
         scenario="Describe your daily morning routine to Beary. What do you usually do?",
         hint='Use present simple for habits: wake up, have breakfast, go to...'),
]


async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        for p in PROMPTS:
            session.add(PracticePrompt(**p))
        await session.commit()

    print(f"Inserted {len(PROMPTS)} practice prompts.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the seed script**

```bash
cd backend
python -m scripts.seed_practice_prompts
# Expected: Inserted 15 practice prompts.
```

- [ ] **Step 3: Verify**

```bash
psql english_companion -c "SELECT topic, difficulty FROM practice_prompts ORDER BY topic;"
# Expected: 15 rows across various topics
```

- [ ] **Step 4: Commit**

```bash
git add scripts/seed_practice_prompts.py
git commit -m "feat: seed practice_prompts with 15 scenario-based writing prompts"
```

---

## Task 5: Practice Service (Prompt Selection + Qwen3:8b Validation)

**Files:**
- Create: `backend/app/services/practice_service.py`
- Create: `backend/app/schemas/practice.py`

- [ ] **Step 1: Create `app/schemas/practice.py`**

```python
import uuid
from pydantic import BaseModel, field_validator


class PracticePromptOut(BaseModel):
    id: uuid.UUID
    topic: str
    difficulty: int
    scenario: str
    hint: str | None


class PracticeSubmitRequest(BaseModel):
    prompt_id: uuid.UUID
    user_text: str


class HighlightItem(BaseModel):
    phrase: str
    suggestion: str
    reason: str


class PracticeFeedbackResponse(BaseModel):
    overall_encouragement: str
    highlights: list[HighlightItem]
    corrected_version: str
    beary_tip: str
```

- [ ] **Step 2: Create `app/services/practice_service.py`**

```python
import json
import uuid
from datetime import datetime
import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.practice import PracticePrompt, PracticeSession
from app.models.progress import UserStats


async def get_prompt_for_user(user_id: uuid.UUID, level: str, db: AsyncSession) -> PracticePrompt | None:
    """Select a practice prompt targeting the user's weakest topic."""
    # Get user's weak topics
    result = await db.execute(select(UserStats).where(UserStats.user_id == user_id))
    stats = result.scalar_one_or_none()

    difficulty_map = {"beginner": 1, "intermediate": 2, "advanced": 3}
    difficulty = difficulty_map.get(level, 2)

    if stats and stats.weak_topics:
        # Find weakest topic
        weakest_topic = min(stats.weak_topics, key=lambda t: stats.weak_topics[t])
        # Try to find a matching prompt
        r = await db.execute(
            select(PracticePrompt)
            .where(PracticePrompt.topic == weakest_topic)
            .order_by(func.random())
            .limit(1)
        )
        prompt = r.scalar_one_or_none()
        if prompt:
            return prompt

    # Fallback: random prompt at user's difficulty
    r = await db.execute(
        select(PracticePrompt)
        .where(PracticePrompt.difficulty == difficulty)
        .order_by(func.random())
        .limit(1)
    )
    return r.scalar_one_or_none()


def _build_validation_prompt(scenario: str, topic: str, user_text: str, level: str) -> str:
    return f"""The user is a {level} English learner practicing: {topic}.
Scenario they were given: "{scenario}"
Their response: "{user_text}"

Validate their grammar. Return JSON only (no markdown, no explanation):
{{
  "overall_encouragement": "warm positive 1-sentence comment",
  "highlights": [
    {{"phrase": "exact phrase from user text", "suggestion": "improved version", "reason": "brief explanation"}}
  ],
  "corrected_version": "full corrected version of their text",
  "beary_tip": "one key grammar rule to remember, friendly tone, max 2 sentences"
}}
Highlight maximum 2 issues. Focus on what can be better, not what is wrong.
Never use the words "wrong", "mistake", or "incorrect".
Be warm, encouraging, and supportive."""


async def validate_writing(
    prompt: PracticePrompt,
    user_text: str,
    level: str,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """Call Qwen3:8b, parse feedback JSON, save session, update weak_topics."""
    validation_prompt = _build_validation_prompt(prompt.scenario, prompt.topic, user_text, level)
    payload = {"model": "qwen3:8b", "prompt": validation_prompt, "stream": False}
    timeout = httpx.Timeout(10.0, connect=5.0)

    raw_text = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
                r.raise_for_status()
                raw_text = r.json().get("response", "")
                break
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError):
            if attempt == 1:
                raise

    if not raw_text:
        raise ValueError("Empty response from Ollama")

    # Strip markdown fences if present
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    feedback = json.loads(cleaned.strip())

    # Validate required keys
    required = {"overall_encouragement", "highlights", "corrected_version", "beary_tip"}
    if not required.issubset(feedback.keys()):
        raise ValueError("Incomplete feedback JSON from Ollama")

    # Save practice session
    db.add(PracticeSession(
        user_id=user_id,
        prompt_id=prompt.id,
        user_text=user_text,
        feedback_json=feedback,
    ))

    # Update weak_topics: +0.1 boost unconditionally (engagement = progress)
    result = await db.execute(select(UserStats).where(UserStats.user_id == user_id).with_for_update())
    stats = result.scalar_one_or_none()
    if stats:
        weak = dict(stats.weak_topics or {})
        strong = dict(stats.strong_topics or {})
        topic = prompt.topic
        current = weak.get(topic, strong.get(topic, 0.5))
        updated = round(min(current + 0.1, 1.0), 3)
        if updated < 0.6:
            weak[topic] = updated
            strong.pop(topic, None)
        else:
            strong[topic] = updated
            weak.pop(topic, None)
        stats.weak_topics = weak
        stats.strong_topics = strong

    await db.commit()
    return feedback
```

- [ ] **Step 3: Commit**

```bash
git add app/schemas/practice.py app/services/practice_service.py
git commit -m "feat: practice service — prompt selection and Qwen3:8b writing validation"
```

---

## Task 6: Practice Router + Tests

**Files:**
- Create: `backend/app/routers/practice.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_practice.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_practice.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.models.practice import PracticePrompt
from app.models.progress import UserStats


async def _setup(client, db_session):
    r = await client.post("/auth/register", json={"email": "p@test.com", "password": "pass123"})
    token = r.json()["access_token"]
    from app.models.user import User
    from sqlalchemy import select
    result = await db_session.execute(select(User).where(User.email == "p@test.com"))
    user = result.scalar_one()
    user.onboarding_complete = True
    db_session.add(UserStats(user_id=user.id))
    db_session.add(PracticePrompt(
        topic="past_tense", difficulty=1,
        scenario="Describe what you did yesterday.",
        hint="Use past tense verbs"
    ))
    await db_session.commit()
    return token


@pytest.mark.asyncio
async def test_get_prompt_requires_auth(client):
    r = await client.get("/practice/prompt")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_prompt_returns_prompt(client, db_session):
    token = await _setup(client, db_session)
    r = await client.get("/practice/prompt", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "scenario" in data
    assert "id" in data


@pytest.mark.asyncio
async def test_submit_too_short_returns_400(client, db_session):
    token = await _setup(client, db_session)
    r_prompt = await client.get("/practice/prompt", headers={"Authorization": f"Bearer {token}"})
    prompt_id = r_prompt.json()["id"]

    r = await client.post("/practice/submit",
                          json={"prompt_id": prompt_id, "user_text": "Short"},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
    assert "Beary" in r.json()["detail"]


@pytest.mark.asyncio
async def test_submit_returns_feedback(client, db_session):
    token = await _setup(client, db_session)
    r_prompt = await client.get("/practice/prompt", headers={"Authorization": f"Bearer {token}"})
    prompt_id = r_prompt.json()["id"]

    mock_feedback = {
        "overall_encouragement": "Great effort!",
        "highlights": [],
        "corrected_version": "Yesterday I went to the market and bought vegetables.",
        "beary_tip": "Use simple past tense for completed actions.",
    }

    with patch("app.services.practice_service.validate_writing", new_callable=AsyncMock) as mock_validate:
        mock_validate.return_value = mock_feedback
        r = await client.post(
            "/practice/submit",
            json={"prompt_id": prompt_id, "user_text": "Yesterday I go to the market and buy vegetables."},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["overall_encouragement"] == "Great effort!"
    assert "corrected_version" in data
    assert "beary_tip" in data
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_practice.py -v
# Expected: FAIL — router not implemented
```

- [ ] **Step 3: Create `app/routers/practice.py`**

```python
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
    # Validate minimum text length (400 per spec, not 422)
    if len(body.user_text.strip()) < 20:
        raise HTTPException(400, detail="Please write a bit more for Beary to help you!")

    # Verify prompt exists
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
```

- [ ] **Step 4: Register practice router in `app/main.py`**

```python
from app.routers import auth, onboarding, questions, progress, users, practice  # add practice

app.include_router(practice.router, prefix="/practice", tags=["practice"])
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_practice.py -v
# Expected: 4 PASSED
```

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v
# Expected: all tests PASS
```

- [ ] **Step 7: Commit**

```bash
git add app/routers/practice.py app/main.py tests/test_practice.py
git commit -m "feat: practice tab API — prompt selection and writing validation endpoints"
```

---

## Task 7: Integration Smoke Test

- [ ] **Step 1: Start server and test new endpoints manually**

```bash
uvicorn app.main:app --reload

# Register + login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"smoke@test.com","password":"pass123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Set goal
curl -s -X PATCH http://localhost:8000/users/me/goal \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"goal": "exam", "daily_goal": 10}'
# Expected: {"success": true}

# Get practice prompt
curl -s http://localhost:8000/practice/prompt \
  -H "Authorization: Bearer $TOKEN"
# Expected: JSON with scenario, hint, topic

# Answer a question and check extended response
curl -s -X POST "http://localhost:8000/questions/<QID>/answer" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"chosen_index": 0}'
# Expected: JSON includes xp_earned, daily_xp, daily_answered_count, daily_goal, daily_goal_complete
```

- [ ] **Step 2: Final commit**

```bash
git add .
git commit -m "chore: backend plan 2A complete — gamification fields, practice API, goal endpoint"
```
