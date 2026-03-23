# Backend + Seed Questions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend with PostgreSQL, JWT auth, question API, and a script that uses a cloud AI to generate 100 seed questions.

**Architecture:** Single FastAPI application with clear module boundaries: routers handle HTTP, services contain business logic, models define DB schema via SQLAlchemy + Alembic. A standalone Python script calls a cloud AI (Claude or GPT-4o) to generate the seed question dataset and inserts it directly into the DB.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x (async), Alembic, PostgreSQL 15+, python-jose (JWT), passlib (bcrypt), httpx (async HTTP for Ollama/cloud AI), pytest + pytest-asyncio

---

## File Structure

```
backend/
  app/
    main.py                    # FastAPI app factory, router registration, CORS
    config.py                  # Settings from env vars (pydantic-settings)
    database.py                # Async SQLAlchemy engine + session factory
    models/
      __init__.py
      user.py                  # User, RefreshToken ORM models
      question.py              # Question ORM model
      progress.py              # UserProgress, UserStats, AgentSession ORM models
    routers/
      __init__.py
      auth.py                  # /auth/* endpoints
      onboarding.py            # /onboarding/* endpoints
      questions.py             # /questions/* endpoints
      progress.py              # /progress/* endpoints
    services/
      __init__.py
      auth_service.py          # register, login, refresh, logout logic
      question_router.py       # next-question selection logic
      stats_service.py         # user_stats update, streak logic
      ollama_client.py         # SSE proxy to Ollama /api/generate
    schemas/
      __init__.py
      auth.py                  # Pydantic request/response models for auth
      question.py              # Pydantic models for questions
      progress.py              # Pydantic models for progress
  scripts/
    generate_seed_questions.py # One-shot: call cloud AI, insert 100 questions to DB
  tests/
    conftest.py                # Async test client, DB fixtures, test user factory
    test_auth.py               # Auth endpoint tests
    test_onboarding.py         # Onboarding quiz tests
    test_questions.py          # Question router + answer submission tests
    test_stats.py              # Streak, stats update tests
  alembic/
    env.py
    versions/                  # Migration files (generated)
  alembic.ini
  requirements.txt
  .env.example
```

---

## Task 1: Project Scaffold + Dependencies

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Create `requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.35
asyncpg==0.29.0
alembic==1.13.2
pydantic-settings==2.4.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
httpx==0.27.2
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 2: Create `.env.example`**

```
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/english_companion
SECRET_KEY=change-me-to-a-random-32-char-string
CLOUD_AI_PROVIDER=claude
CLAUDE_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OLLAMA_BASE_URL=http://localhost:11434
```

- [ ] **Step 3: Create `app/config.py`**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cloud_ai_provider: str = "claude"
    claude_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 4: Create `app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, onboarding, questions, progress

app = FastAPI(title="English AI Companion")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
app.include_router(questions.router, prefix="/questions", tags=["questions"])
app.include_router(progress.router, prefix="/progress", tags=["progress"])

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Start PostgreSQL and create the database**

```bash
# Using psql:
createdb english_companion
# Or with Docker:
docker run -d --name pg -e POSTGRES_PASSWORD=password -e POSTGRES_DB=english_companion -p 5432:5432 postgres:15
```

- [ ] **Step 6: Commit**

```bash
cd backend
git init
git add .
git commit -m "feat: scaffold FastAPI project with config and router registration"
```

---

## Task 2: Database Models

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/question.py`
- Create: `backend/app/models/progress.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`

- [ ] **Step 1: Create `app/database.py`**

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 2: Create `app/models/user.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str] = mapped_column(String(20), default="beginner")  # beginner/intermediate/advanced
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 3: Create `app/models/question.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(20), nullable=False)       # vocabulary/grammar
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)    # 1/2/3
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    question_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    choices: Mapped[list] = mapped_column(JSON, nullable=False)         # list of 5 strings
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False) # 0-4
    explanation_hint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_by: Mapped[str] = mapped_column(String(20), default="seed")  # seed/agent
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: Create `app/models/progress.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import Integer, Boolean, DateTime, JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class UserProgress(Base):
    __tablename__ = "user_progress"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    chosen_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_spent_ms: Mapped[int] = mapped_column(Integer, default=0)

