"""Blame attribution.

Walks the pipeline in order to find the earliest stage that went
wrong, then reports every downstream stage as a cascade.
"""

from __future__ import annotations

from src.validation.dependencies import _STAGE_ORDER
from src.validation.models import (
    BlameResult,
    DependencyGraph,
    ValidationResult,
)


def attribute_blame(
    results: dict[str, ValidationResult],
    graph: DependencyGraph | None = None,
) -> BlameResult:
    """Find the root cause and cascade."""

    # Filter to known stages in order
    ordered: list[tuple[str, ValidationResult]] = []
    for stage in _STAGE_ORDER:
        vr = results.get(stage)
        if vr is not None:
            ordered.append((stage, vr))

    if not ordered:
        return BlameResult(
            root_cause_stage="none",
            root_cause_detail="No validation results",
            blame_chain=[],
            confidence=1.0,
        )

    # Find earliest FAIL
    root_stage = ""
    root_detail = ""
    cascade: list[str] = []
    chain: list[tuple[str, str, str]] = []

    found_root = False
    for stage, vr in ordered:
        chain.append((stage, vr.status, vr.summary))
        if not found_root and vr.status == "FAIL":
            root_stage = stage
            root_detail = vr.summary
            found_root = True
        elif found_root:
            cascade.append(stage)

    # If no FAIL, look for WARNING
    if not found_root:
        for stage, vr in ordered:
            if vr.status == "WARNING":
                root_stage = stage
                root_detail = vr.summary
                for s, v in ordered:
                    if s == stage:
                        break
                cascade = [s for s, _ in ordered if ordered.index((s, _)) > ordered.index((stage, vr))]
                break

    # Confidence: if graph shows dependency failures confirming blame, boost it
    confidence = 0.85  # base
    if graph and root_stage:
        # Count dependency nodes that point to root_stage as failing
        failing_deps = [n for n in graph.nodes if n.status == "FAIL"]
        if failing_deps:
            confidence = min(0.95, 0.85 + 0.05 * len(failing_deps))

    return BlameResult(
        root_cause_stage=root_stage or "none",
        root_cause_detail=root_detail or "No failures detected",
        cascade=cascade,
        blame_chain=chain,
        confidence=confidence,
    )


def format_blame(br: BlameResult) -> str:
    """Pretty-print the blame chain."""
    lines = ["Blame Attribution", "-" * 60]
    if not br.blame_chain:
        lines.append("  No failures detected.")
        lines.append("-" * 60)
        return "\n".join(lines)

    for stage, status, summary in br.blame_chain:
        tag = {"PASS": "✓", "WARNING": "!", "FAIL": "✗"}.get(status, "?")
        suffix = " ← ROOT CAUSE" if stage == br.root_cause_stage else ""
        suffix += " (cascade)" if stage in br.cascade else ""
        lines.append(f"  [{tag}] {stage}{suffix}")
        lines.append(f"         {summary}")

    if br.root_cause_stage and br.root_cause_stage != "none":
        lines.append("")
        lines.append(f"  Root cause: {br.root_cause_stage}")
        lines.append(f"  Detail:     {br.root_cause_detail}")
        lines.append(f"  Confidence: {br.confidence:.2f}")
        if br.cascade:
            lines.append(f"  Cascade:    {' → '.join(br.cascade)}")
    lines.append("-" * 60)
    return "\n".join(lines)
