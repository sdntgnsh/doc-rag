import asyncio
import base64
import fitz  # PyMuPDF
import os
import hashlib
import pickle
from openai import AsyncOpenAI
from typing import List, Dict
from utils import clean_text
import short_file_llm
import ppt_to_pdfconv  # <-- Add this import

CACHE_DIR = "cache" # Directory to store cached query answers

def _load_query_from_cache(query_key: str) -> str:
    """Loads a query answer from a pickle file if it exists."""
    try:
        filepath = os.path.join(CACHE_DIR, f"{query_key}.pkl")
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                return pickle.load(f)
        return None
    except Exception as e:
        print(f"Error loading from query cache with key {query_key}: {e}")
        return None

async def handle_pptx_document(questions: List[str], doc_url: str) -> List[str]:
    """
    Handles a request by converting the PPTX to PDF, then answering questions using the PDF.
    """
    # Convert PPTX to PDF and get the PDF path
    pdf_path = ppt_to_pdfconv.process_query({"documents": doc_url, "questions": questions})
    print(f"NIGGAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA : {pdf_path}")
    # Now use the PDF path as the document for short_file_llm
    answers = await short_file_llm.handle_short_document(questions, pdf_path)
    print("--- PPTX Handler processing complete. ---")
    answers = [clean_text(answer) for answer in answers]
    print(f"Answers: {answers}")
    return answers