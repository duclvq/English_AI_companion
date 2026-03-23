# English AI Companion — Design Spec
**Date:** 2026-03-23
**Status:** Approved

---

## Overview

A TikTok-style English learning app where users scroll through lesson cards. Each card presents a multiple-choice question (5 choices). On a wrong answer, an AI (Qwen3:8b via Ollama) explains the mistake. An adaptive agent monitors user performance and generates personalized questions via a cloud AI API.

---

## Target Audience & Content

- **Audience:** Mixed levels — beginner, intermediate, advanced
- **Question types:** Vocabulary + grammar (50/50 mix)
- **Seed distribution:** 20 beginner / 60 intermediate / 20 advanced
- **Platform:** Web (Next.js) + Mobile (React Native / Expo)

---

## Architecture

Single FastAPI backend (monolith with clean internal module boundaries, designed to split later).

```
Clients: Next.js (web) + React Native / Expo (mobile)
    ↓ REST (JSON) + SSE (explanation streaming)
FastAPI Backend
  ├── Auth & Users module
  ├── Question Router module
  ├── Progress & Stats API module
  ├── Adaptive Agent module (asyncio background task)
  ├── Ollama Client (Qwen3:8b, same VM as FastAPI) → explanations via SSE
  └── Cloud AI Client (Claude or GPT-4o) → question generation
    ↓
PostgreSQL DB
```

---

## Data Model

### `users`
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| email | string | unique |
| password_hash | string | bcrypt |
| level | enum | beginner/intermediate/advanced |
| created_at | timestamp | |

### `questions`
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| type | enum | vocabulary/grammar |
| difficulty | int | 1=beginner, 2=intermediate, 3=advanced |
| topic | string | e.g. "past_perfect", "synonyms" |
| question_text | string | |
| choices | JSON | array of 5 strings |
| correct_index | int | 0–4, index into choices array |
| explanation_hint | string | optional hint for Ollama; set by human for seed questions, always `null` for agent-generated questions |
| generated_by | enum | seed/agent |
| created_at | timestamp | |

### `user_progress`
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK users |
| question_id | UUID | FK questions |
| answered_at | timestamp | |
| chosen_index | int | 0–4 |
| is_correct | boolean | |
| time_spent_ms | int | |

### `user_stats`
| Field | Type | Notes |
|-------|------|-------|
| user_id | UUID | PK, FK users |
| total_answered | int | |
| correct_count | int | |
| weak_topics | JSON | {topic: accuracy_float} |
| strong_topics | JSON | {topic: accuracy_float} |
| current_streak | int | resets on wrong answer or 24h inactivity |
| last_active_at | timestamp | |
| agent_last_trigger_count | int | total_answered value when agent last ran |

`user_stats` is updated synchronously in the same DB transaction as each `user_progress` insert.

### `agent_sessions`
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK users |
| triggered_at | timestamp | |
| reasoning_log | JSON | agent's reasoning trace |
| questions_generated | int | |

---

## Auth

- **Access token:** JWT, 30-minute TTL, signed with HS256
- **Refresh token:** Opaque token, 7-day TTL, stored in DB
- **Client storage:** Web → httpOnly secure cookie; Mobile → Expo SecureStore
- **Endpoints:** `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`

---

## API Endpoints

### Auth
| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | `/auth/register` | `{email, password}` | `{access_token, user}` |
| POST | `/auth/login` | `{email, password}` | `{access_token, user}` |
| POST | `/auth/refresh` | Web: reads httpOnly cookie automatically; Mobile: `{refresh_token}` in body | `{access_token}` |
| POST | `/auth/logout` | Web: reads httpOnly cookie; Mobile: `{refresh_token}` in body | `{success: true}` — invalidates refresh token in DB |

### Questions
| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/questions/next` | — | `{id, type, difficulty, topic, question_text, choices[5]}` |
| POST | `/questions/{id}/answer` | `{chosen_index: int}` | `{is_correct, correct_index, streak}` |
| GET | `/questions/{id}/explain` | — | SSE stream of explanation tokens. Returns `403` if user's most recent attempt on this question was correct. |

### Progress
| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/progress/stats` | — | `{total_answered, correct_count, streak, weak_topics, strong_topics}` |

