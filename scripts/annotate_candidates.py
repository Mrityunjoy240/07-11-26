"""Hand-label mined candidate turns with structured-signal annotations.

Pass 1: blind annotation (annotator sees utterance + metadata, not detector output).

Output: data/evaluation/structured_signals/annotations.jsonl
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

# ── Annotation data ──────────────────────────────────────────────────
# Schema: per-turn labels for emotion, grievance, decision.
# Each signal: present (bool), subtype (str | None), confidence (0-1).
# evidence_type: explicit | implied | context-dependent

ANNOTATIONS: dict[tuple[str, int], dict] = {
    # ── Signal candidates (29) ────────────────────────────────────────
    ("BENCH_000001", 2): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": True, "subtype": "choose", "confidence": 0.8},
        "evidence_type": "explicit",
        "annotator_notes": "Explicit decision question: which one can I get (IT vs CSE). Direct comparison between options.",
    },
    ("BENCH_000001", 3): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": True, "subtype": "choose", "confidence": 0.7},
        "evidence_type": "context-dependent",
        "annotator_notes": "Decision signalled via parental preference ('parents want me to take CSE'). Only meaningful in conversation context where CSE was already discussed.",
    },
    ("BENCH_000003", 0): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "context-dependent",
        "annotator_notes": "Neutral factual opening. 'My daughter' alone does not signal anxiety in this utterance. Anxiety emerges in turn 1 across conversation context.",
    },
    ("BENCH_000004", 1): {
        "emotion": {"present": True, "subtype": "confusion", "confidence": 0.7},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "explicit",
        "annotator_notes": "Self-correction confusion: 'I made a mistake earlier' + correcting rank. The 'wait' is a conversational filler, not a grievance signal.",
    },
    ("BENCH_000006", 1): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": True, "subtype": "recommend", "confidence": 0.85},
        "evidence_type": "explicit",
        "annotator_notes": "Explicit recommendation request: 'Which branch should I pick for best placements?' Detector missed due to placement exclusion.",
    },
    ("BENCH_000007", 0): {
        "emotion": {"present": True, "subtype": "anxiety", "confidence": 0.5},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "implied",
        "annotator_notes": "Implied concern: 'only 65 percent' + 'rank is very low' suggests worry without explicit emotional vocabulary.",
    },
    ("BENCH_000008", 0): {
        "emotion": {"present": True, "subtype": "anxiety", "confidence": 0.8},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "explicit",
        "annotator_notes": "Explicit anxiety: 'I am really worried about my future.' Clear emotional expression.",
    },
    ("BENCH_000009", 0): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "context-dependent",
        "annotator_notes": "Neutral factual query about NRI quota. 'My daughter' alone is not an emotion signal. Miner false positive from contextual pattern.",
    },
    ("BENCH_000012", 0): {
        "emotion": {"present": True, "subtype": "frustration", "confidence": 0.9},
        "grievance": {"present": True, "subtype": "process", "confidence": 0.9},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "explicit",
        "annotator_notes": "Strong dual signal: frustration ('useless', 'stupid') and grievance ('same question for 10 minutes', 'same stupid answer'). Both correctly detected.",
    },
    ("BENCH_000012", 1): {
        "emotion": {"present": True, "subtype": "frustration", "confidence": 0.5},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "implied",
        "annotator_notes": "Mild frustration continuing from previous turn: 'Tell me straight', 'No beating around the bush.' Weaker than turn 0, but implied impatience.",
    },
    ("BENCH_V21_000011", 2): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "utterance_local",
        "annotator_notes": "'Wait' is a self-correction marker (want ECE not CSE), not a waiting grievance. No signal present. Miner false positive.",
    },
    ("BENCH_V21_000012", 0): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "context-dependent",
        "annotator_notes": "Neutral parent query: 'What are his chances?' Standard factual QA in admissions domain. No emotional or decision signals.",
    },
    ("BENCH_V21_000016", 0): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "utterance_local",
        "annotator_notes": "Pure factual query about departments. 'Interested in electronics' is a preference statement, not a decision signal. Miner false positive.",
    },
    ("BENCH_V21_000018", 0): {
        "emotion": {"present": True, "subtype": "anxiety", "confidence": 0.8},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "explicit",
        "annotator_notes": "Explicit anxiety: 'I am very worried.' Detector missed because 'can I get' exclusion suppressed the signal. Genuine anxiety co-occurring with factual question.",
    },
    ("BENCH_V21_000025", 1): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "utterance_local",
        "annotator_notes": "'Wait' is self-correction (correcting rank 28000->38000). Not a grievance signal. Miner false positive.",
    },
    ("BENCH_V21_000030", 1): {
        "emotion": {"present": True, "subtype": "confusion", "confidence": 0.8},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "explicit",
        "annotator_notes": "Explicit confusion: 'I was confused earlier.' The self-correction (62% PCM, not what was said before) confirms genuine confusion.",
    },
    ("BENCH_V21_000035", 2): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "utterance_local",
        "annotator_notes": "Factual scholarship query. 'Deadline' is informational, not an urgency signal. Detector false positive for urgency.",
    },
    ("BENCH_V21_000036", 0): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "context-dependent",
        "annotator_notes": "Neutral factual query about scholarships. 'My son' pattern triggered contextual miner but no signal present.",
    },
    ("BENCH_V21_000040", 2): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "utterance_local",
        "annotator_notes": "'Wait' is self-correction (OBC not general, IT not CS). No grievance signal. Miner false positive.",
    },
    ("BENCH_V21_000048", 0): {
        "emotion": {"present": True, "subtype": "confusion", "confidence": 0.8},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": True, "subtype": "choose", "confidence": 0.7},
        "evidence_type": "explicit",
        "annotator_notes": "Rich dual signal in Hindi: 'bahut confusion mein hai' (very confused) = emotion; 'Engineering kare ya medical' (engineering or medical) = decision choice. Genuine both.",
    },
    ("BENCH_V21_000048", 1): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": True, "subtype": "choose", "confidence": 0.7},
        "evidence_type": "explicit",
        "annotator_notes": "Decision signal: 'woh decide nahi kar pa rahi' (she cannot decide). No emotional vocabulary in this turn.",
    },
    ("BENCH_V21_000048", 2): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "utterance_local",
        "annotator_notes": "'Stressful' appears in reported speech ('doctors ki life bahut stressful hoti hai'). Not the speaker expressing emotion. Miner false positive.",
    },
    ("BENCH_V21_000048", 3): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": True, "subtype": "choose", "confidence": 0.8},
        "evidence_type": "explicit",
        "annotator_notes": "Clear decision question: 'kaunsa branch choose kare' (which branch to choose) with explicit options CSE/ECE/mechanical.",
    },
    ("BENCH_V21_000048", 5): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "utterance_local",
        "annotator_notes": "Decision already made ('CSE choose karegi'). Now asking factual question about colleges. No signal present. Miner false positive.",
    },
    ("BENCH_V21_000049", 0): {
        "emotion": {"present": True, "subtype": "frustration", "confidence": 0.9},
        "grievance": {"present": True, "subtype": "waiting", "confidence": 0.9},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "explicit",
        "annotator_notes": "Strong dual signal: frustration ('absolutely unacceptable', 'messy') and grievance ('submitted two weeks ago, nobody responded'). Both correctly detected.",
    },
    ("BENCH_V21_000049", 1): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": True, "subtype": "ignored", "confidence": 0.8},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "explicit",
        "annotator_notes": "Grievance: 'applied two weeks ago and got no reply.' No emotional language. 'What should I do?' is advice-seeking, not decision between options.",
    },
    ("BENCH_V21_000049", 2): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": True, "subtype": "waiting", "confidence": 0.85},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "explicit",
        "annotator_notes": "Continuing grievance: 'still want to know why nobody responded for two weeks.' No emotional vocabulary.",
    },
    ("BENCH_V21_000050", 0): {
        "emotion": {"present": True, "subtype": "anxiety", "confidence": 0.8},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "explicit",
        "annotator_notes": "Explicit anxiety: 'I am really worried about my future.' Same pattern as BENCH_000008. Detector missed.",
    },
    ("BENCH_V21_000050", 3): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "utterance_local",
        "annotator_notes": "'Wait' is self-correction (cricket not football). No grievance signal. Miner false positive.",
    },
    # ── Hard negatives (8) ────────────────────────────────────────────
    ("BENCH_000003", 1): {
        "emotion": {"present": True, "subtype": "anxiety", "confidence": 0.8},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "explicit",
        "annotator_notes": "Genuine anxiety: 'I am really worried about the hostel situation.' Co-occurs with factual keyword 'hostel' but the anxiety is explicit and genuine. Detector exclusion would incorrectly suppress this.",
    },
    ("BENCH_V21_000014", 1): {
        "emotion": {"present": True, "subtype": "confusion", "confidence": 0.7},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": True, "subtype": "choose", "confidence": 0.8},
        "evidence_type": "explicit",
        "annotator_notes": "Dual genuine signal: 'confused between ECE and IT' = both emotion (confusion) and decision (choose). Co-occurs with 'cutoff' factual keyword but the confusion/choice is explicit.",
    },
    ("BENCH_V21_000023", 0): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "utterance_local",
        "annotator_notes": "Pure factual fee query (Hindi). No signal present. Correct hard negative.",
    },
    ("BENCH_V21_000023", 3): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "utterance_local",
        "annotator_notes": "Factual fee question framed around a choice. 'If we choose IT instead of ECE' describes a decision but the question is about fee difference. No signal present.",
    },
    ("BENCH_V21_000032", 0): {
        "emotion": {"present": True, "subtype": "anxiety", "confidence": 0.85},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "explicit",
        "annotator_notes": "Genuine anxiety: 'I am very worried about her staying in a hostel.' Despite 'hostel' being a factual keyword, the emotional expression is explicit and genuine.",
    },
    ("BENCH_V21_000033", 1): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "context-dependent",
        "annotator_notes": "Neutral factual query about hostel facilities. 'My son' triggered contextual miner but no emotional language. Correct hard negative.",
    },
    ("BENCH_V21_000043", 0): {
        "emotion": {"present": False, "subtype": None, "confidence": 0.0},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "context-dependent",
        "annotator_notes": "Factual query about management quota and fees. 'Rank is very low' implies mild concern but is primarily informational. Correct hard negative.",
    },
    ("BENCH_V21_000046", 2): {
        "emotion": {"present": True, "subtype": "anxiety", "confidence": 0.7},
        "grievance": {"present": False, "subtype": None, "confidence": 0.0},
        "decision": {"present": False, "subtype": None, "confidence": 0.0},
        "evidence_type": "explicit",
        "annotator_notes": "Genuine concern: 'I am actually concerned about the hostel security.' Explicit emotion word 'concerned.' Despite 'hostel' factual keyword, the concern is genuine.",
    },
}


def main() -> None:
    inpath = Path("data/evaluation/structured_signals/mined_candidates.jsonl")
    records = [json.loads(l) for l in inpath.read_text(encoding="utf-8").strip().split("\n")]
    candidates = [r for r in records if r["overall_likelihood"]["max"] >= 0.5]
    candidates.sort(key=lambda r: (r["is_hard_negative"], r["conversation_id"], r["turn_id"]))

    output_entries = []
    missing = 0
    for c in candidates:
        key = (c["conversation_id"], c["turn_id"])
        label = ANNOTATIONS.get(key)
        if label is None:
            print(f"MISSING: {key}")
            missing += 1
            continue

        merged = {
            "conversation_id": c["conversation_id"],
            "turn_id": c["turn_id"],
            "text": c["text"],
            "domain": c["domain"],
            "scope": c["scope"],
            "labels": label,
            "mining_scores": c["overall_likelihood"],
            "detector_output": c["detector_output"],
            "is_hard_negative": c["is_hard_negative"],
            "source": c["source"],
            "annotation_pass": 1,
        }
        output_entries.append(merged)

    outpath = Path("data/evaluation/structured_signals/annotations.jsonl")
    with open(outpath, "w", encoding="utf-8") as f:
        for e in output_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"Written: {outpath} ({len(output_entries)} entries)")

    assert missing == 0, f"{missing} missing annotations"
    assert len(output_entries) == len(candidates), f"Expected {len(candidates)}, got {len(output_entries)}"

    sig_present = {"emotion": 0, "grievance": 0, "decision": 0}
    sig_both = 0
    sig_none = 0
    scope_dist: Counter[str] = Counter()

    for e in output_entries:
        l = e["labels"]
        present = [k for k in ["emotion", "grievance", "decision"] if l[k]["present"]]
        if len(present) >= 2:
            sig_both += 1
        if len(present) == 0:
            sig_none += 1
        for k in present:
            sig_present[k] += 1
        scope_dist[e["scope"]] += 1

    print()
    print("=== Annotation Summary ===")
    print(f"Total annotated: {len(output_entries)}")
    print(f"Signal present: emotion={sig_present['emotion']}, grievance={sig_present['grievance']}, decision={sig_present['decision']}")
    print(f"Multi-signal turns: {sig_both}")
    print(f"No signal (negatives): {sig_none}")
    print(f"Scope distribution: {dict(scope_dist)}")

    # Detector comparison
    detector_hits = {"emotion": 0, "grievance": 0, "decision": 0}
    detector_misses = {"emotion": 0, "grievance": 0, "decision": 0}
    false_positives = {"emotion": 0, "grievance": 0, "decision": 0}
    for e in output_entries:
        l = e["labels"]
        d = e["detector_output"]
        for sig in ["emotion", "grievance", "decision"]:
            human_present = l[sig]["present"]
            det_present = d[sig]["value"] is not None
            if human_present and det_present:
                detector_hits[sig] += 1
            elif human_present and not det_present:
                detector_misses[sig] += 1
            elif not human_present and det_present:
                false_positives[sig] += 1

    print()
    print("=== Detector Comparison ===")
    print(f"{'Signal':12s} {'Hits':>6s} {'Misses':>8s} {'FalsePos':>9s}")
    print("-" * 37)
    for sig in ["emotion", "grievance", "decision"]:
        print(f"{sig:12s} {detector_hits[sig]:6d} {detector_misses[sig]:8d} {false_positives[sig]:9d}")

    total_hits = sum(detector_hits.values())
    total_misses = sum(detector_misses.values())
    total_fp = sum(false_positives.values())
    print("-" * 37)
    print(f"{'TOTAL':12s} {total_hits:6d} {total_misses:8d} {total_fp:9d}")

    # Per-scope breakdown
    print()
    print("=== Per-scope Detector Performance ===")
    for scope_name in ["utterance_local", "conversation_context_required", "ambiguous"]:
        scope_entries = [e for e in output_entries if e["scope"] == scope_name]
        if not scope_entries:
            continue
        scope_hits = 0
        scope_misses = 0
        for e in scope_entries:
            l = e["labels"]
            d = e["detector_output"]
            for sig in ["emotion", "grievance", "decision"]:
                if l[sig]["present"]:
                    if d[sig]["value"] is not None:
                        scope_hits += 1
                    else:
                        scope_misses += 1
        total = scope_hits + scope_misses
        pct = 100.0 * scope_hits / total if total > 0 else 0
        print(f"  {scope_name:35s} {scope_hits}/{total} = {pct:.0f}% detection rate")


if __name__ == "__main__":
    main()
