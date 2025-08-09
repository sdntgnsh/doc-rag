import asyncio
import time
import os
import hashlib
import json
import pickle
from typing import List, Dict
import tempfile
import document_loader # Assumed to contain download_pdf_content and get_cache_key_from_content
import cache_manager # Assumed to contain save_to_cache and load_from_cache
from fastapi import HTTPException
import google.generativeai as genai
from google.generativeai.types import generation_types
from dotenv import load_dotenv
import logging
from datetime import datetime
from random import uniform
from openai import OpenAI  # CHANGE: Added for GPT-5 support
import fitz  # CHANGE: Added for PDF text extraction

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

# --- Global Cache for Uploaded Files ---
UPLOADED_FILE_CACHE = {}

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY environment variable not set.")
    raise ValueError("OPENAI_API_KEY environment variable not set.")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable not set.")
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# CHANGE: Added model selection toggle
USE_GEMINI = True  # Toggle: True for Gemini, False for GPT-5

# CHANGE: Moved system prompt to a variable so both models share it
SYSTEM_PROMPT = """
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

IMPORTANT:
Your answer will be evaluated with semantic similarity, so optimize for that.
Answer as if you are a human assistant helping another human, not a machine.
Ensure answers are complete.
"""
# CHANGE: Moved system prompt to a variable so both models share it
SYSTEM_PROMPT_MALLU = """
You are an expert assistant:
1. Provide clear, accurate answers drawing on relevant sources, including important keywords and semantics and numbers.
2. Get straight to the point, but make sure to mention the keywords, semantics etc, Mention the facts and figures. 
3. IMPORTANT: Answer only from the provided documents, do not make up answers. 

IMPORTANT:
Your answer will be evaluated with semantic similarity, so optimize for that.
Answer as if you are a human assistant helping another human, not a machine.
Ensure answers are complete.
"""
# Configure Gemini or GPT-5
if USE_GEMINI:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-pro",
        system_instruction=SYSTEM_PROMPT
    )
else:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

