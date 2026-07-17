"""Post-processors — validation and formatting."""

from __future__ import annotations

import re

from ..core.models import Language


class PostProcessor:
    """Validates and formats responses."""

    async def validate(self, answer: str, context: str, query: str) -> tuple[bool, str]:
        """Validate the answer against context. Returns (is_valid, reason)."""
        if not answer or not answer.strip():
            return False, "empty_answer"

        # Check for common failure patterns
        failure_patterns = [
            r"\bi\s+(?:don'?t|do\s+not)\s+know\b",
            r"\bi\s+(?:couldn'?t|could\s+not)\s+find\b",
            r"\bno\s+information\b",
            r"\bnot\s+available\b",
            r"\bunable\s+to\b",
        ]
        for pattern in failure_patterns:
            if re.search(pattern, answer, re.IGNORECASE):
                return False, "fallback_response"

        return True, ""

    async def format(self, text: str, lang: Language) -> str:
        """Format the response for output (TTS normalization, etc.)."""
        if not text:
            return text

        # Strip any markdown-like formatting
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"\*(.*?)\*", r"\1", text)

        # Normalize numbers for TTS (basic)
        # Keep digits as-is for now — TTS engine handles pronunciation

        return text.strip()
