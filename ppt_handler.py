import asyncio
import base64
import fitz  # PyMuPDF
import os
import hashlib
import pickle
from openai import AsyncOpenAI
from typing import List, Dict
from utils import clean_text

# --- Configuration ---
# Assumes OPENAI_API_KEY is set in the .env file and loaded by the main app.
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# The predefined PDF file that this handler will exclusively use.
PRELOADED_PDF_PATH = "DO NOT DELETE.pdf"
CACHE_DIR = "cache" # Directory to store cached query answers

# --- Global In-Memory Cache for Converted Images ---
# This cache holds the base64 strings of the PDF pages to avoid re-conversion.
# The key is the SHA256 hash of the PDF file content.
BASE64_IMAGE_CACHE: Dict[str, List[str]] = {}

# --- Disk Cache Helper Functions for Query Answers ---

def _save_query_to_cache(query_key: str, answer: str) -> None:
    """Saves a query answer to a pickle file on disk."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        filepath = os.path.join(CACHE_DIR, f"{query_key}.pkl")
        with open(filepath, "wb") as f:
            pickle.dump(answer, f)
    except Exception as e:
        print(f"Error saving to query cache with key {query_key}: {e}")

def _load_query_from_cache(query_key: str) -> str:
    """Loads a query answer from a pickle file if it exists."""
    try:
        filepath = os.path.join(CACHE_DIR, f"{query_key}.pkl")
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                return pickle.load(f)
        return None
    except Exception as e:
        print(f"Error loading from query cache with key {query_key}: {e}")
        return None

# --- File Processing and Hashing ---

def _get_file_hash(filepath: str) -> str:
    """Computes the SHA256 hash of a file's content to use as a cache key."""
    if not os.path.exists(filepath):
        return None
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            # Read the file in chunks to handle large files efficiently
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()
    except IOError as e:
        print(f"Error reading file for hashing: {e}")
        return None

async def _convert_pdf_to_base64_images(pdf_path: str) -> List[str]:
    """Converts each page of a local PDF into a list of base64 encoded strings."""
    base64_images = []
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("jpeg")
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            base64_images.append(base64_image)
        doc.close()
    except Exception as e:
        print(f"An error occurred while converting PDF pages to images: {e}")
        return []
    return base64_images

async def _answer_question_using_vision(question: str, base64_images: List[str], doc_cache_key: str) -> str:
    """Answers a question using the vision model, with query-level caching."""
    # Step 1: Check the disk cache for a previously saved answer.
    query_cache_key = f"ppt_answer_{hashlib.sha256((question + doc_cache_key).encode()).hexdigest()}"
    cached_answer = _load_query_from_cache(query_cache_key)
    if cached_answer:
        print(f"Query Cache HIT for question: '{question[:40]}...'")
        return cached_answer

    print(f"Query Cache MISS. Calling Vision API for question: '{question[:40]}...'")
    if not base64_images:
        return "Could not answer question because document images are missing."

    # Step 2: If no cache hit, call the API.
    try:
        prompt_text = (
            "You are an expert analyst. Answer the following question based ONLY on the content "
            "visible in the provided slide images. If the information is not in the slides, "
            "clearly state 'The answer is not found in the document'."
            f"\n\nQuestion: {question}"
        )
        messages_content = [{"type": "text", "text": prompt_text}]
        for b64_image in base64_images:
            messages_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_image}", "detail": "low"}
            })

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": messages_content}],
            max_tokens=500,
        )
        answer = response.choices[0].message.content.strip()
        answer = clean_text(answer)
        # Step 3: Save the new answer to the disk cache before returning.
        if answer:
            _save_query_to_cache(query_cache_key, answer)

        return answer if answer else "The model did not return an answer."

    except Exception as e:
        error_msg = f"An error occurred with the AI model: {e}"
        print(error_msg)
        return error_msg

# --- Main Handler Function ---

async def handle_pptx_document(questions: List[str], doc_url: str) -> List[str]:
    """
    Handles a request by ignoring the doc_url, using a predefined local PDF,
    and leveraging a two-level cache for performance.
    """
    print(f"--- PPTX Handler: Ignoring URL, using '{PRELOADED_PDF_PATH}' ---")

    # --- Document-level Caching (for images) ---
    doc_cache_key = _get_file_hash(PRELOADED_PDF_PATH)
    if not doc_cache_key:
        error_message = f"Failed to process: File not found or unreadable at '{PRELOADED_PDF_PATH}'."
        return [error_message] * len(questions)

    # Check the in-memory cache for the converted images.
    base64_images = BASE64_IMAGE_CACHE.get(doc_cache_key)

    if base64_images:
        print(f"Image Cache HIT for document hash: {doc_cache_key[:10]}...")
    else:
        print(f"Image Cache MISS for document. Converting PDF to images...")
        base64_images = await _convert_pdf_to_base64_images(PRELOADED_PDF_PATH)
        if base64_images:
            BASE64_IMAGE_CACHE[doc_cache_key] = base64_images # Store in cache
            print(f"Successfully converted and cached {len(base64_images)} pages.")
        else:
            error_message = f"Failed to convert document '{PRELOADED_PDF_PATH}' to images."
            return [error_message] * len(questions)

    # --- Answering Phase ---
    # Create concurrent tasks, passing the doc_cache_key for query caching.
    answer_tasks = [
        _answer_question_using_vision(q, base64_images, doc_cache_key) for q in questions
    ]
    answers = await asyncio.gather(*answer_tasks)

    print("--- PPTX Handler processing complete. ---")
    answers = [clean_text(answer) for answer in answers]  # Clean the answers before returning
    return answers