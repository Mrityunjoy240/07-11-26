from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Turn:
    speaker: str = "assistant"
    action: str = ""
    content: str = ""
    expected_input: str = ""
    confidence: float = 0.0


@dataclass
class Plan:
    turns: list[Turn] = field(default_factory=list)
    confidence: float = 0.0
    escalate: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerDiagnostics:
    input_action: str = ""
    input_rationale: str = ""
    handler_selected: str = ""
    handler_reason: str = ""
    templates_used: list[str] = field(default_factory=list)
    generated_turns: list[Turn] = field(default_factory=list)
    expected_inputs: str = ""
    was_fallback: bool = False
    validation: Any = None

    def format(self) -> str:
        lines = ["=" * 60,
                 f"Planner Diagnostics: {self.handler_selected}",
                 "=" * 60,
                 f"\n  Input:",
                 f"    Action:   {self.input_action}",
                 f"    Rationale: {self.input_rationale[:100]}",
                 f"\n  Handler: {self.handler_selected}",
                 f"    Reason:  {self.handler_reason}",
                 f"    Fallback: {self.was_fallback}",
                 "\n  Turns:"]
        for i, t in enumerate(self.generated_turns, 1):
            ei = f" [expects: {t.expected_input}]" if t.expected_input else ""
            lines.append(f"    {i}. [{t.action}] {t.content[:100]}{ei}")
        lines.append(f"\n  Templates: {', '.join(self.templates_used) if self.templates_used else 'none'}")
        lines.append("=" * 60)
        return "\n".join(lines)
