"""Generate targeted questions based on user performance analysis."""
import json
import re
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.user import User
from app.models.question import Question
from app.models.progress import UserStats

DASHSCOPE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"


def _build_prompt(weak_topics: dict, strong_topics: dict, level: str, count: int) -> str:
    weak_str = ", ".join(f"{t} ({round(s*100)}%)" for t, s in sorted(weak_topics.items(), key=lambda x: x[1]))
    strong_str = ", ".join(f"{t} ({round(s*100)}%)" for t, s in sorted(strong_topics.items(), key=lambda x: -x[1]))
    difficulty_map = {"beginner": 1, "intermediate": 2, "advanced": 3}
    diff = difficulty_map.get(level, 2)

    return f"""Generate {count} English learning questions for a {level} level learner.

Performance analysis:
- Weak areas: {weak_str or 'none identified yet'}
- Strong areas: {strong_str or 'none identified yet'}

Focus 70% of questions on weak areas to help the learner improve.
The remaining 30% should reinforce strong areas or introduce new topics.

Rules:
- Each question has exactly 5 answer choices
- correct_index is 0-4 (randomize the position of correct answers)
- topic is a short tag like: synonyms, antonyms, fill_in_blank, past_tense, present_perfect, conditionals, prepositions, articles, phrasal_verbs, idioms
- question_text is clear and unambiguous
- All 5 choices are plausible
- difficulty: {diff}

Return ONLY a valid JSON array. No explanation, no markdown, no code fences.

Schema per item:
{{
  "type": "vocabulary" or "grammar",
  "difficulty": {diff},
  "topic": "string",
  "question_text": "string",
  "choices": ["string", "string", "string", "string", "string"],
  "correct_index": 0-4
}}"""


def _clean_response(content: str) -> str:
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)
    return content.strip()


async def generate_for_user(user: User, db: AsyncSession) -> int:
    """Analyze user stats and generate 20 targeted questions."""
    result = await db.execute(select(UserStats).where(UserStats.user_id == user.id))
    stats = result.scalar_one_or_none()

    weak = stats.weak_topics if stats else {}
    strong = stats.strong_topics if stats else {}
    count = 20

    prompt = _build_prompt(weak, strong, user.level, count)

    headers = {
        "Authorization": f"Bearer {settings.qwen_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "qwen3.5-plus",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 8192,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(DASHSCOPE_URL, headers=headers, json=body)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        content = _clean_response(content)
        questions = json.loads(content)

    inserted = 0
    for q_data in questions:
        try:
            assert q_data.get("type") in ("vocabulary", "grammar")
            assert isinstance(q_data.get("choices"), list) and len(q_data["choices"]) == 5
            assert 0 <= q_data.get("correct_index", -1) <= 4
            assert q_data.get("question_text")
            db.add(Question(
                type=q_data["type"],
                difficulty=q_data["difficulty"],
                topic=q_data["topic"],
                question_text=q_data["question_text"],
                choices=q_data["choices"],
                correct_index=q_data["correct_index"],
                generated_by="agent",
            ))
            inserted += 1
        except (AssertionError, KeyError):
            continue

    await db.commit()
    return inserted
