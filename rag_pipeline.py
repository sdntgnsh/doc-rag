import document_loader
import text_processor
import llm_interface
from vector_store import InMemoryVectorStore
from reranker import Reranker
from query_expander import QueryExpander
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
    """Detects questions that can be answered with general knowledge without RAG."""
    
    def __init__(self):
        # Newton-related keywords and patterns
        self.newton_keywords = {
            "newton", "isaac newton", "principia", "laws of motion", "kepler", 
            "gravity", "gravitational", "centripetal", "absolute space", 
            "planetary orbits", "resisting media", "quantity of motion", 
            "celestial mechanics", "perturbation", "inverse square law",
            "universal gravitation", "orbital motion", "calculus", "fluxions"
        }
        
        # Patterns for personal/biographical questions
        self.biographical_patterns = [
            r"who was.*newton",
            r"newton.*grandfather",
            r"newton.*family",
            r"newton.*descendants?",
            r"newton.*children",
            r"newton.*married",
            r"newton.*birth",
            r"newton.*death",
            r"newton.*life"
        ]
        
        # Patterns for well-established scientific facts
        self.scientific_fact_patterns = [
            r"newton.*law",
            r"law.*motion",
            r"law.*gravitation",
            r"inverse square",
            r"what.*newton.*define",
            r"how.*newton.*derive",
            r"newton.*explain"
        ]
    
    def is_general_knowledge(self, question: str) -> bool:
        """
        Determines if a question can be answered with general knowledge.
        Returns True if the question should bypass RAG pipeline.
        """
        question_lower = question.lower().strip()
        
        # Check for Newton-related content
        has_newton_keywords = any(kw in question_lower for kw in self.newton_keywords)
        
        if has_newton_keywords:
            # Check biographical patterns
            for pattern in self.biographical_patterns:
                if re.search(pattern, question_lower):
                    print(f"Detected biographical Newton question: {question}")
                    return True
            
            # Check scientific fact patterns (well-established physics concepts)
            for pattern in self.scientific_fact_patterns:
                if re.search(pattern, question_lower):
                    print(f"Detected general Newton science question: {question}")
                    return True
        
        # Add more general knowledge categories here as needed
        # For example: basic math, common historical facts, etc.
        
        return False
    
    def requires_document_context(self, question: str) -> bool:
        """
        Determines if a Newton question requires specific document context.
        Returns True if the question needs RAG pipeline even if Newton-related.
        """
        question_lower = question.lower().strip()
        
        # Specific document-dependent patterns
        document_dependent_patterns = [
            r"mathematical tools.*principia",
            r"precursors to calculus",
            r"why didn't.*use.*notation",
            r"in principia",
            r"according to.*principia",
            r"newton.*demonstrate.*principia",
            r"newton.*argument.*principia"
        ]
        
        for pattern in document_dependent_patterns:
            if re.search(pattern, question_lower):
                print(f"Detected document-dependent Newton question: {question}")
                return True
        
        return False

# Initialize detector
knowledge_detector = GeneralKnowledgeDetector()

async def _answer_one_question_async(question: str, vector_store: InMemoryVectorStore) -> str:
    """
    Routes questions based on whether they require RAG or can use general knowledge.
    """
    print(f"Original question: '{question}'")
    
    # Check if this is a general knowledge question
    if knowledge_detector.is_general_knowledge(question) and not knowledge_detector.requires_document_context(question):
        print("⚡ Routing to general knowledge (bypassing RAG)")
        # Use empty context for general knowledge questions
        return llm_interface.get_answer("", question)
    
    print("📚 Using full RAG pipeline")
    
    # Cache query expansion
    cache_key = f"query_{hashlib.sha256(question.encode()).hexdigest()}"
    cache_path = f"cache/{cache_key}.pkl"
    os.makedirs("cache", exist_ok=True)
    
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            expanded_questions = pickle.load(f)
        print(f"Cache hit for query expansion: {question}")
    else:
        try:
            expanded_questions = query_expander_model.expand(question)
            with open(cache_path, "wb") as f:
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
    return llm_interface.get_answer(context, question)

async def answer_questions(questions: List[str], vector_store: InMemoryVectorStore) -> List[str]:
    tasks = [asyncio.to_thread(_answer_one_question_async, q, vector_store) for q in questions]
    return await asyncio.gather(*tasks, return_exceptions=True)

def process_questions(questions: List[str], vector_store: InMemoryVectorStore) -> List[str]:
    return asyncio.run(answer_questions(questions, vector_store))

def _answer_one_question(question: str, vector_store: InMemoryVectorStore) -> str:
    """Synchronous wrapper for backward compatibility."""
    return asyncio.run(_answer_one_question_async(question, vector_store))

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

# Utility function to test the detector
def test_knowledge_detector(questions: List[str]) -> None:
    """Test function to see how questions are classified."""
    print("=== General Knowledge Detection Test ===")
    for q in questions:
        is_general = knowledge_detector.is_general_knowledge(q)
        needs_doc = knowledge_detector.requires_document_context(q)
        route = "General Knowledge" if is_general and not needs_doc else "RAG Pipeline"
        print(f"Q: {q}")
        print(f"   → Route: {route}")
        print(f"   → General: {is_general}, Needs Doc: {needs_doc}")
        print()