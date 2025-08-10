import json
import requests
import os
import time
from dotenv import load_dotenv

# ✅ Load .env file so BEARER_TOKEN is available
load_dotenv()

API_URL = "http://127.0.0.1:8000/hackrx/run"
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
QUERY_FILE = "data/past_queries/query.json"

def run_queries():
    # Load all queries from query.json
    with open(QUERY_FILE, "r", encoding="utf-8") as f:
        queries = json.load(f)

    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }

    # Wrap single query into list for consistency
    if isinstance(queries, dict):
        queries = [queries]

    for i, query in enumerate(queries, 1):
        print(f"\n📤 Sending request #{i}...")

        start_time = time.perf_counter()  # ⏱ start timer
        response = requests.post(API_URL, headers=headers, json=query)
        end_time = time.perf_counter()    # ⏱ end timer

        elapsed_ms = (end_time - start_time) * 1000  # convert to ms

        # Print structured output
        print(f"✅ Response #{i} (status {response.status_code}, took {elapsed_ms:.2f} ms):")
        try:
            print(json.dumps(response.json(), indent=4))
        except json.JSONDecodeError:
            print(response.text)

if __name__ == "__main__":
    run_queries()
