from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EligibilityEstimate:
    likely: bool = False
    branches: list[str] = field(default_factory=list)
    confidence: float = 0.0
    note: str = ""


@dataclass
class ReadinessResult:
    domain: str = ""
    ready: bool = False
    blocked: bool = False
    missing_critical: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)
    completeness: float = 0.0

    def format(self) -> str:
        if self.blocked:
            m = ", ".join(self.missing_critical) if self.missing_critical else "profile"
            return f"{self.domain}: BLOCKED — missing {m} ({self.completeness:.0%})"
        if self.ready:
            return f"{self.domain}: ready (fields={self.completeness:.0%})"
        m = ", ".join(self.missing_critical)
        return f"{self.domain}: partial — missing {m} ({self.completeness:.0%})"


@dataclass
class ReasoningResult:
    student_stage: str = "discovery"
    profile_completeness: float = 0.0
    readiness: ReadinessResult | None = None
    eligibility: EligibilityEstimate = field(default_factory=EligibilityEstimate)
    current_problem: str = ""
    unknowns: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    knowledge_needed: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleEval:
    condition: str = ""
    matched: bool = False
    score: float = 0.0
    result: str = ""


@dataclass
class FeatureContribution:
    feature: str = ""
    value: float = 0.0
    contribution: float = 0.0
    description: str = ""


@dataclass
class RuleExplanation:
    rule_name: str = ""
    result: str = ""
    base_score: float = 0.0
    features: list[FeatureContribution] = field(default_factory=list)
    final_score: float = 0.0
    matched: bool = False


@dataclass
class ReasoningDiagnostics:
    input_intent: str = ""
    intent_confidence: float = 0.0
    dominant_signal: str = ""
    signal_score: float = 0.0
    profile_completeness: float = 0.0
    stage: str = ""
    confidence_score: float = 0.0
    problems_traced: list[RuleEval] = field(default_factory=list)
    explanations: list[RuleExplanation] = field(default_factory=list)
    runner_up: str = ""
    margin: float = 0.0
    winner: str = ""
    validation: Any = None

    def format(self) -> str:
        lines = ["=" * 60,
                 f"Reasoning Diagnostics: {self.winner}",
                 "=" * 60,
                 f"\n  Context:",
                 f"    Intent:       {self.input_intent} ({self.intent_confidence:.3f})",
                 f"    Signal:       {self.dominant_signal} ({self.signal_score:.2f})",
                 f"    Completeness: {self.profile_completeness:.2f}",
                 f"    Stage:        {self.stage}",
                 f"    Confidence:   {self.confidence_score:.3f}",
                 "\n  Problem Rules:"]
        for r in self.problems_traced:
            mark = "✓" if r.matched else "✗"
            lines.append(f"    {mark} {r.condition}")
            if r.matched and r.result:
                lines.append(f"       → {r.result}")
        if self.explanations:
            lines.append("\n  Feature Explanations:")
            for ex in self.explanations:
                lvl = ">>>" if ex.matched else "   "
                lines.append(f"  {lvl} {ex.rule_name}: {ex.final_score:.2f} → {ex.result}")
                for fc in ex.features:
                    lines.append(f"        {fc.feature}={fc.value:.2f} ({fc.contribution:+.2f}) {fc.description}")
        if self.runner_up:
            lines.append(f"\n  Runner-up: {self.runner_up}  (margin: {self.margin:.3f})")
        lines.append(f"\n  Winner:\n    {self.winner}")
        lines.append("=" * 60)
        return "\n".join(lines)
