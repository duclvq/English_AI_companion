import pytest


@pytest.mark.asyncio
async def test_register_returns_access_token(client):
    r = await client.post("/auth/register", json={"email": "a@b.com", "password": "pass123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_400(client):
    await client.post("/auth/register", json={"email": "a@b.com", "password": "pass123"})
    r = await client.post("/auth/register", json={"email": "a@b.com", "password": "pass123"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_login_returns_access_token(client):
    await client.post("/auth/register", json={"email": "a@b.com", "password": "pass123"})
    r = await client.post("/auth/login", json={"email": "a@b.com", "password": "pass123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    await client.post("/auth/register", json={"email": "a@b.com", "password": "pass123"})
    r = await client.post("/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert r.status_code == 401
