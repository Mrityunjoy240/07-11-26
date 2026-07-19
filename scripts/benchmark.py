#!/usr/bin/env python3
"""
Real benchmark: run the actual Groq pipeline against all gold conversations.

Usage:
    python scripts/benchmark.py                    # run new pipeline on all v0.1 + v0.2
    python scripts/benchmark.py --old              # run legacy GroqService too (if available)
    python scripts/benchmark.py --conversation ADM_LOWRANK_001  # single conversation
    python scripts/benchmark.py --markdown         # output as markdown table
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Ensure GROQ_API_KEY is set
if not os.getenv("GROQ_API_KEY"):
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("GROQ_API_KEY="):
                os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip()
                break

from src.conversation.state import ConversationState
from src.pipeline import PipelineOrchestrator, PipelineResult

from scripts.evaluate import (
    ConversationResult,
    TurnResult,
    StageResult,
    CheckResult,
    evaluate_conversation,
    evaluate_turn,
    load_conversation,
    load_all,
    mock_pipeline_result,
    print_result,
    print_summary,
)

# ── Understanding sub-metrics ──────────────────────────────────────────────

@dataclass
class UnderstandingSubMetrics:
    intent_score: float = 0.0
    intent_checks: int = 0
    entity_score: float = 0.0
    entity_checks: int = 0
    missing_score: float = 0.0
    missing_checks: int = 0
    signal_score: float = 0.0
    signal_checks: int = 0
    domain_score: float = 0.0
    domain_checks: int = 0


def compute_understanding_submetrics(
    pipeline_u: dict, expected_u: dict, expected_turn: dict
) -> UnderstandingSubMetrics:
    """Compute per-sub-metric scores for understanding."""
    m = UnderstandingSubMetrics()

    # Intent: does pipeline intent match expected?
    exp_intent = expected_u.get("intent", "")
    act_intent = pipeline_u.get("intent", {}).get("primary", "")
    if exp_intent:
        m.intent_checks = 1
        m.intent_score = 1.0 if act_intent == exp_intent else 0.0

    # Entities: which expected facts were extracted?
    exp_facts = expected_u.get("facts", {})
    act_facts = pipeline_u.get("facts", {})
    for field, exp_val in exp_facts.items():
        if exp_val is not None:
            m.entity_checks += 1
            if act_facts.get(field) == exp_val:
                m.entity_score += 1

    if m.entity_checks > 0:
        m.entity_score /= m.entity_checks

    # Missing info: overlap between expected missing and actual missing
    exp_missing = set(expected_u.get("missing", []))
    act_missing = set(pipeline_u.get("missing", []))
    if exp_missing or act_missing:
        m.missing_checks = 1
        if exp_missing and act_missing:
            overlap = len(exp_missing & act_missing)
            max_len = max(len(exp_missing), len(act_missing))
            m.missing_score = overlap / max_len if max_len > 0 else 1.0
        elif not exp_missing and not act_missing:
            m.missing_score = 1.0
        else:
            m.missing_score = 0.0

    # Signals: check inference accuracy if expected has inference
    exp_inference = expected_u.get("inference", {})
    if exp_inference:
        _SIGNAL_NAME_MAP = {
            "parent_mode": "parent_influence",
            "budget_concern": "financial_concern",
            "parent_pressure": "parent_influence",
        }
        m.signal_checks = len(exp_inference)
        for sig_name, exp_val in exp_inference.items():
            pipeline_sig = _SIGNAL_NAME_MAP.get(sig_name, sig_name)
            act_val = pipeline_u.get("signals", {}).get(pipeline_sig)
            if isinstance(exp_val, bool):
                if act_val is not None:
                    act_bool = bool(act_val) if not isinstance(act_val, bool) else act_val
                    m.signal_score += 1.0 if act_bool == exp_val else 0.0
                else:
                    m.signal_score += 0.0
            else:
                m.signal_score += 0.5  # partial credit for non-boolean

        if m.signal_checks > 0:
            m.signal_score /= m.signal_checks

    # Domain interpretation: pathway and student_type
    pipeline_domain = pipeline_u.get("domain", {})
    if pipeline_domain:
        m.domain_checks = 2  # pathway + student_type
        exp_pathway = expected_turn.get("domain_pathway", "regular")
        act_pathway = pipeline_domain.get("pathway", "regular")
        if act_pathway == exp_pathway:
            m.domain_score += 1.0
        exp_student_type = expected_turn.get("domain_student_type", "prospective")
        act_student_type = pipeline_domain.get("student_type", "prospective")
        if act_student_type == exp_student_type:
            m.domain_score += 1.0
        m.domain_score /= 2

    return m


# ── Legacy service import ──────────────────────────────────────────────────

_OLD_SERVICE = None


def _get_old_service() -> Any:
    global _OLD_SERVICE
    if _OLD_SERVICE is not None:
        return _OLD_SERVICE
    try:
        import sys
        legacy_paths = [
            Path("21-06-26-college-agent/backend"),
            Path("college_agent-master/backend"),
        ]
        for p in legacy_paths:
            if p.exists():
                sys.path.insert(0, str(p.resolve()))
        from app.services.llm import get_groq_service
        _OLD_SERVICE = get_groq_service()
        return _OLD_SERVICE
    except Exception as exc:
        print(f"  [WARN] Legacy GroqService not available: {exc}", file=sys.stderr)
        return None


# ── Pipeline runners ───────────────────────────────────────────────────────

_PROFILE_TO_FLAT = {
    "academic.rank": "rank",
    "academic.pcm_percentage": "pcm_percentage",
    "academic.exam": "exam",
    "academic.board": "board",
    "academic.qualification": "qualification",
    "academic.diploma_percentage": "diploma_percentage",
    "academic.diploma_branch": "diploma_branch",
    "academic.exam": "exam",
    "academic.current_college": "current_college",
    "academic.current_branch": "current_branch",
    "academic.current_year": "current_year",
    "personal.category": "category",
    "personal.gender": "gender",
    "personal.location": "location",
    "personal.budget": "budget",
    "personal.hostel_required": "hostel_requirement",
    "career.interest": "interest",
    "career.preferred_branch": "preferred_branch",
    "career.career_goal": "career_goal",
}


def _pipeline_to_dict(pr: PipelineResult) -> dict:
    """Convert PipelineResult to the format expected by evaluate_turn.

    The evaluator expects:
        understanding: {"intent": {"primary": "..."},
                       "facts": {"rank": 12000, ...},
                       "missing": [...]}
        decision: {"action": "..."}
        plan: {"turns": [{"action": "...", "content": "..."}, ...]}
        response: "..."
    """
    u_dict: dict[str, Any] = {}
    if pr.understanding is not None:
        u = pr.understanding
        intent_primary = getattr(u.intent, "primary", "unknown") if hasattr(u, "intent") else "unknown"
        facts_dict: dict[str, Any] = {}

        profile = getattr(u, "profile", None)
        if profile is not None:
            facts_dict["rank"] = profile.academic.rank
            facts_dict["pcm_percentage"] = profile.academic.pcm_percentage
            facts_dict["exam"] = profile.academic.exam
            facts_dict["board"] = profile.academic.board
            facts_dict["interest"] = profile.career.interest
            facts_dict["category"] = profile.personal.category
            facts_dict["budget"] = profile.personal.budget
            facts_dict["location"] = profile.personal.location
        else:
            for f in getattr(u, "facts", []):
                if hasattr(f, "field") and hasattr(f, "value"):
                    facts_dict[f.field] = f.value

        missing_raw = list(getattr(getattr(u, "missing_info", None), "items", []) or [])
        missing = [_PROFILE_TO_FLAT.get(m, m) for m in missing_raw]
        u_dict = {
            "intent": {"primary": intent_primary},
            "facts": facts_dict,
            "missing": missing,
        }

    d_dict: dict[str, Any] = {}
    if pr.decision is not None:
        d = pr.decision
        d_dict = {"action": getattr(d, "action", "")}

    plan_dict: dict[str, Any] = {}
    if pr.plan is not None:
        plan = pr.plan
        turns_raw = getattr(plan, "turns", [])
        plan_dict["turns"] = [
            {"action": getattr(t, "action", ""), "content": getattr(t, "content", "")}
            for t in turns_raw
        ]

    brain_dict: dict[str, Any] = {}
    if pr.brain_response is not None and pr.brain_response.admission is not None:
        adm = pr.brain_response.admission
        brain_dict["applicable"] = adm.applicable
        brain_dict["eligible_branches"] = list(adm.data.get("eligible_branches", []))
        brain_dict["why"] = [{"condition": r.condition, "met": r.met, "detail": r.detail} for r in adm.why]

    reasoning_dict: dict[str, Any] = {}
    if pr.reasoning is not None:
        rr = pr.reasoning
        reasoning_dict["stage"] = rr.student_stage
        reasoning_dict["profile_completeness"] = rr.profile_completeness
        # Map float confidence to string label for gold comparison
        if rr.confidence >= 0.7:
            reasoning_dict["confidence"] = "high"
        elif rr.confidence >= 0.4:
            reasoning_dict["confidence"] = "medium"
        else:
            reasoning_dict["confidence"] = "low"
        reasoning_dict["problems"] = rr.risks + rr.unknowns
        reasoning_dict["current_problem"] = rr.current_problem

    # Extract domain interpretation from understanding result
    domain_dict: dict[str, Any] = {}
    if pr.understanding is not None:
        u = pr.understanding
        domain = getattr(u, "domain", None)
        if domain is not None:
            domain_dict = {
                "pathway": getattr(domain, "pathway", "regular"),
                "student_type": getattr(domain, "student_type", "prospective"),
                "qualification": getattr(domain, "qualification", "12th"),
                "primary_intent": getattr(domain, "primary_intent", "unknown"),
                "all_intents": list(getattr(domain, "all_intents", [])),
                "domain_entities": dict(getattr(domain, "domain_entities", {})),
            }

    # Add domain sub-dict inside understanding
    u_dict["domain"] = domain_dict

    # Add raw signals
    if pr.understanding is not None:
        u = pr.understanding
        sig = getattr(u, "signals", None)
        if sig is not None and hasattr(sig, "__dict__"):
            u_dict["signals"] = {k: float(v) for k, v in sig.__dict__.items() if not k.startswith("_")}

    return {
        "understanding": u_dict,
        "reasoning": reasoning_dict,
        "brain": brain_dict,
        "decision": d_dict,
        "plan": plan_dict,
        "response": pr.response or "",
        "latency_ms": pr.latency_ms,
        "versions": pr.versions,
    }


def run_new_pipeline(text: str, pipeline: PipelineOrchestrator | None = None, state: ConversationState | None = None) -> dict | None:
    p = pipeline or PipelineOrchestrator()
    try:
        if state is None:
            state = ConversationState(session_id="benchmark")
        result = p.run(text, state=state)
        return _pipeline_to_dict(result)
    except Exception as exc:
        print(f"    [ERROR] New pipeline: {exc}")
        return None


def run_old_pipeline(text: str) -> dict | None:
    svc = _get_old_service()
    if svc is None:
        return None
    try:
        if hasattr(svc, "answer_question"):
            resp = svc.answer_question(text) or ""
        elif hasattr(svc, "handle_query"):
            resp = svc.handle_query(text) or ""
        else:
            return None
        return {
            "understanding": {},
        "reasoning": reasoning_dict,
            "brain": {},
            "decision": {},
            "plan": {"turns": []},
            "response": resp,
        }
    except Exception as exc:
        print(f"    [ERROR] Old pipeline: {exc}")
        return None


# ── Rich per-stage report ──────────────────────────────────────────────────

@dataclass
class BenchmarkRow:
    conv_id: str
    difficulty: int
    turns: int
    new_score: float = 0.0
    new_passed: int = 0
    new_total: int = 0
    new_latency_ms: float = 0.0
    new_errors: list[str] = field(default_factory=list)
    new_stages: dict[str, float] = field(default_factory=dict)
    new_submetrics: list[UnderstandingSubMetrics] = field(default_factory=list)
    old_score: float = 0.0
    old_passed: int = 0
    old_total: int = 0
    old_latency_ms: float = 0.0
    old_errors: list[str] = field(default_factory=list)
    old_stages: dict[str, float] = field(default_factory=dict)


def run_conversation(conv: dict, pipeline: PipelineOrchestrator, use_old: bool = False) -> BenchmarkRow:
    conv_id = conv["id"]
    row = BenchmarkRow(conv_id=conv_id, difficulty=conv.get("difficulty", 0), turns=len(conv.get("turns", [])))

    # Maintain conversational state across turns
    state = ConversationState(session_id=f"benchmark_{conv_id}")

    new_results: list[dict] = []
    for i, turn in enumerate(conv.get("turns", [])):
        t0 = time.perf_counter()
        r = run_new_pipeline(turn.get("student", ""), pipeline, state=state)
        if r:
            row.new_latency_ms += r.get("latency_ms", {}).get("total", 0)
        new_results.append(r)
        if r is None:
            row.new_errors.append(f"Turn {i}: pipeline returned None")

    valid_results = [r for r in new_results if r is not None]
    if valid_results:
        result = evaluate_conversation(conv, new_results)
        row.new_score = result.overall_score
        row.new_passed = result.total_passed
        row.new_total = result.total_checks
        stage_counts: dict[str, list[float]] = {}
        for tr in result.turn_results:
            for sname, stage in tr.stages.items():
                if stage.total > 0:
                    stage_counts.setdefault(sname, []).append(stage.score)

        # Compute understanding sub-metrics per turn
        for i, turn in enumerate(conv.get("turns", [])):
            pr = new_results[i] if i < len(new_results) else None
            if pr and pr.get("understanding"):
                exp = turn.get("expected", {}).get("understanding", {})
                sm = compute_understanding_submetrics(pr["understanding"], exp, turn)
                row.new_submetrics.append(sm)

        for sname, scores in stage_counts.items():
            row.new_stages[sname] = sum(scores) / len(scores)
        avg_latency = row.new_latency_ms / len(valid_results)
        row.new_latency_ms = round(avg_latency, 1)

    if use_old:
        old_results: list[dict] = []
        for i, turn in enumerate(conv.get("turns", [])):
            t0 = time.perf_counter()
            r = run_old_pipeline(turn.get("student", ""))
            if r:
                row.old_latency_ms += (time.perf_counter() - t0) * 1000
            old_results.append(r)
            if r is None:
                row.old_errors.append(f"Turn {i}: old pipeline returned None")

        old_valid = [r for r in old_results if r is not None]
        if old_valid:
            result = evaluate_conversation(conv, old_results)
            row.old_score = result.overall_score
            row.old_passed = result.total_passed
            row.old_total = result.total_checks
            stage_counts: dict[str, list[float]] = {}
            for tr in result.turn_results:
                for sname, stage in tr.stages.items():
                    if stage.total > 0:
                        stage_counts.setdefault(sname, []).append(stage.score)
            for sname, scores in stage_counts.items():
                row.old_stages[sname] = sum(scores) / len(scores)
            avg_latency = row.old_latency_ms / len(old_valid)
            row.old_latency_ms = round(avg_latency, 1)

    return row


def _aggregate_understanding_submetrics(rows: list[BenchmarkRow]) -> dict[str, float]:
    """Aggregate understanding sub-metrics from all conversations."""
    total = {"intent": 0.0, "entity": 0.0, "missing": 0.0, "signal": 0.0, "domain": 0.0}
    counts = {"intent": 0, "entity": 0, "missing": 0, "signal": 0, "domain": 0}
    for r in rows:
        for sm in getattr(r, "new_submetrics", []):
            if sm.intent_checks > 0:
                total["intent"] += sm.intent_score
                counts["intent"] += 1
            if sm.entity_checks > 0:
                total["entity"] += sm.entity_score
                counts["entity"] += 1
            if sm.missing_checks > 0:
                total["missing"] += sm.missing_score
                counts["missing"] += 1
            if sm.signal_checks > 0:
                total["signal"] += sm.signal_score
                counts["signal"] += 1
            if sm.domain_checks > 0:
                total["domain"] += sm.domain_score
                counts["domain"] += 1
    return {
        k: (total[k] / counts[k] if counts[k] > 0 else 0.0)
        for k in total
    }


def print_benchmark_table(rows: list[BenchmarkRow], use_old: bool) -> None:
    if not rows:
        return

    # Aggregate stage scores
    stage_names = ["understanding", "reasoning", "brain", "decision", "planner"]

    # Per-conversation breakdown
    print(f"\n{'='*80}")
    print(f"  BENCHMARK RESULTS — New Pipeline (GroqLLM)")
    if use_old:
        print(f"  Old vs New comparison")
    print(f"{'='*80}")

    for row in rows:
        status = "✗" if row.new_score < 0.7 else "✓"
        print(f"\n  {status} {row.conv_id:25s}  diff={row.difficulty}  turns={row.turns}")
        print(f"      New:  {row.new_passed:3d}/{row.new_total:<3d} ({row.new_score*100:5.1f}%)  avg_latency={row.new_latency_ms:7.1f}ms")
        for s in stage_names:
            pct = row.new_stages.get(s, 0.0)
            # Normalize: aggregate weighted scores / total
            total_for_stage = sum(1 for tr in [])  # placeholder
            bar = "█" * int(pct * 10) + "░" * int((1 - pct) * 10)
            print(f"         {s:15s} {bar} {pct*100:5.1f}%")

        if use_old and row.old_total > 0:
            print(f"      Old:  {row.old_passed:3d}/{row.old_total:<3d} ({row.old_score*100:5.1f}%)  avg_latency={row.old_latency_ms:7.1f}ms")
            for s in stage_names:
                pct = row.old_stages.get(s, 0.0)
                bar = "█" * int(pct * 10) + "░" * int((1 - pct) * 10)
                print(f"         {s:15s} {bar} {pct*100:5.1f}%")

        if row.new_errors:
            for e in row.new_errors:
                print(f"      ⚠ {e}")
        if use_old and row.old_errors:
            for e in row.old_errors:
                print(f"      ⚠ {e}")

    # Summary
    total_new_p = sum(r.new_passed for r in rows)
    total_new_c = sum(r.new_total for r in rows)
    avg_new = total_new_p / total_new_c if total_new_c > 0 else 0.0
    print(f"\n  {'─'*60}")
    print(f"  TOTAL NEW: {total_new_p}/{total_new_c} ({avg_new*100:.1f}%)")

    if use_old:
        total_old_p = sum(r.old_passed for r in rows)
        total_old_c = sum(r.old_total for r in rows)
        avg_old = total_old_p / total_old_c if total_old_c > 0 else 0.0
        delta = avg_new - avg_old
        arrow = "▲" if delta > 0 else "▼" if delta < 0 else "="
        print(f"  TOTAL OLD: {total_old_p}/{total_old_c} ({avg_old*100:.1f}%)")
        print(f"  DELTA:     {arrow} {delta*100:+.1f}%")

    # Aggregate stage comparison
    for label, key in [("NEW", "new_stages"), ("OLD", "old_stages") if use_old else (None, None)]:
        if label is None:
            continue
        print(f"\n  Aggregate {label} per-stage:")
        for s in stage_names:
            scores = [(getattr(r, key).get(s, 0.0)) for r in rows if getattr(r, key).get(s, 0.0) > 0]
            if scores:
                avg_s = sum(scores) / len(scores)
                bar = "█" * int(avg_s * 10) + "░" * int((1 - avg_s) * 10)
                print(f"    {s:20s} {bar} {avg_s*100:5.1f}%")

    # Understanding sub-metrics (computed from pipeline data)
    print(f"\n  ── Understanding sub-metrics (NEW pipeline) ──")
    sub_metrics = _aggregate_understanding_submetrics(rows)
    for metric, score in sub_metrics.items():
        bar = "█" * int(score * 10) + "░" * int((1 - score) * 10)
        print(f"    {metric:20s} {bar} {score*100:5.1f}%")


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    use_old = "--old" in args
    to_markdown = "--markdown" in args
    single_conv = None
    for i, a in enumerate(args):
        if a == "--conversation" and i + 1 < len(args):
            single_conv = args[i + 1]

    print(f"  Initializing pipeline with GroqLLM...", end=" ")
    sys.stdout.flush()
    pipeline = PipelineOrchestrator()
    llm_type = type(pipeline._llm).__name__
    print(f"{llm_type}")

    if llm_type == "MockLLM":
        print("  ⚠ WARNING: Using MockLLM! Set GROQ_API_KEY in .env for real evaluation.")
        print()

    if single_conv:
        conv = load_conversation(single_conv)
        convs = [conv]
    else:
        convs = []
        for d in ["data/benchmark/v0.1", "data/benchmark/v0.2"]:
            convs.extend(load_all(d))

    print(f"  Running {len(convs)} conversations...")
    rows: list[BenchmarkRow] = []
    for i, conv in enumerate(convs):
        conv_id = conv["id"]
        print(f"  [{i+1}/{len(convs)}] {conv_id}...", end=" ")
        sys.stdout.flush()
        t0 = time.perf_counter()
        row = run_conversation(conv, pipeline, use_old=use_old)
        elapsed = time.perf_counter() - t0
        status = "✓" if row.new_score >= 0.7 else "✗"
        print(f"{status} ({row.new_score*100:.1f}%) [{elapsed:.1f}s]")
        rows.append(row)

    # Sort by score ascending (worst first)
    rows.sort(key=lambda r: r.new_score)

    if to_markdown:
        print_markdown(rows, use_old)
    else:
        print_benchmark_table(rows, use_old)

    # Latency budget check
    print(f"\n  ── Latency budget ──")
    all_latencies = [r.new_latency_ms for r in rows if r.new_latency_ms > 0]
    if all_latencies:
        avg_lat = sum(all_latencies) / len(all_latencies)
        max_lat = max(all_latencies)
        p95 = sorted(all_latencies)[int(len(all_latencies) * 0.95)]
        print(f"    Avg: {avg_lat:.0f}ms  P95: {p95:.0f}ms  Max: {max_lat:.0f}ms")
        budget = 1500
        if avg_lat < budget:
            print(f"    ✓ Average within {budget}ms budget")
        else:
            print(f"    ✗ Average EXCEEDS {budget}ms budget by {avg_lat - budget:.0f}ms")

    print()


def print_markdown(rows: list[BenchmarkRow], use_old: bool) -> None:
    print(f"\n## Benchmark Results\n")
    print(f"| Conversation | Difficulty | Turns | New Score | New Latency |", end="")
    if use_old:
        print(f" Old Score | Old Latency | Delta |", end="")
    print()
    print(f"|---|---|---|---|---|", end="")
    if use_old:
        print(f"|---|---|---|", end="")
    print()

    for row in rows:
        delta_str = ""
        if use_old and row.old_total > 0:
            delta = row.new_score - row.old_score
            delta_str = f" {'▲' if delta > 0 else '▼'}{delta*100:+.1f}%"
        print(f"| {row.conv_id} | {row.difficulty} | {row.turns} | "
              f"{row.new_score*100:.1f}% ({row.new_passed}/{row.new_total}) | {row.new_latency_ms:.0f}ms |", end="")
        if use_old:
            print(f" {row.old_score*100:.1f}% ({row.old_passed}/{row.old_total}) | {row.old_latency_ms:.0f}ms | {delta_str} |", end="")
        print()

    print()
    print(f"**Total New:** {sum(r.new_passed for r in rows)}/{sum(r.new_total for r in rows)} ({sum(r.new_passed for r in rows)/max(sum(r.new_total for r in rows),1)*100:.1f}%)")
    if use_old:
        print(f"**Total Old:** {sum(r.old_passed for r in rows)}/{sum(r.old_total for r in rows)} ({sum(r.old_passed for r in rows)/max(sum(r.old_total for r in rows),1)*100:.1f}%)")


if __name__ == "__main__":
    main()
