import faiss
import numpy as np
from typing import List

class FAISSStore:

    def __init__(self, dimension, embedder):
        self.dimension = dimension
        self.embedder = embedder
        self.index = faiss.IndexFlatIP(dimension)
        self.text_chunks = []

    def _normalize(self, vectors: np.ndarray):
        faiss.normalize_L2(vectors)

    def add(self, embeddings: np.ndarray, chunks: List[dict]):
        embeddings = embeddings.astype("float32")
        self._normalize(embeddings)

        self.index.add(embeddings)
        self.text_chunks.extend(chunks)

    def search(self, query_embedding: np.ndarray, top_k: int = 3):
        if self.index.ntotal == 0:
            return []

        query_embedding = query_embedding.astype("float32")
        self._normalize(query_embedding)

        scores, indices = self.index.search(query_embedding, top_k)

        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < len(self.text_chunks):
                results.append({
                    "chunk": self.text_chunks[idx],
                    "score": float(score)
                })

        return results

    def save(self, index_path: str, chunks_path: str):
        faiss.write_index(self.index, index_path)
        np.save(chunks_path, np.array(self.text_chunks, dtype=object))

    def load(self, index_path: str, chunks_path: str):
        self.index = faiss.read_index(index_path)
        self.text_chunks = list(np.load(chunks_path, allow_pickle=True))

    def rebuild_index(self, chunks: List[dict]):
        self.index = faiss.IndexFlatIP(self.dimension)
        self.text_chunks = chunks

        if not chunks:
            return

        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedder.embed(texts)
        embeddings = np.array(embeddings).astype("float32")

        self._normalize(embeddings)
        self.index.add(embeddings)