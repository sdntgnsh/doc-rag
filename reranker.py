# reranker.py
from sentence_transformers import CrossEncoder
from typing import List

class Reranker:
    """
    A reranker class that uses a CrossEncoder model to re-order documents
    based on their relevance to a query.
    """
    def __init__(self, model_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'):
        """
        Initializes the CrossEncoder model. This model is lightweight and fast,
        making it ideal for a reranking step.
        """
        # The model is loaded only once when the class is instantiated.
        self.model = CrossEncoder(model_name)
        print(f"Reranker model '{model_name}' loaded.")

    def rerank(self, query: str, documents: List[str], top_k: int = 3) -> List[str]:
        """
        Reranks a list of documents based on a query.

        Args:
            query: The user's question.
            documents: A list of documents retrieved from the initial search.
            top_k: The number of top documents to return.

        Returns:
            A sorted list of the top_k most relevant documents.
        """
        if not documents:
            return []

        # Create pairs of [query, document] for the model
        model_input = [[query, doc] for doc in documents]
        
        # Predict scores for each pair
        scores = self.model.predict(model_input)
        
        # Pair documents with their scores
        scored_docs = list(zip(scores, documents))
        
        # Sort the documents by score in descending order
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # Return the text of the top_k documents
        return [doc for score, doc in scored_docs[:top_k]]

