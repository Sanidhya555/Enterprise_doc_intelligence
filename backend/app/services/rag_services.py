import os
from pipeline.embeddings.embedder import Embedder
from pipeline.vector_store.faiss_store import FAISSStore
from pipeline.retriever.vector_retriever import VectorRetriever
from pipeline.llm.prompt_template import PromptTemplate
from pipeline.ingestion.ingestion_pipeline import IngestionPipeline
from pipeline.chunking.recursive_chunker import RecursiveChunker
from datetime import datetime
from pipeline.llm.generator import OllamaGenerator, OpenAIGenerator
from fastapi import HTTPException
from app.core.logger import setup_logger

logger = setup_logger()

class RAGService:

    def __init__(self):
        self.embedder = Embedder()

        self.vector_store = FAISSStore(dimension=384, embedder=self.embedder)
        self.retriever = VectorRetriever(self.embedder, self.vector_store)

        use_ollama = os.getenv("USE_OLLAMA", "true").lower() == "true"

        if use_ollama:
            logger.info("Using Ollama LLM")
            self.generator = OllamaGenerator(model="mistral")
        else:
            logger.info("Using OpenAI LLM")
            self.generator = OpenAIGenerator()

        if os.path.exists("data/embeddings/faiss.index"):
            self.vector_store.load(
                index_path="data/embeddings/faiss.index",
                chunks_path="data/embeddings/chunks.npy"
            )
        else:
            logger.info("No existing index found. Starting fresh.")

    def query(self, question: str):
        results = self.retriever.retrieve(question, top_k=3)

        # Extract text properly from metadata dict
        context_chunks = []

        for chunk, _ in results:
            if isinstance(chunk, dict):
                context_chunks.append(chunk["text"])
            else:
                context_chunks.append(chunk)

        context = "\n\n".join(context_chunks)

        prompt = PromptTemplate.build(context, question)
        answer = self.generator.generate(prompt)

        return answer

    def add_document(self, file_path: str):
        ingestion = IngestionPipeline()
        chunker = RecursiveChunker(chunk_size=300, overlap=50)

        text = ingestion.process(file_path)
        chunks = chunker.chunk(text)
    
        filename = os.path.basename(file_path)
        timestamp = datetime.utcnow().isoformat()

        metadata_chunks = []

        for i, chunk in enumerate(chunks):
            metadata_chunks.append({
                "chunk_id": i,
                "text" : chunk,
                "filename" : filename,
                "uploaded_at" : timestamp
            })

        embeddings = self.embedder.embed([c["text"] for c in metadata_chunks])

        self.vector_store.add(embeddings, metadata_chunks)

        self.vector_store.save(
            index_path="data/embeddings/faiss.index",
            chunks_path="data/embeddings/chunks.npy"
        )

        logger.info(f"Document indexed successfully: {filename}")

        return {
            "status": "document indexed successfully",
            "filename": filename,
            "chunks_added": len(metadata_chunks)
        }
    
    def list_documents(self):
        documents = {}

        for chunk in self.vector_store.text_chunks:
            if isinstance(chunk, dict):
                filename = chunk["filename"]
                uploaded_at = chunk["uploaded_at"]
                documents[filename] = uploaded_at

        return [
            {"filename": k, "uploaded_at": v}
            for k, v in documents.items()
        ]
    
    def delete_document(self, filename: str):

        filename = filename.strip().lower()

        # Count how many chunks belong to this file
        matched_chunks = [
            chunk for chunk in self.vector_store.text_chunks
            if isinstance(chunk, dict)
            and chunk["filename"].strip().lower() == filename
        ]

        if not matched_chunks:
            raise HTTPException(status_code=404, detail="Document not found")

        # Keep only chunks that are NOT this file
        filtered_chunks = [
            chunk for chunk in self.vector_store.text_chunks
            if isinstance(chunk, dict)
            and chunk["filename"].strip().lower() != filename
        ]

        # Rebuild index with remaining chunks
        self.vector_store.rebuild_index(filtered_chunks)

        self.vector_store.save(
            index_path="data/embeddings/faiss.index",
            chunks_path="data/embeddings/chunks.npy"
        )

        logger.info("Document Deleted")