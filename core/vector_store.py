# vector_store.py

import os
import openai
import numpy as np
from typing import List
from dotenv import load_dotenv
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100  # Safe batch size

class InMemoryVectorStore:
    def __init__(self):
        self.embeddings = []
        self.chunks = []

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a list of texts using OpenAI Embeddings API in batches.
        Filters out empty or invalid strings.
        """
        if not texts:
            return []

        texts = [t for t in texts if isinstance(t, str) and t.strip()]  # Remove empty/invalid

        embeddings = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            try:
                response = openai.embeddings.create(
                    model=EMBED_MODEL,
                    input=batch
                )
                batch_embeddings = [record.embedding for record in response.data]
                embeddings.extend(batch_embeddings)
            except Exception as e:
                print(f"❌ Embedding batch failed: {e}")
                # To align length of embeddings with chunks in build_index
                embeddings.extend([[0.0] * 1536] * len(batch))  # assuming 1536 dims for fallback
        return embeddings

    def build_index(self, chunks: List[str]):
        self.chunks = chunks
        self.embeddings = self._embed_texts(chunks)

    def search(self, query: str, top_k: int = 5) -> List[str]:
        if not self.embeddings:
            return []

        query_embedding = self._embed_texts([query])[0]
        similarities = cosine_similarity([query_embedding], self.embeddings)[0]
        top_k_indices = np.argsort(similarities)[-top_k:][::-1]
        return [self.chunks[i] for i in top_k_indices]
