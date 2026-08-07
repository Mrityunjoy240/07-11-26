import os
import logging
from typing import List, Any
from pathlib import Path

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
logger = logging.getLogger(__name__)

# Single source of truth for the embedding model.
# Query AND ingest/reindex paths must share this exact model so the persisted
# collection dimension always matches the query-time dimension. Switching this
# constant without clearing + rebuilding the collection raises a loud error in
# add_documents() instead of silently corrupting retrieval.
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


class VectorStoreService:
    """
    Professional Vector Store Service using ChromaDB.
    Handles semantic search for the RAG pipeline.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(VectorStoreService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return

        # Use absolute path anchored to project root to avoid CWD-dependent bugs
        # vector_store.py lives at: backend/app/services/vector_store.py
        # .parent x4 = project root
        _project_root = Path(__file__).resolve().parent.parent.parent.parent
        self.db_path = str(_project_root / "chroma_db" / "chroma_db_v2")
        os.makedirs(self.db_path, exist_ok=True)
        logger.info(f"ChromaDB path: {self.db_path}")

        # Using all-MiniLM-L6-v2 for fast startup (~2s vs 45s for BGE-M3).
        # Sufficient for intent classification and multilingual RAG at demo scale.
        self.embedding_model_name = EMBEDDING_MODEL_NAME

        logger.info(f"Initializing VectorStoreService with model: {self.embedding_model_name}")

        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.embedding_model_name,
                model_kwargs={"device": "cpu", "local_files_only": False},
                encode_kwargs={"normalize_embeddings": True},
            )

            self._collection_name = "bcrec_knowledge_base"
            self.vector_store = Chroma(
                persist_directory=self.db_path,
                embedding_function=self.embeddings,
                collection_name=self._collection_name,
            )

            stored_dim = self._collection_dimension()
            model_dim = len(self.embeddings.embed_query("dimension probe"))
            if stored_dim and stored_dim != model_dim:
                logger.warning(
                    f"Collection dimension mismatch detected: stored={stored_dim}, "
                    f"model={model_dim} ({self.embedding_model_name}). "
                    "Rebuild the collection via /admin/kb/reindex to realign."
                )
            else:
                logger.info(
                    f"Embedding dimensions consistent: stored={stored_dim or 'empty'}, "
                    f"model={model_dim} ({self.embedding_model_name})."
                )

            self.initialized = True
            logger.info("VectorStoreService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize VectorStoreService: {e}")
            self.vector_store = None

    def _collection_dimension(self) -> int:
        """Return the persisted collection's embedding dimension, or 0 if empty."""
        try:
            collection = self.vector_store._collection
            if collection.count() == 0:
                return 0
            embeddings = collection.get(limit=1, include=["embeddings"]).get("embeddings")
            if embeddings is None:
                return 0
            if len(embeddings) > 0 and embeddings[0] is not None:
                return len(embeddings[0])
            return 0
        except Exception as e:
            logger.error(f"Error reading collection dimension: {e}")
            return 0

    def search(self, query: str, k: int = 8) -> List[Document]:
        """
        Pure semantic search using ChromaDB.
        Single retriever — no keyword boosting, no hardcoded intent maps.
        """
        docs, _ = self.search_with_scores(query, k=k)
        return docs

    def search_with_scores(self, query: str, k: int = 8) -> tuple[List[Document], float]:
        """
        Like search() but also returns the max relevance score (confidence).
        Returns (documents, max_score). max_score is 0.0 if no results.
        """
        if not self.vector_store:
            logger.warning("Vector store not initialized. Returning empty results.")
            return [], 0.0

        try:
            results_with_scores = self.vector_store.similarity_search_with_relevance_scores(
                query, k=k
            )

            max_score = max((score for _, score in results_with_scores), default=0.0)

            RELEVANCE_THRESHOLD = 0.15
            filtered = [doc for doc, score in results_with_scores if score >= RELEVANCE_THRESHOLD]

            if not filtered and results_with_scores:
                logger.warning("Threshold fallback active.")
                return [doc for doc, score in results_with_scores[:3]], max_score

            return filtered[:k], max_score
        except Exception as e:
            logger.error(f"Search error: {e}")
            return [], 0.0

    def add_documents(self, documents: List[Document]):
        """
        Add documents to the vector store.
        Refuses to add if the stored collection dimension differs from the
        current embedding model dimension (prevents silent mixed-dim corruption).
        """
        if not self.vector_store:
            logger.error("Vector store not initialized.")
            return

        try:
            stored_dim = self._collection_dimension()
            model_dim = len(self.embeddings.embed_query("dimension probe"))
            if stored_dim and stored_dim != model_dim:
                logger.error(
                    f"Refusing to add documents: collection dimension {stored_dim} "
                    f"!= model dimension {model_dim} ({self.embedding_model_name}). "
                    "Rebuild the collection via /admin/kb/reindex with the matching model."
                )
                return
            self.vector_store.add_documents(documents)
            logger.info(f"Added {len(documents)} documents to vector store.")
        except Exception as e:
            logger.error(f"Error adding documents: {e}")

    def clear_collection(self):
        """
        Clear all documents from the collection WITHOUT dropping/recreating it.
        This preserves all existing references to the singleton, preventing
        the stale-reference bug where other services hold a dead pointer.
        """
        if not self.vector_store:
            return

        try:
            # Get the underlying Chroma collection and delete all docs
            collection = self.vector_store._collection
            # Get count first
            count = collection.count()
            if count > 0:
                # Fetch all IDs and delete them
                all_ids = collection.get()["ids"]
                if all_ids:
                    collection.delete(ids=all_ids)
            logger.info(f"Vector store collection cleared ({count} documents removed).")
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")
            # Fallback: recreate collection (old behavior)
            try:
                self.vector_store.delete_collection()
                self.vector_store = Chroma(
                    persist_directory=self.db_path,
                    embedding_function=self.embeddings,
                    collection_name=self._collection_name,
                )
                logger.info("Collection cleared via fallback (recreate).")
            except Exception as e2:
                logger.error(f"Fallback clear also failed: {e2}")


# Singleton getter
def get_vector_store():
    return VectorStoreService()
