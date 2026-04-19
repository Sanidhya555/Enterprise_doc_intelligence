"""
RAG Service — central orchestrator.
Wires together: hybrid retrieval, reranker, query expansion,
guardrails, short/long-term memory, caching, evaluation, streaming.
"""
import hashlib
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.services.evaluator import RAGEvaluator
from pipeline.chunking.recursive_chunker import RecursiveChunker
from pipeline.embeddings.embedder import Embedder
from pipeline.guardrails.guardrails import Guardrails
from pipeline.ingestion.ingestion_pipeline import IngestionPipeline
from pipeline.llm.generator import OllamaGenerator, OpenAIGenerator
from pipeline.llm.prompt_template import PromptTemplate
from pipeline.memory.long_term import LongTermMemory
from pipeline.memory.short_term import ShortTermMemory
from pipeline.query_expansion.query_expander import QueryExpander
from pipeline.reranker.cross_encoder_reranker import CrossEncoderReranker
from pipeline.retriever.bm25_retriever import BM25Retriever
from pipeline.retriever.hybrid_retriever import HybridRetriever
from pipeline.retriever.vector_retriever import VectorRetriever
from pipeline.vector_store.faiss_store import FAISSStore
from app.core.logger import setup_logger

logger = setup_logger()


# ─── Query Cache ──────────────────────────────────────────────────────────────

class _QueryCache:
    """Simple TTL-based in-memory cache for query results."""

    def __init__(self, max_size: int = 200, ttl: int = 600):
        self._store: Dict[str, Tuple[Dict, float]] = {}
        self.max_size = max_size
        self.ttl = ttl

    def _key(self, question: str, session_id: str) -> str:
        return hashlib.md5(f"{session_id}||{question.strip().lower()}".encode()).hexdigest()

    def get(self, question: str, session_id: str = "") -> Optional[Dict]:
        k = self._key(question, session_id)
        if k in self._store:
            payload, ts = self._store[k]
            if time.time() - ts < self.ttl:
                return payload
            del self._store[k]
        return None

    def set(self, question: str, session_id: str, payload: Dict):
        if len(self._store) >= self.max_size:
            oldest = min(self._store, key=lambda k: self._store[k][1])
            del self._store[oldest]
        self._store[self._key(question, session_id)] = (payload, time.time())

    @property
    def size(self) -> int:
        return len(self._store)


# ─── RAG Service ──────────────────────────────────────────────────────────────

