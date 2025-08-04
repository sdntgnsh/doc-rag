import json
import os
import RAG.document_loader as document_loader
import rag_pipeline as rag_pipeline
import Cache_Code.cache_manager as cache_manager
from typing import Dict, Tuple
from Config import PROJECT_ROOT

json_path = os.path.join(PROJECT_ROOT, "query.json")

def initialize_cache_from_json(file_path: str = json_path) -> Dict[Tuple[int, str], object]:
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
        pdf_content = document_loader.download_pdf_content(url)
        if not pdf_content:
            continue

        cache_key = document_loader.get_cache_key_from_content(pdf_content)

        vector_store = cache_manager.load_from_cache(cache_key)

        if not vector_store:
            print(f"Not found in disk cache. Processing document with key: {cache_key}")
            vector_store = rag_pipeline.setup_pipeline_from_content(pdf_content)
            if vector_store:
                cache_manager.save_to_cache(cache_key, vector_store)

        if vector_store:
            in_memory_cache[cache_key] = vector_store
            
    return in_memory_cache


if __name__ == "__main__":
    initialize_cache_from_json()  # uses default json_path
    print("Cache initialization complete.")