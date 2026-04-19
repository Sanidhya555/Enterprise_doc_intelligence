from typing import List, Tuple
import numpy as np
from pipeline.vector_store.faiss_store import FAISSStore
from pipeline.embeddings.embedder import Embedder

class VectorRetriever:

    def __init__(self, embedder : Embedder, vector_store : FAISSStore):
        # Retriever depends on abstraction of embedder and vector store
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve(self, query : str, top_k : int = 3) -> List[Tuple[str, float]]:
        #  Convert query to embedding and search similar chunks.
        query_embedding = self.embedder.embed([query])
        results = self.vector_store.search(query_embedding, top_k = top_k)
        return results