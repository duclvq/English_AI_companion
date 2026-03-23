import pytest


async def _register_and_get_token(client):
    r = await client.post("/auth/register", json={"email": "a@b.com", "password": "pass123"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_get_onboarding_questions_requires_auth(client):
    r = await client.get("/onboarding/questions")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_onboarding_questions_returns_5(client, db_session):
    from app.models.question import Question

    # Seed questions at different difficulties to match onboarding distribution
    for i in range(2):
        db_session.add(
            Question(
                type="vocabulary", difficulty=1, topic="test",
                question_text=f"Q_beg{i}", choices=["a", "b", "c", "d", "e"],
                correct_index=0,
            )
        )
    for i in range(2):
        db_session.add(
            Question(
                type="vocabulary", difficulty=2, topic="test",
                question_text=f"Q_int{i}", choices=["a", "b", "c", "d", "e"],
                correct_index=0,
            )
        )
    db_session.add(
        Question(
            type="vocabulary", difficulty=3, topic="test",
            question_text="Q_adv0", choices=["a", "b", "c", "d", "e"],
            correct_index=0,
        )
    )
    await db_session.commit()

    token = await _register_and_get_token(client)
    r = await client.get(
        "/onboarding/questions", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert len(r.json()) == 5


@pytest.mark.asyncio
async def test_submit_onboarding_sets_level(client, db_session):
    from app.models.question import Question

    questions = []
    for i in range(5):
        q = Question(
            type="vocabulary", difficulty=1, topic="test",
            question_text=f"Q{i}", choices=["a", "b", "c", "d", "e"],
            correct_index=0,
        )
        db_session.add(q)
        questions.append(q)
    await db_session.commit()

    token = await _register_and_get_token(client)
    answers = [{"question_id": str(q.id), "chosen_index": 0} for q in questions]
    r = await client.post(
        "/onboarding/submit",
        json={"answers": answers},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["level"] == "advanced"
