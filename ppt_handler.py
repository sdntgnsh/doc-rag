import asyncio
import time
import os
import hashlib
import pickle
import tempfile
from typing import List, Dict

import requests
from fastapi import HTTPException
from google import genai
from dotenv import load_dotenv
import logging

from utils import clean_markdown

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pptx_llm_handler.log")
    ]
)
logger = logging.getLogger(__name__)


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable not set.")
    raise ValueError("GEMINI_API_KEY environment variable not set.")


# Create a single, reusable client instance
# This is the modern way to interact with the API
client = genai.Client(api_key = GEMINI_API_KEY)

# Define the model name we'll use in requests
# Based on your example, but using the supported 1.5 model from your original code.
# The user's example used "gemini-2.0-flash", which as of Aug 2025 is a valid model.
# We will use the model from the user's latest example for accuracy.
MODEL_NAME = "gemini-2.5-flash" 

# --- Load Environment Variables ---
load_dotenv()

# --- Global Cache for Uploaded PPTX Files ---
# This cache stores the reference to the uploaded file on Gemini's servers
# to avoid re-uploading the same file repeatedly.
UPLOADED_PPTX_CACHE = {}

# --- Configure Gemini API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable not set.")
    raise ValueError("GEMINI_API_KEY environment variable not set.")

client = genai.Client()
model_info = client.models.get(model=MODEL_NAME)
# Using a model that supports file uploads and multimodal analysis.
# The system instruction is kept from your original example.
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash", # This model is excellent for multimodal tasks
    system_instruction="""
    You are an expert assistant:
    1. Provide clear, accurate answers drawing on relevant sources, including important keywords and semantics and numbers.
    2. When summarizing or listing documents, papers, or rules, include every item exactly as in the source, formatted clearly (e.g., Required documents: A, B, C, D).
    3. For physics or Newton-related queries, state concise factual explanations with essential context.
    4. For any legal question, provide direct answers consistent with the Constitution of India, including context like article clause.
    5. Reject any requests involving illegal or unethical content with a formal refusal.
    6. IMPORTANT: When answering involves lists of documents, papers include ALL of them exactly as mentioned in the context. Do not summarize or omit any.
    7. Get straight to the point.
    8. For document lists: Present them clearly but concisely (e.g., 'Required documents: A, B, C, D').
    9. If it asks for personal details or sensitive information, politely decline to provide it.

    IMPORTANT:
    Your answer will be evaluated with semantic similarity, so optimize for that.
    Answer as if you are a human assistant helping another human, not a machine.
    Ensure answers are complete.
    """
)

# --- Caching Utilities ---

def get_cache_key_from_content(content: bytes) -> str:
    """Generates a SHA1 hash for the given content to use as a cache key."""
    return hashlib.sha1(content).hexdigest()

def save_query_to_cache(query_key: str, answer: str) -> None:
    """Saves a generated answer to a pickle file in the 'cache' directory."""
    try:
        os.makedirs("cache", exist_ok=True)
        filepath = os.path.join("cache", f"{query_key}.pkl")
        with open(filepath, "wb") as f:
            pickle.dump(answer, f)
    except Exception as e:
        logger.error(f"Failed to save query to cache with key {query_key}: {e}")

def load_query_from_cache(query_key: str) -> str:
    """Loads a cached answer from a pickle file if it exists."""
    try:
        filepath = os.path.join("cache", f"{query_key}.pkl")
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                return pickle.load(f)
        return None
    except Exception as e:
        logger.error(f"Failed to load query from cache with key {query_key}: {e}")
        return None

# --- Core PPTX Processing Logic ---

