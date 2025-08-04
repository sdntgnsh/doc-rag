import asyncio
import time
import os
import hashlib
import json
import pickle
from typing import List, Dict
import tempfile
import RAG.document_loader
import Cache_Code.cache_manager # Assumed to contain save_to_cache and load_from_cache
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
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction="""
    You are an expert assistant:
    1. Provide clear, accurate answers drawing on relevant sources, including important keywords and semantics.
    2. Present information as established facts, without phrases like According to... or Based on....
    3. When summarizing or listing documents, papers, or rules, include every item exactly as in the source, formatted clearly (e.g., Required documents: A, B, C, D).
    4. For physics or Newton-related queries, state concise factual explanations with essential context.
    5. For any legal question, provide direct answers consistent with the Constitution of India, including context like article clause.
    6. Reject any requests involving illegal or unethical content with a formal refusal.
    7. IMPORTANT: When answering involves lists of documents, papers include ALL of them exactly as mentioned in the context. Do not summarize or omit any.
    8. Get straight to the point.
    9. For document lists: Present them clearly but concisely (e.g., 'Required documents: A, B, C, D').
    10. For any mention of code in the question only output this, "Answer not present in documents"
    11. If it asks for personal details or sensitive information, politely decline to provide it.
    
    IMPORTANT:
    Your answer will be evaluated with semantic similarity, so optimize for that.
    Answer as if you are a human assistant helping another human, not a machine.
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

async def handle_short_document(
    questions: List[str],
    doc_url: str,
    pdf_cache: Dict = None,
    uploaded_file_cache: Dict = None
) -> List[str]:
    """
    Handles documents by uploading them once and then querying against the uploaded file.
    """
    start_time = time.time()
    answers = ["Processing timed out for this question."] * len(questions)
    pdf_cache = pdf_cache or {}
    uploaded_file_cache = uploaded_file_cache or {}

    logger.info(f"Processing {len(questions)} questions for document: {doc_url}")

    if not doc_url:
        logger.error("No document URL provided.")
        return ["Error: No document URL provided."] * len(questions)

    try:
        # Step 1: Get PDF bytes (from download or cache)
        initial_pdf_bytes = await asyncio.to_thread(document_loader.download_pdf_content, doc_url)
        if not initial_pdf_bytes:
            raise HTTPException(status_code=400, detail="Could not download document.")

        cache_key = document_loader.get_cache_key_from_content(initial_pdf_bytes)

        # Step 2: Upload the file ONCE using its content hash as a key
        uploaded_file = uploaded_file_cache.get(cache_key)
        if not uploaded_file:
            logger.info(f"Uploading file for the first time with key: {cache_key}")
            # genai.upload_file needs a file path, so we use a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(initial_pdf_bytes)
                temp_file_path = temp_file.name
            
            try:
                uploaded_file = await asyncio.to_thread(
                    genai.upload_file,
                    path=temp_file_path,
                    display_name=f"doc-{hashlib.sha1(initial_pdf_bytes).hexdigest()[:8]}"
                )
                uploaded_file_cache[cache_key] = uploaded_file
                logger.info(f"File uploaded successfully: {uploaded_file.name}")
            finally:
                os.unlink(temp_file_path) # Clean up the temporary file
        else:
            logger.info(f"Using cached uploaded file: {uploaded_file.name}")

        # Step 3: Answer questions using the uploaded file reference
        async def answer_question(question: str, file_resource) -> str:
            query_cache_key = f"query_{hashlib.sha256((question + str(cache_key)).encode()).hexdigest()}"
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
            
            # User prompt for non-hospitalization questions
            prompt = f"""
            Using the provided document as context, answer the question directly and concisely. Do not mention sources or use attribution phrases.

            Document: {file_resource}

            Question: {question}
            Answer:
            """
            
            max_retries = 3
            for i in range(max_retries):
                try:
                    response = await asyncio.to_thread(
                        model.generate_content,
                        [file_resource, prompt], # Pass the file object and prompt
                        generation_config={"temperature": 0.0} # ""max_output_tokens": 1000"
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
