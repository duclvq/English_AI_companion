# UX Improvements + Practice Tab — Design Spec
**Date:** 2026-03-23
**Status:** Approved
**Depends on:** `2026-03-23-english-app-design.md` (Phase 1 backend)

---

## Overview

Three interconnected UX improvements built as a unified game loop:
1. **Forest Theme** — dark forest visual identity with geography-based seasonal scenes
2. **Gamification & Mascot** — Beary the bear, daily streak, XP, goal picker, celebration screens
3. **Practice Tab** — writing prompts that target weak grammar topics, validated by Qwen3:8b

All three reinforce the same emotional loop: enter the forest → learn → get encouraged → improve.

---

## Section 1 — Forest Theme & Seasonal Scenes

### Visual Identity
- **Base palette:** Dark deep green backgrounds (`#0d1f0d` → `#1a3a1a`), glowing green accents (`#4ade80`, `#86efac`)
- **Decorative elements:** Tree silhouettes (bottom of screens), floating leaves, fireflies (glowing dot particles)
- **Typography:** White/light green text on dark backgrounds
- **Cards:** Semi-transparent dark glass with green border glow

### Seasonal Scenes
Season is determined by the user's **real-world geography**. Detection order:
1. Request location permission on first launch → derive hemisphere from latitude
2. If denied → infer hemisphere from device timezone offset (UTC+ = likely north, UTC- = likely south, equatorial zones default to north)
3. If still unknown → default to Summer scene

**Hemisphere → Season mapping:**

| Month | Northern Hemisphere | Southern Hemisphere |
|-------|-------------------|-------------------|
| Dec–Feb | ❄️ Winter | ☀️ Summer |
| Mar–May | 🌸 Spring | 🍂 Autumn |
| Jun–Aug | ☀️ Summer | ❄️ Winter |
| Sep–Nov | 🍂 Autumn | 🌸 Spring |

**Seasonal palettes & details:**

| Season | Background | Accent | Flora | Beary Outfit |
|--------|-----------|--------|-------|-------------|
| 🌸 Spring | `#0d2010` → `#1a3d1a` | `#fbcfe8`, `#4ade80` | Cherry blossoms 🌸, pink fireflies | Flower crown |
| ☀️ Summer | `#0a1f0a` → `#16381a` | `#4ade80`, `#fef08a` | Lush leaves 🌿🍃, golden fireflies | Leaf backpack |
| 🍂 Autumn | `#1a0f05` → `#2d1a08` | `#fb923c`, `#fbbf24` | Falling leaves 🍂🍁, warm orange glows | Cosy scarf |
| ❄️ Winter | `#050f1a` → `#0a1f2e` | `#bae6fd`, `#7dd3fc` | Snowflakes ❄️, ice-blue particles, pine trees | Knit hat & mittens |

**Implementation:** Season is computed on each full page/app load and stored in local session state (not persisted to localStorage or service worker cache). Switching mid-session is not required. For web (Next.js), "app launch" means each full page load or session initialization — not cached across tabs. UTC+0 timezone defaults to Northern Hemisphere.

---

## Section 2 — Gamification & Mascot (Unified Game Loop)

### Mascot
**Beary** 🐻 — a friendly bear who guides the user through learning. Appears:
- Onboarding screens (animated intro)
- Wrong answer explanation CTA ("Beary's got your back!")
- Daily goal celebration screen
- Practice tab feedback

Beary's visual outfit changes with the season (see Section 1).

### New DB Fields

**`users` table additions:**
| Field | Type | Notes |
|-------|------|-------|
| goal | enum | travel/exam/work/general — set during onboarding |
| daily_goal | int | 5/10/20/30 — questions per day, set during onboarding |

**`user_stats` table additions:**
| Field | Type | Notes |
|-------|------|-------|
| xp_total | int | cumulative XP, default 0 |
| daily_xp | int | XP earned today, resets at UTC midnight, default 0 |
| daily_answered_count | int | total answers today (correct + wrong), resets at UTC midnight, default 0 |
| daily_correct_count | int | correct answers today, resets at UTC midnight, default 0 |
| daily_goal_completed_at | timestamp/null | null if not yet completed today |

XP award: +10 XP per correct answer (added to both `xp_total` and `daily_xp`). `daily_answered_count` increments on every answer; `daily_correct_count` increments on correct answers only.

**Daily reset logic:** On `GET /questions/next`, if `date(last_active_at, 'UTC') < date(now(), 'UTC')` (calendar day boundary, not rolling 24h), reset: `daily_answered_count = 0`, `daily_correct_count = 0`, `daily_xp = 0`, `daily_goal_completed_at = null`.

