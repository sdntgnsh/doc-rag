import asyncio
import time
import os
import hashlib
import json
import pickle
from typing import List, Dict
import document_loader # Assumed to contain download_pdf_content and get_cache_key_from_content
import cache_manager # Assumed to contain save_to_cache and load_from_cache
from fastapi import HTTPException
import google.generativeai as genai
from google.generativeai.types import generation_types
from dotenv import load_dotenv
import logging
from datetime import datetime
from random import uniform

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("short_file_llm.log")
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable not set.")
    raise ValueError("GEMINI_API_KEY environment variable not set.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def save_query_to_cache(query_key: str, answer: str) -> None:
    try:
        os.makedirs("cache", exist_ok=True)
        filepath = os.path.join("cache", f"{query_key}.pkl")
        with open(filepath, "wb") as f:
            pickle.dump(answer, f)
    except Exception as e:
        logger.error(f"Failed to save query to cache with key {query_key}: {e}")

def load_query_from_cache(query_key: str) -> str:
    try:
        filepath = os.path.join("cache", f"{query_key}.pkl")
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                return pickle.load(f)
        return None
    except Exception as e:
        logger.error(f"Failed to load query from cache with key {query_key}: {e}")
        return None

async def handle_short_document(questions: List[str], doc_url: str, pdf_cache: Dict = None) -> List[str]:
    start_time = time.time()
    answers = ["Processing timed out for this question."] * len(questions)
    pdf_cache = pdf_cache or {}

    logger.info(f"Processing {len(questions)} questions for document: {doc_url}")

    if not doc_url:
        logger.error("No document URL provided.")
        return ["Error: No document URL provided."] * len(questions)

    try:
        initial_pdf_bytes = await asyncio.to_thread(document_loader.download_pdf_content, doc_url)
        if not initial_pdf_bytes:
            logger.error("Failed to download document.")
            raise HTTPException(status_code=400, detail="Could not download document.")

        cache_key = document_loader.get_cache_key_from_content(initial_pdf_bytes)
        
        pdf_bytes = None
        cached_item = pdf_cache.get(cache_key)
        if isinstance(cached_item, bytes):
            pdf_bytes = cached_item
        
        if pdf_bytes is None:
            cached_item_disk = cache_manager.load_from_cache(cache_key)
            if isinstance(cached_item_disk, bytes):
                pdf_bytes = cached_item_disk
                pdf_cache[cache_key] = pdf_bytes

        if pdf_bytes is None:
            logger.info(f"Cache miss for PDF bytes: {cache_key}. Using downloaded content.")
            pdf_bytes = initial_pdf_bytes
            cache_manager.save_to_cache(cache_key, pdf_bytes)
            pdf_cache[cache_key] = pdf_bytes

        async def answer_question(question: str, pdf_content: bytes) -> str:
            query_cache_key = f"query_{hashlib.sha256((question + str(cache_key)).encode()).hexdigest()}"
            cached_answer = load_query_from_cache(query_cache_key)
            if cached_answer:
                return cached_answer

            logger.info(f"Query cache miss. Generating answer for: '{question[:50]}...'")
            prompt = f"""
            Using the provided PDF document as context, provide a concise and direct answer to the question.
            Do not mention the source or use phrases like "according to" or "the document states."
            If the answer is not in the document, state "Answer not found in the document."

            Question: {question}
            Answer:
            """
            pdf_file_part = {"mime_type": "application/pdf", "data": pdf_content}

            max_retries = 3
            for i in range(max_retries):
                try:
                    response = await asyncio.to_thread(
                        model.generate_content,
                        [prompt, pdf_file_part],
                        generation_config={"temperature": 0.0, "max_output_tokens": 500}
                    )
                    
                    # *** ROBUST RESPONSE HANDLING ***
                    if response.prompt_feedback.block_reason:
                        block_reason = response.prompt_feedback.block_reason.name
                        logger.warning(f"Response blocked for safety reasons: {block_reason}")
                        return f"Model response blocked due to: {block_reason}"

                    if not response.candidates:
                        logger.warning("No candidates returned from the model.")
                        return "Model returned no response."

                    answer = ''.join(part.text for part in response.candidates[0].content.parts).strip()
                    
                    if not answer:
                         return "Model returned an empty answer."
                         
                    save_query_to_cache(query_cache_key, answer)
                    return answer

                except generation_types.StopCandidateException as e:
                    logger.error(f"Generation stopped unexpectedly: {e}")
                    return f"Generation failed: {e}"
                except Exception as e:
                    logger.error(f"Attempt {i+1}/{max_retries} failed for question '{question}': {e}")
                    if i == max_retries - 1:
                        return "Answer generation failed after multiple retries."
                    await asyncio.sleep(1 * (2 ** i)) # Exponential backoff
            return "Answer generation failed."

        remaining_time = 35.0 - (time.time() - start_time)
        if remaining_time <= 0:
            logger.warning("No time left for answering phase.")
            return answers

        tasks = [asyncio.create_task(answer_question(q, pdf_bytes)) for q in questions]
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
                    logger.error(f"Task for question {idx+1} failed with exception: {e}", exc_info=True)
                    temp_answers[idx] = f"An error occurred: {e}"

        for i in range(len(questions)):
             answers[i] = temp_answers.get(i, "Processing timed out for this question.")

    except Exception as e:
        logger.error(f"An unexpected error occurred in handle_short_document: {e}", exc_info=True)
        answers = ["Error: Could not process document or generate answers."] * len(questions)

    finally:
        total_time = time.time() - start_time
        completed_count = sum(1 for a in answers if not a.startswith(("Processing timed out", "Error:", "Model", "Answer generation failed")))
        logger.info(f"Request finished in {total_time:.2f}s with {completed_count}/{len(answers)} successful answers.")
        try:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "document": doc_url,
                "questions": questions,
                "answers": answers
            }
            with open("logs.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to logs.jsonl: {e}")

    return answers