class RAGService:

    def __init__(self):
        # Core retrieval stack
        self.embedder = Embedder()
        self.vector_store = FAISSStore(dimension=384, embedder=self.embedder)
        self.vector_retriever = VectorRetriever(self.embedder, self.vector_store)
        self.bm25_retriever = BM25Retriever()
        self.hybrid_retriever = HybridRetriever(self.vector_retriever, self.bm25_retriever)
        self.reranker = CrossEncoderReranker()

        # LLM
        use_ollama = os.getenv("USE_OLLAMA", "true").lower() == "true"
        if use_ollama:
            logger.info("LLM backend: Ollama (%s)", os.getenv("OLLAMA_MODEL", "mistral"))
            self.generator = OllamaGenerator(model=os.getenv("OLLAMA_MODEL", "mistral"))
        else:
            logger.info("LLM backend: OpenAI")
            self.generator = OpenAIGenerator()

        # Advanced components
        self.query_expander = QueryExpander(generator=self.generator, num_expansions=2)
        self.guardrails = Guardrails(strict_mode=False)
        self.short_term = ShortTermMemory(max_turns=10)
        self.long_term = LongTermMemory(db_path="data/memory.db")
        self.cache = _QueryCache(max_size=200, ttl=600)
        dataset_path = str(Path(__file__).resolve().parents[2] / "eval_set.json")
        self.evaluator = RAGEvaluator(
            rag_service=self,
            dataset_path=dataset_path,
        )

        # Load existing FAISS index
        if os.path.exists("data/embeddings/faiss.index"):
            self.vector_store.load(
                index_path="data/embeddings/faiss.index",
                chunks_path="data/embeddings/chunks.npy",
            )
            self.bm25_retriever.index(self.vector_store.text_chunks)
            logger.info("Loaded index: %d vectors", self.vector_store.index.ntotal)
        else:
            logger.info("No index found — starting fresh")

    # ─── Internal helpers ────────────────────────────────────────────────────

    def _retrieve_rerank(self, query: str, top_k: int) -> List[Tuple[Dict, float]]:
        results = self.hybrid_retriever.retrieve(query, top_k=top_k * 2)
        if self.reranker.available and results:
            results = self.reranker.rerank(query, results, top_k=top_k)
        return results[:top_k]

    def _multi_query_retrieve(self, queries: List[str], top_k: int) -> List[Tuple[Dict, float]]:
        """Retrieve for each expanded query and merge by best score."""
        seen: Dict[str, Tuple[Dict, float]] = {}
        for q in queries:
            for chunk, score in self._retrieve_rerank(q, top_k):
                if not isinstance(chunk, dict):
                    continue
                key = f"{chunk.get('filename')}::{chunk.get('chunk_id')}"
                if key not in seen or seen[key][1] < score:
                    seen[key] = (chunk, score)
        return sorted(seen.values(), key=lambda x: x[1], reverse=True)[:top_k]

    def _build_context(self, results: List[Tuple[Dict, float]]) -> Tuple[str, List[Dict]]:
        chunks = [r[0]["text"] for r in results if isinstance(r[0], dict)]
        context = "\n\n---\n\n".join(chunks) if chunks else "No relevant documents found."
        sources = [
            {
                "filename": r[0].get("filename", ""),
                "chunk_id": r[0].get("chunk_id", 0),
                "score": round(r[1], 4),
            }
            for r in results
            if isinstance(r[0], dict)
        ]
        return context, sources

    def _auto_title(self, session_id: str, question: str, answer: str):
        """Generate and persist a short session title after first turn."""
        sessions = self.long_term.list_sessions()
        session = next((s for s in sessions if s["session_id"] == session_id), None)
        if session and session.get("title") == "New Chat":
            prompt = PromptTemplate.build_summary([
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ])
            try:
                title = self.generator.generate(prompt).strip()[:60]
                self.long_term.update_session_title(session_id, title)
            except Exception:
                pass

    # ─── Public query API ────────────────────────────────────────────────────

    def query(
        self,
        question: str,
        session_id: str = "default",
        top_k: int = 5,
        use_cache: bool = True,
    ) -> Dict:
        t0 = time.time()

        # 1. Guardrails
        safe, reason = self.guardrails.check_input(question)
        if not safe:
            return {"answer": reason, "sources": [], "latency_ms": 0, "cached": False}

        # 2. Cache lookup
        if use_cache:
            cached = self.cache.get(question, session_id)
            if cached:
                logger.info("Cache hit for session=%s", session_id)
                return {
                    **cached,
                    "metrics": cached.get("metrics", {
                        "total_latency": round((time.time() - t0), 3),
                        "retrieval_time": 0.0,
                        "generation_time": 0.0,
                    }),
                    "latency_ms": round((time.time() - t0) * 1000, 2),
                    "cached": True,
                }

        # 3. Query expansion
        queries = self.query_expander.expand(question)

        # 4. Hybrid retrieval + reranking across all expanded queries
        retrieval_start = time.time()
        results = self._multi_query_retrieve(queries, top_k)
        context, sources = self._build_context(results)
        retrieval_latency = time.time() - retrieval_start

        # 5. Conversation history
        history = self.short_term.format_for_prompt(session_id)

        # 6. Prompt → generate
        generation_start = time.time()
        prompt = PromptTemplate.build(context, question, history)
        answer = self.generator.generate(prompt)
        generation_latency = time.time() - generation_start

        # 7. Output guardrails
        _, answer = self.guardrails.check_output(answer, [r[0].get("text","") for r in results if isinstance(r[0],dict)])
        answer = self.guardrails.sanitize_output(answer)

        # 8. Memory persistence
        self.short_term.add(session_id, "user", question)
        self.short_term.add(session_id, "assistant", answer)
        self.long_term.save_message(session_id, "user", question)
        self.long_term.save_message(session_id, "assistant", answer)

        # 9. Cache & auto-title
        metrics = {
            "total_latency": round((time.time() - t0), 3),
            "retrieval_time": round(retrieval_latency, 3),
            "generation_time": round(generation_latency, 3),
            "faithfulness_score": self.evaluator.quick_check(answer, [r[0]["text"] for r in results if isinstance(r[0], dict)]),
        }

        response_payload = {
            "answer": answer,
            "sources": sources,
            "expanded_queries": queries,
            "contexts": [r[0]["text"] for r in results if isinstance(r[0], dict)],
            "metrics": metrics,
        }
        self.cache.set(question, session_id, response_payload)
        self._auto_title(session_id, question, answer)

        latency = round((time.time() - t0) * 1000, 2)
        logger.info("Query done in %sms | session=%s | expanded=%d", latency, session_id, len(queries))

        return {
            **response_payload,
            "latency_ms": latency,
            "cached": False,
        }

    async def query_stream(
        self,
        question: str,
        session_id: str = "default",
        top_k: int = 5,
    ) -> AsyncIterator[str]:
        """Streaming query — yields tokens one by one."""

        safe, reason = self.guardrails.check_input(question)
        if not safe:
            yield reason
            return

        queries = self.query_expander.expand(question)
        results = self._multi_query_retrieve(queries, top_k)
        context, _ = self._build_context(results)
        history = self.short_term.format_for_prompt(session_id)
        prompt = PromptTemplate.build(context, question, history)

        full_tokens: List[str] = []
        async for token in self.generator.stream(prompt):
            full_tokens.append(token)
            yield token

        answer = "".join(full_tokens)
        answer = self.guardrails.sanitize_output(answer)

        self.short_term.add(session_id, "user", question)
        self.short_term.add(session_id, "assistant", answer)
        self.long_term.save_message(session_id, "user", question)
        self.long_term.save_message(session_id, "assistant", answer)
        self._auto_title(session_id, question, answer)

    # ─── Document management ─────────────────────────────────────────────────

    def add_document(self, file_path: str) -> Dict:
        ingestion = IngestionPipeline()
        chunker = RecursiveChunker(chunk_size=400, overlap=60)

        text = ingestion.process(file_path)
        chunks = chunker.chunk(text)

        filename = os.path.basename(file_path)
        timestamp = datetime.utcnow().isoformat()

        meta_chunks = [
            {"chunk_id": i, "text": chunk, "filename": filename, "uploaded_at": timestamp}
            for i, chunk in enumerate(chunks)
        ]

        embeddings = self.embedder.embed([c["text"] for c in meta_chunks])
        self.vector_store.add(embeddings, meta_chunks)
        self.vector_store.save(
            index_path="data/embeddings/faiss.index",
            chunks_path="data/embeddings/chunks.npy",
        )
        self.bm25_retriever.index(self.vector_store.text_chunks)

        logger.info("Indexed: %s (%d chunks)", filename, len(meta_chunks))
        return {"status": "indexed", "filename": filename, "chunks_added": len(meta_chunks)}

    def list_documents(self) -> List[Dict]:
        docs: Dict[str, Dict] = {}
        for chunk in self.vector_store.text_chunks:
            if not isinstance(chunk, dict):
                continue
            fn = chunk["filename"]
            if fn not in docs:
                docs[fn] = {"filename": fn, "uploaded_at": chunk.get("uploaded_at", ""), "chunks": 0}
            docs[fn]["chunks"] += 1
        return list(docs.values())

    def delete_document(self, filename: str) -> Dict:
        filename = filename.strip()
        matched = [
            c for c in self.vector_store.text_chunks
            if isinstance(c, dict) and c["filename"].strip().lower() == filename.lower()
        ]
        if not matched:
            raise HTTPException(status_code=404, detail=f"Document '{filename}' not found")

        filtered = [
            c for c in self.vector_store.text_chunks
            if isinstance(c, dict) and c["filename"].strip().lower() != filename.lower()
        ]
        self.vector_store.rebuild_index(filtered)
        self.vector_store.save(
            index_path="data/embeddings/faiss.index",
            chunks_path="data/embeddings/chunks.npy",
        )
        self.bm25_retriever.index(filtered)
        logger.info("Deleted: %s", filename)
        return {"status": "deleted", "filename": filename}

    # ─── Session management ──────────────────────────────────────────────────

    def new_session(self, session_id: str) -> Dict:
        self.short_term.clear(session_id)
        self.long_term.upsert_session(session_id)
        return {"session_id": session_id, "status": "created"}

    def list_sessions(self) -> List[Dict]:
        return self.long_term.list_sessions()

    def get_session_messages(self, session_id: str) -> List[Dict]:
        return self.long_term.get_messages(session_id)

    def delete_session(self, session_id: str) -> Dict:
        self.long_term.delete_session(session_id)
        self.short_term.clear(session_id)
        return {"status": "deleted", "session_id": session_id}

    # ─── System metrics ──────────────────────────────────────────────────────

    def get_metrics(self) -> Dict:
        docs = self.list_documents()
        return {
            "documents_indexed": len(docs),
            "total_chunks": len(self.vector_store.text_chunks),
            "vector_dimension": self.vector_store.dimension,
            "bm25_chunks_indexed": len(self.bm25_retriever.chunks),
            "reranker_available": self.reranker.available,
            "active_sessions": len(self.long_term.list_sessions()),
            "query_cache_size": self.cache.size,
        }
