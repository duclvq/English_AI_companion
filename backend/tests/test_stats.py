import pytest
from app.models.question import Question
from app.models.progress import UserStats


async def _setup(client, db_session):
    r = await client.post("/auth/register", json={"email": "a@b.com", "password": "pass123"})
    token = r.json()["access_token"]
    from app.models.user import User
    from sqlalchemy import select

    result = await db_session.execute(select(User).where(User.email == "a@b.com"))
    user = result.scalar_one()
    user.onboarding_complete = True
    db_session.add(UserStats(user_id=user.id))
    await db_session.commit()
    return token, user


@pytest.mark.asyncio
async def test_stats_endpoint_returns_defaults(client, db_session):
    token, _ = await _setup(client, db_session)
    r = await client.get("/progress/stats", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["total_answered"] == 0
    assert data["streak"] == 0


@pytest.mark.asyncio
async def test_stats_update_after_answer(client, db_session):
    token, _ = await _setup(client, db_session)
    q = Question(
        type="grammar", difficulty=2, topic="past_tense",
        question_text="Q1", choices=["a", "b", "c", "d", "e"],
        correct_index=0,
    )
    db_session.add(q)
    await db_session.commit()

    await client.post(
        f"/questions/{q.id}/answer",
        json={"chosen_index": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = await client.get("/progress/stats", headers={"Authorization": f"Bearer {token}"})
    data = r.json()
    assert data["total_answered"] == 1
    assert data["correct_count"] == 1
    assert data["streak"] == 1
