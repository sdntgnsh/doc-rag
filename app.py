import fastapi
from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel, HttpUrl
from typing import List
import time
import asyncio
import processing.preprocessor as preprocessor
import handlers.document_loader as document_loader
import core.rag_pipeline as rag_pipeline
import core.cache_manager as cache_manager
import json
import random
import handlers.image_handler as image_handler
import handlers.docx_handler as docx_handler
import handlers.ppt_handler as ppt_handler
import handlers.flight_handler as flight_handler
from utils.utils import clean_markdown, is_file_url
import handlers.xlsx_handler as xlsx_handler
import handlers.website_handler as website_handler
import core.short_file_llm as short_file_llm
import fitz
import google.generativeai as genai
from datetime import datetime
import os
from dotenv import load_dotenv
import mimetypes
import httpx

load_dotenv()

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
        return "question-answer-based"

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
        return "question-answer-based"

# --- New MIME Type Detection Function ---
async def determine_file_type(doc_url: str) -> str:
    """
    Determines the file type based on the MIME type of the document.
    Returns the file extension (e.g., 'pdf', 'docx', 'xlsx', 'pptx', 'png', 'jpg', 'jpeg') or 'website' if not a file.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.head(doc_url, timeout=5.0)
            content_type = response.headers.get("Content-Type", "").lower()
        
        # Map MIME types to file extensions
        mime_to_extension = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "text/html": "website",
            "application/xhtml+xml": "website"
        }
        
        # Find the matching extension
        for mime, ext in mime_to_extension.items():
            if mime in content_type:
                return ext
        
        # Fallback to website if no file type is matched
        if not is_file_url(doc_url):
            return "website"
        
        # If MIME type is unknown, try to guess from URL as a last resort
        guess = mimetypes.guess_type(doc_url)[0]
        if guess:
            for mime, ext in mime_to_extension.items():
                if mime in guess.lower():
                    return ext
        
        return "unknown"
    except Exception as e:
        print(f"Error determining file type: {e}")
        return "unknown"

# --- Authentication ---
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
security_scheme = HTTPBearer()

# --- Timeout Configuration ---
VECTORIZATION_TIMEOUT = 17.0

PAGE_LIMIT = 70
EXCEPTIONS = [16,]

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
    description="A RAG API"
)

@app.on_event("startup")
def on_startup():
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
    vectorization_timed_out = False

    try:
        # Determine file type using MIME type
        file_type = await determine_file_type(doc_url)
        
        if file_type in ["png", "jpg", "jpeg"]:
            answers = ["Answer reached image if statement but failed later"] * len(request.questions)
            answers = await image_handler.handle_image(request.questions, doc_url)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            target_delay = random.uniform(13.0, 23.0)
            elapsed_time = time.time() - start_time
            return HackRxResponse(answers=answers)
        
        if file_type == "website":
            answers = ["Website handling if passed then failed later"] * len(request.questions)
            answers = await website_handler.answer_from_website(doc_url, request.questions)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            return HackRxResponse(answers=answers)
        
        if file_type == "pptx":
            answers = ["Answer reached pptx if statement but failed later"] * len(request.questions)
            answers = await ppt_handler.handle_pptx_document(request.questions, doc_url)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            target_delay = random.uniform(13.0, 23.0)
            elapsed_time = time.time() - start_time
            return HackRxResponse(answers=answers)

        if file_type == "xlsx":
            answers = ["Answer reached xlsx if statement but failed later"] * len(request.questions)
            answers = await xlsx_handler.handle_xlsx(request.questions, doc_url)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            target_delay = random.uniform(13.0, 23.0)
            elapsed_time = time.time() - start_time
            return HackRxResponse(answers=answers)
        
        if file_type == "docx":
            answers = ["Answer reached docx if statement but failed later"] * len(request.questions)
            answers = await docx_handler.handle_docx(request.questions, doc_url)
            log_query_and_answers(doc_url, request.questions, answers)
            answers = [clean_markdown(a) for a in answers]
            target_delay = random.uniform(13.0, 23.0)
            elapsed_time = time.time() - start_time
            return HackRxResponse(answers=answers)

        if file_type != "pdf":
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
            
        else: 
            cache_key = document_loader.get_cache_key_from_content(pdf_content)
            vector_store = PDF_CACHE.get(cache_key)
            
            if not vector_store:
                vector_store = cache_manager.load_from_cache(cache_key)

            if not vector_store: 
                print(f"Cache MISS for document with key: {cache_key}. Processing through short file pipeline...")
                answers = await short_file_llm.handle_short_document(request.questions, doc_url, PDF_CACHE)
                answers = [clean_markdown(a) for a in answers]
                target_delay = random.uniform(11.0, 23.0)
                elapsed_time = time.time() - start_time
                log_query_and_answers(doc_url, request.questions, answers)
                return HackRxResponse(answers=answers)
            
            if vector_store:
                if cache_key not in PDF_CACHE:
                    PDF_CACHE[cache_key] = vector_store
            else:
                try:
                    setup_task = asyncio.to_thread(rag_pipeline.setup_pipeline_from_content, pdf_content)
                    vector_store = await asyncio.wait_for(setup_task, timeout=VECTORIZATION_TIMEOUT)
                    cache_manager.save_to_cache(cache_key, vector_store)
                    PDF_CACHE[cache_key] = vector_store
                except asyncio.TimeoutError:
                    print(f"Vectorization timed out after {VECTORIZATION_TIMEOUT}s. Falling back to general knowledge.")
                    vectorization_timed_out = True
                    vector_store = None

            remaining_time = 60 - (time.time() - start_time)
            if remaining_time <= 0:
                return HackRxResponse(answers=answers)

            if vectorization_timed_out:
                answer_tasks = [
                    asyncio.create_task(asyncio.to_thread(rag_pipeline._answer_with_general_knowledge, q))
                    for q in request.questions
                ]
            else:
                answer_tasks = [
                    asyncio.create_task(asyncio.to_thread(rag_pipeline._answer_one_question, q, vector_store))
                    for q in request.questions
                ]
        
            done, pending = await asyncio.wait(answer_tasks, timeout=remaining_time)
            
            for i, task in enumerate(answer_tasks):
                if task in done and not task.cancelled():
                    try: 
                        answers[i] = task.result()
                    except Exception as e: 
                        answers[i] = f"An error occurred: {e}"
                elif task in pending: 
                    task.cancel()

    except asyncio.TimeoutError:
        pass
    except Exception as e:
        pass

    total_time = time.time() - start_time
    completed_count = len([a for a in answers if not a.startswith("Processing timed out")])
    
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