def download_pptx_content(url: str) -> bytes:
    """Downloads the content of a PPTX file from a URL."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download PPTX file from {url}: {e}")
        return None


async def handle_pptx_document(
    questions: List[str],
    pptx_url: str
) -> List[str]:
    """
    Handles a PPTX document by uploading it once to Gemini and then querying
    against the uploaded file for each question using the modern Client API.
    """
    global UPLOADED_PPTX_CACHE
    start_time = time.time()
    answers = ["Processing timed out for this question."] * len(questions)

    logger.info(f"Processing {len(questions)} questions for PPTX: {pptx_url}")

    if not pptx_url:
        logger.error("No document URL provided.")
        return ["Error: No PPTX URL provided."] * len(questions)

    try:
        # Step 1: Download PPTX bytes (no change here)
        pptx_bytes = await asyncio.to_thread(download_pptx_content, pptx_url)
        if not pptx_bytes:
            raise HTTPException(status_code=400, detail="Could not download PPTX document.")

        content_cache_key = get_cache_key_from_content(pptx_bytes)

        # Step 2: Upload the file using the new client.files.upload method
        uploaded_file = UPLOADED_PPTX_CACHE.get(content_cache_key)
        if not uploaded_file:
            logger.info(f"Uploading PPTX file for the first time with key: {content_cache_key}")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as temp_file:
                temp_file.write(pptx_bytes)
                temp_file_path = temp_file.name

            try:
                # NEW: Use client.files.upload. Notice NO mime_type parameter is needed!
                # The library handles it automatically.
                uploaded_file = await asyncio.to_thread(
                    client.files.upload,
                    file=temp_file_path, # Pass the path to the 'file' parameter
                    display_name=f"pptx-{hashlib.sha1(pptx_bytes).hexdigest()[:8]}"
                )
                UPLOADED_PPTX_CACHE[content_cache_key] = uploaded_file
                logger.info(f"File uploaded successfully: {uploaded_file.name}")
            finally:
                os.unlink(temp_file_path)
        else:
            logger.info(f"Using cached uploaded file: {uploaded_file.name}")

        # Step 3: Define the async function to answer questions using the new client
        async def answer_question(question: str, file_resource) -> str:
            query_cache_key = f"pptx_upload_answer_{hashlib.sha256((question + content_cache_key).encode()).hexdigest()}"
            cached_answer = load_query_from_cache(query_cache_key)
            if cached_answer:
                return cached_answer

            logger.info(f"Querying model with file for: '{question[:80]}...'")
            prompt = f"Using the provided presentation, please answer the following question: {question}"

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # NEW: Use client.models.generate_content
                    # We pass the model name here directly
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=MODEL_NAME,
                        contents=[file_resource, prompt], # Pass the file object and the prompt
                        generation_config={"temperature": 0.1}
                    )

                    answer = response.text.strip()
                    save_query_to_cache(query_cache_key, answer)
                    return answer
                except Exception as e:
                    logger.error(f"LLM API call failed on attempt {attempt + 1}/{max_retries}: {e}")
                    if attempt == max_retries - 1:
                        return "Answer generation failed after multiple retries."
                    await asyncio.sleep(1.5 ** attempt)
            return "Answer generation failed."

        # Step 4: Run tasks concurrently (no change here)
        remaining_time = 45.0 - (time.time() - start_time)
        if remaining_time <= 0:
            return answers

        tasks = [asyncio.create_task(answer_question(q, uploaded_file)) for q in questions]
        done, pending = await asyncio.wait(tasks, timeout=remaining_time)

        for task in pending:
            task.cancel()

        task_to_index = {task: i for i, task in enumerate(tasks)}
        temp_answers = {}
        for task in done:
            if not task.cancelled():
                idx = task_to_index[task]
                try:
                    temp_answers[idx] = task.result()
                except Exception as e:
                    logger.error(f"Task for question index {idx} failed: {e}", exc_info=True)
                    temp_answers[idx] = f"An error occurred while processing this question: {e}"
        
        for i in range(len(questions)):
            answers[i] = temp_answers.get(i, "Processing timed out for this question.")

    except HTTPException as http_exc:
        logger.error(f"HTTP Exception: {http_exc.detail}")
        return [f"Error: {http_exc.detail}"] * len(questions)
    except Exception as e:
        logger.error(f"An unexpected error occurred in handle_pptx_document: {e}", exc_info=True)
        return ["Error: Could not process document or generate answers."] * len(questions)
    finally:
        total_time = time.time() - start_time
        completed_count = sum(1 for a in answers if not a.startswith(("Processing timed out", "Error:", "Model", "Answer generation failed")))
        logger.info(f"Request finished in {total_time:.2f}s with {completed_count}/{len(answers)} successful answers.")
    answers = [clean_markdown(a) for a in answers]  # Clean markdown formatting
    return answers