import requests

tests = [
    ("P001", "I need to book an appointment with a general physician"),
    ("P002", "I have severe chest pain and difficulty breathing"),
    ("P003", "Can you explain my HbA1c lab results?"),
]

for pid, query in tests:
    r = requests.post(
        "http://localhost:8004/inquiry",
        json={"patient_id": pid, "query": query},
        timeout=20
    )
    if r.status_code == 200:
        d = r.json()
        print(f"[{d['intent'].upper()}] Source: {d['source']} | Escalated: {d['escalated']}")
        print(f"  -> {d['response'][:130]}")
    else:
        print(f"ERROR {r.status_code}: {r.text[:200]}")
    print()