class UserStats(Base):
    __tablename__ = "user_stats"

    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    total_answered: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    weak_topics: Mapped[dict] = mapped_column(JSON, default=dict)
    strong_topics: Mapped[dict] = mapped_column(JSON, default=dict)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    agent_last_trigger_count: Mapped[int] = mapped_column(Integer, default=0)

class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reasoning_log: Mapped[dict] = mapped_column(JSON, default=dict)
    questions_generated: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 5: Init Alembic**

```bash
cd backend
pip install -r requirements.txt
alembic init alembic
```

- [ ] **Step 6: Edit `alembic/env.py` — add async support (do this BEFORE running any alembic revision)**

Replace the `run_migrations_online` function with:

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.database import Base
from app.models import user, question, progress  # import all models
from app.config import settings

target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 7: Generate and apply the migration**

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

- [ ] **Step 8: Verify tables were created**

```bash
psql english_companion -c "\dt"
# Expected: users, refresh_tokens, questions, user_progress, user_stats, agent_sessions
```

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "feat: add SQLAlchemy models and Alembic initial migration"
```

---

## Task 3: Auth Service + Endpoints

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/auth_service.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing tests for auth**

Create `tests/conftest.py`:

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app
from app.database import Base, get_db

TEST_DB_URL = "postgresql+asyncpg://postgres:password@localhost:5432/english_companion_test"

@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

Create `tests/test_auth.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
createdb english_companion_test
pytest tests/test_auth.py -v
# Expected: ERRORS — routers/auth.py not implemented yet
```

- [ ] **Step 3: Create `app/schemas/auth.py`**

```python
from pydantic import BaseModel, EmailStr
import uuid

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str | None = None  # None = web (cookie)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    level: str
    onboarding_complete: bool
```

- [ ] **Step 4: Create `app/services/auth_service.py`**

```python
import secrets
import uuid
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.user import User, RefreshToken

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.secret_key, algorithm=settings.algorithm)

async def create_refresh_token(user_id: uuid.UUID, db: AsyncSession) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    db.add(RefreshToken(user_id=user_id, token=token, expires_at=expires))
    await db.commit()
    return token

async def register_user(email: str, password: str, db: AsyncSession) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("Email already registered")
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def authenticate_user(email: str, password: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")
    return user

async def get_current_user(token: str, db: AsyncSession) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = uuid.UUID(payload["sub"])
    except Exception:
        raise ValueError("Invalid token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")
    return user
```

- [ ] **Step 5: Create `app/routers/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse, UserOut
from app.services import auth_service
from app.models.user import RefreshToken
from sqlalchemy import select

router = APIRouter()

def _auth_response(access_token: str, refresh_token: str, response: Response) -> dict:
    response.set_cookie("refresh_token", refresh_token, httponly=True, secure=False, samesite="lax", max_age=7*86400)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register")
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.register_user(body.email, body.password, db)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    access_token = auth_service.create_access_token(user.id)
    refresh_token = await auth_service.create_refresh_token(user.id, db)
    return _auth_response(access_token, refresh_token, response)

@router.post("/login")
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.authenticate_user(body.email, body.password, db)
    except ValueError:
        raise HTTPException(401, detail="Invalid credentials")
    access_token = auth_service.create_access_token(user.id)
    refresh_token = await auth_service.create_refresh_token(user.id, db)
    return _auth_response(access_token, refresh_token, response)

@router.post("/refresh")
async def refresh(request: Request, body: RefreshRequest = RefreshRequest(), db: AsyncSession = Depends(get_db)):
    token_str = body.refresh_token or request.cookies.get("refresh_token")
    if not token_str:
        raise HTTPException(401, detail="No refresh token")
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == token_str, RefreshToken.revoked == False))
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(401, detail="Invalid or expired refresh token")
    return {"access_token": auth_service.create_access_token(rt.user_id)}

@router.post("/logout")
async def logout(request: Request, body: RefreshRequest = RefreshRequest(), response: Response, db: AsyncSession = Depends(get_db)):
    token_str = body.refresh_token or request.cookies.get("refresh_token")
    if token_str:
        result = await db.execute(select(RefreshToken).where(RefreshToken.token == token_str))
        rt = result.scalar_one_or_none()
        if rt:
            rt.revoked = True
            await db.commit()
    response.delete_cookie("refresh_token")
    return {"success": True}
