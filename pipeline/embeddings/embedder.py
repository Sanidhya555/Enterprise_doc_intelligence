from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List

class Embedder:

    def __init__(self, model_name : str = "all-MiniLM-L6-v2"):
        # load embedding model
        self.model = SentenceTransformer(model_name)

    def embed(self, texts : List[str]) -> np.ndarray:
        # convert list of text into embedding vectors
        embeddings = self.model.encode(
            texts,
            convert_to_numpy= True,
            show_progress_bar= True
        )
        return embeddings
