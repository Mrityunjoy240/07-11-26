"""Request observability — per-request logging for the QA pipeline.

Pure observation. Does NOT modify prompts, business logic, routing, RAG,
retrieval, memory, shadow routing, or signal detectors.

Provides:
    * RequestLogger — thread-safe in-memory ring buffer (last N requests)
      plus a persistent JSONL sink for durable, grep-able logs.
    * get_request_logger() — module singleton.
    * record_request(entry) — convenience helper.

Persistent JSONL path (env-overridable):
    REQUEST_LOG_PATH  (default: data/telemetry/request_log.jsonl)

Environment variables:
    REQUEST_LOG_PATH       — JSONL sink path
    REQUEST_LOG_RING_SIZE  — in-memory buffer size (default: 100)
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import deque
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_REQUEST_LOG_PATH = Path(os.getenv("REQUEST_LOG_PATH", "data/telemetry/request_log.jsonl"))
_RING_SIZE = int(os.getenv("REQUEST_LOG_RING_SIZE", "100"))


class RequestLogger:
    """Thread-safe in-memory ring buffer + JSONL sink for request records."""

    def __init__(self, path: Path = _REQUEST_LOG_PATH, maxlen: int = _RING_SIZE) -> None:
        self.path = path
        self.maxlen = maxlen
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._buf: deque = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        logger.info("RequestLogger initialized: path=%s ring=%d", self.path, maxlen)

    def record(self, entry: dict[str, Any]) -> None:
        """Append a request record to the ring buffer and JSONL sink."""
        if "timestamp" not in entry:
            entry["timestamp"] = datetime.now(UTC).isoformat()
        with self._lock:
            self._buf.append(entry)
        self._append_jsonl(entry)

    def snapshot(self) -> list[dict[str, Any]]:
        """Return buffered records in chronological order (oldest first)."""
        with self._lock:
            return list(self._buf)

    def _append_jsonl(self, entry: dict[str, Any]) -> None:
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except OSError:
            logger.exception("Failed to write request log record to %s", self.path)


_logger_singleton: Optional[RequestLogger] = None


def get_request_logger() -> RequestLogger:
    global _logger_singleton
    if _logger_singleton is None:
        _logger_singleton = RequestLogger()
    return _logger_singleton


def record_request(entry: dict[str, Any]) -> None:
    get_request_logger().record(entry)
