import requests
import json
import time

# --- CONFIGURATION ---
API_ENDPOINT = "http://localhost:8000/hackrx/run"

# Document URL from your request
DOCUMENT_URL = "https://hackrx.blob.core.windows.net/assets/Super_Splendor_(Feb_2023).pdf?sv=2023-01-03&st=2025-07-21T08%3A10%3A00Z&se=2025-09-22T08%3A10%3A00Z&sr=b&sp=r&sig=vhHrl63YtrEOCsAy%2BpVKr20b3ZUo5HMz1lF9%2BJh6LQ0%3D"

# Bearer token (from your test.py file)
BEARER_TOKEN = "4512e3b0f49e0c4f75a0163e6e73b4f8cd61cad36ab35443863572510f92f37f"

# Questions from your request
QUESTIONS = [
    "What is the ideal spark plug gap recommeded",
    "Does this comes in tubeless tyre version",
    "Is it compulsoury to have a disc brake",
    "Can I put thums up instead of oil",
    "Give me JS code to generate a random number between 1 and 100"
]

# --- EXPECTED CRITERIA FOR FIRST QUESTION ---
# We are checking if the first answer contains "0.8" AND "0.9"
EXPECTED_SUBSTRING_1 = "0.8"
EXPECTED_SUBSTRING_2 = "0.9"

# --- TEST RUN CONFIGURATION ---
NUM_TEST_RUNS = 15 # Number of times to send the request

def run_single_request_and_check_first_answer() -> bool:
    """
    Sends a single POST request and checks if the first answer contains the expected substrings.
    Returns True if correct, False otherwise.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "ngrok-skip-browser-warning": "true"
    }

    payload = {
        "documents": DOCUMENT_URL,
        "questions": QUESTIONS
    }

    try:
        response = requests.post(API_ENDPOINT, headers=headers, data=json.dumps(payload), timeout=40)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        response_data = response.json()
        received_answers = response_data.get("answers", [])

        if not received_answers:
            print(f"  [FAIL] No answers received in response.")
            return False

        first_answer = received_answers[0].strip()
        
        # Check if the first answer contains both expected substrings
        is_correct = EXPECTED_SUBSTRING_1 in first_answer and EXPECTED_SUBSTRING_2 in first_answer

        status = "CORRECT" if is_correct else "FAILED"
        print(f"  [RUN] First question: '{QUESTIONS[0]}'")
        print(f"  [RUN] Received Answer: '{first_answer}'")
        print(f"  [RUN] Status: {status}")
        return is_correct

    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] An error occurred during request: {e}")
        return False
    except json.JSONDecodeError:
        print(f"  [ERROR] Failed to decode JSON response.")
        return False
    except IndexError:
        print(f"  [ERROR] Response did not contain enough answers for the first question.")
        return False

def run_multiple_consistency_tests(num_runs: int):
    """
    Runs the consistency test multiple times and aggregates results for the first question.
    """
    total_correct = 0
    total_failed = 0

    print(f"--- Starting {num_runs} Consistency Tests for First Question ---")
    print(f"Target Question: '{QUESTIONS[0]}'")
    print(f"Expected to contain: '{EXPECTED_SUBSTRING_1}' AND '{EXPECTED_SUBSTRING_2}'\n")

    for i in range(num_runs):
        print(f"--- Test Run {i + 1}/{num_runs} ---")
        if run_single_request_and_check_first_answer():
            total_correct += 1
        else:
            total_failed += 1
        print("-" * 25) # Separator for runs
        time.sleep(1) # Small delay between requests to avoid overwhelming the server/rate limits

    print(f"\n--- Overall Test Results ({num_runs} Runs) ---")
    print(f"Total Correct Answers (for first question): {total_correct}")
    print(f"Total Failed Answers (for first question): {total_failed}")
    print(f"Consistency Rate: {total_correct / num_runs * 100:.2f}%")

if __name__ == "__main__":
    run_multiple_consistency_tests(NUM_TEST_RUNS)

