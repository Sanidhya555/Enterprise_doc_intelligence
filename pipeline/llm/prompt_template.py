"""Prompt templates for the RAG pipeline."""


class PromptTemplate:

    @staticmethod
    def build(context: str, question: str, history: str = "") -> str:
        """Main RAG prompt with optional conversation history."""
        history_block = ""
        if history:
            history_block = f"\n## Conversation History\n{history}\n"

        return f"""You are an enterprise document assistant. Answer questions using ONLY the context provided below.
If the answer cannot be found in the context, say: "I don't have enough information in the provided documents."
Be concise, accurate, and cite the source document when possible.
{history_block}
## Context from Documents
{context}

## Current Question
{question}

## Answer"""

    @staticmethod
    def build_summary(messages: list) -> str:
        """Prompt to summarize a conversation into a short title/description."""
        history = "\n".join(f"{m['role'].title()}: {m['content']}" for m in messages[-6:])
        return f"""Summarize the following conversation in one short sentence (max 10 words) suitable as a chat title.
Return ONLY the title, no quotes or punctuation.

{history}

Title:"""
