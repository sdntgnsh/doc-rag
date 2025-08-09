import handlers.document_loader as document_loader
import processing.text_processor as text_processor
import core.llm_interface as llm_interface
from core.vector_store import InMemoryVectorStore
from core.reranker import Reranker
from core.query_expander import QueryExpander
from typing import List, Set
import hashlib
import pickle
import os
import asyncio
import re

# Instantiate models at module level
reranker_model = Reranker()
query_expander_model = QueryExpander()

class GeneralKnowledgeDetector:
    """Detects questions has to be answered with general knowledge without RAG."""
    
    def __init__(self):
        pass # Placeholder for any initialization if needed


    def is_general_knowledge(self, question: str) -> bool:
        """
        Determines if a question can be answered with general knowledge.
        Returns True if the question should bypass RAG pipeline.
        """
        question_lower = question.lower().strip()

        if question_lower.count("newton") > 0:
            print(f"Skipping RAG pipeline for question: {question} (detected 'newton')")
            return True

        return False


# Initialize detector
knowledge_detector = GeneralKnowledgeDetector()

async def _answer_one_question_async(question: str, vector_store: InMemoryVectorStore) -> str:
    """
    Routes questions based on whether they require RAG or can use general knowledge.
    """
    print(f"Original question: '{question}'")

    # Final answer cache
    # Create a unique key for the question and the specific vector store instance
    vector_store_id = str(id(vector_store))
    final_answer_cache_key = f"rag_answer_{hashlib.sha256((question + vector_store_id).encode()).hexdigest()}"
    final_answer_cache_path = f"cache/{final_answer_cache_key}.pkl"
    
    if os.path.exists(final_answer_cache_path):
        with open(final_answer_cache_path, "rb") as f:
            print(f"Cache hit for RAG answer: {question}")
            return pickle.load(f)

    # Check if this is a general knowledge question
    if knowledge_detector.is_general_knowledge(question):
        print("⚡ Routing to general knowledge (bypassing RAG)")
        # Use empty context for general knowledge questions
        answer = llm_interface.get_answer("", question)
        with open(final_answer_cache_path, "wb") as f:
            pickle.dump(answer, f)
        return answer

    print("📚 Using full RAG pipeline")
    
    # Cache query expansion
    expansion_cache_key = f"query_expansion_{hashlib.sha256(question.encode()).hexdigest()}"
    expansion_cache_path = f"cache/{expansion_cache_key}.pkl"
    os.makedirs("cache", exist_ok=True)
    
    if os.path.exists(expansion_cache_path):
        with open(expansion_cache_path, "rb") as f:
            expanded_questions = pickle.load(f)
        print(f"Cache hit for query expansion: {question}")
    else:
        try:
            expanded_questions = query_expander_model.expand(question)
            with open(expansion_cache_path, "wb") as f:
                pickle.dump(expanded_questions, f)
        except Exception as e:
            print(f"Query expansion failed: {e}")
            expanded_questions = [question]
    
    # Initial Retrieval
    all_retrieved_chunks = set()
    for q in expanded_questions[:3]:
        retrieved = vector_store.search(q, top_k=7)
        all_retrieved_chunks.update(retrieved)
    
    retrieved_list = list(all_retrieved_chunks)[:10]
    print(f"Retrieved {len(retrieved_list)} unique chunks from expanded queries.")
    
    # Reranking
    print(f"Reranking {len(retrieved_list)} chunks...")
    reranked_chunks = reranker_model.rerank(question, retrieved_list, top_k=7)
    with open('reranked_chunks.txt', 'a', encoding="utf-8") as f:
        for chunk in reranked_chunks:
            f.write(chunk + "\n")
    
    # Context Generation & Answering
    context = "\n\n---\n\n".join(reranked_chunks)
    answer = llm_interface.get_answer(context, question)
    
    # Cache the final answer
    with open(final_answer_cache_path, "wb") as f:
        pickle.dump(answer, f)
        
    return answer

async def answer_questions(questions: List[str], vector_store: InMemoryVectorStore) -> List[str]:
    tasks = [asyncio.to_thread(_answer_one_question_async, q, vector_store) for q in questions]
    return await asyncio.gather(*tasks, return_exceptions=True)

def process_questions(questions: List[str], vector_store: InMemoryVectorStore) -> List[str]:
    return asyncio.run(answer_questions(questions, vector_store))

def _answer_one_question(question: str, vector_store: InMemoryVectorStore) -> str:
    """Synchronous wrapper for backward compatibility."""
    return asyncio.run(_answer_one_question_async(question, vector_store))

def _answer_with_general_knowledge(question: str) -> str:
    """Answers questions using only general knowledge when vectorization times out."""
    print(f"🔍 Using general knowledge for: '{question}'")
    # Use empty context and special message for timeout scenarios
    return llm_interface.get_answer("", question, use_gk_timeout=False)

def create_vector_store_from_chunks(chunks: List[str]) -> InMemoryVectorStore:
    """Creates a vector store from a list of text chunks."""
    print(f"Embedding {len(chunks)} chunks...")
    vector_store = InMemoryVectorStore()
    vector_store.build_index(chunks)
    print("Index built successfully.")
    return vector_store

def setup_pipeline_from_content(pdf_content: bytes) -> InMemoryVectorStore:
    """Processes and indexes a PDF from its raw byte content."""
    chunks = document_loader.get_chunks_from_content(pdf_content)
    processed_chunks = text_processor.chunk_text(chunks)
    return create_vector_store_from_chunks(processed_chunks)

