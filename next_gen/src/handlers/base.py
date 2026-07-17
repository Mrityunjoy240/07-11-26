"""Base handler interface and common utilities."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from ..core.models import ConversationState, Intent, Language


class BaseHandler(ABC):
    """Base class for all structured handlers."""

    @abstractmethod
    def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can handle the given intent."""
        ...

    @abstractmethod
    async def handle(self, query: str, lang: Language, state: ConversationState | None) -> str | None:
        """Handle the query and return a response, or None if cannot handle."""
        ...

    def extract_department(self, query: str) -> str | None:
        """Extract department code from query."""
        from ..knowledge.loader import get_kb
        return get_kb().search_department_code(query)

    def format_response(self, en: str, hi: str, bn: str, lang: Language) -> str:
        """Return the appropriate language response."""
        if lang == Language.HI:
            return hi
        if lang == Language.BN:
            return bn
        return en

    def format_inr(self, amount: int, lang: Language) -> str:
        """Format amount in Indian number words for TTS."""
        if amount == 0:
            return "zero rupees" if lang == Language.EN else "शून्य रुपये" if lang == Language.HI else "শূন্য টাকা"

        parts = []
        remaining = amount

        crores = remaining // 10000000
        remaining %= 10000000
        lakhs = remaining // 100000
        remaining %= 100000
        thousands = remaining // 1000
        remaining %= 1000
        hundreds = remaining // 100
        remaining %= 100

        num_words_en = {
            0: "zero", 1: "one", 2: "two", 3: "three", 4: "four",
            5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
            10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen",
            14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen",
            18: "eighteen", 19: "nineteen", 20: "twenty", 30: "thirty",
            40: "forty", 50: "fifty", 60: "sixty", 70: "seventy",
            80: "eighty", 90: "ninety",
        }

        def _num_en(n: int) -> str:
            if n < 20:
                return num_words_en.get(n, str(n))
            if n < 100:
                return num_words_en.get(n // 10 * 10, "") + ("-" + num_words_en.get(n % 10, "") if n % 10 else "")
            return str(n)

        if lang == Language.HI:
            if crores:
                parts.append(f"{crores} करोड़")
            if lakhs:
                parts.append(f"{lakhs} लाख")
            if thousands:
                parts.append(f"{thousands} हज़ार")
            if remaining:
                parts.append(str(remaining))
            suffix = "रुपये"
        elif lang == Language.BN:
            if crores:
                parts.append(f"{crores} কোটি")
            if lakhs:
                parts.append(f"{lakhs} লাখ")
            if thousands:
                parts.append(f"{thousands} হাজার")
            if remaining:
                parts.append(str(remaining))
            suffix = "টাকা"
        else:
            if crores:
                parts.append(f"{_num_en(crores)} crore")
            if lakhs:
                parts.append(f"{_num_en(lakhs)} lakh")
            if thousands:
                parts.append(f"{_num_en(thousands)} thousand")
            if hundreds:
                parts.append(f"{_num_en(hundreds)} hundred")
            if remaining:
                parts.append(_num_en(remaining))
            suffix = "rupees"

        return " ".join(parts) + " " + suffix if parts else suffix