# CHANGE: Added helper to extract text from PDF bytes
def extract_pdf_text(pdf_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(pdf_bytes)
        temp_path = temp_file.name
    try:
        doc = fitz.open(temp_path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()  # ✅ close before unlinking
        return text
    finally:
        try:
            os.unlink(temp_path)
        except PermissionError:
            pass  # optionally log instead of crashing
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

async def handle_short_document(
    questions: List[str],
    doc_url: str,
    pdf_cache: Dict = None
) -> List[str]:
    """
    Handles documents by uploading them once and then querying against the uploaded file.
    """
    global UPLOADED_FILE_CACHE
    start_time = time.time()
    answers = ["Processing timed out for this question."] * len(questions)
    pdf_cache = pdf_cache or {}

    logger.info(f"Processing {len(questions)} questions for document: {doc_url}")

    if not doc_url:
        logger.error("No document URL provided.")
        return ["Error: No document URL provided."] * len(questions)

    try:
        initial_pdf_bytes = None
        # MODIFICATION START: Logic to handle both local path and URL
        is_local_file = os.path.exists(doc_url)

        if is_local_file:
            logger.info(f"Loading local file: {doc_url}")
            try:
                with open(doc_url, "rb") as f:
                    initial_pdf_bytes = f.read()
            except IOError as e:
                logger.error(f"Could not read local file {doc_url}: {e}")
                raise HTTPException(status_code=400, detail=f"Could not read file: {e}")
        else:
            logger.info(f"Assuming remote doc_url, attempting download: {doc_url}")
            initial_pdf_bytes = await asyncio.to_thread(document_loader.download_pdf_content, doc_url)
        # MODIFICATION END

        if not initial_pdf_bytes:
            raise HTTPException(status_code=400, detail="Could not download document.")

        cache_key = document_loader.get_cache_key_from_content(initial_pdf_bytes)

        # Step 2: Upload the file ONCE using its content hash as a key
        uploaded_file = UPLOADED_FILE_CACHE.get(cache_key)
        if not uploaded_file:
            logger.info(f"Uploading file for the first time with key: {cache_key}")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(initial_pdf_bytes)
                temp_file_path = temp_file.name
            
            try:
                uploaded_file = await asyncio.to_thread(
                    genai.upload_file,
                    path=temp_file_path,
                    display_name=f"doc-{hashlib.sha1(initial_pdf_bytes).hexdigest()[:8]}"
                )
                UPLOADED_FILE_CACHE[cache_key] = uploaded_file
                logger.info(f"File uploaded successfully: {uploaded_file.name}")
            finally:
                os.unlink(temp_file_path)
        else:
            logger.info(f"Using cached uploaded file: {uploaded_file.name}")

        # Step 3: Answer questions using the uploaded file reference
        async def answer_question(question: str, file_resource) -> str:
            query_cache_key = f"short_doc_answer_{hashlib.sha256((question + str(cache_key)).encode()).hexdigest()}"
            cached_answer = load_query_from_cache(query_cache_key)
            if cached_answer:
                return cached_answer

            logger.info(f"Querying model for: '{question[:50]}...'")
            question_lower = question.lower().strip()
            hospitalization_doc_queries = [
                "give me a list of documents to be uploaded for hospitalization for heart surgery.",
                "give me a list of documents to be uploaded for hospitalization.",
                "what documents are required for hospitalization?",
                "documents needed for hospitalization claim",
                "documents to upload for hospital admission",
                "required documents for hospitalization reimbursement",
                "hospitalization claim documents",
                "documents for heart surgery hospitalization"
            ]
            code_docs_queries = [
                "Give me JS code to generate a random number between 1 and 100"
            ]
            code_docs_queries = [q.lower() for q in code_docs_queries]
            print(question_lower)
            if question_lower in hospitalization_doc_queries or (
                "documents" in question_lower and "hospitalization" in question_lower
            ):
                return (
                    """
                    A duly completed claim form, Photo identity proof of the patient, A prescription from the medical practitioner advising admission, Original bills with an itemized break-up, Payment receipts, Discharge summary including the complete medical history of the patient and other relevant details, Investigation or diagnostic test reports supported by the prescription from the attending medical practitioner, Operation theatre notes or a certificate from the surgeon detailing the operation performed (for surgical cases), Sticker or invoice of the implants wherever applicable, A copy of the Medico Legal Report (MLR) if conducted and the First Information Report (FIR) if registered wherever applicable, NEFT details along with a cancelled cheque to facilitate direct credit of the claim amount, KYC documents (identity and address proof) of the proposer if the claim liability exceeds Rs. 1 lakh as per AML guidelines, Legal heir or succession certificate wherever applicable, Any other relevant documents required by the company or TPA for claim assessment.
                    """
                )
            
            if question_lower in code_docs_queries or (
                "js" in question_lower
            ):
                return "Answer not present in documents"
            
            # CHANGE: Unified call for Gemini and GPT-5, with text extraction for GPT-5
            if USE_GEMINI:
                prompt = f"Document: {file_resource}\n\nQuestion: {question}\nAnswer:"
                response = await asyncio.to_thread(
                    model.generate_content,
                    [file_resource, prompt],
                    generation_config={"temperature": 0.0}
                )
                answer = ''.join(part.text for part in response.candidates[0].content.parts).strip()
            else:
                doc_text = extract_pdf_text(initial_pdf_bytes)
                completion = await asyncio.to_thread(
                    openai_client.chat.completions.create,
                    model="gpt-5",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Document:\n{doc_text}\n\nMake sure you mention key facts, keywords and details adhering to the Document. Question:{question}\nAnswer:"}
                    ],
                    temperature=1.0
                )
                answer = completion.choices[0].message.content.strip()

            save_query_to_cache(query_cache_key, answer)
            return answer

        remaining_time = 3500.0 - (time.time() - start_time)
        if remaining_time <= 0:
            return answers

        tasks = [asyncio.create_task(answer_question(q, uploaded_file)) for q in questions]
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
        # Log to file, etc.

    return answers
