"""Guardrails for input validation and output safety."""
import re
import logging
from typing import Tuple, List

logger = logging.getLogger("rag_app")

# ─── Patterns ────────────────────────────────────────────────────────────────

_HARMFUL = [
    r'\b(how\s+to\s+(make|build|synthesize|create)\s+(bomb|weapon|poison|drug|explosive))\b',
    r'\b(suicide|self[- ]?harm|kill\s+myself)\b',
    r'\b(hack\s+into|sql\s+injection|xss\s+attack|exploit\s+vulnerability|malware)\b',
]

_PROMPT_INJECTION = [
    r'ignore (previous|all|prior) instructions',
    r'disregard your (system|previous)',
    r'you are now (a|an|DAN)',
    r'jailbreak',
    r'pretend you have no restrictions',
]

MAX_INPUT_LEN = 1000
MAX_OUTPUT_LEN = 5000


class Guardrails:
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self._harmful = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _HARMFUL]
        self._injection = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _PROMPT_INJECTION]

    # ─── Input ───────────────────────────────────────────────────────────────

    def check_input(self, text: str) -> Tuple[bool, str]:
        """
        Returns (is_safe, message).
        is_safe=True  → proceed normally.
        is_safe=False → return message to user, skip LLM call.
        """
        if not text or not text.strip():
            return False, "Please enter a question."

        if len(text) > MAX_INPUT_LEN:
            return False, f"Your question is too long (max {MAX_INPUT_LEN} characters). Please shorten it."

        for pattern in self._injection:
            if pattern.search(text):
                logger.warning(f"Prompt injection attempt blocked: {text[:80]}")
                return False, "I'm not able to process that request."

        for pattern in self._harmful:
            if pattern.search(text):
                logger.warning(f"Harmful query blocked: {text[:80]}")
                return False, "That type of question falls outside what I can help with."

        return True, "ok"

    # ─── Output ──────────────────────────────────────────────────────────────

    def sanitize_output(self, output: str) -> str:
        """Remove embedded injection attempts from LLM output."""
        if not output:
            return output
        for p in self._injection:
            output = p.sub("", output)
        # Trim to max length
        if len(output) > MAX_OUTPUT_LEN:
            output = output[:MAX_OUTPUT_LEN] + "\n\n*[Response truncated]*"
        return output.strip()

    def check_output(self, output: str, context_chunks: List[str]) -> Tuple[bool, str]:
        """Basic output validation — returns (is_valid, cleaned_output)."""
        if not output or not output.strip():
            return False, "I wasn't able to generate a response. Please try again."
        cleaned = self.sanitize_output(output)
        return True, cleaned
