from .base_loader import BaseLoader
from docx import Document

class DocxLoader(BaseLoader):
    def load(self, file_path : str) -> str:
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs if para.text().strip()])
        return text

        