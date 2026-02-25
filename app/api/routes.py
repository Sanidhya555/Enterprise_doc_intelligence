from fastapi import APIRouter, HTTPException
from app.services.rag_services import RAGService
from fastapi import UploadFile, File
from pydantic import BaseModel
import shutil
import os
from app.core.security import create_access_token,verify_token
from app.core.logger import setup_logger
from app.core.config import settings
from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter()
rag_service = RAGService()
logger = setup_logger()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

class QueryRequest(BaseModel):
    question : str


@router.get("/health")
def health():
    return {
        "status": "healthy",
        "documents_indexed": len(rag_service.list_documents())
    }

@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    current_user: str = Depends(verify_token)
):

    if not file.filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    MAX_SIZE_MB = 10
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")

    filename = os.path.basename(file.filename)

    existing_files = [
        doc["filename"] for doc in rag_service.list_documents()
    ]

    if filename.lower() in [f.lower() for f in existing_files]:
        raise HTTPException(status_code=400, detail="Document already indexed")

    save_path = os.path.join("data/raw", filename)

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = rag_service.add_document(save_path)

    logger.info(f"User {current_user} uploaded {filename}")

    return result

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == settings.ADMIN_USERNAME and form_data.password == settings.ADMIN_PASSWORD:
        token = create_access_token({"sub": form_data.username})
        return {
            "access_token": token,
            "token_type": "bearer"
        }

    logger.warning(f"Failed login attempt for user: {form_data.username}")
    raise HTTPException(status_code=401, detail="Invalid credentials")

@router.post("/query")
def ask_question(
    request: QueryRequest,
    user: str = Depends(verify_token)
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    answer = rag_service.query(request.question)

    return {"answer": answer}

@router.get("/documents")
def list_documents(user: str = Depends(verify_token)):
    return rag_service.list_documents()

@router.delete("/documents/{filename}")
def delete_document(filename : str, user : str = Depends(verify_token)):
    logger.info(f"User {user} deleted {filename}")
    return rag_service.delete_document(filename)


@router.get("/metrics")
def metrics(user: str = Depends(verify_token)):

    total_chunks = len(rag_service.vector_store.text_chunks)

    unique_docs = len(set(
        chunk["filename"]
        for chunk in rag_service.vector_store.text_chunks
        if isinstance(chunk, dict)
    ))

    return {
        "documents_indexed": unique_docs,
        "total_chunks": total_chunks,
        "vector_dimension": rag_service.vector_store.dimension
    }
