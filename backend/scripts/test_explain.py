"""Test the explain SSE endpoint end-to-end."""
import requests
import json

BASE = "http://localhost:8000"
s = requests.Session()

# Register
r = s.post(f"{BASE}/auth/register", json={"email": "test_explain@test.com", "password": "test123"})
if r.status_code == 400:
    r = s.post(f"{BASE}/auth/login", json={"email": "test_explain@test.com", "password": "test123"})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

# Onboarding
oq = s.get(f"{BASE}/onboarding/questions", headers=h)
if oq.status_code == 200:
    questions = oq.json()
    answers = [{"question_id": q["id"], "chosen_index": 0} for q in questions]
    s.post(f"{BASE}/onboarding/submit", headers=h, json={"answers": answers})
    print("Onboarding done")

# Get question
q = s.get(f"{BASE}/questions/next", headers=h).json()
print(f"Question: {q['question_text']}")
print(f"Choices: {q['choices']}")

# Answer wrong on purpose (try all indices until we get a wrong one)
for idx in range(5):
    ar = s.post(f"{BASE}/questions/{q['id']}/answer", headers=h, json={"chosen_index": idx, "time_spent_ms": 500})
    data = ar.json()
    if not data["is_correct"]:
        print(f"Answered index {idx} -> WRONG (correct was {data['correct_index']})")
        break
    else:
        print(f"Answered index {idx} -> correct, need to get next question")
        q = s.get(f"{BASE}/questions/next", headers=h).json()
        continue

# Now stream explanation
print("\n--- Streaming explanation ---")
r = s.get(f"{BASE}/questions/{q['id']}/explain", headers=h, stream=True)
print(f"Status: {r.status_code}")
for line in r.iter_lines(decode_unicode=True):
    if not line:
        continue
    if line.startswith("data: "):
        chunk = line[6:]
        if chunk == "[DONE]":
            print("\n[DONE]")
            break
        try:
            d = json.loads(chunk)
            if "token" in d:
                print(d["token"], end="", flush=True)
            elif "error" in d:
                print(f"\nERROR: {d['error']}")
        except json.JSONDecodeError:
            pass
print("\nTest complete!")
