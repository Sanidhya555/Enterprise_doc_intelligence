# 🧠 Enterprise Document Intelligence System  
### Retrieval-Augmented Generation (RAG) with FAISS + FastAPI + Ollama

A production-ready enterprise document intelligence system that enables secure document ingestion, semantic search, and AI-powered question answering using Retrieval-Augmented Generation (RAG).

Built with FastAPI, FAISS, SentenceTransformers, and Ollama (Mistral), with a Streamlit frontend and Docker support.

---

## 🚀 Features

- ✅ Secure JWT Authentication
- ✅ PDF Document Ingestion
- ✅ Intelligent Text Chunking
- ✅ SentenceTransformer Embeddings
- ✅ FAISS Vector Search (Cosine Similarity)
- ✅ Retrieval-Augmented Generation (RAG)
- ✅ Ollama LLM Integration (Mistral)
- ✅ Streamlit Frontend UI
- ✅ Dockerized Deployment
- ✅ Production-Ready Project Structure

---

## 🏗️ System Architecture

```text
User
  ↓
Streamlit Frontend
  ↓
FastAPI Backend
  ↓
Embedding Model (SentenceTransformers)
  ↓
FAISS Vector Store
  ↓
Top-K Retrieval
  ↓
Prompt Builder
  ↓
Ollama (Mistral LLM)
  ↓
Final Answer
```

---

## 📂 Project Structure

```bash
enterprise_doc_intelligence/
│
├── app/                     # FastAPI application
│   ├── api/                 # Route definitions
│   ├── core/                # Config & security
│   ├── services/            # Business logic
│   └── main.py
│
├── pipeline/                # RAG pipeline modules
│   ├── chunking/
│   ├── embeddings/
│   ├── ingestion/
│   ├── retriever/
│   ├── vector_store/
│   ├── llm/
│   └── evaluation/
│
├── frontend/                # Streamlit UI
│   └── app.py
│
├── docker/
│   └── Dockerfile
│
├── data/
│   └── embeddings/          # FAISS index stored here (runtime generated)
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI |
| Frontend | Streamlit |
| Vector Database | FAISS (IndexFlatIP) |
| Embeddings | sentence-transformers |
| LLM | Ollama (Mistral) |
| Authentication | JWT |
| Deployment | Docker |
| Language | Python 3.10+ |

---

## 🔐 Authentication

All protected endpoints require a valid JWT token.

### Login Endpoint


POST /login


Default credentials (configurable via `.env`):


username: admin
password: admin123


---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|------------|
| GET | /health | Health check |
| POST | /login | Generate JWT token |
| POST | /upload | Upload document |
| GET | /documents | List indexed documents |
| DELETE | /documents/{filename} | Delete document |
| POST | /query | Ask a question |
| GET | /metrics | System metrics |

---

## 🧠 RAG Workflow

1. Upload PDF document
2. Extract text
3. Chunk with overlap
4. Generate embeddings
5. Normalize embeddings
6. Store in FAISS (cosine similarity)
7. On query:
   - Embed query
   - Retrieve top-k chunks
   - Build contextual prompt
   - Send to Ollama
   - Return final answer

---

## 🖥️ Local Setup

### 1️⃣ Clone Repository

```bash
git clone https://github.com/Sanidhya555/Enterprise_doc_intelligence.git
cd Enterprise_doc_intelligence
```

---

### 2️⃣ Create Virtual Environment

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
```

---

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4️⃣ Setup Environment Variables

Create a `.env` file in the root directory:

```env
SECRET_KEY=your_secret_key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
OLLAMA_BASE_URL=http://localhost:11434
```

---

### 5️⃣ Start Ollama

Install Ollama from:

https://ollama.com/download

Then run:

```bash
ollama serve
ollama pull mistral
```

---

### 6️⃣ Run Backend

```bash
uvicorn app.main:app --reload
```

Swagger Docs:  
http://127.0.0.1:8000/docs

---

### 7️⃣ Run Frontend

```bash
streamlit run frontend/app.py
```

Open:  
http://localhost:8501


## 🐳 Docker Setup

### Build Image

```bash
docker build -t enterprise-rag -f docker/Dockerfile .
```

### Run Container

```bash
docker run -p 8000:8000 enterprise-rag
```
---

## 📊 FAISS Configuration

- **Index Type:** `IndexFlatIP`
- **Similarity Metric:** Cosine similarity (L2-normalized vectors)
- **Embedding dtype:** `float32`
- **Persistent Storage:** `data/embeddings/`

---

## 🔒 Production Considerations

- Runtime-generated FAISS index is not committed to Git
- Sensitive configuration values stored in `.env`
- Vector normalization ensures consistent cosine similarity scoring
- Clean repository structure (no virtual environment or generated files)
- Modular RAG pipeline for maintainability and scalability

---

## 🚀 Future Improvements

- Role-Based Access Control (RBAC)
- Streaming LLM responses
- Async embedding pipeline
- Scalable FAISS IVF index
- Cloud storage integration (S3)
- CI/CD pipeline
- Kubernetes deployment
- Redis caching layer

---

## 🎯 Use Cases

- Enterprise document search
- Internal knowledge assistant
- Legal document analysis
- HR policy Q&A
- Research document summarization

---

## 👨‍💻 Author

**Sanidhya Sachin Kulkarni**  
AI/ML Engineer | Backend Developer  

---

## 📜 License

MIT License