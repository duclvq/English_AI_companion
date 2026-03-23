"""Quick end-to-end smoke test against the running server."""
import httpx

base = "http://localhost:8000"

# 1. Health check
r = httpx.get(f"{base}/health")
print("Health:", r.json())

# 2. Register
r = httpx.post(f"{base}/auth/register", json={"email": "demo@test.com", "password": "demo123"})
data = r.json()
print("Register:", r.status_code, list(data.keys()))
token = data["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 3. Get onboarding questions
r = httpx.get(f"{base}/onboarding/questions", headers=headers)
questions = r.json()
print(f"Onboarding: {len(questions)} questions")
for q in questions:
    print(f"  [diff={q['difficulty']}] {q['question_text'][:70]}")

# 4. Submit onboarding (answer index 0 for all)
answers = [{"question_id": q["id"], "chosen_index": 0} for q in questions]
r = httpx.post(f"{base}/onboarding/submit", json={"answers": answers}, headers=headers)
print("Onboarding result:", r.json())

# 5. Get next question from feed
r = httpx.get(f"{base}/questions/next", headers=headers)
q = r.json()
print(f"\nNext question: {q['question_text']}")
print(f"  Choices: {q['choices']}")

# 6. Answer wrong (pick index 4)
r = httpx.post(f"{base}/questions/{q['id']}/answer", json={"chosen_index": 4}, headers=headers)
print("Answer result:", r.json())

# 7. Check stats
r = httpx.get(f"{base}/progress/stats", headers=headers)
print("Stats:", r.json())

print("\n--- Smoke test complete ---")
