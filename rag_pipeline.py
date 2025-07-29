# rag_pipeline.py
import document_loader
import text_processor
import llm_interface
from vector_store import InMemoryVectorStore
from reranker import Reranker
from query_expander import QueryExpander # Import the new Gemini-powered QueryExpander
from typing import List

# --- Instantiate all models at the module level ---
# This ensures they are loaded only once when the application starts.
reranker_model = Reranker()
query_expander_model = QueryExpander()

def _answer_one_question(question: str, vector_store: InMemoryVectorStore) -> str:
    """
    Expands the user's query, retrieves context, reranks it, and generates an answer.
    """
    print(f"Original question: '{question}'")
    
    # Step 1: Query Expansion using the Gemini-powered expander
    expanded_questions = query_expander_model.expand(question)
    
    # Step 2: Initial Retrieval for all expanded questions
    # Use a set to automatically handle duplicate chunks from different queries.
    all_retrieved_chunks = set()
    for q in expanded_questions:
        # Retrieve a smaller number of chunks per query to cast a wide net.
        retrieved = vector_store.search(q, top_k=5)
        all_retrieved_chunks.update(retrieved)
    
    retrieved_list = list(all_retrieved_chunks)
    print(f"Retrieved {len(retrieved_list)} unique chunks from expanded queries.")
    
    # Step 3: Reranking
    # Rerank the combined, unique results using the original question for relevance.
    print(f"Reranking {len(retrieved_list)} chunks...")
    reranked_chunks = reranker_model.rerank(question, retrieved_list, top_k=5)
    with open('reranked_chunks.txt', 'a', encoding="utf-8") as f:
        for chunk in reranked_chunks:
            f.write(chunk + "\n")
    # Step 4: Context Generation & Answering
    context = "\n\n---\n\n".join(reranked_chunks)
    answer = llm_interface.get_answer(context, question)
    return answer

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
