from __future__ import annotations

import json
from pathlib import Path

from src.fabric.eval_store import EvalRecord, EvalStore


class JsonEvalStore(EvalStore):
    def __init__(self, directory: str | Path = "data/eval") -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)

    def save(self, record: EvalRecord) -> None:
        path = self._directory / f"{record.conversation_id}.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record_to_dict(record), ensure_ascii=False) + "\n")

    def load(self, conversation_id: str) -> list[EvalRecord]:
        path = self._directory / f"{conversation_id}.jsonl"
        if not path.exists():
            return []
        records: list[EvalRecord] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(dict_to_record(json.loads(line)))
        return records


def record_to_dict(record: EvalRecord) -> dict:
    return {
        "conversation_id": record.conversation_id,
        "turn_index": record.turn_index,
        "runtime": record.runtime,
        "query": record.query,
        "response": record.response,
        "structured_output": record.structured_output,
        "tool_calls": list(record.tool_calls),
        "latency_ms": record.latency_ms,
        "checks_passed": record.checks_passed,
        "checks_total": record.checks_total,
        "score": record.score,
        "trace_id": record.trace_id,
        "metadata": record.metadata,
    }


def dict_to_record(data: dict) -> EvalRecord:
    return EvalRecord(
        conversation_id=data["conversation_id"],
        turn_index=data["turn_index"],
        runtime=data.get("runtime", ""),
        query=data.get("query", ""),
        response=data.get("response", ""),
        structured_output=data.get("structured_output"),
        tool_calls=list(data.get("tool_calls", [])),
        latency_ms=float(data.get("latency_ms", 0.0)),
        checks_passed=int(data.get("checks_passed", 0)),
        checks_total=int(data.get("checks_total", 0)),
        score=float(data.get("score", 0.0)),
        trace_id=data.get("trace_id"),
        metadata=data.get("metadata", {}),
    )
