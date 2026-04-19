from typing import List

class RecursiveChunker:

    def __init__(self, chunk_size : int = 500, overlap : int = 50):
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk size")
        
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text : str) -> List[str]:
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = min(start + self.chunk_size, text_length)
            chunk = text[start:end].strip()
            chunks.append(chunk)

            start += self.chunk_size - self.overlap

        return chunks
        