**Streak reset logic (overrides Phase 1):** `current_streak` now resets **only** on 24h inactivity (rolling window from `last_active_at`). It no longer resets on wrong answers. This spec supersedes the Phase 1 rule. Both resets are checked on `GET /questions/next`.

### Onboarding Flow (4 Screens)

**Skip condition:** If `users.goal IS NOT NULL`, skip the entire onboarding flow and go directly to the feed. Users cannot re-run onboarding in v1 (no settings screen to change goal/daily_goal).

1. **Beary Intro** — large Beary emoji, "Hi, I'm Beary! Welcome to the forest. Let's learn English together, one leaf at a time. 🍃" → "Enter the forest →" button
2. **Goal Selection** — "What's your goal?" → 4 options: ✈️ Travel & everyday chat / 📝 Exam prep (TOEIC/IELTS) / 💼 Work & business English / 🎓 General improvement.
3. **Daily Goal Picker** — "How many questions per day?" → 4 options: 🌱 Casual (5) / 🔥 Regular (10) / 💪 Intense (20) / 🚀 Serious (30).
4. **Level Quiz Intro** — Beary says "Let's find your level! 5 quick questions — only takes 1 minute." → "Start quiz →" → existing 5-question onboarding quiz.

`PATCH /users/me/goal` is called **once** at the end of screen 3, sending both `goal` and `daily_goal` together. Both fields are required. If the user abandons after screen 2, `goal` and `daily_goal` are not saved — the onboarding will restart from screen 1 on next login.

### Feed HUD (Persistent Top Bar)

Always visible at top of feed screen:
- Left: 🐻 "Forest English" logo
- Right: 🔥 streak count (orange) + ⚡ daily progress "X/Y" (green)
- Below header: green gradient progress bar (width = daily_answered_count / daily_goal %)

### Answer Feedback

**Correct answer:**
- Green flash on card border
- "+10 XP ⭐" popup in green pill badge (top center, glowing)
- Correct choice highlighted with green border + glow
- Streak counter increments visually
- Auto-advance to next card after 1.5s

**Wrong answer:**
- Warm orange (not red) border flash on card
- Orange pill badge: "Almost! You're learning 💪"
- User's chosen answer shown with warm orange border + "← your pick" label
- Correct answer highlighted in green
- Beary CTA card: "Beary's got your back! → Tap to understand why 📖"
- **No streak penalty shown to user** — streak internally does not reset on wrong answers (encouragement-first design)
- User taps Beary CTA → explanation sheet slides up (existing SSE stream)

### Daily Goal Celebration Screen

Triggered when `daily_answered_count` reaches `daily_goal` for the first time that day:
- Full-screen forest overlay with seasonal confetti/particles
- Beary in seasonal outfit: "Forest cleared! 🌲" (or seasonal variant: "Meadow bloomed! 🌸" / "Leaves collected! 🍂" / "Snowflakes caught! ❄️")
- Stats summary card: streak 🔥 (`current_streak`) / accuracy today (`daily_correct_count / daily_answered_count`) / XP earned today (`daily_xp`)
- Two buttons: "Keep exploring 🌿" (continue feed) / "Come back tomorrow 🌙" (exit)
- Sets `daily_goal_completed_at = now()`

### New API Endpoints

| Method | Path | Request | Response |
|--------|------|---------|----------|
| PATCH | `/users/me/goal` | `{goal, daily_goal}` | `{success: true}` — called after onboarding screens 2 & 3 |

Existing `POST /questions/{id}/answer` response extended with:
```json
{
  "is_correct": true,
  "correct_index": 1,
  "streak": 6,
  "xp_earned": 10,
  "daily_answered_count": 7,
  "daily_correct_count": 6,
  "daily_xp": 60,
  "daily_goal": 10,
  "daily_goal_complete": false
}
```

---

## Section 3 — Practice Tab

### Overview
A dedicated "Practice" tab in the bottom navigation. Users write a response to a scenario prompt; Qwen3:8b validates their grammar and returns structured encouraging feedback. Writing only in v1; voice input planned for v2.

### Tab Navigation
Bottom nav: 🌿 Feed | ✍️ Practice | 📊 Stats

The **Stats tab** displays the existing Phase 1 progress dashboard (`GET /progress/stats`): total answered, accuracy %, current streak, weak topics list, strong topics list. No new screen spec required beyond what Phase 1 defines. Forest theme styling applies.

### Practice Prompt Generation

