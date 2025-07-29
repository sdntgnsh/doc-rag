# vector_store.py
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import List

class InMemoryVectorStore:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initializes the vector store with a sentence transformer model.
        """
        self.model = SentenceTransformer(model_name)
        self.chunks = []
        self.embeddings = None

    def build_index(self, chunks: List[str]):
        """
        Creates embeddings for the text chunks and stores them.
        """
        self.chunks = chunks
        print(f"Embedding {len(chunks)} chunks...")
        self.embeddings = self.model.encode(chunks, show_progress_bar=False)
        print("Index built successfully.")

    def search(self, query: str, top_k: int = 3) -> List[str]:
        """
        Finds the top_k most relevant chunks for a given query.
        """
        if self.embeddings is None:
            raise RuntimeError("Index has not been built. Call build_index() first.")
        
        query_embedding = self.model.encode([query], show_progress_bar=False)
        
        # Calculate similarities and get the top_k indices
        sims = cosine_similarity(query_embedding, self.embeddings)[0]
        top_k_indices = np.argsort(sims)[-top_k:][::-1]
        
        return [self.chunks[i] for i in top_k_indices]