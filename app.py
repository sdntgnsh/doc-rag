# app.py
from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel, HttpUrl
from typing import List
import time
import asyncio
import processing.preprocessor as preprocessor
import handlers.document_loader as document_loader
import core.rag_pipeline as rag_pipeline
import core.cache_manager as cache_manager  # Import the new cache manager
import json
import random
import handlers.image_handler as image_handler
import handlers.docx_handler as docx_handler
import handlers.ppt_handler as ppt_handler
import handlers.flight_handler as flight_handler
from utils.utils import clean_markdown, is_file_url
import handlers.xlsx_handler as xlsx_handler
import handlers.xlsx_handler as xlsx_handler
import handlers.website_handler as website_handler
import core.short_file_llm as short_file_llm
import fitz  # For PDF text extraction
import google.generativeai as genai # For classification

from datetime import datetime


import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

# --- Global In-Memory Cache (populated at startup) ---
PDF_CACHE = {}

# --- Gemini Classifier Setup ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
classification_model = None
if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY is not set. PDF classification will be skipped.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        classification_model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction="You are a highly precise document classifier. Your sole function is to determine if a document's primary purpose is 'task-based' or 'question-answer-based'. A 'task-based' document contains explicit, step-by-step instructions for an automated system to perform a task that involves external interactions, such as making API calls to a URL. A 'question-answer-based' document is for informational retrieval. This includes user manuals (like for a vehicle), policy documents, articles, and reports. Even if it contains instructions for a human user, it is still 'question-answer-based' unless it directs an automated system to perform external API calls. Respond with ONLY 'task-based' or 'question-answer-based'."
        )
        print("Gemini classification model loaded successfully.")
    except Exception as e:
        print(f"Error loading Gemini classification model: {e}")

async def classify_pdf_type(pdf_content: bytes) -> str:
    """
    Classifies a PDF as 'task-based' or 'question-answer-based' using the first 5 pages.
    """
    if not classification_model:
        return "question-answer-based"  # Fallback if model isn't loaded

    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        num_pages_to_check = min(len(doc), 5)
        if num_pages_to_check == 0:
            return "question-answer-based"

        first_pages_text = "".join(doc[i].get_text("text") for i in range(num_pages_to_check))
        
        if not first_pages_text.strip():
            return "question-answer-based"

        prompt = f'''Based on the following text from the first {num_pages_to_check} pages of a document, is this document 'task-based' or 'question-answer-based'?

Content (first 4000 chars):
---
{first_pages_text}
---

Respond with ONLY 'task-based' or 'question-answer-based'.'''
        
        response = await asyncio.to_thread(
            classification_model.generate_content,
            [prompt],
            generation_config={"temperature": 0.0}
        )
        
        classification = response.text.strip().lower()
        if "task-based" in classification:
            print("PDF classified as: task-based")
            return "task-based"
        else:
            print("PDF classified as: question-answer-based")
            return "question-answer-based"
            
    except Exception as e:
        print(f"Error during PDF classification: {e}")
        return "question-answer-based"  # Fallback on error

# --- Authentication ---
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
security_scheme = HTTPBearer()

# --- Timeout Configuration ---
VECTORIZATION_TIMEOUT = 17.0  # 17 seconds timeout for vectorization


PAGE_LIMIT = 70  # Maximum number of pages for short document handling
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
            target_delay = random.uniform(13.0, 23.0)
            elapsed_time = time.time() - start_time
            
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)
        
        if not is_file_url(doc_url): # if it's not a file URL, treat it as a website check if it has a file extension

            answers = ["Website handling if pased then failed later"] * len(request.questions)
            answers = await website_handler.answer_from_website(doc_url, request.questions)
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
            target_delay = random.uniform(13.0, 23.0)
            elapsed_time = time.time() - start_time
            
            # Return the final response object.
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)

        if doc_url.lower().split('?')[0].endswith('.xlsx'):
            answers =  ["Answer reached xlsx if statement but failed later"] * len(request.questions)
            answers = await xlsx_handler.handle_xlsx(request.questions, doc_url)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            target_delay = random.uniform(13.0, 23.0)
            elapsed_time = time.time() - start_time
            
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)
        
        if doc_url.lower().split('?')[0].endswith('.docx'):
            answers =  ["Answer reached docx if statement but failed later"] * len(request.questions)
            answers = await docx_handler.handle_docx(request.questions, doc_url)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            target_delay = random.uniform(13.0, 23.0)
            elapsed_time = time.time() - start_time
            

            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)

        if not doc_url.lower().split('?')[0].endswith('.pdf'):
            answers = ["Unsupported file type. Please provide a URL to a PDF, DOCX, XLSX, or image file (png, jpg, jpeg)."] * len(request.questions)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)

        # For PDF files, download the content first to classify them
        pdf_content = await asyncio.to_thread(document_loader.download_pdf_content, doc_url)
        if not pdf_content:
            raise HTTPException(status_code=400, detail="Could not download document.")

        # Classify the PDF to determine the correct handler
        pdf_type = await classify_pdf_type(pdf_content)
        if pdf_type == "task-based":
            print("TASK BASED PDF ----------------------------------")
            answers = await flight_handler.handle_flight_query(doc_url)
            log_query_and_answers(doc_url, request.questions, answers)
            return HackRxResponse(answers=answers)
        
        # If not task-based, proceed with the normal RAG pipeline
        
        page_count = await asyncio.to_thread(document_loader.get_pdf_page_count, pdf_content)
        print(page_count)
        elapsed_time = time.time() - start_time 
        if page_count < PAGE_LIMIT and page_count not in EXCEPTIONS:
            print(f"📄 Document has {page_count} pages (<70). Bypassing RAG pipeline.")
            answers = await short_file_llm.handle_short_document(request.questions, doc_url, PDF_CACHE)
            log_query_and_answers(doc_url, request.questions, answers)
            target_delay = random.uniform(11.0, 23.0)
            elapsed_time = time.time() - start_time
            
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)
            

        elif False and page_count > 500: 
            print(f"📄 Document has {page_count} pages (>500). Skipping RAG pipeline and using general knowledge.")
            answers = await rag_pipeline.answer_questions(request.questions)
            done, pending = await asyncio.wait(answer_tasks, timeout=40)
    
            for i, task in enumerate(answer_tasks):
                if task in done and not task.cancelled():
                    try:
                        answers[i] = task.result()
                    except Exception as e:
                        answers[i] = f"An error occurred: {e}"
                elif task in pending:
                    task.cancel()
                    answers[i] = "Processing timed out for this question."
            
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)
        
     
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
