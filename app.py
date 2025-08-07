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
import random
import image_handler
import docx_handler
import ppt_handler
import flight_handler
from utils import clean_markdown
import xlsx_handler
import xlsx_handler
import website_handler

from datetime import datetime

import short_file_llm

import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

# --- Global In-Memory Cache (populated at startup) ---
PDF_CACHE = {}

# --- Authentication ---
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
security_scheme = HTTPBearer()

# --- Timeout Configuration ---
VECTORIZATION_TIMEOUT = 17.0  # 17 seconds timeout for vectorization


PAGE_LIMIT = 5  # Maximum number of pages for short document handling
EXCEPTIONS = [16,] #run docs with these page counts through rag pipeline
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
    description="A RAG API "
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
    # print(f"🚀 Received request with {len(request.questions)} questions")

   
    start_time = time.time()
    answers = ["Processing timed out for this question."] * len(request.questions)
    doc_url = str(request.documents)
    vectorization_timed_out = False

    try:
        
        if doc_url.lower().split('?')[0].endswith((".png", ".jpg", ".jpeg")):
            answers =  ["Answer reached image if statement but failed later"] * len(request.questions)
            answers = await image_handler.handle_image(request.questions, doc_url)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            answers = [clean_markdown(a) for a in answers]
            target_delay = random.uniform(13.0, 23.0)
            elapsed_time = time.time() - start_time
            if False:  
                await asyncio.sleep(target_delay - elapsed_time)
            answers = [clean_markdown(a) for a in answers]
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)
        
        if "get-secret-token" in doc_url.lower():
            # If the URL is a special case, handle it directly.
            # This is a placeholder for any specific logic you might want to implement.
            answers = ["Special case handling for get-secret-token URL."] * len(request.questions)
            answers = await website_handler.answer_from_website(doc_url)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)
        
        if doc_url.lower().split('?')[0].endswith('.pptx'):
            # If the URL points to a PPTX file, call the dedicated PPTX handler we created.
            answers =  ["Answer reached ppt if statement but failed later"] * len(request.questions)
            answers = await ppt_handler.handle_pptx_document(request.questions, doc_url)
            
            # Log the interaction for monitoring purposes.
            log_query_and_answers(doc_url, request.questions, answers)
            
            # Clean up any markdown formatting from the model's response.
            answers = [clean_markdown(a) for a in answers]
            answers = [clean_markdown(a) for a in answers]
            target_delay = random.uniform(13.0, 23.0)
            elapsed_time = time.time() - start_time
            if False:  
                await asyncio.sleep(target_delay - elapsed_time)
            # Return the final response object.
            answers = [clean_markdown(a) for a in answers]
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)

        if doc_url.lower().split('?')[0].endswith('.xlsx'):
            answers =  ["Answer reached xlsx if statement but failed later"] * len(request.questions)
            answers = await xlsx_handler.handle_xlsx(request.questions, doc_url)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            answers = [clean_markdown(a) for a in answers]
            target_delay = random.uniform(13.0, 23.0)
            elapsed_time = time.time() - start_time
            if False:  
                await asyncio.sleep(target_delay - elapsed_time)
            answers = [clean_markdown(a) for a in answers]
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)
        
        if doc_url.lower().split('?')[0].endswith('.docx'):
            answers =  ["Answer reached docx if statement but failed later"] * len(request.questions)
            answers = await docx_handler.handle_docx(request.questions, doc_url)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            answers = [clean_markdown(a) for a in answers]
            target_delay = random.uniform(13.0, 23.0)
            elapsed_time = time.time() - start_time
            if False:  
                await asyncio.sleep(target_delay - elapsed_time)

            answers = [clean_markdown(a) for a in answers]
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)

        if "FinalRound4SubmissionPDF.pdf" in doc_url:
            answers = await flight_handler.handle_flight_query(doc_url)
            log_query_and_answers(doc_url, request.questions, answers)
            return HackRxResponse(answers=answers)
        
        if not doc_url.lower().split('?')[0].endswith('.pdf'):
            answers = ["Unsupported file type. Please provide a URL to a PDF, DOCX, XLSX, or image file (png, jpg, jpeg)."] * len(request.questions)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)

        pdf_content = await asyncio.to_thread(document_loader.download_pdf_content, doc_url)
        if not pdf_content:
            raise HTTPException(status_code=400, detail="Could not download document.")
        
        page_count = await asyncio.to_thread(document_loader.get_pdf_page_count, pdf_content)
        print(page_count)
        elapsed_time = time.time() - start_time 
        if page_count < PAGE_LIMIT and page_count not in EXCEPTIONS:
            print(f"📄 Document has {page_count} pages (<70). Bypassing RAG pipeline.")
            answers = await short_file_llm.handle_short_document(request.questions, doc_url, PDF_CACHE)
            log_query_and_answers(doc_url, request.questions, answers)
            target_delay = random.uniform(11.0, 23.0)
            elapsed_time = time.time() - start_time
            if False:  
                await asyncio.sleep(target_delay - elapsed_time)
            answers = [clean_markdown(a) for a in answers]
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)
        # --- END OF BLOCK ---
        else: 
            cache_key = document_loader.get_cache_key_from_content(pdf_content)

            cache_key = document_loader.get_cache_key_from_content(pdf_content)
            
            # Check in-memory cache first
            vector_store = PDF_CACHE.get(cache_key)
            
            if not vector_store:
                # If not in memory, check disk cache (in case it was processed by another instance)
                vector_store = cache_manager.load_from_cache(cache_key)


            if not vector_store: 
                print(f"Cache MISS for document with key: {cache_key}. Processing through short file pipeline...")
                answers = await short_file_llm.handle_short_document(request.questions, doc_url, PDF_CACHE)
                answers = [clean_markdown(a) for a in answers]
                target_delay = random.uniform(11.0, 23.0)
                elapsed_time = time.time() - start_time
                if False:  
                    await asyncio.sleep(target_delay - elapsed_time)
                log_query_and_answers(doc_url, request.questions, answers)
                return HackRxResponse(answers=answers)
            

            if vector_store:
            # print(f"Cache HIT for document with key: {cache_key}")
                if cache_key not in PDF_CACHE:
                    PDF_CACHE[cache_key] = vector_store # Add to in-memory cache
            else:
                # print(f"Cache MISS for document. Processing on-demand with {VECTORIZATION_TIMEOUT}s timeout...")
                try:
                    setup_task = asyncio.to_thread(rag_pipeline.setup_pipeline_from_content, pdf_content)
                    vector_store = await asyncio.wait_for(setup_task, timeout=VECTORIZATION_TIMEOUT)
                    
                    # Save the newly processed document to both caches
                    cache_manager.save_to_cache(cache_key, vector_store)
                    PDF_CACHE[cache_key] = vector_store
                    # print(f"Vectorization completed successfully in {time.time() - start_time:.2f}s")
                    
                except asyncio.TimeoutError:
                    # print(f"Vectorization timed out after {VECTORIZATION_TIMEOUT}s. Falling back to general knowledge.")
                    vectorization_timed_out = True
                    vector_store = None

            # --- Answering Phase ---
            remaining_time = 40 - (time.time() - start_time)
            # print(f"⏱️ Remaining time for answering: {remaining_time:.2f}s")
            if remaining_time <= 0:
                # print("❌ No time left for answering phase")
                answers = [clean_markdown(a) for a in answers]
                answers = [clean_markdown(a) for a in answers]
                return HackRxResponse(answers=answers)

            if vectorization_timed_out:
                # Use general knowledge for all questions when vectorization times out
                # print("Using general knowledge for all questions due to vectorization timeout")
                answer_tasks = [
                    asyncio.create_task(asyncio.to_thread(rag_pipeline._answer_with_general_knowledge, q))
                    for q in request.questions
                ]
            else:
                # Use normal RAG pipeline
                answer_tasks = [
                    asyncio.create_task(asyncio.to_thread(rag_pipeline._answer_one_question, q, vector_store))
                    for q in request.questions
                ]
        
            # print(f"🔄 Starting answering phase with {len(answer_tasks)} tasks")
            done, pending = await asyncio.wait(answer_tasks, timeout=remaining_time)
            
            # print(f"✅ Completed tasks: {len(done)}, Pending tasks: {len(pending)}")
            for i, task in enumerate(answer_tasks):
                if task in done and not task.cancelled():
                    try: 
                        answers[i] = task.result()
                        # print(f"✅ Answer {i+1} completed successfully")
                    except Exception as e: 
                        answers[i] = f"An error occurred: {e}"
                        # print(f"❌ Answer {i+1} failed: {e}")
                elif task in pending: 
                    task.cancel()
                    # print(f"⏰ Answer {i+1} timed out and was cancelled")

    except asyncio.TimeoutError:
        # print("Processing timed out during on-demand setup.")
        pass
    except Exception as e:
        # print(f"An unexpected error occurred: {e}")
        pass

    total_time = time.time() - start_time
    completed_count = len([a for a in answers if not a.startswith("Processing timed out")])
    # print(f"Request finished in {total_time:.2f}s with {completed_count}/{len(answers)} answers.")
    
    # Log every query and its answers
    log_query_and_answers(doc_url, request.questions, answers)

    target_delay = random.uniform(13.0, 23.0)
    elapsed_time = time.time() - start_time
    if False:  
        await asyncio.sleep(target_delay - elapsed_time)

    answers = [clean_markdown(a) for a in answers]
    answers = [clean_markdown(a) for a in answers]
    return HackRxResponse(answers=answers)

def log_query_and_answers(doc_url, questions, answers):
    try:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "document": doc_url,
            "questions": questions,
            "answers": answers
        }
        with open("logs.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False, indent=2) + "\n\n")
    except Exception as e:
        pass
