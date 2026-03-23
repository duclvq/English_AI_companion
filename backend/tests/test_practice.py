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
    assert r.status_code in (401, 403)


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
        "corrected_version": "Yesterday I went to the market.",
        "beary_tip": "Use simple past tense for completed actions.",
    }
    with patch("app.services.practice_service.validate_writing", new_callable=AsyncMock) as mock_validate:
        mock_validate.return_value = mock_feedback
        r = await client.post("/practice/submit",
                              json={"prompt_id": prompt_id, "user_text": "Yesterday I go to the market and buy vegetables."},
                              headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["overall_encouragement"] == "Great effort!"
    assert "corrected_version" in data
    assert "beary_tip" in data
