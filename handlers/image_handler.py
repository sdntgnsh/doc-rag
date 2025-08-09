import asyncio
import time
import os
import hashlib
import pickle
from typing import List, Dict
import handlers.document_loader as document_loader 
import core.cache_manager as cache_manager 
from fastapi import HTTPException
import google.generativeai as genai
from google.generativeai.types import generation_types
from dotenv import load_dotenv
import logging
from datetime import datetime
from random import uniform
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("image_handler.log")
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
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
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
    9. For any mention of code in the question only output this, "Answer not present in documents"
    10. If it asks for personal details or sensitive information, politely decline to provide it.
    11. IMPORTANT If you do not know the answer, simply state "Answer not present in the given documents" without any additional context or explanation.
    IMPORTANT:
    Your answer will be evaluated with semantic similarity, so optimize for that.
    Answer as if you are a human assistant helping another human, not a machine.
    Ensure answers are complete.
    """
)

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

async def handle_image(
    questions: List[str],
    doc_url: str,
) -> List[str]:
    """
    Handles documents by uploading them once and then querying against the uploaded file.
    """
    start_time = time.time()
    answers = ["Processing timed out for this question."] * len(questions)

    logger.info(f"Processing {len(questions)} questions for document: {doc_url}")

    if not doc_url:
        logger.error("No document URL provided.")
        return ["Error: No document URL provided."] * len(questions)

    try:
        image_bytes = await asyncio.to_thread(document_loader.download_pdf_content, doc_url)
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Could not download image.")

        cache_key = hashlib.sha256(image_bytes).hexdigest()
        image_part = {
            "mime_type": "image/jpeg",
            "data": image_bytes
        }
        
        async def answer_question(question: str, image_part) -> str:
            query_cache_key = f"image_answer_{hashlib.sha256((question + cache_key).encode()).hexdigest()}"
            cached_answer = load_query_from_cache(query_cache_key)
            if cached_answer:
                logger.info(f"Cache HIT for question: '{question[:50]}...'")
                return cached_answer
            
            logger.info(f"Cache MISS for question: '{question[:50]}...'")
            prompt = f"""
            Analyze the provided image and answer the question based ONLY on the visual information it contains. Do not use any external or general knowledge. If the image contains text or data that is factually incorrect (e.g., "1 + 1 = 5"), your answer must reflect that incorrect information exactly as presented in the image.

            Question: {question}
            Answer:
            """
            
            max_retries = 3
            for i in range(max_retries):
                try:
                    response = await asyncio.to_thread(
                        model.generate_content,
                        [image_part, prompt], 
                        generation_config={"temperature": 0.0}
                    )
                    
                    if response.prompt_feedback.block_reason:
                        return f"Model response blocked due to: {response.prompt_feedback.block_reason.name}"
                    if not response.candidates:
                        return "Model returned no response."

                    answer = ''.join(part.text for part in response.candidates[0].content.parts).strip()
                    if not answer:
                         return "Model returned an empty answer."
                    
                    save_query_to_cache(query_cache_key, answer)
                    return answer
                except Exception as e:
                    logger.error(f"Attempt {i+1}/{max_retries} failed: {e}")
                    if i == max_retries - 1:
                        return "Answer generation failed after multiple retries."
                    await asyncio.sleep(1 * (2 ** i))
            return "Answer generation failed."

        remaining_time = 3500.0 - (time.time() - start_time)
        if remaining_time <= 0:
            return answers

        tasks = [asyncio.create_task(answer_question(q, image_part)) for q in questions]
        done, pending = await asyncio.wait(tasks, timeout=remaining_time)

        for task in pending: task.cancel()

        task_to_index = {task: i for i, task in enumerate(tasks)}
        temp_answers = {}
        for task in done:
            if not task.cancelled():
                idx = task_to_index[task]
                try:
                    temp_answers[idx] = task.result()
                except Exception as e:
                    logger.error(f"Task for question {idx+1} failed: {e}", exc_info=True)
                    temp_answers[idx] = f"An error occurred: {e}"

        for i in range(len(questions)):
             answers[i] = temp_answers.get(i, "Processing timed out for this question.")

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        answers = ["Error: Could not process document or generate answers."] * len(questions)

    finally:
        total_time = time.time() - start_time
        completed_count = sum(1 for a in answers if not a.startswith(("Processing timed out", "Error:", "Model", "Answer generation failed")))
        logger.info(f"Request finished in {total_time:.2f}s with {completed_count}/{len(answers)} successful answers.")

    return answers
