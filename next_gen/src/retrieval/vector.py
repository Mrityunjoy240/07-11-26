"""Vector store interface and ChromaDB implementation."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from ..core.models import SearchResult

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_CHROMA_DIR = _DATA_DIR / "chroma_db"


class VectorStore(ABC):
    """Abstract vector store interface."""

    @abstractmethod
    async def search(self, query: str, k: int = 5) -> list[SearchResult]:
        """Search for similar documents."""
        ...

    @abstractmethod
    async def add_documents(self, texts: list[str], metadatas: list[dict] | None = None) -> None:
        """Add documents to the store."""
        ...


class ChromaVectorStore(VectorStore):
    """ChromaDB vector store implementation."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        try:
            from langchain_chroma import Chroma
            from langchain_huggingface import HuggingFaceEmbeddings

            _CHROMA_DIR.mkdir(parents=True, exist_ok=True)

            self.embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu", "local_files_only": False},
                encode_kwargs={"normalize_embeddings": True},
            )

            self.vector_store = Chroma(
                persist_directory=str(_CHROMA_DIR),
                embedding_function=self.embeddings,
                collection_name="bcrec_knowledge",
            )
            self._initialized = True
            logger.info("ChromaDB vector store initialized")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.vector_store = None
            self._initialized = True

    async def search(self, query: str, k: int = 5) -> list[SearchResult]:
        """Search for similar documents."""
        if not self.vector_store:
            return []

        try:
            results = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
            return [
                SearchResult(
                    text=doc.page_content,
                    score=score,
                    metadata=doc.metadata if hasattr(doc, "metadata") else {},
                )
                for doc, score in results
                if score >= 0.15  # Relevance threshold
            ]
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    async def add_documents(self, texts: list[str], metadatas: list[dict] | None = None) -> None:
        """Add documents to the store."""
        if not self.vector_store:
            return

        try:
            from langchain_core.documents import Document
            docs = [
                Document(page_content=text, metadata=meta or {})
                for text, meta in zip(texts, metadatas or [{}] * len(texts))
            ]
            self.vector_store.add_documents(docs)
            logger.info(f"Added {len(docs)} documents to vector store")
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")


def get_vector_store() -> VectorStore:
    """Get the singleton vector store instance."""
    return ChromaVectorStore()
