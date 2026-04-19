from .base_loader import BaseLoader
from docx import Document

class DocxLoader(BaseLoader):
    def load(self, file_path: str) -> str:
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
