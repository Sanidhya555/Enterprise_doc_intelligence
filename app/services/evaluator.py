import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger("rag_app")

try:
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision
    from datasets import Dataset
    RAGAS_ENABLED = True
except ImportError:
    RAGAS_ENABLED = False


class RAGEvaluator:
    def __init__(self, rag_service=None, dataset_path: Optional[str] = None):
        self.rag = rag_service
        self.dataset_path = dataset_path
        self.metrics = [faithfulness, answer_relevancy, context_precision] if RAGAS_ENABLED else []

    def _load_dataset(self) -> List[Dict[str, Any]]:
        if not self.dataset_path:
            raise FileNotFoundError("No evaluation dataset configured. Set dataset_path.")

        dataset_path = Path(self.dataset_path)
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {self.dataset_path}")

        with dataset_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _score_context_precision(self, contexts: List[str], reference_context: str) -> float:
        if not reference_context or not contexts:
            return 0.0

        reference = reference_context.strip().lower()
        for chunk in contexts:
            if reference in chunk.lower():
                return 1.0

        ref_tokens = set(re.findall(r"\w+", reference))
        if not ref_tokens:
            return 0.0

        best_overlap = 0
        for chunk in contexts:
            chunk_tokens = set(re.findall(r"\w+", chunk.lower()))
            overlap = len(ref_tokens & chunk_tokens)
            best_overlap = max(best_overlap, overlap)

        return round(best_overlap / max(len(ref_tokens), 1), 4)

    def _score_faithfulness(self, answer: str, contexts: List[str]) -> float:
        sentences = [s.strip() for s in re.split(r"[.!?]", answer) if len(s.strip()) > 10]
        if not sentences:
            return 1.0

        context_text = " ".join(contexts).lower()
        faithful_count = 0
        for sent in sentences:
            significant = [w for w in re.findall(r"\w+", sent.lower()) if len(w) > 4]
            if significant and any(w in context_text for w in significant):
                faithful_count += 1

        return round(faithful_count / len(sentences), 4)

    def _score_answer_relevancy(self, question: str, answer: str) -> float:
        q_words = set(re.findall(r"\w+", question.lower())) - {
            "what",
            "how",
            "why",
            "when",
            "where",
            "is",
            "the",
            "a",
            "an",
            "and",
            "or",
            "to",
            "of",
            "for",
        }
        a_words = set(re.findall(r"\w+", answer.lower()))
        if not q_words:
            return 1.0

        overlap = len(q_words & a_words) / len(q_words)
        return round(overlap, 4)

    def evaluate_answer_relevancy(self, question: str, answer: str) -> Dict[str, float]:
        return {"answer_relevancy": self._score_answer_relevancy(question, answer)}

    def evaluate_faithfulness(self, answer: str, contexts: List[str]) -> Dict[str, float]:
        return {"faithfulness": self._score_faithfulness(answer, contexts)}

    def quick_check(self, answer: str, contexts: List[str]) -> float:
        return self._score_faithfulness(answer, contexts)

    def evaluate_retrieval(self, top_k: int = 5) -> Dict[str, float]:
        if self.rag is None:
            raise RuntimeError("RAG service is not available for retrieval evaluation.")

        dataset = self._load_dataset()
        if not dataset:
            return {"num_queries": 0, f"context_precision@{top_k}": 0.0}

        precisions = []
        for sample in dataset:
            query = sample.get("question", "")
            reference_context = sample.get("reference_context", "")
            results = self.rag.hybrid_retriever.retrieve(query, top_k=top_k)
            chunks = [r[0]["text"] for r in results if isinstance(r[0], dict)]
            precisions.append(self._score_context_precision(chunks, reference_context))

        return {
            "num_queries": len(precisions),
            f"context_precision@{top_k}": round(sum(precisions) / len(precisions), 4) if precisions else 0.0,
        }

    def run_batch_eval(self, test_samples: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if self.rag is None:
            raise RuntimeError("RAG service is not available for evaluation.")

        if test_samples is None:
            test_samples = self._load_dataset()

        rows: List[Dict[str, Any]] = []
        for sample in test_samples:
            response = self.rag.query(sample["question"])
            contexts = response.get("contexts", [])
            if isinstance(contexts, str):
                contexts = [contexts]

            row = {
                "question": sample["question"],
                "answer": response.get("answer", ""),
                "ground_truth": sample.get("ground_truth", ""),
                "reference_context": sample.get("reference_context", ""),
                "contexts": contexts,
                "context_precision": self._score_context_precision(contexts, sample.get("reference_context", "")),
                "faithfulness": self._score_faithfulness(response.get("answer", ""), contexts),
                "answer_relevancy": self._score_answer_relevancy(sample["question"], response.get("answer", "")),
            }
            rows.append(row)

        summary = {
            "num_samples": len(rows),
            "avg_context_precision": round(sum(r["context_precision"] for r in rows) / len(rows), 4) if rows else 0.0,
            "avg_faithfulness": round(sum(r["faithfulness"] for r in rows) / len(rows), 4) if rows else 0.0,
            "avg_answer_relevancy": round(sum(r["answer_relevancy"] for r in rows) / len(rows), 4) if rows else 0.0,
        }

        ragas_score = None
        if RAGAS_ENABLED and rows:
            dataset = Dataset.from_list(
                [
                    {
                        "question": row["question"],
                        "answer": row["answer"],
                        "contexts": row["contexts"],
                        "ground_truth": row["ground_truth"],
                    }
                    for row in rows
                ]
            )
            result = evaluate(dataset, metrics=self.metrics)
            try:
                ragas_score = result.to_pandas().to_dict(orient="records")
            except Exception:
                ragas_score = str(result)

        return {
            "rows": rows,
            "summary": summary,
            "ragas_score": ragas_score,
        }
