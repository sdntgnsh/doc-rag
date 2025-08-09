import asyncio
import time
import os
import hashlib
import pickle
from typing import List, Dict
import pandas as pd
import io

import handlers.document_loader as document_loader
from fastapi import HTTPException
import google.generativeai as genai
from dotenv import load_dotenv
import logging

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("xlsx_handler.log")  # Dedicated log file
    ]
)
logger = logging.getLogger(__name__)

# --- Environment and API Setup ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable not set.")
    raise ValueError("GEMINI_API_KEY environment variable not set.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction="""
    You are an expert data analyst. Your task is to answer questions based on the provided Excel data context.
    1. Provide clear, accurate answers based ONLY on the data given.
    2. Do not invent or infer data that is not present in the context.
    3. If the answer cannot be found in the provided data, state that clearly.
    4. When asked for specific data points (e.g., a salary or phone number), provide them exactly as they appear.
    5. Answer concisely and directly with context tied to the original question. Include a brief sentence or two summarizing the result before providing the actual data. For example, if asked for someone's phone number, respond with: 'John's phone number is:' followed by the number. Do not return raw data alone—always frame the answer in a clear, natural sentence..
    """
)

# --- Caching Functions ---
def save_query_to_cache(query_key: str, answer: str) -> None:
    """Saves a generated answer to the cache."""
    try:
        os.makedirs("cache", exist_ok=True)
        filepath = os.path.join("cache", f"{query_key}.pkl")
        with open(filepath, "wb") as f:
            pickle.dump(answer, f)
    except Exception as e:
        logger.error(f"Failed to save query to cache with key {query_key}: {e}")

def load_query_from_cache(query_key: str) -> str:
    """Loads an answer from the cache if it exists."""
    try:
        filepath = os.path.join("cache", f"{query_key}.pkl")
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                return pickle.load(f)
        return None
    except Exception as e:
        logger.error(f"Failed to load query from cache with key {query_key}: {e}")
        return None

# --- Core Logic ---
async def handle_xlsx(questions: List[str], doc_url: str) -> List[str]:
    """
    Handles XLSX documents by converting them to text and using an LLM for Q&A.
    """
    start_time = time.time()
    answers = ["Processing timed out for this question."] * len(questions)
    logger.info(f"Processing {len(questions)} questions for XLSX document: {doc_url}")

    try:
        # 1. Download XLSX content
        xlsx_bytes = await asyncio.to_thread(document_loader.download_pdf_content, doc_url)
        if not xlsx_bytes:
            raise HTTPException(status_code=400, detail="Could not download XLSX document.")

        # 2. Create a unique key based on file content
        content_hash = hashlib.sha256(xlsx_bytes).hexdigest()
        
        # 3. Convert XLSX to a string format for the LLM
        # This is a simplified representation. For complex files, this might need adjustment.
        xls = pd.ExcelFile(io.BytesIO(xlsx_bytes))
        data_context = ""
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            data_context += f"--- Sheet: {sheet_name} ---\n"
            data_context += df.to_csv(index=False)
            data_context += "\n\n"

        # 4. Answer questions asynchronously
        async def answer_question(question: str, context: str) -> str:
            query_cache_key = f"query_{hashlib.sha256((question + content_hash).encode()).hexdigest()}"
            
            cached_answer = load_query_from_cache(query_cache_key)
            if cached_answer:
                logger.info(f"Cache HIT for question: '{question[:50]}...'")
                return cached_answer
            
            logger.info(f"Cache MISS for question: '{question[:50]}...'")
            prompt = f"""
            Here is the data from an Excel file:
            
            {context}
            
            Based ONLY on the data provided above, answer the following question.
            
            Question: {question}
            Answer:
            """
            
            try:
                response = await asyncio.to_thread(
                    model.generate_content,
                    prompt,
                    generation_config={"temperature": 0.0}
                )
                answer = response.text.strip()
                save_query_to_cache(query_cache_key, answer)
                return answer
            except Exception as e:
                logger.error(f"Answer generation failed for question '{question[:50]}...': {e}")
                return "Error: Could not generate an answer from the model."

        tasks = [asyncio.create_task(answer_question(q, data_context)) for q in questions]
        done, pending = await asyncio.wait(tasks, timeout=35.0) # 35s timeout for all questions

        for task in pending:
            task.cancel()

        results = {}
        for i, task in enumerate(tasks):
            if task in done and not task.cancelled():
                try:
                    results[i] = task.result()
                except Exception as e:
                    results[i] = f"An error occurred: {e}"
            else:
                results[i] = "Processing timed out for this question."
        
        answers = [results[i] for i in range(len(questions))]

    except Exception as e:
        logger.error(f"An unexpected error occurred in handle_xlsx: {e}", exc_info=True)
        answers = [f"An unexpected error occurred: {e}"] * len(questions)

    finally:
        total_time = time.time() - start_time
        completed_count = sum(1 for a in answers if not a.startswith("Processing timed out"))
        logger.info(f"Request finished in {total_time:.2f}s with {completed_count}/{len(answers)} answers.")

    return answers