### Onboarding
Both endpoints require a valid access token (user must register first). The feed is locked until onboarding is complete.

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/onboarding/questions` | — | array of 5 questions (mixed difficulty) |
| POST | `/onboarding/submit` | `{answers: [{question_id, chosen_index}]}` | `{level}` |

---

## Question Router Logic

1. Pull the oldest unanswered question from the user's agent-generated queue (difficulty weighted toward weak topics)
2. If queue is empty, fall back to seed questions the user has not yet answered, matching their current level
3. If all seed questions answered, request an immediate agent run (synchronous, small batch of 5)
4. Never repeat a question the user answered correctly within the last 30 days
5. Questions answered incorrectly may reappear after 7 days (spaced repetition)

---

## Onboarding Quiz

- 5 questions: 2 beginner, 2 intermediate, 1 advanced (from seed dataset)
- Scoring: 0–1 correct → beginner; 2–3 correct → intermediate; 4–5 correct → advanced
- Sets `users.level` immediately after submission

---

## User Flow

1. **Login / Register** — JWT auth. New users take the onboarding quiz before seeing the feed.
2. **Feed Screen** — Vertical full-screen cards, one question per card. Light theme, green accents. Backend serves next question via Question Router.
3. **Answer Tap** —
   - ✅ Correct → green flash, streak +1, auto-scroll after 1.5s
   - ❌ Wrong → red flash, correct answer highlighted, AI explanation panel slides up
4. **AI Explanation** — Bottom sheet, streams Qwen3:8b tokens via SSE. Adaptive by level:
   - Beginner: full rule + example + memory tip
   - Intermediate: rule + example
   - Advanced: concise reason only
   - Timeout: 10s. On timeout/failure → show static message "Explanation unavailable, try again."
   - User taps "Got it" → closes → auto-scroll
5. **Adaptive Agent** — Triggers async when `total_answered - agent_last_trigger_count >= 10`. Idempotency: uses `SELECT ... FOR UPDATE` on `user_stats` row to atomically check and update `agent_last_trigger_count`, preventing double-trigger under concurrent requests.
6. **Progress Dashboard** — Streak, accuracy %, weak/strong topic breakdown.

---

## Adaptive Agent

Triggers every 10 answers (per-user, idempotent via `agent_last_trigger_count`).

**Process:**
1. Query last 10 `user_progress` rows → compute per-topic accuracy
2. Build reasoning prompt identifying weak topics
3. Call cloud AI → expect JSON array (schema below) → validate
4. On invalid response: retry up to 2 times, then log and skip this cycle
5. Insert valid questions to DB with `generated_by = 'agent'`
6. Update `user_stats.weak_topics`, `strong_topics`, `agent_last_trigger_count`

**Expected cloud AI output schema:**
```json
[
  {
    "type": "vocabulary" | "grammar",
    "difficulty": 1 | 2 | 3,
    "topic": "string",
    "question_text": "string",
    "choices": ["string", "string", "string", "string", "string"],
    "correct_index": 0-4,
    "explanation_hint": null
  }
]
```
`explanation_hint` is always `null` for agent-generated questions.

**Explanation prompt (Qwen3:8b):**
```
User level: {level}.
Question: {question_text}
Correct answer: {choices[correct_index]}. User chose: {choices[chosen_index]}.
Explain why the correct answer is right and why the user's choice is wrong.
Adapt detail level to {level}: beginner=full rule+example+memory tip, intermediate=rule+example, advanced=concise only.
Be friendly and clear.
```

---

## Ollama Deployment

- Qwen3:8b runs on the same VM as FastAPI, accessible at `http://localhost:11434`
- Explanation requests are proxied via SSE from FastAPI to the client
- Timeout: 10 seconds. On timeout → return SSE error event, client shows fallback message
- No request queue in v1 — concurrent explanations go directly to Ollama (acceptable for MVP load)

---

## UI Design

- **Style:** Light theme, white cards, green accents (#16a34a)
- **Card layout:** Level badge (top-left), type label (top-right), question text, 5 bordered choice buttons
- **Feedback:** Color flash on answer (green/red), correct answer highlighted in green
- **Explanation panel:** Bottom sheet, streams text token by token via SSE
- **Error states:**
  - Network failure loading next question → "Connection error. Pull to retry."
  - Explanation timeout → "Explanation unavailable. Tap to try again."
  - Agent generation failure → silent (user sees no change, next questions come from seed fallback)

---

## Streak Rules

- `current_streak` increments on each correct answer
- Resets to 0 on any wrong answer
- Also resets to 0 if `last_active_at` is more than 24 hours before `now()` — checked on every call to `GET /questions/next` before serving the next question

---

## Out of Scope (v1)

- Social features (sharing, leaderboards)
- Audio pronunciation
- Offline mode
- Push notifications
- Custom question creation by user
- Celery / external task queue (asyncio background tasks only in v1)
