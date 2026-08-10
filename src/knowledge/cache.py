from __future__ import annotations

import copy
import threading
from collections import OrderedDict
from collections.abc import Hashable
from typing import Any


class RetrievalCache:
    """Tiny thread-safe LRU cache for the retrieval/response layer.

    Keyed by ``(normalized_query, kb_fingerprint)`` so repeated questions are
    served from cache while any KB update (new fingerprint) transparently
    invalidates every entry. This is deliberately a small bounded cache: the
    KB corpus is operator-curated and small, so an LRU dict is the right tool;
    Parquet and distributed caches would add nothing here.
    """

    def __init__(self, maxsize: int = 256) -> None:
        self._maxsize = max(1, maxsize)
        self._store: OrderedDict[Hashable, Any] = OrderedDict()
        self._lock = threading.Lock()

    def _key(self, query: str, kb_fingerprint: str) -> tuple[str, str]:
        return query.strip().lower(), kb_fingerprint

    def get(self, query: str, kb_fingerprint: str) -> Any | None:
        key = self._key(query, kb_fingerprint)
        with self._lock:
            value = self._store.get(key)
            if value is not None:
                self._store.move_to_end(key)
                return copy.deepcopy(value)
        return None

    def put(self, query: str, kb_fingerprint: str, value: Any) -> None:
        key = self._key(query, kb_fingerprint)
        with self._lock:
            self._store[key] = copy.deepcopy(value)
            self._store.move_to_end(key)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