Prompts are scenario-based and secretly target the user's weakest grammar topic from `user_stats.weak_topics`.

**Selection logic:**
1. Read `weak_topics` — pick the topic with lowest accuracy
2. Select a matching prompt from `practice_prompts` table (see Data Model)
3. If no weak topic exists (new user) → pick a random intermediate prompt

**Example prompt targeting `past_perfect`:**
> "You just returned from a trip. Tell Beary about something interesting that happened before you arrived at your destination."
> 💡 Try to use "had" in your answer

### Data Model

**`practice_prompts` table (seed data, not agent-generated):**
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| topic | string | must exactly match a value used in `questions.topic` (shared taxonomy, enforced by convention not FK) |
| difficulty | int | 1–3 |
| scenario | string | the scenario description shown to user |
| hint | string | optional grammar hint shown below prompt |

**Example seed rows:**
| topic | difficulty | scenario | hint |
|-------|-----------|----------|------|
| past_perfect | 2 | "You just returned from a trip. Tell Beary about something interesting that happened before you arrived." | Try to use "had" in your answer |
| present_perfect | 2 | "Tell Beary about something you have never done but want to try." | Use "have never" or "have always wanted" |
| conditionals | 3 | "If you could live anywhere in the world, where would you live and why?" | Use "would" and "if I..." |
| past_tense | 1 | "Describe what you did last weekend." | Use past tense verbs (went, ate, saw...) |
| articles | 2 | "Describe your favourite place in your city to a friend who has never been there." | Pay attention to when to use 'a', 'an', or 'the' |

**`practice_sessions` table:**
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK users |
| prompt_id | UUID | FK practice_prompts |
| user_text | string | what the user typed |
| feedback_json | JSON | parsed Qwen3:8b response (see below) |
| created_at | timestamp | |

### Validation Flow

1. User submits text → `POST /practice/submit`
2. Backend builds prompt for Qwen3:8b:

```
The user is a {level} English learner practicing: {topic}.
Scenario they were given: "{scenario}"
Their response: "{user_text}"

Validate their grammar. Return JSON only:
{
  "overall_encouragement": "string (warm, positive, 1 sentence)",
  "highlights": [
    {"phrase": "exact phrase from user text", "suggestion": "improved version", "reason": "brief explanation"}
  ],
  "corrected_version": "full corrected text",
  "beary_tip": "one key grammar rule to remember, friendly tone, max 2 sentences"
}
Highlight maximum 2 issues. Do not mention what was wrong — only what can be better.
Focus on encouragement. Never use the word 'wrong' or 'mistake'.
```

3. Parse JSON response → store in `practice_sessions.feedback_json`
4. Update `user_stats.weak_topics`: apply +0.1 accuracy boost (capped at 1.0) for the practiced topic **unconditionally on any valid submission** (submitting and engaging is itself progress). This is intentionally lenient — the goal is encouragement, not gate-keeping.
5. Return feedback to client

### Feedback UI

**Writing screen:**
- Scenario card (dark glass, green border, topic badge in yellow "🎯 Targeting: Past Perfect")
- Large text input area (dark background, light green cursor)
- "Check with Beary 🐻" button (green gradient)
- "🎙️ Voice coming soon" label (greyed out)

**Feedback screen:**
- Beary header + `overall_encouragement` text
- "YOUR WRITING" section: user's original text with highlighted phrases (warm yellow underline, not red)
- "✨ EVEN BETTER" section: `corrected_version` in green text
- "🐻 BEARY'S TIP" card: amber background, `beary_tip` text
- "Next prompt 🌿" button

### Input Validation

`POST /practice/submit` requires `user_text` to be at least **20 characters**. If shorter, return `400: {"detail": "Please write a bit more for Beary to help you!"}`.

### Error Handling

Qwen3:8b timeout: 10 seconds (same as Phase 1 explanation endpoint). On timeout or JSON parse failure: retry once. If still failing, return `503: {"detail": "Beary is thinking... try again in a moment."}`. Do not persist a failed session.

### New API Endpoints

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/practice/prompt` | — | `{id, scenario, hint, topic, difficulty}` — prompt_id is client-held state, not a server session |
| POST | `/practice/submit` | `{prompt_id, user_text}` (min 20 chars) | `{overall_encouragement, highlights, corrected_version, beary_tip}` |

---

## Out of Scope (v2)

- Voice/speaking input (Web Speech API or Whisper)
- Beary animated character (use emoji for v1)
- Push notifications for daily goal reminders
- Conversation mode (back-and-forth with Beary)
- Season manual override in settings
