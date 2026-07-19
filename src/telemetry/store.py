from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config.settings import settings
from src.pipeline import PIPELINE_VERSION, PipelineResult

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL DEFAULT '',
    pipeline_version TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    run_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at ON pipeline_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_conversation ON pipeline_runs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_version ON pipeline_runs(pipeline_version);
"""


def _get_db_path() -> str:
    path = getattr(settings, "sqlite_path", "data/conversations.db")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _asdict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {f: _asdict(getattr(obj, f)) for f in obj.__dataclass_fields__}
    if isinstance(obj, list):
        return [_asdict(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _asdict(v) for k, v in obj.items()}
    return obj


def save_run(
    result: PipelineResult,
    conversation_id: str = "",
) -> str:
    run_id = str(uuid.uuid4())[:12]
    run_data = _asdict(result)
    run_json_str = json.dumps(run_data, default=str, ensure_ascii=False)
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO pipeline_runs "
                "(id, conversation_id, pipeline_version, created_at, run_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (run_id, conversation_id, PIPELINE_VERSION, _now(), run_json_str),
            )
    except Exception as exc:
        logger.error("Failed to save pipeline run: %s", exc)
    return run_id


def get_run(run_id: str) -> dict[str, Any] | None:
    try:
        with _get_conn() as conn:
            row = conn.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return dict(row)
    except Exception as exc:
        logger.error("Failed to load pipeline run %s: %s", run_id, exc)
        return None


def list_runs(
    conversation_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    try:
        with _get_conn() as conn:
            if conversation_id:
                rows = conn.execute(
                    "SELECT id, conversation_id, pipeline_version, created_at "
                    "FROM pipeline_runs WHERE conversation_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (conversation_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, conversation_id, pipeline_version, created_at "
                    "FROM pipeline_runs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("Failed to list runs: %s", exc)
        return []


def count_runs() -> int:
    try:
        with _get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM pipeline_runs").fetchone()
        return row["cnt"] if row else 0
    except Exception as exc:
        logger.error("Failed to count runs: %s", exc)
        return 0


def get_timing_summary(limit: int = 100) -> dict[str, Any]:
    """Compute per-stage latency statistics across recent runs.

    Returns a dict mapping each stage name to its count, mean, p50, p95,
    and max latency in milliseconds.  Only runs that contain latency data
    are included.
    """
    import statistics

    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT run_json FROM pipeline_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    except Exception as exc:
        logger.error("Failed to load runs for timing summary: %s", exc)
        return {}

    stage_values: dict[str, list[int]] = {}
    for row in rows:
        try:
            run = json.loads(row["run_json"])
            latencies = run.get("latency_ms", {})
            for stage, ms in latencies.items():
                if isinstance(ms, (int, float)):
                    stage_values.setdefault(stage, []).append(int(ms))
        except (json.JSONDecodeError, TypeError):
            continue

    summary: dict[str, Any] = {}
    for stage, values in stage_values.items():
        if not values:
            continue
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        summary[stage] = {
            "count": n,
            "mean": round(statistics.mean(values), 1),
            "p50": round(statistics.median(values), 1),
            "p95": round(sorted_vals[int(n * 0.95)] if n >= 2 else sorted_vals[-1], 1),
            "max": max(values),
        }
    return summary
