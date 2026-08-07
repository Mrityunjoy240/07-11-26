from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Environment Awareness ──────────────────────────────────────────────

@dataclass
class EnvironmentInfo:
    llm_type: str = "unknown"   # "mock" | "groq" | "unknown"
    skip_semantic: bool = False
    tag: str = ""


@dataclass
class GroundTruth:
    expected_intent: str = ""
    expected_problem: str = ""
    expected_action: str = ""
    expected_turns: int = 0

    def is_empty(self) -> bool:
        return not (
            self.expected_intent
            or self.expected_problem
            or self.expected_action
            or self.expected_turns > 0
        )


# ── Single Check ───────────────────────────────────────────────────────

@dataclass
class ValidationCheck:
    name: str = ""
    status: str = "PASS"                # PASS | WARNING | FAIL
    detail: str = ""
    confidence: float = 1.0             # 0.0 – 1.0
    check_type: str = "implementation"   # "implementation" | "semantic" | "dependency"


# ── Result Aggregation ─────────────────────────────────────────────────

def _aggregate_status(checks: list[ValidationCheck]) -> str:
    status = "PASS"
    for c in checks:
        if c.status == "FAIL":
            status = "FAIL"
        elif c.status == "WARNING" and status != "FAIL":
            status = "WARNING"
    return status


def _summary(checks: list[ValidationCheck]) -> str:
    return (f"{sum(1 for c in checks if c.status == 'FAIL')} fail, "
            f"{sum(1 for c in checks if c.status == 'WARNING')} warning, "
            f"{sum(1 for c in checks if c.status == 'PASS')} pass")


def _avg_confidence(checks: list[ValidationCheck], default: float = 1.0) -> float:
    if not checks:
        return default
    return sum(c.confidence for c in checks) / len(checks)


@dataclass
class ValidationResult:
    status: str = "PASS"
    checks: list[ValidationCheck] = field(default_factory=list)
    summary: str = ""
    confidence: float = 1.0

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    @property
    def failed(self) -> bool:
        return self.status == "FAIL"

    @classmethod
    def from_checks(cls, checks: list[ValidationCheck]) -> ValidationResult:
        return cls(
            status=_aggregate_status(checks),
            checks=checks,
            summary=_summary(checks),
            confidence=_avg_confidence(checks),
        )

    def merge(self, other: ValidationResult) -> ValidationResult:
        all_checks = self.checks + other.checks
        status = _aggregate_status(all_checks)
        return ValidationResult(
            status=status,
            checks=all_checks,
            summary=_summary(all_checks),
            confidence=_avg_confidence(all_checks),
        )


# ── Dependency Tracking ────────────────────────────────────────────────

@dataclass
class DependencyNode:
    source_stage: str = ""
    depends_on_stage: str = ""
    depends_on_field: str = ""
    status: str = "PASS"
    detail: str = ""


@dataclass
class DependencyGraph:
    nodes: list[DependencyNode] = field(default_factory=list)

    @property
    def failed(self) -> list[DependencyNode]:
        return [n for n in self.nodes if n.status == "FAIL"]

    @property
    def passed(self) -> list[DependencyNode]:
        return [n for n in self.nodes if n.status == "PASS"]


# ── Blame Attribution ──────────────────────────────────────────────────

@dataclass
class BlameResult:
    root_cause_stage: str = ""
    root_cause_detail: str = ""
    cascade: list[str] = field(default_factory=list)
    blame_chain: list[tuple[str, str, str]] = field(default_factory=list)  # stage, status, detail
    confidence: float = 0.0


# ── Statistics ─────────────────────────────────────────────────────────

@dataclass
class StageStats:
    total: int = 0
    passed: int = 0
    warned: int = 0
    failed: int = 0
    confidences: list[float] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0

    @property
    def avg_confidence(self) -> float:
        return sum(self.confidences) / len(self.confidences) if self.confidences else 0.0

    def add(self, vr: ValidationResult) -> None:
        self.total += 1
        if vr.status == "PASS":
            self.passed += 1
        elif vr.status == "WARNING":
            self.warned += 1
        elif vr.status == "FAIL":
            self.failed += 1
        self.confidences.append(vr.confidence)


@dataclass
class ValidationStats:
    per_stage: dict[str, StageStats] = field(default_factory=dict)
    total_runs: int = 0

    def record(self, results: dict[str, ValidationResult]) -> None:
        self.total_runs += 1
        for stage, vr in results.items():
            if stage not in self.per_stage:
                self.per_stage[stage] = StageStats()
            self.per_stage[stage].add(vr)

    def format_table(self) -> str:
        lines = ["Validation Statistics", "-" * 60,
                 f"{'Stage':<20} {'PASS':>6} {'WARN':>6} {'FAIL':>6} {'Rate':>8} {'Avg Conf':>9}",
                 "-" * 60]
        for stage in sorted(self.per_stage):
            s = self.per_stage[stage]
            lines.append(
                f"{stage:<20} {s.passed:>6} {s.warned:>6} {s.failed:>6} "
                f"{s.pass_rate:>7.0%} {s.avg_confidence:>8.2f}"
            )
        lines.append("-" * 60)
        return "\n".join(lines)
