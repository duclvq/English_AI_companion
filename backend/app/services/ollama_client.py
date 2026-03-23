import json
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
        f"Explain why '{correct}' is correct and why '{chosen}' is wrong. "
        f"{detail} Be friendly and clear."
    )


async def stream_explanation(q: Question, chosen_index: int, level: str):
    prompt = _build_prompt(q, chosen_index, level)
    payload = {"model": "qwen3:8b", "prompt": prompt, "stream": True}
    timeout = httpx.Timeout(60.0, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/generate",
                json=payload,
            ) as resp:
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

async def stream_followup(q: Question, chosen_index: int, level: str, history: list[dict], user_question: str):
    """Stream a follow-up answer given conversation history."""
    correct = q.choices[q.correct_index]
    chosen = q.choices[chosen_index]
    system_msg = (
        f"You are an English tutor. User level: {level}. "
        f"The question was: {q.question_text}\n"
        f"Correct answer: {correct}. User chose: {chosen}.\n"
        f"Answer the user's follow-up question concisely. Use markdown formatting."
    )
    messages = [{"role": "system", "content": system_msg}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_question})

    payload = {"model": "qwen3:8b", "messages": messages, "stream": True}
    timeout = httpx.Timeout(60.0, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/chat",
                json=payload,
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield f"data: {json.dumps({'token': token})}\n\n"
                        if data.get("done"):
                            yield "data: [DONE]\n\n"
                            return
                    except json.JSONDecodeError:
                        continue
    except (httpx.TimeoutException, httpx.ConnectError):
        yield f"data: {json.dumps({'error': 'Could not get a response, try again.'})}\n\n"


def suggest_followups(q: Question, level: str) -> list[str]:
    """Generate 2 suggested follow-up questions based on the question context."""
    suggestions = {
        "vocabulary": [
            f"Can you use '{q.choices[q.correct_index]}' in more example sentences?",
            "What are some common mistakes with this word?",
        ],
        "grammar": [
            "Can you explain this grammar rule in simpler terms?",
            "Can you give me more examples of this pattern?",
        ],
    }
    return suggestions.get(q.type, suggestions["grammar"])



async def stream_followup(q: Question, chosen_index: int, level: str, history: list[dict], user_question: str):
    """Stream a follow-up answer given conversation history."""
    correct = q.choices[q.correct_index]
    chosen = q.choices[chosen_index]
    system_msg = (
        f"You are an English tutor. User level: {level}. "
        f"The question was: {q.question_text}\n"
        f"Correct answer: {correct}. User chose: {chosen}.\n"
        f"Answer the user's follow-up question concisely. Use markdown formatting."
    )
    messages = [{"role": "system", "content": system_msg}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_question})

    payload = {"model": "qwen3:8b", "messages": messages, "stream": True}
    timeout = httpx.Timeout(60.0, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/chat",
                json=payload,
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield f"data: {json.dumps({'token': token})}\n\n"
                        if data.get("done"):
                            yield "data: [DONE]\n\n"
                            return
                    except json.JSONDecodeError:
                        continue
    except (httpx.TimeoutException, httpx.ConnectError):
        yield f"data: {json.dumps({'error': 'Could not get a response, try again.'})}\n\n"


def suggest_followups(q: Question, level: str) -> list[str]:
    """Generate 2 suggested follow-up questions based on the question context."""
    suggestions = {
        "vocabulary": [
            f"Can you use '{q.choices[q.correct_index]}' in more example sentences?",
            "What are some common mistakes with this word?",
        ],
        "grammar": [
            "Can you explain this grammar rule in simpler terms?",
            "Can you give me more examples of this pattern?",
        ],
    }
    return suggestions.get(q.type, suggestions["grammar"])
