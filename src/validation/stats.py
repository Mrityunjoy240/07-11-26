"""Aggregate validation statistics across multiple runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.validation.models import ValidationStats


class StatsCollector:
    """Accumulates validation results and produces summary statistics."""

    def __init__(self) -> None:
        self.stats = ValidationStats()

    def record(self, results: dict[str, Any]) -> None:
        """Record a single run's validation results.

        Accepts both ValidationResult objects and dicts of
        serialized validation data.
        """
        from src.validation.models import ValidationResult

        parsed: dict[str, ValidationResult] = {}
        for stage, vr in results.items():
            if isinstance(vr, dict):
                parsed[stage] = ValidationResult(
                    status=vr.get("status", "PASS"),
                    confidence=vr.get("confidence", 1.0),
                )
            elif isinstance(vr, ValidationResult):
                parsed[stage] = vr
        self.stats.record(parsed)

    def report(self) -> str:
        return self.stats.format_table()

    def save(self, path: str | Path) -> None:
        data = {
            "total_runs": self.stats.total_runs,
            "per_stage": {
                stage: {
                    "total": s.total,
                    "passed": s.passed,
                    "warned": s.warned,
                    "failed": s.failed,
                    "pass_rate": round(s.pass_rate, 4),
                    "avg_confidence": round(s.avg_confidence, 4),
                }
                for stage, s in self.stats.per_stage.items()
            },
        }
        Path(path).write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> StatsCollector:
        data = json.loads(Path(path).read_text())
        sc = cls()
        sc.stats.total_runs = data["total_runs"]
        for stage, sdata in data["per_stage"].items():
            from src.validation.models import StageStats
            ss = StageStats(
                total=sdata["total"],
                passed=sdata["passed"],
                warned=sdata["warned"],
                failed=sdata["failed"],
                confidences=[sdata["avg_confidence"]],
            )
            sc.stats.per_stage[stage] = ss
        return sc
