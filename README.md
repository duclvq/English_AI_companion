# English AI Companion

A TikTok-style English learning app. Swipe through full-screen question cards, get instant AI explanations when you answer wrong, and watch the app adapt to your weak spots over time.

## How It Works

1. Register and take a 5-question placement quiz → get assigned beginner / intermediate / advanced
2. Scroll through multiple-choice cards (vocabulary + grammar)
3. Correct → green flash, streak +1, auto-advance
4. Wrong → red flash, AI explanation streams in via Ollama (Qwen3:8b), with follow-up chat
5. Every 10 answers, an adaptive agent generates personalized questions targeting your weak topics

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 14, React 18, Tailwind CSS 3, TypeScript |
| Backend | FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL |
| AI (explanations) | Ollama + Qwen3:8b (local, SSE streaming) |
| AI (question gen) | Qwen 3.5 Plus via DashScope API |
| Auth | JWT access tokens + httpOnly refresh cookies |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── models/          # SQLAlchemy models (user, question, progress)
│   │   ├── routers/         # FastAPI routes (auth, questions, onboarding, progress)
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # Business logic (auth, question router, stats, ollama)
│   │   ├── config.py        # Settings via pydantic-settings
│   │   ├── database.py      # Async engine + session
│   │   └── main.py          # FastAPI app entry
│   ├── alembic/             # DB migrations
│   ├── scripts/             # Seed generation, smoke test, utilities
│   ├── tests/               # Pytest async tests
│   └── requirements.txt
├── frontend/
│   ├── app/                 # Next.js App Router pages
│   │   ├── login/           # Sign in
│   │   ├── register/        # Sign up
│   │   ├── onboarding/      # Placement quiz
│   │   └── feed/            # Main question feed
│   ├── components/          # QuestionCard, ExplanationPanel, StatsBar
│   ├── lib/                 # API client, auth helpers
│   └── package.json
└── docs/                    # Design spec and plans
```
