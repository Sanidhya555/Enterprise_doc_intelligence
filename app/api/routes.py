"""FastAPI routes — all endpoints under /api prefix."""
import json
import os
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.config import settings
from app.core.logger import setup_logger
from app.core.security import create_access_token, verify_token
from app.services.rag_services import RAGService

router = APIRouter()
rag = RAGService()
logger = setup_logger()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    session_id: str = "default"
    top_k: int = 5
    stream: bool = False
    use_cache: bool = True


class SessionRequest(BaseModel):
    session_id: str


class TitleRequest(BaseModel):
    session_id: str
    title: str


# ─── Health ───────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "healthy", "documents_indexed": len(rag.list_documents())}


# ─── Auth ─────────────────────────────────────────────────────────────────────

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if (
        form_data.username == settings.ADMIN_USERNAME
        and form_data.password == settings.ADMIN_PASSWORD
    ):
        token = create_access_token({"sub": form_data.username})
        return {"access_token": token, "token_type": "bearer"}
    logger.warning("Failed login attempt: %s", form_data.username)
    raise HTTPException(status_code=401, detail="Invalid credentials")


# ─── Documents ────────────────────────────────────────────────────────────────

@router.post("/upload")
def upload_document(file: UploadFile = File(...), user: str = Depends(verify_token)):
    if not file.filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 10 MB limit.")

    filename = os.path.basename(file.filename)
    existing = {d["filename"].lower() for d in rag.list_documents()}
    if filename.lower() in existing:
        raise HTTPException(status_code=400, detail="Document already indexed.")

    os.makedirs("data/raw", exist_ok=True)
    save_path = os.path.join("data/raw", filename)
    with open(save_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    result = rag.add_document(save_path)
    logger.info("User %s uploaded %s", user, filename)
    return result


@router.get("/documents")
def list_documents(user: str = Depends(verify_token)):
    return rag.list_documents()


@router.delete("/documents/{filename}")
def delete_document(filename: str, user: str = Depends(verify_token)):
    logger.info("User %s deleting %s", user, filename)
    return rag.delete_document(filename)


# ─── Query ────────────────────────────────────────────────────────────────────

@router.post("/query")
async def ask_question(request: QueryRequest, user: str = Depends(verify_token)):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if request.stream:
        async def event_stream():
            try:
                async for token in rag.query_stream(
                    request.question, request.session_id, request.top_k
                ):
                    yield f"data: {json.dumps({'token': token})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return rag.query(
        request.question,
        session_id=request.session_id,
        top_k=request.top_k,
        use_cache=request.use_cache,
    )


# ─── Sessions ─────────────────────────────────────────────────────────────────

@router.get("/sessions")
def list_sessions(user: str = Depends(verify_token)):
    return rag.list_sessions()


@router.post("/sessions/new")
def new_session(body: SessionRequest, user: str = Depends(verify_token)):
    return rag.new_session(body.session_id)


@router.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str, user: str = Depends(verify_token)):
    return rag.get_session_messages(session_id)


@router.put("/sessions/{session_id}/title")
def update_session_title(session_id: str, body: TitleRequest, user: str = Depends(verify_token)):
    rag.long_term.update_session_title(session_id, body.title)
    return {"status": "updated"}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, user: str = Depends(verify_token)):
    return rag.delete_session(session_id)


# ─── Evaluation ───────────────────────────────────────────────────────────────

@router.post("/evaluate/retrieval")
def evaluate_retrieval(top_k: int = 5, user: str = Depends(verify_token)):
    return rag.evaluator.evaluate_retrieval(top_k=top_k)


@router.post("/evaluate/batch")
def evaluate_batch(user: str = Depends(verify_token)):
    return rag.evaluator.run_batch_eval()


@router.post("/evaluate/answer_relevancy")
def evaluate_answer_relevancy(
    question: str,
    answer: str,
    user: str = Depends(verify_token),
):
    return rag.evaluator.evaluate_answer_relevance(question, answer)


# ─── Metrics ──────────────────────────────────────────────────────────────────

@router.get("/metrics")
def metrics(user: str = Depends(verify_token)):
    return rag.get_metrics()