```

- [ ] **Step 6: Create empty router stubs so the app starts**

Create `app/routers/onboarding.py`, `app/routers/questions.py`, `app/routers/progress.py` each with:

```python
from fastapi import APIRouter
router = APIRouter()
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_auth.py -v
# Expected: 4 PASSED
```

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "feat: auth service with register, login, refresh, logout"
```

---

## Task 4: Onboarding Endpoints

**Files:**
- Create: `backend/app/schemas/question.py`
- Create: `backend/app/routers/onboarding.py`
- Create: `backend/tests/test_onboarding.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_onboarding.py`:

```python
import pytest

async def _register_and_get_token(client):
    r = await client.post("/auth/register", json={"email": "a@b.com", "password": "pass123"})
    return r.json()["access_token"]

@pytest.mark.asyncio
async def test_get_onboarding_questions_requires_auth(client):
    r = await client.get("/onboarding/questions")
    assert r.status_code == 401

@pytest.mark.asyncio
async def test_get_onboarding_questions_returns_5(client, db_session):
    # Seed 5 questions in DB first
    from app.models.question import Question
    for i in range(5):
        db_session.add(Question(
            type="vocabulary", difficulty=1, topic="test",
            question_text=f"Q{i}", choices=["a","b","c","d","e"], correct_index=0
        ))
    await db_session.commit()

    token = await _register_and_get_token(client)
    r = await client.get("/onboarding/questions", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) == 5

@pytest.mark.asyncio
async def test_submit_onboarding_sets_level(client, db_session):
    from app.models.question import Question
    questions = []
    for i in range(5):
        q = Question(type="vocabulary", difficulty=1, topic="test",
                     question_text=f"Q{i}", choices=["a","b","c","d","e"], correct_index=0)
        db_session.add(q)
        questions.append(q)
    await db_session.commit()

    token = await _register_and_get_token(client)
    # Answer all 5 correctly → advanced level
    answers = [{"question_id": str(q.id), "chosen_index": 0} for q in questions]
    r = await client.post("/onboarding/submit",
                          json={"answers": answers},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["level"] == "advanced"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_onboarding.py -v
# Expected: FAIL — endpoints not implemented
```

- [ ] **Step 3: Create `app/schemas/question.py`**

```python
import uuid
from pydantic import BaseModel

class QuestionOut(BaseModel):
    id: uuid.UUID
    type: str
    difficulty: int
    topic: str
    question_text: str
    choices: list[str]

class OnboardingAnswer(BaseModel):
    question_id: uuid.UUID
    chosen_index: int

class OnboardingSubmit(BaseModel):
    answers: list[OnboardingAnswer]
```

- [ ] **Step 4: Create `app/routers/onboarding.py`**

```python
import uuid
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

async def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: AsyncSession = Depends(get_db)) -> User:
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
async def get_onboarding_questions(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    # 2 beginner, 2 intermediate, 1 advanced
    results = []
    for difficulty, count in [(1, 2), (2, 2), (3, 1)]:
        r = await db.execute(
            select(Question).where(Question.difficulty == difficulty)
            .order_by(func.random()).limit(count)
        )
        results.extend(r.scalars().all())
    return results

@router.post("/submit")
async def submit_onboarding(body: OnboardingSubmit, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    question_ids = [a.question_id for a in body.answers]
    r = await db.execute(select(Question).where(Question.id.in_(question_ids)))
    questions = {q.id: q for q in r.scalars().all()}

    correct = sum(1 for a in body.answers if questions.get(a.question_id) and questions[a.question_id].correct_index == a.chosen_index)
    level = _score_to_level(correct)

    user.level = level
    user.onboarding_complete = True

    # Init user_stats
    stats = UserStats(user_id=user.id)
    db.add(stats)
    await db.commit()

    return {"level": level}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_onboarding.py -v
# Expected: 3 PASSED
```

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat: onboarding quiz endpoints with level scoring"
```

---

## Task 5: Question Router + Answer Submission

**Files:**
- Create: `backend/app/services/question_router.py`
- Create: `backend/app/services/stats_service.py`
- Modify: `backend/app/routers/questions.py`
- Create: `backend/tests/test_questions.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_questions.py`:

```python
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
    assert r.status_code == 401

