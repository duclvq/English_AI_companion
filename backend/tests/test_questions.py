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
async def test_get_next_question_requires_auth(client):
    r = await client.get("/questions/next")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_next_question_returns_question(client, db_session):
    token, _ = await _setup(client, db_session)
    db_session.add(
        Question(
            type="vocabulary", difficulty=1, topic="synonyms",
            question_text="Q1", choices=["a", "b", "c", "d", "e"],
            correct_index=1,
        )
    )
    await db_session.commit()
    r = await client.get("/questions/next", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "question_text" in data
    assert "choices" in data
    assert len(data["choices"]) == 5


@pytest.mark.asyncio
async def test_answer_correct_increments_streak(client, db_session):
    token, user = await _setup(client, db_session)
    q = Question(
        type="vocabulary", difficulty=2, topic="synonyms",
        question_text="Q1", choices=["a", "b", "c", "d", "e"],
        correct_index=1,
    )
    db_session.add(q)
    await db_session.commit()

    r = await client.post(
        f"/questions/{q.id}/answer",
        json={"chosen_index": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["is_correct"] is True
    assert data["streak"] == 1


@pytest.mark.asyncio
async def test_answer_wrong_resets_streak(client, db_session):
    token, user = await _setup(client, db_session)
    q = Question(
        type="vocabulary", difficulty=2, topic="synonyms",
        question_text="Q1", choices=["a", "b", "c", "d", "e"],
        correct_index=1,
    )
    db_session.add(q)
    await db_session.commit()

    r = await client.post(
        f"/questions/{q.id}/answer",
        json={"chosen_index": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["is_correct"] is False
    assert data["streak"] == 0
