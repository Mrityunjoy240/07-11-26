from __future__ import annotations

import math
from collections.abc import Sequence

from src.knowledge.chunking import tokenize
from src.knowledge.embeddings import cosine
from src.knowledge.models import KnowledgeChunk, RetrievalHit

STOPWORDS = {
    "a", "an", "the", "of", "to", "is", "are", "was", "were", "what", "which",
    "how", "do", "does", "did", "can", "could", "for", "with", "about", "on",
    "in", "at", "tell", "me", "please", "give", "share", "know", "want", "any",
    "into", "from", "there", "you", "your", "have", "has",
}


class KnowledgeIndex:
    """In-memory vector + lexical index over knowledge chunks.

    Retrieval is a deterministic hybrid: embedding cosine similarity plus an
    IDF-weighted lexical term-overlap component. The lexical term matters for
    terse college queries (short acronyms like ``ECE``, ``WBJEE``, ``B.Tech``)
    and IDF down-weights ubiquitous words (``college``) so a rare, specific
    term (``timings``, ``fee``) dominates the score. Both components are
    normalized to [0, 1] so the combined score is comparable across builds.
    """

    EMBEDDING_WEIGHT = 0.6
    LEXICAL_WEIGHT = 0.4

    def __init__(self) -> None:
        self.chunks: list[KnowledgeChunk] = []
        self.vectors: list[list[float]] = []
        self._terms: list[set[str]] = []
        self._idf: dict[str, float] = {}

    def __len__(self) -> int:
        return len(self.chunks)

    def add(self, chunks: Sequence[KnowledgeChunk], vectors: list[list[float]]) -> None:
        for chunk, vec in zip(chunks, vectors, strict=False):
            self.chunks.append(chunk)
            self.vectors.append(vec)
            self._terms.append(set(tokenize(chunk.text)))
        self._rebuild_idf()

    def _rebuild_idf(self) -> None:
        df: dict[str, int] = {}
        for terms in self._terms:
            for term in terms:
                df[term] = df.get(term, 0) + 1
        n = max(1, len(self._terms))
        self._idf = {
            term: math.log(1.0 + n / (1.0 + count))
            for term, count in df.items()
        }

    def _query_terms(self, query: str) -> dict[str, float]:
        weighted: dict[str, float] = {}
        for term in set(tokenize(query)):
            if term in STOPWORDS:
                continue
            weighted[term] = self._idf.get(term, math.log(1.0 + len(self._terms) + 1.0))
        return weighted

    def _lexical_score(self, query_terms: dict[str, float], chunk_terms: set[str]) -> float:
        if not query_terms:
            return 0.0
        matched = sum(w for t, w in query_terms.items() if t in chunk_terms)
        total = sum(query_terms.values())
        return matched / total if total else 0.0

    def search(
        self,
        query: str,
        query_vector: list[float],
        top_k: int = 4,
        threshold: float = 0.0,
    ) -> list[RetrievalHit]:
        query_terms = self._query_terms(query)
        scored: list[tuple[float, int]] = []
        for i, vec in enumerate(self.vectors):
            emb = cosine(query_vector, vec)
            lex = self._lexical_score(query_terms, self._terms[i])
            total = self.EMBEDDING_WEIGHT * emb + self.LEXICAL_WEIGHT * lex
            if total >= threshold:
                scored.append((total, i))

        scored.sort(key=lambda t: (-t[0], t[1]))
        hits = [
            RetrievalHit(
                chunk=self.chunks[i],
                score=score,
                embedding_score=cosine(query_vector, self.vectors[i]),
                lexical_score=self._lexical_score(query_terms, self._terms[i]),
            )
            for score, i in scored[:top_k]
        ]
        return hits
