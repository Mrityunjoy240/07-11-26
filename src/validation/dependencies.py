"""Dependency graph for the pipeline.

Each stage depends on specific fields produced by earlier stages.
This module checks whether those dependencies are satisfied and
records the dependency chain so blame attribution can walk it.
"""

from __future__ import annotations

from src.decision.models import DecisionDiagnostics
from src.understanding.models import IntentDiagnostics
from src.planner.models import PlannerDiagnostics
from src.reasoning.models import ReasoningDiagnostics
from src.validation.models import (
    DependencyGraph,
    DependencyNode,
    GroundTruth,
)

# ── Pipeline stage order ────────────────────────────────────────────────

_STAGE_ORDER = [
    "understanding",
    "reasoning",
    "decision",
    "planner",
    "composer",
]


def build_graph(
    intent_diag: IntentDiagnostics | None,
    reasoning_diag: ReasoningDiagnostics | None,
    decision_diag: DecisionDiagnostics | None,
    planner_diag: PlannerDiagnostics | None,
    ground_truth: GroundTruth | None = None,
) -> DependencyGraph:
    """Build the dependency graph by checking each stage's inputs."""
    nodes: list[DependencyNode] = []

    # Understanding depends on raw text only — always available
    if intent_diag:
        nodes.append(DependencyNode(
            source_stage="understanding",
            depends_on_stage="input",
            depends_on_field="text",
            status="PASS",
            detail="Raw input text available",
        ))

    # Reasoning depends on: intent, profile completeness, signals
    if reasoning_diag and intent_diag:
        intent_ok = intent_diag.winner != "unknown"
        nodes.append(DependencyNode(
            source_stage="reasoning",
            depends_on_stage="understanding",
            depends_on_field="intent",
            status="PASS" if intent_ok else "FAIL",
            detail=(f"Intent='{intent_diag.winner}' (conf={intent_diag.confidence:.3f})"
                    if intent_ok else "Intent is 'unknown'"),
        ))
        nodes.append(DependencyNode(
            source_stage="reasoning",
            depends_on_stage="understanding",
            depends_on_field="signals",
            status="PASS",
            detail=f"Signal='{reasoning_diag.dominant_signal}' ({reasoning_diag.signal_score:.2f})",
        ))
        nodes.append(DependencyNode(
            source_stage="reasoning",
            depends_on_stage="understanding",
            depends_on_field="profile_completeness",
            status="PASS",
            detail=f"Completeness={reasoning_diag.profile_completeness:.2f}",
        ))

    # Decision depends on: problem (from reasoning)
    if decision_diag and reasoning_diag:
        problem_ok = bool(decision_diag.input_problem)
        nodes.append(DependencyNode(
            source_stage="decision",
            depends_on_stage="reasoning",
            depends_on_field="problem",
            status="PASS" if problem_ok else "FAIL",
            detail=f"Problem='{decision_diag.input_problem}'" if problem_ok else "No problem identified",
        ))

    # Planner depends on: action (from decision)
    if planner_diag and decision_diag:
        action_ok = bool(planner_diag.input_action)
        nodes.append(DependencyNode(
            source_stage="planner",
            depends_on_stage="decision",
            depends_on_field="action",
            status="PASS" if action_ok else "FAIL",
            detail=f"Action='{planner_diag.input_action}'" if action_ok else "No action",
        ))

    # Composer depends on: plan turns and decision context
    if planner_diag:
        has_turns = len(planner_diag.generated_turns) > 0
        nodes.append(DependencyNode(
            source_stage="composer",
            depends_on_stage="planner",
            depends_on_field="turns",
            status="PASS" if has_turns else "FAIL",
            detail=f"{len(planner_diag.generated_turns)} turn(s) available" if has_turns else "No turns generated",
        ))

    # Ground-truth dependencies (benchmark mode)
    if ground_truth and not ground_truth.is_empty():
        if intent_diag and ground_truth.expected_intent:
            nodes.append(DependencyNode(
                source_stage="benchmark",
                depends_on_stage="understanding",
                depends_on_field="expected_intent",
                status="PASS" if intent_diag.winner == ground_truth.expected_intent else "FAIL",
                detail=f"Expected '{ground_truth.expected_intent}', got '{intent_diag.winner}'",
            ))
        if reasoning_diag and ground_truth.expected_problem:
            nodes.append(DependencyNode(
                source_stage="benchmark",
                depends_on_stage="reasoning",
                depends_on_field="expected_problem",
                status="PASS" if reasoning_diag.winner == ground_truth.expected_problem else "FAIL",
                detail=f"Expected '{ground_truth.expected_problem}', got '{reasoning_diag.winner}'",
            ))
        if decision_diag and ground_truth.expected_action:
            nodes.append(DependencyNode(
                source_stage="benchmark",
                depends_on_stage="decision",
                depends_on_field="expected_action",
                status="PASS" if decision_diag.final_action == ground_truth.expected_action else "FAIL",
                detail=f"Expected '{ground_truth.expected_action}', got '{decision_diag.final_action}'",
            ))

    return DependencyGraph(nodes=nodes)


def format_graph(graph: DependencyGraph) -> str:
    """Pretty-print the dependency graph."""
    lines = ["Dependency Graph", "-" * 60]
    for node in graph.nodes:
        tag = {"PASS": "✓", "WARNING": "!", "FAIL": "✗"}.get(node.status, "?")
        lines.append(
            f"  [{tag}] {node.source_stage}"
            f" ← {node.depends_on_stage}.{node.depends_on_field}"
        )
        lines.append(f"       {node.detail}")
    lines.append("-" * 60)
    return "\n".join(lines)
