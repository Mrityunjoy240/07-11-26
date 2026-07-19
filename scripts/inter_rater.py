#!/usr/bin/env python3
"""
Cohen's Kappa calculator for inter-annotator agreement on benchmark conversations.

Usage:
    # Compare two annotation sets (directories of conversation JSONs)
    python scripts/inter_rater.py annotator_a/ annotator_b/

    # Compare single conversation
    python scripts/inter_rater.py annotator_a/ADM_LOWRANK_001.json annotator_b/ADM_LOWRANK_001.json

    # With verbose per-metric breakdown
    python scripts/inter_rater.py annotator_a/ annotator_b/ --verbose
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


# ── Cohen's Kappa ─────────────────────────────────────────────────────────

def cohens_kappa(labels_a: list[str], labels_b: list[str]) -> float:
    """Compute Cohen's kappa for two lists of categorical labels.

    kappa = (p_o - p_e) / (1 - p_e)
    where p_o = observed agreement, p_e = expected agreement by chance.
    """
    assert len(labels_a) == len(labels_b), "Label lists must have same length"
    n = len(labels_a)
    if n == 0:
        return 0.0

    # Observed agreement
    agreements = sum(1 for a, b in zip(labels_a, labels_b) if a == b)
    p_o = agreements / n

    # Expected agreement by chance
    counter_a = Counter(labels_a)
    counter_b = Counter(labels_b)
    p_e = sum((counter_a[k] / n) * (counter_b[k] / n) for k in set(counter_a) | set(counter_b))

    if p_e == 1.0:
        return 1.0  # perfect agreement, no chance correction needed
    return (p_o - p_e) / (1 - p_e)


def kappa_interpretation(kappa: float) -> str:
    """Interpret kappa value per Landis & Koch (1977)."""
    if kappa < 0.0:
        return "poor (less than chance)"
    elif kappa < 0.20:
        return "slight"
    elif kappa < 0.40:
        return "fair"
    elif kappa < 0.60:
        return "moderate"
    elif kappa < 0.80:
        return "substantial"
    else:
        return "almost perfect"


# ── Metric extraction ─────────────────────────────────────────────────────

def extract_metric_labels(turn: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Extract all evaluable metric labels from a turn's expected output.

    Returns list of (metric_path, label_value) pairs.
    """
    labels = []
    expected = turn.get("expected", {})

    # Understanding
    u = expected.get("understanding", {})
    intent = u.get("intent")
    if intent:
        labels.append(("understanding.intent", str(intent)))

    for field, val in u.get("facts", {}).items():
        if val is not None:
            labels.append((f"understanding.facts.{field}", str(val)))

    missing = u.get("missing", [])
    if missing:
        # Sort for consistent ordering
        labels.append(("understanding.missing", "|".join(sorted(missing))))

    # Reasoning
    r = expected.get("reasoning", {})
    if r.get("stage"):
        labels.append(("reasoning.stage", str(r["stage"])))
    if r.get("profile_completeness") is not None:
        # Bin into 0.1 buckets for categorical comparison
        bucket = round(r["profile_completeness"], 1)
        labels.append(("reasoning.profile_completeness", str(bucket)))
    if r.get("confidence"):
        labels.append(("reasoning.confidence", str(r["confidence"])))
    if r.get("current_problem"):
        labels.append(("reasoning.current_problem", str(r["current_problem"])))

    # Brain
    b = expected.get("brain", {})
    if b.get("applicable") is not None:
        labels.append(("brain.applicable", str(b["applicable"])))
    if b.get("eligible_branches"):
        labels.append(("brain.eligible_branches", "|".join(sorted(b["eligible_branches"]))))

    # Decision
    d = expected.get("decision", {})
    if d.get("action"):
        labels.append(("decision.action", str(d["action"])))

    # Planner
    p = expected.get("planner", {})
    for i, pt in enumerate(p.get("turns", [])):
        if pt.get("action"):
            labels.append((f"planner.turn[{i}].action", str(pt["action"])))

    return labels


def extract_labels_for_kappa(turn_a: dict, turn_b: dict) -> list[tuple[str, str, str]]:
    """Extract matching metric labels from two annotators' turns.

    Returns list of (metric_path, label_a, label_b) for metrics present in either turn.
    """
    labels_a = {path: label for path, label in extract_metric_labels(turn_a)}
    labels_b = {path: label for path, label in extract_metric_labels(turn_b)}

    all_paths = sorted(set(labels_a) | set(labels_b))
    result = []
    for path in all_paths:
        la = labels_a.get(path, "__MISSING__")
        lb = labels_b.get(path, "__MISSING__")
        result.append((path, la, lb))

    return result


# ── Agreement helpers ─────────────────────────────────────────────────────

def exact_match_agreement(labels_a: list[str], labels_b: list[str]) -> float:
    """Simple percentage agreement (not kappa)."""
    if not labels_a:
        return 1.0
    return sum(1 for a, b in zip(labels_a, labels_b) if a == b) / len(labels_a)


