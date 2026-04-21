import requests
import time

def test_multi_turn():
    patient_id = "P-MEMORY-TEST-001"
    
    turns = [
        "I want to book an appointment with a cardiologist.",
        "Also, can you check my insurance claim status?",
        "Wait, what was the cardiologist appointment for again?"
    ]
    
    print(f"Testing multi-turn memory for patient: {patient_id}\n")
    
    for i, query in enumerate(turns):
        print(f"--- Turn {i+1} ---")
        print(f"Query: {query}")
        
        r = requests.post(
            "http://localhost:8004/inquiry",
            json={"patient_id": patient_id, "query": query},
            timeout=30
        )
        
        if r.status_code == 200:
            d = r.json()
            print(f"Intent: {d['intent']}")
            print(f"Response: {d['response']}")
        else:
            print(f"Error: {r.status_code} - {r.text}")
        print()
        time.sleep(1)

if __name__ == "__main__":
    test_multi_turn()
