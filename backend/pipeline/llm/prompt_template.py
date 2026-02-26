class PromptTemplate:

    @staticmethod
    def build(context: str, question: str) -> str:
        return f"""
You are an enterprise document assistant.

Use ONLY the context provided below to answer the question.
If the answer is not in the context, say "I don't have enough information."

Context:
{context}

Question:
{question}

Answer:
"""