from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionStep:
    step: str = ""
    action: str = ""
    priority: str = ""
    rationale: str = ""
    conditions: list[str] = field(default_factory=list)


@dataclass
class DecisionDiagnostics:
    input_problem: str = ""
    completeness: float = 0.0
    risks: list[str] = field(default_factory=list)
    knowledge_needed: list[str] = field(default_factory=list)
    stage: str = ""
    steps: list[DecisionStep] = field(default_factory=list)
    final_action: str = ""
    final_priority: str = ""
    final_rationale: str = ""
    validation: Any = None

    def format(self) -> str:
        lines = ["=" * 60,
                 f"Decision Diagnostics: {self.final_action} ({self.final_priority})",
                 "=" * 60,
                 f"\n  Input:",
                 f"    Problem:    {self.input_problem}",
                 f"    Completeness: {self.completeness:.2f}",
                 f"    Stage:      {self.stage}",
                 f"    Risks:      {', '.join(self.risks) if self.risks else 'none'}",
                 "\n  Trace:"]
        for s in self.steps:
            lines.append(f"\n    {s.step}")
            lines.append(f"      action={s.action} ({s.priority})")
            lines.append(f"      reason={s.rationale}")
            for c in s.conditions:
                lines.append(f"      └ {c}")
        lines.append(f"\n  Final:\n    {self.final_action} ({self.final_priority})"
                     f"\n    {self.final_rationale}")
        lines.append("=" * 60)
        return "\n".join(lines)
