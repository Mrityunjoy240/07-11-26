"""Run the full pipeline with diagnostics, validation, blame, and stats."""
import sys

from src.conversation.state import ConversationState
from src.engines.interfaces import (
    DecisionInput,
    ReasoningInput,
    UnderstandingInput,
)
from src.pipeline import PipelineOrchestrator
from src.validation import (
    EnvironmentInfo,
    GroundTruth,
    ValidationResult,
    attribute_blame,
    build_graph,
    format_blame,
    format_graph,
    run_all_validations,
)
from src.validation.stats import StatsCollector


def _print_validation(vr_dict: dict[str, ValidationResult], prefix: str = ""):
    for stage, vr in vr_dict.items():
        tag = {"PASS": "✓", "WARNING": "!", "FAIL": "✗"}
        print(f"  {prefix}[{tag.get(vr.status, '?')}] {stage}: {vr.status} "
              f"(conf={vr.confidence:.2f}) — {vr.summary}")
        for c in vr.checks:
            t = {"PASS": "  ·", "WARNING": "  !", "FAIL": "  ✗"}
            print(f"  {prefix}{t.get(c.status, '  ?')} {c.name}: {c.detail}")
            if c.confidence < 0.5:
                print(f"  {prefix}    (low confidence: {c.confidence:.2f})")


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "what is the fee for CSE?"

    # Optional ground truth for benchmark mode
    if "--gt" in sys.argv:
        gt = GroundTruth(
            expected_intent="fee",
            expected_problem="needs_fee_information",
            expected_action="provide_fee_info",
            expected_turns=2,
        )
        print("  [GT] Benchmark mode: expected intent=fee, problem=needs_fee_information, action=provide_fee_info")
    else:
        gt = GroundTruth()

    env = EnvironmentInfo(
        llm_type="mock",
        skip_semantic=False,
        tag="debug-script",
    )
    collector = StatsCollector()
    state = ConversationState(session_id="debug")
    p = PipelineOrchestrator()

    # Understanding
    ur = p.understanding.process(UnderstandingInput(query, state=state, debug=True))
    diag = ur.metadata.get("intent_diagnostics")
    if diag:
        print(diag.format() if hasattr(diag, "format") else ur.metadata.get("intent_diagnostics_str", ""))
    print()

    # Reasoning
    rr = p.reasoning.process(ReasoningInput(understanding=ur, state=state, debug=True))
    rdiag = rr.metadata.get("reasoning_diagnostics")
    if rdiag:
        print(rdiag.format())
    print()

    # Decision
    dr = p.decision.process(
        DecisionInput(reasoning=rr, debug=True, metadata={"student_text": query})
    )
    ddiag = dr.metadata.get("decision_diagnostics")
    if ddiag:
        print(ddiag.format())
    print()

    # Planner
    plan = p.planner.process(dr, debug=True)
    pdiag = plan.metadata.get("planner_diagnostics")
    if pdiag:
        print(pdiag.format())
    print()

    # Composer
    cr = p.composer.compose(plan=plan, decision=dr, user_text=query, debug=True)
    print("Response:", cr.text)
    if cr.diagnostics:
        print(cr.diagnostics.format())

    # ── Validation Layer ──────────────────────────────────────────────
    print()
    print("=" * 60)
    print("State Validation (ground-truth + implementation)")
    print("=" * 60)
    vr_dict = run_all_validations(
        intent_diag=diag,
        reasoning_diag=rdiag,
        decision_diag=ddiag,
        planner_diag=pdiag,
        composer_diag=cr.diagnostics if cr else None,
        ground_truth=gt if not gt.is_empty() else None,
        env=env,
    )
    _print_validation(vr_dict)

    # ── Dependency Graph ──────────────────────────────────────────────
    print()
    print(format_graph(build_graph(diag, rdiag, ddiag, pdiag, gt if not gt.is_empty() else None)))

    # ── Blame Attribution ─────────────────────────────────────────────
    graph = build_graph(diag, rdiag, ddiag, pdiag, gt if not gt.is_empty() else None)
    br = attribute_blame(vr_dict, graph)
    print(format_blame(br))

    # ── Stats ─────────────────────────────────────────────────────────
    collector.record(vr_dict)
    print(collector.report())
