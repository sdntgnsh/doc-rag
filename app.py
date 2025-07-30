# app.py
from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel, HttpUrl
from typing import List
import time
import asyncio
import preprocessor
import document_loader
import rag_pipeline
import cache_manager  # Import the new cache manager
import json
from datetime import datetime

import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

# --- Global In-Memory Cache (populated at startup) ---
PDF_CACHE = {}

# --- Authentication ---
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
security_scheme = HTTPBearer()

async def verify_token(credentials: HTTPBearer = Depends(security_scheme)):
    if credentials.credentials != BEARER_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing bearer token")

# --- Pydantic Models ---
class HackRxRequest(BaseModel):
    documents: HttpUrl
    questions: List[str]

class HackRxResponse(BaseModel):
    answers: List[str]

app = FastAPI(
    title="HackRx RAG API",
    description="A RAG API with persistent disk caching."
)

@app.on_event("startup")
def on_startup():
    """Runs when the API server starts up."""
    print("--- Server Startup: Initializing document cache from disk... ---")
    global PDF_CACHE
    PDF_CACHE = preprocessor.initialize_cache_from_json("query.json")
    print("--- Cache initialization complete. Server is ready. ---")

@app.post(
    "/hackrx/run", 
    response_model=HackRxResponse,
    dependencies=[Depends(verify_token)]
)
async def run_hackrx_pipeline(request: HackRxRequest = Body(...)):
    start_time = time.time()
    answers = ["Processing timed out for this question."] * len(request.questions)
    doc_url = str(request.documents)

    try:
        pdf_content = await asyncio.to_thread(document_loader.download_pdf_content, doc_url)
        if not pdf_content:
            raise HTTPException(status_code=400, detail="Could not download document.")

        cache_key = document_loader.get_cache_key_from_content(pdf_content)
        
        # Check in-memory cache first
        vector_store = PDF_CACHE.get(cache_key)
        
        if not vector_store:
            # If not in memory, check disk cache (in case it was processed by another instance)
            vector_store = cache_manager.load_from_cache(cache_key)

        if vector_store:
            print(f"Cache HIT for document with key: {cache_key}")
            if cache_key not in PDF_CACHE:
                PDF_CACHE[cache_key] = vector_store # Add to in-memory cache
        else:
            print(f"Cache MISS for document. Processing on-demand...")
            setup_task = asyncio.to_thread(rag_pipeline.setup_pipeline_from_content, pdf_content)
            vector_store = await asyncio.wait_for(setup_task, timeout=28.0)
            
            # Save the newly processed document to both caches
            cache_manager.save_to_cache(cache_key, vector_store)
            PDF_CACHE[cache_key] = vector_store

        # --- Answering Phase ---
        remaining_time = 28.0 - (time.time() - start_time)
        if remaining_time <= 0:
            return HackRxResponse(answers=answers)

        answer_tasks = [
            asyncio.create_task(asyncio.to_thread(rag_pipeline._answer_one_question, q, vector_store))
            for q in request.questions
        ]
        
        done, pending = await asyncio.wait(answer_tasks, timeout=remaining_time)
        
        for i, task in enumerate(answer_tasks):
            if task in done and not task.cancelled():
                try: answers[i] = task.result()
                except Exception as e: answers[i] = f"An error occurred: {e}"
            elif task in pending: task.cancel()

    except asyncio.TimeoutError:
        print("Processing timed out during on-demand setup.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    total_time = time.time() - start_time
    completed_count = len([a for a in answers if not a.startswith("Processing timed out")])
    print(f"Request finished in {total_time:.2f}s with {completed_count}/{len(answers)} answers.")
    
    # Log every query and its answers
    log_query_and_answers(doc_url, request.questions, answers)
    return HackRxResponse(answers=answers)

def log_query_and_answers(doc_url, questions, answers):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "document": doc_url,
        "questions": questions,
        "answers": answers
    }
    with open("logs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False, indent=2) + "\n\n")
