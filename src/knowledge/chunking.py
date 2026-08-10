from __future__ import annotations

import re

from src.knowledge.models import KnowledgeChunk, KnowledgeDocument

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['\u2019][A-Za-z0-9]+)*")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_ABBREV_RE = re.compile(
    r"\b(?:Rs|Dr|No|Mr|Mrs|Ms|vs|etc|approx|Sr|Jr|St|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.(?=\s|$)",
    re.IGNORECASE,
)


def tokenize(text: str) -> list[str]:
    """Deterministic tokenizer: lowercase word/numeral tokens."""
    return _WORD_RE.findall(text.lower())


def _count_tokens(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _split_units(text: str) -> list[str]:
    """Split a document into sentence-aligned units.

    Line-oriented first (structured fact sheets like a college KB are line
    based), then within each line split on sentence punctuation so prose
    paragraphs also yield bounded units. Lines containing an abbreviation
    (e.g. ``Rs.`` in fee tables, ``Dr.`` in names) are kept whole so numbers
    and names are not cut mid-way.
    """
    units: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line:
            continue
        if _ABBREV_RE.search(line):
            units.append(line)
            continue
        pieces = _SENTENCE_RE.split(line)
        for piece in pieces:
            piece = piece.strip()
            if piece:
                units.append(piece)
    return units


def split_into_chunks(
    doc: KnowledgeDocument,
    max_tokens: int = 160,
    overlap_tokens: int = 24,
) -> list[KnowledgeChunk]:
    """Split a document into overlapping, sentence-aligned token windows.

    Tokenization + chunking live here so retrieval operates on bounded,
    indexable units instead of whole (possibly huge) documents. Units are
    aligned to sentence/line boundaries (no mid-sentence starts) and a short
    tail overlap preserves answers that straddle a window boundary.
    """
    if max_tokens <= 0 or overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("max_tokens must be positive and overlap_tokens < max_tokens")

    units = _split_units(doc.text)
    if not units:
        return []

    chunks: list[KnowledgeChunk] = []
    current: list[str] = []
    current_tokens = 0
    for unit in units:
        unit_tokens = _count_tokens(unit)
        if current and current_tokens + unit_tokens > max_tokens:
            chunks.append(KnowledgeChunk(
                chunk_id=f"{doc.doc_id}:c{len(chunks):04d}",
                doc_id=doc.doc_id,
                doc_title=doc.title,
                index=len(chunks),
                text=" ".join(current),
            ))
            current, current_tokens = _tail_overlap(current, overlap_tokens)
        current.append(unit)
        current_tokens += unit_tokens

    if current:
        chunks.append(KnowledgeChunk(
            chunk_id=f"{doc.doc_id}:c{len(chunks):04d}",
            doc_id=doc.doc_id,
            doc_title=doc.title,
            index=len(chunks),
            text=" ".join(current),
        ))
    return chunks


def _tail_overlap(units: list[str], overlap_tokens: int) -> tuple[list[str], int]:
    carry: list[str] = []
    tokens = 0
    for unit in reversed(units):
        unit_tokens = _count_tokens(unit)
        if tokens + unit_tokens > overlap_tokens:
            break
        carry.insert(0, unit)
        tokens += unit_tokens
    return carry, tokens
