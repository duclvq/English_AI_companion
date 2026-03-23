"""
Generate 100 seed questions using Qwen API (DashScope) and insert into DB.
Run once: python -m scripts.generate_seed_questions

Requires: QWEN_API_KEY in .env
          DB must be migrated: alembic upgrade head
"""
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models.question import Question

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
- topic is a short tag like: synonyms, antonyms, fill_in_blank, past_tense, \
present_perfect, conditionals, prepositions, articles, phrasal_verbs, idioms
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

DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"


def _clean_response(content: str) -> str:
    """Strip <think> tags and markdown fences from Qwen responses."""
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)
    return content.strip()


async def call_qwen(prompt: str) -> list[dict]:
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
        r = await client.post(DASHSCOPE_BASE_URL, headers=headers, json=body)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        content = _clean_response(content)
        return json.loads(content)


async def call_claude(prompt: str) -> list[dict]:
    headers = {
        "x-api-key": settings.claude_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages", headers=headers, json=body
        )
        r.raise_for_status()
        content = r.json()["content"][0]["text"]
        return json.loads(content)


async def call_openai(prompt: str) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    wrapped_prompt = prompt + '\n\nReturn JSON in this exact format: {"questions": [...]}'
    body = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": wrapped_prompt}],
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions", headers=headers, json=body
        )
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
            if provider == "qwen":
                questions = await call_qwen(prompt)
            elif provider == "claude":
                questions = await call_claude(prompt)
            else:
                questions = await call_openai(prompt)
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
            print(f"  Attempt {attempt + 1} failed: {e}")
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
            session.add(
                Question(
                    type=q_data["type"],
                    difficulty=q_data["difficulty"],
                    topic=q_data["topic"],
                    question_text=q_data["question_text"],
                    choices=q_data["choices"],
                    correct_index=q_data["correct_index"],
                    explanation_hint=None,
                    generated_by="seed",
                )
            )
        await session.commit()

    print(f"Done! {len(all_questions)} seed questions inserted.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
