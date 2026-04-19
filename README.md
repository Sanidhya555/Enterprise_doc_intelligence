# 🧠 Document Intelligence 

A production-grade RAG pipeline with a **ChatGPT-like UI**, hybrid retrieval, conversation memory, reranking, query expansion, and guardrails.

---

## ✨ What's in Project

| Feature | Details |
|---|---|
| **ChatGPT-like UI** | Streaming chat, session sidebar with load/delete, markdown rendering, code highlighting |
| **Hybrid Retrieval** | BM25 (sparse) + FAISS (dense) fused via Reciprocal Rank Fusion |
| **Cross-Encoder Reranker** | `ms-marco-MiniLM-L-6-v2` reranks retrieved chunks for precision |
| **Query Expansion** | LLM generates 2 alternative phrasings → broader recall |
| **Short-term Memory** | In-memory sliding window (last 10 turns) included in every prompt |
| **Long-term Memory** | All sessions and messages persisted to SQLite |
| **Guardrails** | Input: length, harmful content, prompt injection. Output: sanitization |
| **Evaluation** | Recall@K, Precision@K, MRR@K, NDCG@K + faithfulness heuristic |
| **Latency Optimization** | Query cache (TTL 10 min), async streaming, batch embeddings |
| **Streaming** | Token-by-token SSE streaming responses in the UI |

---

## 🏗️ Architecture

```
Browser (ChatGPT-like UI)
  │  SSE streaming / REST
  ▼
FastAPI Backend  (/api/*)
  │
  ├─ Guardrails (input check)
  ├─ Query Expansion (LLM → 2 sub-queries)
  │
  ├─ Hybrid Retriever
  │    ├─ FAISS Dense Retriever (SentenceTransformers all-MiniLM-L6-v2)
  │    └─ BM25 Sparse Retriever (rank-bm25)
  │         └─ Reciprocal Rank Fusion
  │
  ├─ Cross-Encoder Reranker (ms-marco-MiniLM-L-6-v2)
  │
  ├─ Short-term Memory (in-memory, per session)
  ├─ Long-term Memory (SQLite, persisted)
  │
  ├─ Prompt Builder (context + history)
  ├─ LLM Generator (Ollama/Mistral or OpenAI)
  │
  ├─ Output Guardrails
  └─ Query Cache (TTL dict, 200 entries)
```

---

## 📂 Project Structure

```
rag /
├── backend/
│   ├── app/
│   │   ├── api/routes.py          # All FastAPI endpoints
│   │   ├── core/                  # Config, logger, security (JWT)
│   │   ├── services/rag_services.py  # Central orchestrator
│   │   └── main.py
│   ├── pipeline/
│   │   ├── chunking/              # RecursiveChunker
│   │   ├── embeddings/            # SentenceTransformer embedder
│   │   ├── evaluation/            # Recall, Precision, MRR, NDCG, faithfulness
│   │   ├── guardrails/            # Input & output safety
│   │   ├── ingestion/             # PDF + DOCX loaders
│   │   ├── llm/                   # Ollama + OpenAI (sync/async/stream)
│   │   ├── memory/                # Short-term + long-term memory
│   │   ├── query_expansion/       # LLM-based query expansion
│   │   ├── reranker/              # Cross-encoder reranker
│   │   ├── retriever/             # Vector, BM25, Hybrid retrievers
│   │   └── vector_store/          # FAISS store
│   ├── data/                      # Embeddings, raw docs, memory.db
│   ├── Dockerfile
│   ├── requirements.txt
│   └── eval_set.json
├── frontend/
│   ├── app.py                     # Streamlit ChatGPT-like UI
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

---

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Install Ollama
https://ollama.com/download
ollama serve
ollama pull mistral
```

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create .env
cat > .env << EOF
SECRET_KEY=your-secret-key-here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
USE_OLLAMA=true
EOF

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend

In a new terminal:

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

### 4. Open the UI

Visit **http://localhost:8501** for the Streamlit frontend (default Streamlit port).

Login with `admin` / `admin123`.

### 5. (Optional) OpenAI instead of Ollama

```env
USE_OLLAMA=false
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

---

## 🐳 Docker

```bash
docker-compose up --build
```

Then open **http://localhost:8501** for the frontend and **http://localhost:8000** for the API.

---

## 📡 API Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/login` | Get JWT token |
| GET  | `/api/health` | Health check |
| POST | `/api/upload` | Upload PDF/DOCX |
| GET  | `/api/documents` | List documents |
| DELETE | `/api/documents/{filename}` | Delete document |
| POST | `/api/query` | Query (supports `stream: true`) |
| GET  | `/api/sessions` | List chat sessions |
| POST | `/api/sessions/new` | Create session |
| GET  | `/api/sessions/{id}/messages` | Session history |
| DELETE | `/api/sessions/{id}` | Delete session |
| GET  | `/api/metrics` | System metrics |
| POST | `/api/evaluate/retrieval` | Run retrieval evaluation |

### Query Request

```json
{
  "question": "What are the key findings?",
  "session_id": "sess_abc123",
  "top_k": 5,
  "stream": true,
  "use_cache": true
}
```

### Query Response (non-streaming)

```json
{
  "answer": "The key findings include...",
  "sources": [
    {"filename": "report.pdf", "chunk_id": 12, "score": 0.87}
  ],
  "latency_ms": 1243,
  "cached": false,
  "expanded_queries": ["What are the key findings?", "What are the main results?"]
}
```

---

## 📊 Evaluation Dataset Format

Create `backend/data/eval_dataset.json`:

```json
[
  {"query": "What is machine learning?", "relevant_keyword": "machine learning"},
  {"query": "How does RAG work?",        "relevant_keyword": "retrieval augmented"}
]
```

Then call `POST /api/evaluate/retrieval?top_k=5`.

---

## ⚙️ Configuration

| Env Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | — | JWT signing key (required) |
| `ADMIN_USERNAME` | `admin` | Login username |
| `ADMIN_PASSWORD` | `admin123` | Login password |
| `USE_OLLAMA` | `true` | Use Ollama instead of OpenAI |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `mistral` | Ollama model name |
| `OPENAI_API_KEY` | — | OpenAI key (if USE_OLLAMA=false) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |

---

## 👨‍💻 Author

**Sanidhya Sachin Kulkarni** — AI/ML Engineer

---

## 📜 License

MIT
