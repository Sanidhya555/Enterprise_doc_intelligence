import json
from typing import List
from pipeline.retriever.vector_retriever import VectorRetriever
from pipeline.evaluation.retrieval_metrics import recall_at_k, precision_at_k

class Evaluator:

    def __init__(self, retriever : VectorRetriever, dataset_path : str):
        self.retriever = retriever
        self.dataset_path = dataset_path

    def evaluate(self, top_k : int = 3):
        with open(self.dataset_path, "r") as f:
            dataset = json.load(f)

        total_recall = 0
        total_precision = 0

        for item in dataset:
            query = item["query"]
            keyword = item["relevant_keyword"]

            results = self.retriever.retrieve(query, top_k= top_k)
            retrieved_chunks = [chunk for chunk, _ in results]

            recall = recall_at_k(retrieved_chunks, keyword)
            precision = precision_at_k(retrieved_chunks, keyword)

            total_recall += recall
            total_precision += precision

            print(f"\n Query: {query}")
            print(f"Recall {top_k} : {recall}")
            print(f"Precision {top_k} : {precision}")

        n = len(dataset)
        print("\n =====Overall Metrics=====")
        print(f"Average Recall {top_k} : {total_recall / n}")
        print(f"Average Precision {top_k} : {total_precision/ n}")
