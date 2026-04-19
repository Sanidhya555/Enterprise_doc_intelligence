import os
from .base_loader import BaseLoader
from .docx_loader import DocxLoader
from .pdf_loader import PDFLoader

class IngestionPipeline:
    def __init__(self):
        self.loaders = {".pdf": PDFLoader(), ".docx": DocxLoader()}

    def process(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.loaders:
            raise ValueError(f"Unsupported file format: {ext}")
        return self.loaders[ext].load(file_path)
