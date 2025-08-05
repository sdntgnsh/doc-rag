# preprocessor.py
import json
import document_loader
import rag_pipeline
import cache_manager  # Import the new cache manager
from typing import Dict, Tuple

def initialize_cache_from_json(file_path: str) -> Dict[Tuple[int, str], object]:
    """
    Reads a JSON file, checks for a disk cache first, and processes documents if not cached.
    """
    in_memory_cache = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            queries = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Could not read or parse {file_path}: {e}")
        return in_memory_cache

    unique_urls = sorted(list(set(item['documents'] for item in queries if 'documents' in item)))
    print(f"Found {len(unique_urls)} unique documents to pre-process or load from cache.")

    for url in unique_urls:
        print(f"\n--- Checking document: {url} ---")
        if "principia_newton.pdf" in url:
            print(f"Skipping Newton document: {url}")
            continue
        
        if url.lower().split('?')[0].endswith('.docx'):
            print(f"Skipping DOCX file: {url}")
            continue
            
        if not url.lower().split('?')[0].endswith('.pdf'):
            print(f"Skipping non-PDF file: {url}")
            continue
        
        pdf_content = document_loader.download_pdf_content(url)
        if not pdf_content:
            continue

        cache_key = document_loader.get_cache_key_from_content(pdf_content)
        
        # Try to load from disk first
        vector_store = cache_manager.load_from_cache(cache_key)

        if not vector_store:
            # If not on disk, process it
            print(f"Not found in disk cache. Processing document with key: {cache_key}")
            vector_store = rag_pipeline.setup_pipeline_from_content(pdf_content)
            if vector_store:
                # Save the new object to disk for the next run
                cache_manager.save_to_cache(cache_key, vector_store)
        
        if vector_store:
            # Add to the in-memory cache for the current session
            in_memory_cache[cache_key] = vector_store
            
    return in_memory_cache
