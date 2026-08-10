from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

_WORD_RE = re.compile(r"[a-z0-9]+(?:['\u2019][a-z0-9]+)*")


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into fixed-dimension dense vectors."""
        ...


class LocalNgramEmbedder:
    """Deterministic, offline, fixed-dimension hashed n-gram embedder.

    This is the default embedder: it needs no model download, no API key and
    no GPU, so the demo and the benchmark are fully reproducible. Features are
    word unigrams/bigrams plus character 3-grams/4-grams, hashed into a fixed
    dimension with md5 (hashlib, so results are independent of PYTHONHASHSEED).
    The same code embeds queries at retrieval time, giving a real vector space
    with cosine similarity.
    """

    name = "local-ngram-v1"
    _md5 = hashlib.md5

    def __init__(
        self,
        dim: int = 512,
        word_ngrams: tuple[int, ...] = (1, 2),
        char_ngrams: tuple[int, ...] = (3, 4),
        seed: int = 42,
    ) -> None:
        self.dim = dim
        self._word_ngrams = word_ngrams
        self._char_ngrams = char_ngrams
        self._seed = seed

    @staticmethod
    def _hash(feature: str, seed: int, dim: int) -> int:
        return int(
            hashlib.md5(f"{seed}:{feature}".encode()).hexdigest()[:8], 16
        ) % dim

    def _features(self, text: str) -> list[str]:
        words = _WORD_RE.findall(text.lower())
        feats: list[str] = []
        for n in self._word_ngrams:
            if n == 1:
                feats.extend(words)
            else:
                feats.extend(
                    " ".join(words[i : i + n]) for i in range(len(words) - n + 1)
                )
        for token in words:
            if len(token) >= 3:
                for n in self._char_ngrams:
                    feats.extend(
                        token[i : i + n] for i in range(len(token) - n + 1)
                    )
        return feats

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for feature in self._features(text):
            vec[self._hash(feature, self._seed, self.dim)] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            inv = 1.0 / norm
            vec = [v * inv for v in vec]
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]


class SentenceTransformerEmbedder:
    """Optional real-embedding backend (sentence-transformers / all-MiniLM).

    Enabled by the operator with KB_EMBEDDER=sentence_transformers. The model
    is loaded lazily on first use so the default local path stays dependency-
    free; it is never required for the demo or the benchmark.
    """

    name = "sentence-transformers"

    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model
        self._model = None
        self.dim = 384 if "MiniLM" in model else 0

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            self.dim = int(self._model.get_sentence_embedding_dimension())
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        return [v.tolist() for v in model.encode(texts, normalize_embeddings=True)]


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors (both pre-normalized)."""
    if len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=False))
