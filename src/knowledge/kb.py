from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Sequence
from pathlib import Path

from src.knowledge.cache import RetrievalCache
from src.knowledge.chunking import _split_units, split_into_chunks, tokenize
from src.knowledge.embeddings import Embedder, LocalNgramEmbedder
from src.knowledge.index import STOPWORDS, KnowledgeIndex
from src.knowledge.ingest import load_documents
from src.knowledge.models import (
    KnowledgeAnswer,
    KnowledgeChunk,
    KnowledgeDocument,
    RetrievalHit,
    RetrievalResult,
)

_DEFAULT_THRESHOLD = 0.28
_DEFAULT_TOP_K = 4
_MAX_ANSWER_CHARS = 380


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _query_terms(query: str) -> set[str]:
    return {t for t in tokenize(query) if t not in STOPWORDS}


def _select_snippet(
    chunk_text: str, query: str, max_chars: int = _MAX_ANSWER_CHARS
) -> str | None:
    """Pick the unit(s) of a chunk that best match the query.

    Returns None when no unit shares a meaningful term with the query, which
    means the chunk is not actually grounded on the question — the caller then
    falls back to the structured brain instead of inventing content.
    """
    query_terms = _query_terms(query)
    if not query_terms:
        return None
    units = _split_units(chunk_text)
    if not units:
        return None

    def _unit_match(unit: str) -> tuple[int, int]:
        unit_terms = set(tokenize(unit))
        exact = len(query_terms & unit_terms)
        # "charge" should also credit "charges": count word-prefix matches.
        prefix = sum(
            1 for t in query_terms if len(t) >= 4 and any(w.startswith(t) for w in unit_terms)
        )
        return exact, prefix

    best_index = -1
    best_score = (0, 0)
    for i, unit in enumerate(units):
        score = _unit_match(unit)
        if score > best_score:
            best_score = score
            best_index = i
    if best_index < 0 or best_score == (0, 0):
        return None

    out = units[best_index]
    chars = len(out)
    for unit in units[best_index + 1 :]:
        if chars + len(unit) + 1 > max_chars:
            break
        out = f"{out} {unit}"
        chars += len(unit) + 1
    return out


