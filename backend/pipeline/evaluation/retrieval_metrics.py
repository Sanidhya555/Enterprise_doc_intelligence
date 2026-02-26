from typing import List

def recall_at_k(results : List[str] , relevant_keyword : str) -> float:
    # Recall@K: Did we retrieve at least one relevant chunk?
    for chunk in results:
        if relevant_keyword.lower() in chunk.lower():
            return 1.0
        return 0.0
    

def precision_at_k(results : List[str] , relevant_keyword : str) -> float:
    # Precision@K: How many retrieved chunks are relevant?
    relevant_count = 0

    for chunk in results:
        if relevant_keyword.lower() in chunk.lower():
            relevant_count += 1

    return relevant_count / len(results) if results else 0.0