@pytest.mark.asyncio
async def test_get_next_question_returns_question(client, db_session):
    token, _ = await _setup(client, db_session)
    db_session.add(Question(type="vocabulary", difficulty=2, topic="synonyms",
                            question_text="Q1", choices=["a","b","c","d","e"], correct_index=1))
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
    q = Question(type="vocabulary", difficulty=2, topic="synonyms",
                 question_text="Q1", choices=["a","b","c","d","e"], correct_index=1)
    db_session.add(q)
    await db_session.commit()

    r = await client.post(f"/questions/{q.id}/answer",
                          json={"chosen_index": 1},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["is_correct"] is True
    assert data["streak"] == 1

@pytest.mark.asyncio
async def test_answer_wrong_resets_streak(client, db_session):
    token, user = await _setup(client, db_session)
    q = Question(type="vocabulary", difficulty=2, topic="synonyms",
                 question_text="Q1", choices=["a","b","c","d","e"], correct_index=1)
    db_session.add(q)
    await db_session.commit()

    r = await client.post(f"/questions/{q.id}/answer",
                          json={"chosen_index": 0},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["is_correct"] is False
    assert data["streak"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_questions.py -v
# Expected: FAIL
```

- [ ] **Step 3: Create `app/services/stats_service.py`**

```python
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.progress import UserStats, UserProgress
from app.models.question import Question
import uuid

async def record_answer(user_id: uuid.UUID, question: Question, chosen_index: int, time_spent_ms: int, db: AsyncSession) -> UserStats:
    is_correct = chosen_index == question.correct_index

    # Insert progress record
    db.add(UserProgress(
        user_id=user_id,
        question_id=question.id,
        chosen_index=chosen_index,
        is_correct=is_correct,
        time_spent_ms=time_spent_ms,
    ))

    # Update stats with SELECT FOR UPDATE to prevent race conditions
    result = await db.execute(select(UserStats).where(UserStats.user_id == user_id).with_for_update())
    stats = result.scalar_one()

    # Check 24h inactivity streak reset
    if stats.last_active_at and datetime.utcnow() - stats.last_active_at > timedelta(hours=24):
        stats.current_streak = 0

    stats.total_answered += 1
    if is_correct:
        stats.correct_count += 1
        stats.current_streak += 1
    else:
        stats.current_streak = 0

    # Update topic accuracy
    topic = question.topic
    weak = dict(stats.weak_topics or {})
    strong = dict(stats.strong_topics or {})

    # Simple rolling accuracy per topic (approximate)
    prev = weak.get(topic, strong.get(topic, 0.5))
    updated = prev * 0.8 + (1.0 if is_correct else 0.0) * 0.2
    if updated < 0.6:
        weak[topic] = round(updated, 3)
        strong.pop(topic, None)
    else:
        strong[topic] = round(updated, 3)
        weak.pop(topic, None)
    stats.weak_topics = weak
    stats.strong_topics = strong
    stats.last_active_at = datetime.utcnow()

    await db.commit()
    await db.refresh(stats)
    return stats
```

- [ ] **Step 4: Create `app/services/question_router.py`**

```python
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, and_, not_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.question import Question
from app.models.progress import UserProgress
from app.models.user import User

async def get_next_question(user: User, db: AsyncSession) -> Question | None:
    # IDs the user answered correctly in last 30 days (suppress)
    cutoff_correct = datetime.utcnow() - timedelta(days=30)
    suppress_result = await db.execute(
        select(UserProgress.question_id).where(
            and_(
                UserProgress.user_id == user.id,
                UserProgress.is_correct == True,
                UserProgress.answered_at >= cutoff_correct,
            )
        )
    )
    suppress_ids = [r[0] for r in suppress_result.all()]

    # IDs answered incorrectly within last 7 days (also suppress, will re-appear after)
    cutoff_wrong = datetime.utcnow() - timedelta(days=7)
    wrong_result = await db.execute(
        select(UserProgress.question_id).where(
            and_(
                UserProgress.user_id == user.id,
                UserProgress.is_correct == False,
                UserProgress.answered_at >= cutoff_wrong,
            )
        )
    )
    suppress_ids += [r[0] for r in wrong_result.all()]

    difficulty_map = {"beginner": 1, "intermediate": 2, "advanced": 3}
    difficulty = difficulty_map.get(user.level, 2)

    # 1. Try agent-generated questions first, matching user difficulty
    result = await db.execute(
        select(Question).where(
            and_(
                Question.generated_by == "agent",
                Question.difficulty == difficulty,
                not_(Question.id.in_(suppress_ids)) if suppress_ids else True,
            )
        ).order_by(Question.created_at).limit(1)
    )
    q = result.scalar_one_or_none()
    if q:
        return q

    # 2. Fall back to seed questions matching user level
    result = await db.execute(
        select(Question).where(
            and_(
                Question.generated_by == "seed",
                Question.difficulty == difficulty,
                not_(Question.id.in_(suppress_ids)) if suppress_ids else True,
            )
        ).order_by(Question.created_at).limit(1)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 5: Implement `app/routers/questions.py`**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.models.question import Question
from app.models.progress import UserProgress
from app.schemas.question import QuestionOut
from app.services.auth_service import get_current_user
from app.services import question_router as qr, stats_service
from pydantic import BaseModel

router = APIRouter()
bearer = HTTPBearer()

async def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: AsyncSession = Depends(get_db)) -> User:
    try:
        return await get_current_user(creds.credentials, db)
    except ValueError:
        raise HTTPException(401, "Invalid token")

class AnswerRequest(BaseModel):
    chosen_index: int
    time_spent_ms: int = 0

@router.get("/next", response_model=QuestionOut)
async def next_question(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if not user.onboarding_complete:
        raise HTTPException(403, "Complete onboarding first")
    q = await qr.get_next_question(user, db)
    if not q:
        raise HTTPException(404, "No questions available")
    return q

@router.post("/{question_id}/answer")
async def answer_question(question_id: uuid.UUID, body: AnswerRequest, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Question).where(Question.id == question_id))
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")
    if body.chosen_index not in range(5):
        raise HTTPException(400, "chosen_index must be 0-4")
    stats = await stats_service.record_answer(user.id, q, body.chosen_index, body.time_spent_ms, db)
    return {"is_correct": body.chosen_index == q.correct_index, "correct_index": q.correct_index, "streak": stats.current_streak}

@router.get("/{question_id}/explain")
async def explain_question(question_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    # Guard: only allow if user's last attempt was wrong
    result = await db.execute(
        select(UserProgress).where(
            UserProgress.user_id == user.id,
            UserProgress.question_id == question_id,
        ).order_by(UserProgress.answered_at.desc()).limit(1)
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
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_questions.py -v
# Expected: 4 PASSED
```

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "feat: question router, answer submission, streak tracking"
```

---

## Task 6: Ollama Client (SSE Explanation Streaming)

**Files:**
- Create: `backend/app/services/ollama_client.py`

- [ ] **Step 1: Create `app/services/ollama_client.py`**

```python
import json
import asyncio
import httpx
from app.models.question import Question
from app.config import settings

def _build_prompt(q: Question, chosen_index: int, level: str) -> str:
    correct = q.choices[q.correct_index]
    chosen = q.choices[chosen_index]
    detail = {
        "beginner": "Explain the full grammar/vocabulary rule, give an example sentence, and add a memory tip.",
        "intermediate": "Explain the rule briefly and give one example sentence.",
        "advanced": "Give a concise reason only, no examples needed.",
    }.get(level, "Explain briefly.")
    return (
        f"User level: {level}.\n"
        f"Question: {q.question_text}\n"
        f"Correct answer: {correct}. User chose: {chosen}.\n"
        f"Explain why '{correct}' is correct and why '{chosen}' is wrong. {detail} Be friendly and clear."
    )

async def stream_explanation(q: Question, chosen_index: int, level: str):
    prompt = _build_prompt(q, chosen_index, level)
    payload = {"model": "qwen3:8b", "prompt": prompt, "stream": True}
    timeout = httpx.Timeout(10.0, connect=5.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{settings.ollama_base_url}/api/generate", json=payload) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield f"data: {json.dumps({'token': token})}\n\n"
                        if data.get("done"):
                            yield "data: [DONE]\n\n"
                            return
                    except json.JSONDecodeError:
                        continue
    except (httpx.TimeoutException, httpx.ConnectError):
        yield f"data: {json.dumps({'error': 'Explanation unavailable, try again.'})}\n\n"
```

- [ ] **Step 2: Manual test with curl (requires Ollama running with qwen3:8b)**

```bash
# Start the server
cd backend && uvicorn app.main:app --reload

# Register and login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@test.com","password":"test123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Get onboarding questions (need seed data first — see Task 7)
curl -s http://localhost:8000/onboarding/questions -H "Authorization: Bearer $TOKEN"
```

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "feat: Ollama SSE streaming client for explanations"
```

---

## Task 7: Progress Endpoint

**Files:**
- Modify: `backend/app/routers/progress.py`
- Create: `backend/app/schemas/progress.py`

- [ ] **Step 1: Create `app/schemas/progress.py`**

```python
from pydantic import BaseModel

class StatsOut(BaseModel):
    total_answered: int
    correct_count: int
    streak: int
    weak_topics: dict
    strong_topics: dict
```

- [ ] **Step 2: Implement `app/routers/progress.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.models.progress import UserStats
from app.schemas.progress import StatsOut
from app.services.auth_service import get_current_user

router = APIRouter()
bearer = HTTPBearer()

async def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: AsyncSession = Depends(get_db)) -> User:
    try:
        return await get_current_user(creds.credentials, db)
    except ValueError:
        raise HTTPException(401, "Invalid token")

@router.get("/stats", response_model=StatsOut)
async def get_stats(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserStats).where(UserStats.user_id == user.id))
    stats = result.scalar_one_or_none()
    if not stats:
        return StatsOut(total_answered=0, correct_count=0, streak=0, weak_topics={}, strong_topics={})
    return StatsOut(
        total_answered=stats.total_answered,
        correct_count=stats.correct_count,
        streak=stats.current_streak,
        weak_topics=stats.weak_topics or {},
        strong_topics=stats.strong_topics or {},
    )
```

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "feat: progress stats endpoint"
```

---

## Task 8: Seed Question Generation Script

**Files:**
- Create: `backend/scripts/generate_seed_questions.py`

This script calls the cloud AI once and inserts 100 questions into the DB. Run it once after the DB is set up.

- [ ] **Step 1: Create `scripts/generate_seed_questions.py`**

```python
"""
Generate 100 seed questions using Claude API and insert into DB.
Run once: python -m scripts.generate_seed_questions

Requires: CLAUDE_API_KEY or OPENAI_API_KEY in .env
          DB must be migrated: alembic upgrade head
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models.question import Question
from app.database import Base

# Distribution: 20 beginner, 60 intermediate, 20 advanced
BATCHES = [
    {"difficulty": 1, "label": "beginner", "count": 20},
    {"difficulty": 2, "label": "intermediate", "count": 60},
    {"difficulty": 3, "label": "advanced", "count": 20},
]

PROMPT_TEMPLATE = """Generate {count} English learning questions for {label} level learners.
Mix vocabulary and grammar questions equally (about 50% each).

Rules:
- Each question has exactly 5 answer choices
- correct_index is 0-4 (index of the correct choice in the choices array)
- topic is a short tag like: synonyms, antonyms, fill_in_blank, past_tense, present_perfect, conditionals, prepositions, articles, phrasal_verbs, idioms
- question_text is clear and unambiguous
- All 5 choices are plausible (wrong answers are not obviously wrong)

Return ONLY a valid JSON array. No explanation, no markdown, no code fences.

Schema per item:
{{
  "type": "vocabulary" or "grammar",
  "difficulty": {difficulty},
  "topic": "string",
  "question_text": "string",
  "choices": ["string", "string", "string", "string", "string"],
  "correct_index": 0-4
}}
"""

async def call_claude(prompt: str) -> list[dict]:
    headers = {
        "x-api-key": settings.claude_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-opus-4-6",
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
        r.raise_for_status()
        content = r.json()["content"][0]["text"]
        return json.loads(content)

async def call_openai(prompt: str) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    # OpenAI json_object mode requires the response to be a JSON object, not a bare array.
    # We wrap the request: ask for {"questions": [...]} and extract the key.
    wrapped_prompt = prompt + '\n\nReturn JSON in this exact format: {"questions": [...]}'
    body = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": wrapped_prompt}],
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        return data["questions"]

async def generate_batch(batch: dict) -> list[dict]:
    prompt = PROMPT_TEMPLATE.format(**batch)
    provider = settings.cloud_ai_provider
    print(f"  Calling {provider} for {batch['count']} {batch['label']} questions...")
    for attempt in range(3):
        try:
            if provider == "claude":
                questions = await call_claude(prompt)
            else:
                questions = await call_openai(prompt)
            # Validate
            valid = []
            for q in questions:
                assert q.get("type") in ("vocabulary", "grammar")
                assert isinstance(q.get("choices"), list) and len(q["choices"]) == 5
                assert 0 <= q.get("correct_index", -1) <= 4
                assert q.get("question_text")
                valid.append(q)
            print(f"  Got {len(valid)} valid questions.")
            return valid
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            if attempt == 2:
                raise
    return []

async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    all_questions = []
    for batch in BATCHES:
        print(f"\nGenerating {batch['label']} questions...")
        questions = await generate_batch(batch)
        all_questions.extend(questions)

    print(f"\nInserting {len(all_questions)} questions into DB...")
    async with session_factory() as session:
        for q_data in all_questions:
            session.add(Question(
                type=q_data["type"],
                difficulty=q_data["difficulty"],
                topic=q_data["topic"],
                question_text=q_data["question_text"],
                choices=q_data["choices"],
                correct_index=q_data["correct_index"],
                explanation_hint=None,
                generated_by="seed",
            ))
        await session.commit()

    print(f"Done! {len(all_questions)} seed questions inserted.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Copy `.env.example` to `.env` and fill in your API key**

```bash
cp .env.example .env
# Edit .env: set DATABASE_URL, SECRET_KEY, CLOUD_AI_PROVIDER, and the relevant API key
```

- [ ] **Step 3: Run the seed script**

```bash
cd backend
python -m scripts.generate_seed_questions
# Expected output:
# Generating beginner questions...
#   Calling claude for 20 beginner questions...
#   Got 20 valid questions.
# Generating intermediate questions...
#   ...
# Done! 100 seed questions inserted.
```

- [ ] **Step 4: Verify questions in DB**

```bash
psql english_companion -c "SELECT difficulty, count(*) FROM questions GROUP BY difficulty ORDER BY difficulty;"
# Expected:
#  difficulty | count
# -----------+-------
#          1 |    20
#          2 |    60
#          3 |    20
```

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_seed_questions.py
git commit -m "feat: seed question generation script using cloud AI"
```

---

## Task 9: Integration Smoke Test

- [ ] **Step 1: Run full test suite**

```bash
cd backend
pytest tests/ -v
# Expected: all tests PASS
```

- [ ] **Step 2: Manual end-to-end smoke test**

```bash
# Start server
uvicorn app.main:app --reload

# 1. Register
curl -s -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@test.com","password":"demo123"}'

# 2. Get onboarding questions (use token from step 1)
curl -s http://localhost:8000/onboarding/questions \
  -H "Authorization: Bearer <TOKEN>"

# 3. Submit onboarding answers
curl -s -X POST http://localhost:8000/onboarding/submit \
  -H "Authorization: Bearer <TOKEN>" \
  -H 'Content-Type: application/json' \
  -d '{"answers": [{"question_id": "<ID>", "chosen_index": 0}, ...]}'

# 4. Get next question from feed
curl -s http://localhost:8000/questions/next \
  -H "Authorization: Bearer <TOKEN>"

# 5. Submit a wrong answer then stream explanation
curl -s -X POST "http://localhost:8000/questions/<QID>/answer" \
  -H "Authorization: Bearer <TOKEN>" \
  -H 'Content-Type: application/json' \
  -d '{"chosen_index": 2}'

curl -N "http://localhost:8000/questions/<QID>/explain" \
  -H "Authorization: Bearer <TOKEN>"
# Expected: SSE stream of tokens from Qwen3:8b
```

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "chore: backend plan 1 complete — auth, questions, seed data, Ollama SSE"
```