class KnowledgeBase:
    """Operator-curated document knowledge base (ingest -> index -> retrieve -> answer).

    Storage note (why JSON and not Parquet):
      The college corpus is small, human-curated and replaced as a whole on
      operator uploads. JSON (manifest parcel + JSONL chunk store) is directly
      inspectable, diffable and versioned in git. Parquet is reserved for
      large-scale analytics over big, columnar datasets; it would add an
      unnecessary dependency and zero value for a few hundred text chunks, so
      it is deliberately NOT used here.

    The brain is untouched: recommendation/eligibility/policy decisions stay in
    src/brain + src/reasoning; this module only answers informational queries
    from the uploaded documents.
    """

    def __init__(
        self,
        root_dir: str | os.PathLike[str] = "data/knowledge",
        embedder: Embedder | None = None,
        cache: RetrievalCache | None = None,
        threshold: float = _DEFAULT_THRESHOLD,
        top_k: int = _DEFAULT_TOP_K,
        auto_load: bool = True,
    ) -> None:
        self.root = Path(root_dir)
        self.documents_dir = self.root / "documents"
        self.index_dir = self.root / "index"
        self.manifest_path = self.index_dir / "manifest.json"
        self.chunks_path = self.index_dir / "chunks.jsonl"
        self.embedder = embedder or LocalNgramEmbedder()
        self.cache = cache or RetrievalCache()
        self.threshold = threshold
        self.top_k = top_k

        self._index = KnowledgeIndex()
        self._documents: dict[str, KnowledgeDocument] = {}
        self._fingerprint = ""
        self._embedder_params = self._serialize_embedder_params()

        if auto_load:
            self._load()

    # ------------------------------------------------------------------ #
    # Document lifecycle (operator-facing)
    # ------------------------------------------------------------------ #

    def ingest_paths(self, paths: Sequence[str | os.PathLike[str]]) -> int:
        """Ingest files/directories, replacing documents that changed.

        Returns the number of documents added or updated. An identical
        re-upload is a no-op (same content hash -> same doc_id).
        """
        docs: list[KnowledgeDocument] = []
        for path in paths:
            docs.extend(load_documents(Path(path)))

        added = 0
        for doc in docs:
            existing = self._documents.get(doc.doc_id)
            if existing is not None and existing.text == doc.text:
                continue
            # Re-uploading an edited document from the same source path replaces
            # the previous version instead of leaving a stale copy behind.
            replaced_id = None
            for other_id, other in self._documents.items():
                if other.source == doc.source and other.doc_id != doc.doc_id:
                    replaced_id = other_id
                    break
            if replaced_id is not None:
                del self._documents[replaced_id]
            self._documents[doc.doc_id] = doc
            added += 1

        if added:
            self._rebuild_index()
            self._save()
            self.cache.clear()
        return added

    def remove_document(self, doc_id: str) -> bool:
        if doc_id not in self._documents:
            return False
        del self._documents[doc_id]
        self._rebuild_index()
        self._save()
        self.cache.clear()
        return True

    def clear(self) -> None:
        self._documents.clear()
        self._index = KnowledgeIndex()
        self._fingerprint = ""
        self._save()
        self.cache.clear()

    # ------------------------------------------------------------------ #
    # Retrieval / answer
    # ------------------------------------------------------------------ #

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    @property
    def documents(self) -> list[KnowledgeDocument]:
        return sorted(self._documents.values(), key=lambda d: d.title)

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def chunk_count(self) -> int:
        return len(self._index)

    def retrieve(self, query: str, top_k: int | None = None) -> RetrievalResult:
        top_k = top_k or self.top_k
        cached = self.cache.get(query, self._fingerprint)
        if cached is not None:
            cached.cached = True
            return cached

        if not query.strip() or self.chunk_count == 0:
            result = RetrievalResult(query=query, hits=[], kb_version=self._fingerprint)
        else:
            vector = self.embedder.embed([query])[0]
            hits = self._index.search(query, vector, top_k=top_k, threshold=self.threshold)
            result = RetrievalResult(query=query, hits=hits, kb_version=self._fingerprint)
        self.cache.put(query, self._fingerprint, result)
        return result

    def answer(self, query: str, top_k: int | None = None) -> KnowledgeAnswer | None:
        result = self.retrieve(query, top_k=top_k)
        if not result.hits:
            return None

        best: RetrievalHit = result.hits[0]
        snippet = _select_snippet(best.chunk.text, query)
        if snippet is None:
            return None
        text = _normalize_text(snippet)

        second: RetrievalHit | None = None
        for hit in result.hits[1:]:
            if hit.chunk.doc_id != best.chunk.doc_id:
                second = hit
                break
        if second is not None and len(text) < 90:
            extra = _select_snippet(second.chunk.text, query, max_chars=_MAX_ANSWER_CHARS // 2)
            if extra:
                text = f"{text} {_normalize_text(extra)}".strip()

        sources: list[str] = []
        for hit in result.hits:
            title = hit.chunk.doc_title
            if title and title not in sources:
                sources.append(title)
            if len(sources) >= 3:
                break

        return KnowledgeAnswer(
            text=text,
            sources=sources,
            confidence=best.score,
            kb_version=self._fingerprint,
            hits=list(result.hits),
        )

    # ------------------------------------------------------------------ #
    # Status / persistence
    # ------------------------------------------------------------------ #

    def status(self) -> dict:
        return {
            "root": str(self.root.resolve()),
            "documents": self.document_count,
            "chunks": self.chunk_count,
            "fingerprint": self._fingerprint or None,
            "embedder": {"name": self.embedder.name, "dim": getattr(self.embedder, "dim", 0)},
            "threshold": self.threshold,
            "cache_entries": len(self.cache),
        }

    def _rebuild_index(self) -> None:
        index = KnowledgeIndex()
        chunks: list[KnowledgeChunk] = []
        for doc in self._documents.values():
            if not _normalize_text(doc.text):
                continue
            chunks.extend(split_into_chunks(doc))
        if chunks:
            vectors = self.embedder.embed([c.text for c in chunks])
            index.add(chunks, vectors)
        self._index = index
        self._fingerprint = self._compute_fingerprint(chunks)

    @staticmethod
    def _compute_fingerprint(chunks: list[KnowledgeChunk]) -> str:
        ordered = sorted(chunks, key=lambda c: c.chunk_id)
        payload = "\n".join(f"{c.chunk_id}|{c.text}" for c in ordered)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]

    def _serialize_embedder_params(self) -> dict:
        return {
            "name": self.embedder.name,
            "dim": getattr(self.embedder, "dim", 0),
            "model": getattr(self.embedder, "model_name", None),
        }

    def _save(self) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "format": "knowledge-parcel",
            "version": 1,
            "fingerprint": self._fingerprint,
            "embedder": self._embedder_params,
            "threshold": self.threshold,
            "docs": [
                {
                    "doc_id": d.doc_id,
                    "title": d.title,
                    "source": d.source,
                    "chars": len(d.text),
                    "bytes": d.metadata.get("bytes"),
                    "updated_ns": d.metadata.get("updated_ns"),
                    "text": d.text,
                }
                for d in self.documents
            ],
            "chunk_count": self.chunk_count,
        }
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        with self.chunks_path.open("w", encoding="utf-8") as fh:
            for chunk, vec in zip(self._index.chunks, self._index.vectors, strict=False):
                fh.write(
                    json.dumps(
                        {
                            "chunk_id": chunk.chunk_id,
                            "doc_id": chunk.doc_id,
                            "doc_title": chunk.doc_title,
                            "index": chunk.index,
                            "text": chunk.text,
                            "vector": vec,
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                )

    def _load(self) -> None:
        if not self.manifest_path.exists() or not self.chunks_path.exists():
            return
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if manifest.get("format") != "knowledge-parcel":
            return

        chunks: list[KnowledgeChunk] = []
        vectors: list[list[float]] = []
        with self.chunks_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=row["chunk_id"],
                        doc_id=row["doc_id"],
                        doc_title=row["doc_title"],
                        index=row["index"],
                        text=row["text"],
                    )
                )
                vectors.append(row["vector"])

        docs = {}
        for doc in manifest.get("docs", []):
            docs[doc["doc_id"]] = KnowledgeDocument(
                doc_id=doc["doc_id"],
                title=doc["title"],
                source=doc.get("source", ""),
                text=doc.get("text", ""),
                metadata={
                    "bytes": doc.get("bytes"),
                    "updated_ns": doc.get("updated_ns"),
                },
            )
        self._documents = docs
        self._index = KnowledgeIndex()
        self._index.add(chunks, vectors)
        self._fingerprint = manifest.get("fingerprint", "")
