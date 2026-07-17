"""RAG engine — combines vector search with LLM generation."""

from __future__ import annotations

import logging
from pathlib import Path

from ..core.models import Language, LLMResponse, SearchResult
from ..llm.base import LLMProvider
from .vector import VectorStore

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "prompts"


class RAGEngine:
    """Retrieval-Augmented Generation engine."""

    def __init__(self, vector_store: VectorStore, llm: LLMProvider):
        self.vector_store = vector_store
        self.llm = llm
        self._system_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load the system prompt from file."""
        prompt_file = _PROMPTS_DIR / "system.txt"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        return self._default_prompt()

    def _default_prompt(self) -> str:
        return """You are a friendly BCREC admission counselor. You work for Dr. B.C. Roy Engineering College, Durgapur. Be warm, helpful, and conversational.

CORE RULES:
1. Answer ONLY in the user's language.
2. Be concise: 2-3 short sentences maximum.
3. Be conversational — like a helpful campus counselor.
4. Never use filler like "Based on the context". Just answer directly.
5. If you don't have information, say so honestly.

KEY FACTS:
- Principal: Dr. Sanjay S. Pawar (Phone: 0343-2501353)
- Vice Principal: Prof. Dr. Partha Pratim Sarkar
- College Phones: 0343-2501353, 0343-2502449
- Email: info@bcrec.ac.in
- Address: Jemua Road, Fuljhore, Durgapur - 713206
- Established: August 2000, Autonomous from 2024
- NAAC B+ grade, NIRF 201-250
- NBA Accredited: CSE, ECE, IT, EE, ME"""

    async def retrieve(self, query: str, lang: Language) -> list[SearchResult]:
        """Retrieve relevant documents from vector store."""
        return await self.vector_store.search(query, k=5)

    async def generate(
        self,
        query: str,
        context: list[SearchResult],
        history: list[dict[str, str]],
        lang: Language,
    ) -> LLMResponse:
        """Generate a response using retrieved context."""
        # Build context string
        context_str = "\n\n".join([f"[{r.metadata.get('section', '')}] {r.text}" for r in context])

        # Build messages
        lang_hint = {
            Language.HI: " Reply in Roman Hindi (NOT Devanagari). Never use Bengali.",
            Language.BN: " Reply in Banglish (Roman Bengali). Never use Hindi.",
            Language.EN: " Reply in English.",
        }.get(lang, " Reply in the same language as the user.")

        messages = [{"role": "system", "content": self._system_prompt}]

        # Add conversation history (last 5 turns)
        for turn in history[-10:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        # Add current query with context
        user_message = f"""CONTEXT FROM KNOWLEDGE BASE:
{context_str}

USER QUESTION: {query}
{lang_hint} Answer based only on the context above."""

        messages.append({"role": "user", "content": user_message})

        return await self.llm.complete(messages)
