from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(title="Enterprise Document Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    max_size = 10 * 1024 * 1024  # 10MB
    if request.headers.get("content-length"):
        if int(request.headers["content-length"]) > max_size:
            raise HTTPException(status_code=413, detail="File too large")
    return await call_next(request)