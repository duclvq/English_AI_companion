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
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_set_goal_requires_auth(client):
    r = await client.patch("/users/me/goal", json={"goal": "exam", "daily_goal": 10})
    assert r.status_code in (401, 403)
