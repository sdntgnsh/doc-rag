import os
import time
import io
import asyncio
import hashlib
import pickle
from typing import List
import requests
from docx import Document
import google.generativeai as genai
from google.generativeai.types import generation_types
from fastapi import HTTPException
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("docx_handler.log")
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable not set.")
    raise ValueError("GEMINI_API_KEY environment variable not set.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-2.5-pro",
    system_instruction="""
You are a helpful assistant answering based only on the provided .docx content.
Be concise, complete, and accurate.
Reject requests for code or sensitive information.
If an answer is not in the content, say so.
answer directly without saying based on the document etc.
"""
)

def save_query_to_cache(query_key: str, answer: str) -> None:
    try:
        os.makedirs("cache", exist_ok=True)
        with open(f"cache/{query_key}.pkl", "wb") as f:
            pickle.dump(answer, f)
    except Exception as e:
        logger.error(f"Failed to save to cache: {e}")

def load_query_from_cache(query_key: str) -> str | None:
    try:
        path = f"cache/{query_key}.pkl"
        if os.path.exists(path):
            with open(path, "rb") as f:
                return pickle.load(f)
    except Exception as e:
        logger.error(f"Failed to load from cache: {e}")
    return None

def download_docx_content(url: str) -> bytes | None:
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Failed to download DOCX: {e}")
        return None

def extract_text_from_docx(docx_bytes: bytes) -> str:
    try:
        document = Document(io.BytesIO(docx_bytes))
        return "\n".join([p.text for p in document.paragraphs if p.text.strip()])
    except Exception as e:
        logger.error(f"Failed to extract DOCX content: {e}")
        return ""

async def handle_docx(questions: List[str], doc_url: str) -> List[str]:
    start_time = time.time()
    answers = ["Processing failed."] * len(questions)

    logger.info(f"Processing DOCX from {doc_url} for {len(questions)} questions...")

    docx_bytes = await asyncio.to_thread(download_docx_content, doc_url)
    if not docx_bytes:
        return ["Error: Could not download the DOCX file."] * len(questions)

    cache_key = hashlib.sha256(docx_bytes).hexdigest()
    docx_text = await asyncio.to_thread(extract_text_from_docx, docx_bytes)
    if not docx_text:
        return ["Error: Failed to extract content from DOCX."] * len(questions)

    async def answer_question(question: str) -> str:
        query_key = f"docx_answer_{hashlib.sha256((question + cache_key).encode()).hexdigest()}"
        cached = load_query_from_cache(query_key)
        if cached:
            logger.info(f"Cache HIT for question: {question}")
            return cached

        prompt = f"""
Answer the following question based only on this document content:
---DOCX CONTENT---
{docx_text}
------------------
Question: {question}
Answer:
"""
        try:
            response = await asyncio.to_thread(
                model.generate_content,
                [prompt],
                generation_config={"temperature": 0.0}
            )
            answer = ''.join(part.text for part in response.candidates[0].content.parts).strip()
            if not answer:
                answer = "No answer generated."
            save_query_to_cache(query_key, answer)
            return answer
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return "Error: Failed to generate answer."

    tasks = [asyncio.create_task(answer_question(q)) for q in questions]
    done, pending = await asyncio.wait(tasks, timeout=3500)

    for task in pending:
        task.cancel()

    for i, task in enumerate(tasks):
        try:
            answers[i] = task.result()
        except Exception as e:
            logger.error(f"Task failed: {e}")
            answers[i] = "Error: Task failed."

    logger.info(f"Completed DOCX processing in {time.time() - start_time:.2f}s.")
    return answers
