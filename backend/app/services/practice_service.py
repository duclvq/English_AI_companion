import json
import uuid
from datetime import datetime
import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.practice import PracticePrompt, PracticeSession
from app.models.progress import UserStats


async def get_prompt_for_user(user_id: uuid.UUID, level: str, db: AsyncSession) -> PracticePrompt | None:
    """Select a practice prompt targeting the user's weakest topic."""
    result = await db.execute(select(UserStats).where(UserStats.user_id == user_id))
    stats = result.scalar_one_or_none()

    difficulty_map = {"beginner": 1, "intermediate": 2, "advanced": 3}
    difficulty = difficulty_map.get(level, 2)

    if stats and stats.weak_topics:
        weakest_topic = min(stats.weak_topics, key=lambda t: stats.weak_topics[t])
        r = await db.execute(
            select(PracticePrompt)
            .where(PracticePrompt.topic == weakest_topic)
            .order_by(func.random())
            .limit(1)
        )
        prompt = r.scalar_one_or_none()
        if prompt:
            return prompt

    # Fallback: random prompt at user's difficulty
    r = await db.execute(
        select(PracticePrompt)
        .where(PracticePrompt.difficulty == difficulty)
        .order_by(func.random())
        .limit(1)
    )
    return r.scalar_one_or_none()


def _build_validation_prompt(scenario: str, topic: str, user_text: str, level: str) -> str:
    return f"""The user is a {level} English learner practicing: {topic}.
Scenario they were given: "{scenario}"
Their response: "{user_text}"

Validate their grammar. Return JSON only (no markdown, no explanation):
{{
  "overall_encouragement": "warm positive 1-sentence comment",
  "highlights": [
    {{"phrase": "exact phrase from user text", "suggestion": "improved version", "reason": "brief explanation"}}
  ],
  "corrected_version": "full corrected version of their text",
  "beary_tip": "one key grammar rule to remember, friendly tone, max 2 sentences"
}}
Highlight maximum 2 issues. Focus on what can be better, not what is wrong.
Never use the words "wrong", "mistake", or "incorrect".
Be warm, encouraging, and supportive."""


async def validate_writing(
    prompt: PracticePrompt,
    user_text: str,
    level: str,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """Call Qwen3:8b, parse feedback JSON, save session, update weak_topics."""
    validation_prompt = _build_validation_prompt(prompt.scenario, prompt.topic, user_text, level)
    payload = {"model": "qwen3:8b", "prompt": validation_prompt, "stream": False}
    timeout = httpx.Timeout(60.0, connect=10.0)

    raw_text = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
                r.raise_for_status()
                raw_text = r.json().get("response", "")
                break
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError):
            if attempt == 1:
                raise

    if not raw_text:
        raise ValueError("Empty response from Ollama")

    # Strip markdown fences and <think> tags if present
    cleaned = raw_text.strip()
    # Remove <think>...</think> blocks
    import re
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    feedback = json.loads(cleaned.strip())

    required = {"overall_encouragement", "highlights", "corrected_version", "beary_tip"}
    if not required.issubset(feedback.keys()):
        raise ValueError("Incomplete feedback JSON from Ollama")

    # Save practice session
    db.add(PracticeSession(
        user_id=user_id,
        prompt_id=prompt.id,
        user_text=user_text,
        feedback_json=feedback,
    ))

    # Update weak_topics: +0.1 boost unconditionally
    result = await db.execute(select(UserStats).where(UserStats.user_id == user_id).with_for_update())
    stats = result.scalar_one_or_none()
    if stats:
        weak = dict(stats.weak_topics or {})
        strong = dict(stats.strong_topics or {})
        topic = prompt.topic
        current = weak.get(topic, strong.get(topic, 0.5))
        updated = round(min(current + 0.1, 1.0), 3)
        if updated < 0.6:
            weak[topic] = updated
            strong.pop(topic, None)
        else:
            strong[topic] = updated
            weak.pop(topic, None)
        stats.weak_topics = weak
        stats.strong_topics = strong

    await db.commit()
    return feedback
