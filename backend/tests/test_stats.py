import pytest
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
    for i in range(3):
        q = Question(type="vocabulary", difficulty=2, topic="synonyms",
                     question_text=f"Q{i}", choices=["a","b","c","d","e"], correct_index=0)
        db_session.add(q)
    await db_session.commit()
    from sqlalchemy import select
    qs = (await db_session.execute(select(Question))).scalars().all()
    for q in qs:
        await client.post(f"/questions/{q.id}/answer",
                          json={"chosen_index": 0},
                          headers={"Authorization": f"Bearer {token}"})
    # Answer wrong — streak must NOT reset
    q_wrong = Question(type="vocabulary", difficulty=2, topic="synonyms",
                       question_text="Qwrong", choices=["a","b","c","d","e"], correct_index=0)
    db_session.add(q_wrong)
    await db_session.commit()
    r = await client.post(f"/questions/{q_wrong.id}/answer",
                          json={"chosen_index": 1},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.json()["streak"] == 3


@pytest.mark.asyncio
async def test_wrong_answer_increments_daily_answered_not_correct(client, db_session):
    token, user = await _setup_user_with_stats(client, db_session)
    q = Question(type="vocabulary", difficulty=2, topic="synonyms",
                 question_text="Q", choices=["a","b","c","d","e"], correct_index=0)
    db_session.add(q)
    await db_session.commit()
    r = await client.post(f"/questions/{q.id}/answer",
                          json={"chosen_index": 1},
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