def missing_overlap(labels_a: list[str], labels_b: list[str]) -> float:
    """Check missing-info agreement using overlap metric (matching evaluator relaxation)."""
    if not labels_a:
        return 1.0
    total = 0.0
    for a, b in zip(labels_a, labels_b):
        set_a = set(a.split("|")) if a != "__MISSING__" else set()
        set_b = set(b.split("|")) if b != "__MISSING__" else set()
        union = set_a | set_b
        if union:
            total += len(set_a & set_b) / len(union)
        else:
            total += 1.0
    return total / len(labels_a)


# ── Main ──────────────────────────────────────────────────────────────────

def load_conversations(path: str | Path) -> dict[str, dict]:
    """Load all conversation JSONs from a directory or single file, keyed by id."""
    p = Path(path)
    if p.is_file():
        data = json.loads(p.read_text())
        return {data["id"]: data}
    elif p.is_dir():
        convs = {}
        for f in sorted(p.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                convs[data["id"]] = data
            except Exception as e:
                print(f"  [SKIP] {f.name}: {e}")
        return convs
    else:
        raise FileNotFoundError(f"Not found: {path}")


def compute_inter_rater(
    convs_a: dict[str, dict],
    convs_b: dict[str, dict],
    verbose: bool = False,
) -> dict[str, Any]:
    """Compute Cohen's kappa between two annotation sets.

    Returns dict with per-metric kappas and overall kappa.
    """
    # Find common conversations
    common_ids = sorted(set(convs_a) & set(convs_b))
    if not common_ids:
        print("  No common conversations found between the two sets.")
        return {}

    print(f"\n  Common conversations: {len(common_ids)}")

    # Collect all metric labels across all turns
    metric_labels_a: dict[str, list[str]] = {}
    metric_labels_b: dict[str, list[str]] = {}
    all_pairs: list[tuple[str, str, str]] = []

    for conv_id in common_ids:
        turns_a = convs_a[conv_id].get("turns", [])
        turns_b = convs_b[conv_id].get("turns", [])
        max_turns = max(len(turns_a), len(turns_b))

        for i in range(max_turns):
            ta = turns_a[i] if i < len(turns_a) else {}
            tb = turns_b[i] if i < len(turns_b) else {}
            pairs = extract_labels_for_kappa(ta, tb)

            for path, la, lb in pairs:
                if path not in metric_labels_a:
                    metric_labels_a[path] = []
                    metric_labels_b[path] = []
                metric_labels_a[path].append(la)
                metric_labels_b[path].append(lb)
                all_pairs.append((path, la, lb))

    # Compute per-metric kappa
    results = {}
    all_a = []
    all_b = []

    print(f"\n  {'Metric':<45s} {'Kappa':>7s}  {'Agree%':>6s}  Interpretation")
    print(f"  {'-'*45} {'-'*7}  {'-'*6}  {'-'*20}")

    for metric_path in sorted(metric_labels_a.keys()):
        labels_a = metric_labels_a[metric_path]
        labels_b = metric_labels_b[metric_path]
        n = len(labels_a)

        # Kappa
        kappa = cohens_kappa(labels_a, labels_b)
        agree = exact_match_agreement(labels_a, labels_b)
        interp = kappa_interpretation(kappa)

        results[metric_path] = {
            "kappa": round(kappa, 3),
            "agreement": round(agree, 3),
            "n": n,
            "interpretation": interp,
        }

        if verbose:
            print(f"  {metric_path:<45s} {kappa:>7.3f}  {agree:>5.0%}  {interp}")

        all_a.extend(labels_a)
        all_b.extend(labels_b)

    # Overall kappa
    overall_kappa = cohens_kappa(all_a, all_b)
    overall_agree = exact_match_agreement(all_a, all_b)
    overall_interp = kappa_interpretation(overall_kappa)

    print(f"\n  {'OVERALL':<45s} {overall_kappa:>7.3f}  {overall_agree:>5.0%}  {overall_interp}")
    print(f"  Total label pairs: {len(all_a)}")
    print()

    return {
        "overall_kappa": round(overall_kappa, 3),
        "overall_agreement": round(overall_agree, 3),
        "n_conversations": len(common_ids),
        "n_label_pairs": len(all_a),
        "per_metric": results,
        "interpretation": overall_interp,
    }


def main():
    args = sys.argv[1:]
    verbose = "--verbose" in args
    args = [a for a in args if not a.startswith("--")]

    if len(args) < 2:
        print(__doc__)
        return

    path_a, path_b = args[0], args[1]
    convs_a = load_conversations(path_a)
    convs_b = load_conversations(path_b)

    print(f"  Annotation set A: {len(convs_a)} conversations from {path_a}")
    print(f"  Annotation set B: {len(convs_b)} conversations from {path_b}")

    result = compute_inter_rater(convs_a, convs_b, verbose=verbose)

    if result:
        # Write results
        out_path = Path("data/benchmark/inter_rater_results.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2))
        print(f"  Results written to {out_path}")


if __name__ == "__main__":
    main()
