from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeDocument:
    """A single operator-uploaded source document (txt/md/pdf)."""

    doc_id: str
    title: str
    source: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeChunk:
    """A fixed-size token window carved out of a KnowledgeDocument."""

    chunk_id: str
    doc_id: str
    doc_title: str
    index: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalHit:
    chunk: KnowledgeChunk
    score: float
    embedding_score: float = 0.0
    lexical_score: float = 0.0


@dataclass
class RetrievalResult:
    query: str
    hits: list[RetrievalHit]
    kb_version: str = ""
    cached: bool = False


@dataclass
class KnowledgeAnswer:
    text: str
    sources: list[str]
    confidence: float
    kb_version: str
    hits: list[RetrievalHit] = field(default_factory=list)
