# test_api.py
import requests
import json
import time

# --- CONFIGURATION ---
# Replace with your actual ngrok URL
API_ENDPOINT = "https://top-live-tadpole.ngrok-free.app/hackrx/run" 

# IMPORTANT: Replace this with the public URL of the PDF you generated.
# You must host 'large_document.pdf' online for the API to access it.
DOCUMENT_URL = "https://drive.google.com/file/d/1BhPnB3NC-oNVG0hXoluncw0CpDKXa8yW/view?usp=sharing" 

BEARER_TOKEN = "4512e3b0f49e0c4f75a0163e6e73b4f8cd61cad36ab35443863572510f92f37f"

# Questions designed to test the content of the generated PDF
QUESTIONS = [
    "What is the purpose of the AsyncProcessor class?",
    "How do you shut down the executor in the AsyncProcessor?",
    "What is the document version mentioned in the metadata?",
    "Who is the author of the document?",
    "What does the run_in_thread method do?",
    "What is the reviewer's name in the metadata for Section 50?",
    "Describe the lorem ipsum text in Section 100.",
    "What is the status of the document according to the metadata?",
    "What font is used for code snippets?",
    "How many workers does the AsyncProcessor use by default?",
    "When was the document created?",
    "What is the title of the document?"
]

def run_test():
    """
    Sends a POST request to the RAG API and prints the response.
    """
    if "YOUR_PUBLIC_URL" in DOCUMENT_URL:
        print("ERROR: Please update the DOCUMENT_URL variable in this script with the actual public URL of your test PDF.")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "ngrok-skip-browser-warning": "true" 
    }

    payload = {
        "documents": DOCUMENT_URL,
        "questions": QUESTIONS
    }

    print(f"Sending request to: {API_ENDPOINT}")
    print(f"Document URL: {DOCUMENT_URL}")
    print(f"Number of questions: {len(QUESTIONS)}")

    try:
        start_time = time.time()
        response = requests.post(API_ENDPOINT, headers=headers, data=json.dumps(payload), timeout=35)
        end_time = time.time()

        print(f"\n--- Response ---")
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {end_time - start_time:.2f} seconds")

        if response.status_code == 200:
            response_data = response.json()
            print("\nAnswers Received:")
            for i, (question, answer) in enumerate(zip(QUESTIONS, response_data.get("answers", []))):
                print(f"  {i+1}. Q: {question}")
                print(f"     A: {answer}\n")
        else:
            print("\nError Response:")
            print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    run_test()
