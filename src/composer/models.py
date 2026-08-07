from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComposerDiagnostics:
    system_prompt: str = ""
    history_used: list[dict] = field(default_factory=list)
    user_message: str = ""
    serialized_plan: str = ""
    decision_context: str = ""
    brain_context: str = ""
    final_prompt: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""
    temperature: float = 0.0
    finish_reason: str = ""
    raw_llm_response: str = ""
    parsed_response: str = ""
    final_output: str = ""
    followed_plan: bool = True
    violations: list[str] = field(default_factory=list)
    hallucination_risk: str = "low"
    validation: Any = None

    def format(self) -> str:
        lines = ["=" * 60,
                 f"Composer Diagnostics: {self.finish_reason}",
                 "=" * 60,
                 f"\n  LLM: {self.model} (temp={self.temperature})",
                 f"  Tokens: {self.prompt_tokens} prompt + {self.completion_tokens} completion = {self.total_tokens}",
                 f"  Latency: {self.latency_ms:.0f}ms",
                 f"  Finish: {self.finish_reason}",
                 "\n  Plan Following:",
                 f"    Followed: {self.followed_plan}",
                 f"    Violations: {', '.join(self.violations) if self.violations else 'none'}",
                 f"    Hallucination risk: {self.hallucination_risk}",
                 "\n  Final Output:",
                 f"    {self.final_output[:300]}" + ("..." if len(self.final_output) > 300 else ""),
                 "\n  Raw Response:",
                 f"    {self.raw_llm_response[:200]}" + ("..." if len(self.raw_llm_response) > 200 else ""),
                 ]
        if self.final_prompt:
            lines.append("\n  Full Prompt (last 1000 chars):")
            lines.append(f"    ...{self.final_prompt[-1000:]}" if len(self.final_prompt) > 1000 else f"    {self.final_prompt}")
        lines.append("=" * 60)
        return "\n".join(lines)


@dataclass
class ComposerResult:
    text: str
    diagnostics: ComposerDiagnostics | None = None
