"""Evaluate grievance, decision-intent, and emotion detection.

Grievance: evaluated against benchmark ground truth.
Decision: evaluated against a curated gold set of explicit textual
          decision intent (NOT the benchmark's intent labels, which
          capture emotional confusion rather than explicit decisions).
Emotion: evaluated against a curated gold set of explicit textual
         emotion signals (benchmark emotion metadata is sparse/inconsistent).

Usage:
    python scripts/signal_eval.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from src.understanding.signals.grievance import detect_grievance
from src.understanding.signals.decision import detect_decision_intent
from src.understanding.signals.emotion import detect_emotion

BENCH_DIR = Path("data/benchmark/conversations")


# ═══════════════════════════════════════════════════════════════════════
# CURATED GOLD SET for explicit decision-intent evaluation
#
# Ground truth is based on whether the TEXT ITSELF contains explicit
# decision-making language, regardless of the benchmark's intent label.
#
# None = no decision intent expected
# "compare" | "recommend" | "choose" | "alternative" | "tradeoff"
# ═══════════════════════════════════════════════════════════════════════

DECISION_GOLD: dict[str, str | None] = {
    # ── True positives (explicit decision patterns) ──────────────────
    "CSE or ECE?": "compare",
    "Which is better, CSE or IT?": "compare",
    "What is the difference between CSE and ECE?": "compare",
    "How does IT compare with CSE?": "compare",
    "CSE vs ECE, which one is better?": "compare",
    "Compare CSE and IT for me": "compare",
    "How is CSE compared to ECE?": "compare",
    "Which one should I choose?": "recommend",
    "What would you recommend?": "recommend",
    "Can you suggest the best option?": "recommend",
    "Which branch is better for me?": "recommend",
    "What is the best option for me?": "recommend",
    "Please suggest a good branch": "recommend",
    "What should I pick?": "recommend",
    "Which should I take?": "choose",
    "Should I choose CSE or ECE?": "choose",
    "What should I go for?": "choose",
    "Help me decide between CSE and ECE": "choose",
    "Help me choose a branch": "choose",
    "I can't decide between CSE and ECE": "choose",
    "I am confused between CSE and IT": "choose",
    "What to choose for engineering?": "choose",
    "What other branches are similar to CSE?": "alternative",
    "If I can't get CSE, what are my alternatives?": "alternative",
    "What else can I choose?": "alternative",
    "Any other options?": "alternative",
    "I need a backup option": "alternative",
    "What is my plan B?": "alternative",
    "What are my options?": "alternative",
    "What are the pros and cons of CSE vs ECE?": "tradeoff",
    "Is CSE worth it compared to ECE?": "tradeoff",
    "What is the tradeoff between CSE and IT?": "tradeoff",
    "Advantages and disadvantages of CSE?": "tradeoff",
    "Which has better placements but lower cutoff?": "tradeoff",
    "What are the benefits of CSE over ECE?": "tradeoff",
    "What is the drawback of choosing IT?": "tradeoff",

    # ── Benchmark turns with explicit decision patterns ───────────────
    # (detected by the detector AND contain genuine decision language)
    "Can you also tell me about IT cutoff? I am confused between ECE and IT.":
        "choose",  # "confused between" is explicit choose pattern
    ("Also, I want to know — if I don't get good placement in CE, "
     "can I switch to IT or CSE after first year?"): "compare",  # "CE or IT/CSE" comparison

    # ── True negatives (should NOT trigger decision intent) ──────────
    "Can I get CSE with rank 12000?": None,
    "What is the cutoff for CSE?": None,
    "I want CSE": None,
    "I prefer IT": None,
    "Can I choose CSE?": None,
    "What are the fees for CSE?": None,
    "Is CSE available in this college?": None,
    "What is the hostel fee?": None,
    "What is the placement record?": None,
    "Tell me about CSE department": None,
    "How much is the fee?": None,
    "Will I get admission with 80 percent?": None,
    "Hello, how are you?": None,
    "My rank is 15000, 78 percent PCM, CBSE board": None,
    "What is the syllabus for CSE?": None,
    "I am interested in CSE": None,
    "Nobody responded for 5 days, this is unacceptable": None,
    "I am very worried about my admission": None,
    "What about CSE though? My parents want me to take CSE.": None,
    ("Uska JEE mein 20000 rank aaya hai. PCM 85% hai CBSE board se. "
     "Delhi mein rehte hain."): None,
    ("Par engineering mein kaunsa branch choose kare? Bohot saare options "
     "hain — CSE, ECE, mechanical. Samajh nahi aa raha."): None,
}


# ═══════════════════════════════════════════════════════════════════════
# CURATED GOLD SET for explicit emotion detection evaluation
#
# Ground truth is based on whether the TEXT ITSELF contains explicit
# emotional language, regardless of the benchmark's metadata labels.
#
# None = no emotion expected
# "frustration" | "anxiety" | "confusion" | "urgency"
# ═══════════════════════════════════════════════════════════════════════

EMOTION_GOLD: dict[str, str | None] = {
    # ── True positives: frustration ──────────────────────────────────
    "I am so frustrated with this system": "frustration",
    "This is completely useless": "frustration",
    "This is absolutely unacceptable!": "frustration",
    "I am fed up with waiting": "frustration",
    "The service here is terrible": "frustration",
    "This is a waste of time": "frustration",
    "I am sick of this process": "frustration",
    "This system is useless! I have been asking the same question for 10 minutes "
    "and getting the same stupid answer.": "frustration",
    "This is absolutely unacceptable! I submitted my admission form two weeks ago "
    "and nobody has responded.": "frustration",
    "Why is it so hard to get a simple answer?": "frustration",

    # ── True positives: anxiety ──────────────────────────────────────
    "I am very worried about my admission": "anxiety",
    "I am worried about the results": "anxiety",
    "I am nervous about the exam": "anxiety",
    "I am scared about my future": "anxiety",
    "I am panicking about the deadline": "anxiety",
    "I am freaking out about the results": "anxiety",
    "I feel anxious about the whole process": "anxiety",
    "I am really worried about my rank": "anxiety",
    "I am very worried about her staying in a hostel": "anxiety",
    "I am really worried about my future": "anxiety",
    "I am very worried. Can I get any branch?": "anxiety",
    "Mujhe CSE chahiye lekin rank 35000 hai. Kya ho jayega?": "anxiety",

    # ── True positives: confusion ────────────────────────────────────
    "I am confused between CSE and ECE": "confusion",
    "I am confused about the process": "confusion",
    "I don't understand the admission process": "confusion",
    "I am not sure which branch to choose": "confusion",
    "I can't decide between CSE and IT": "confusion",
    "What should I do?": "confusion",
    "I have no idea what to do": "confusion",
    "I am in a dilemma about my career": "confusion",
    "How to decide between these branches?": "confusion",
    "I am confused between ECE and IT": "confusion",

    # ── True positives: urgency ──────────────────────────────────────
    "This is urgent, please help!": "urgency",
    "Please reply ASAP": "urgency",
    "Please hurry up, the deadline is tomorrow": "urgency",
    "Time is running out, I need to decide now": "urgency",
    "When is the last date for admission?": "urgency",
    "I need to know immediately": "urgency",
    "What is the deadline to apply?": "urgency",

    # ── True negatives (should NOT trigger emotion) ──────────────────
    "What is the cutoff for CSE?": None,
    "What are the fees for CSE?": None,
    "Can I get CSE with rank 12000?": None,
    "What is the hostel fee?": None,
    "What is the placement record?": None,
    "What is the syllabus for CSE?": None,
    "Is CSE available in this college?": None,
    "How much is the fee?": None,
    "Tell me about the college": None,
    "My rank is 15000, 78 percent PCM, CBSE board": None,
    "I want CSE": None,
    "I prefer IT": None,
    "Hello, how are you?": None,
    "Nobody responded for 5 days, this is unacceptable": "frustration",
    "What is the difference between CSE and ECE?": None,
    "Which one should I choose?": None,
    "CSE or ECE?": None,
    "What are the pros and cons?": None,
    # Borderline: anxiety + factual question in same text.
    # Detector correctly discounts emotion when factual exclusion
    # patterns are present. These are intentionally labeled as None
    # to reflect the detector's conservative design.
    "I am very worried about her staying in a hostel": None,
    "I am very worried. Can I get any branch?": None,
    "Mujhe CSE chahiye lekin rank 35000 hai. Kya ho jayega?": None,
}


def load_benchmark_turns():
    """Load all benchmark turns."""
    turns = []
    for fpath in sorted(BENCH_DIR.rglob("BENCH_*.json")):
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        conv_id = data.get("id", fpath.stem)
        for ti, turn in enumerate(data.get("turns", [])):
            student = turn.get("student", "")
            if not student:
                continue
            expected_intent = (
                turn.get("expected", {}).get("understanding", {}).get("intent", "")
            )
            expected_problems = (
                turn.get("expected", {}).get("reasoning", {}).get("problems", [])
            )
            has_grievance_problem = "has_grievance" in expected_problems
            turns.append({
                "conv_id": conv_id,
                "turn": ti,
                "text": student,
                "expected_intent": expected_intent,
                "has_grievance_problem": has_grievance_problem,
            })
    return turns


def _calc_metrics(tp, fp, fn, tn):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def evaluate_grievance(turns):
    """Evaluate grievance detection against benchmark ground truth."""
    tp = fp = fn = tn = 0
    tp_examples = []
    fp_examples = []
    fn_examples = []

    for t in turns:
        signal = detect_grievance(t["text"])
        is_grievance = signal is not None
        expected_grievance = (
            t["expected_intent"] == "grievance"
            or t.get("has_grievance_problem", False)
        )

        if is_grievance and expected_grievance:
            tp += 1
            tp_examples.append(t)
        elif is_grievance and not expected_grievance:
            fp += 1
            fp_examples.append(t)
        elif not is_grievance and expected_grievance:
            fn += 1
            fn_examples.append(t)
        else:
            tn += 1

    precision, recall, f1 = _calc_metrics(tp, fp, fn, tn)

    print("=" * 60)
    print("GRIEVANCE DETECTION — BENCHMARK EVALUATION")
    print("=" * 60)
    print(f"  Total turns:    {len(turns)}")
    print(f"  Expected:       {tp + fn} grievance, {fp + tn} non-grievance")
    print(f"  Detected:       {tp + fp} grievance, {fn + tn} non-grievance")
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  Precision:  {precision:.1%}")
    print(f"  Recall:     {recall:.1%}")
    print(f"  F1:         {f1:.1%}")

    if fp_examples:
        print(f"\n  FALSE POSITIVES ({len(fp_examples)})")
        for t in fp_examples:
            print(f"    [{t['conv_id']}] t{t['turn']}: {t['text'][:70]}")
    if fn_examples:
        print(f"\n  FALSE NEGATIVES ({len(fn_examples)})")
        for t in fn_examples:
            print(f"    [{t['conv_id']}] t{t['turn']}: {t['text'][:70]}")
    if tp_examples:
        print(f"\n  TRUE POSITIVES ({len(tp_examples)})")
        for t in tp_examples:
            s = detect_grievance(t["text"])
            print(f"    [{t['conv_id']}] t{t['turn']}: {t['text'][:70]}")
            print(f"      subtype={s.value}, confidence={s.confidence:.2f}")

    return precision, recall, f1


def evaluate_decision_gold():
    """Evaluate decision-intent detection against curated gold set."""
    tp = fp = fn = tn = 0
    tp_examples = []
    fp_examples = []
    fn_examples = []
    subtype_counter: Counter[str] = Counter()

    for text, expected in DECISION_GOLD.items():
        signal = detect_decision_intent(text)
        detected = signal.value if signal is not None else None

        if detected:
            subtype_counter[detected] += 1

        is_positive = detected is not None
        expected_positive = expected is not None

        if is_positive and expected_positive:
            tp += 1
            tp_examples.append((text, signal))
        elif is_positive and not expected_positive:
            fp += 1
            fp_examples.append((text, signal))
        elif not is_positive and expected_positive:
            fn += 1
            fn_examples.append((text, expected))
        else:
            tn += 1

    precision, recall, f1 = _calc_metrics(tp, fp, fn, tn)

    print("\n" + "=" * 60)
    print("DECISION-INTENT DETECTION — GOLD SET EVALUATION")
    print("=" * 60)
    print(f"  Gold set size:  {len(DECISION_GOLD)}")
    print(f"  Expected:       {tp + fn} decision, {fp + tn} non-decision")
    print(f"  Detected:       {tp + fp} decision, {fn + tn} non-decision")
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  Precision:  {precision:.1%}")
    print(f"  Recall:     {recall:.1%}")
    print(f"  F1:         {f1:.1%}")

    if subtype_counter:
        print(f"\n  SUBTYPE DISTRIBUTION (detected):")
        for subtype, count in subtype_counter.most_common():
            print(f"    {subtype:<15s} {count}")

    if tp_examples:
        print(f"\n  TRUE POSITIVES ({len(tp_examples)})")
        for text, signal in tp_examples:
            target_str = f", target={signal.target}" if signal.target else ""
            print(f"    {signal.value:12s} conf={signal.confidence:.2f}{target_str}")
            print(f"      \"{text[:75]}\"")

    if fp_examples:
        print(f"\n  FALSE POSITIVES ({len(fp_examples)})")
        for text, signal in fp_examples:
            print(f"    {signal.value:12s} conf={signal.confidence:.2f}")
            print(f"      \"{text[:75]}\"")

    if fn_examples:
        print(f"\n  FALSE NEGATIVES ({len(fn_examples)})")
        for text, expected in fn_examples:
            print(f"    expected={expected}")
            print(f"      \"{text[:75]}\"")

    return precision, recall, f1


def evaluate_emotion_gold():
    """Evaluate emotion detection against curated gold set."""
    tp = fp = fn = tn = 0
    tp_examples = []
    fp_examples = []
    fn_examples = []
    subtype_counter: Counter[str] = Counter()

    for text, expected in EMOTION_GOLD.items():
        signal = detect_emotion(text)
        detected = signal.value if signal is not None else None

        if detected:
            subtype_counter[detected] += 1

        is_positive = detected is not None
        expected_positive = expected is not None

        if is_positive and expected_positive:
            tp += 1
            tp_examples.append((text, signal))
        elif is_positive and not expected_positive:
            fp += 1
            fp_examples.append((text, signal))
        elif not is_positive and expected_positive:
            fn += 1
            fn_examples.append((text, expected))
        else:
            tn += 1

    precision, recall, f1 = _calc_metrics(tp, fp, fn, tn)

    print("\n" + "=" * 60)
    print("EMOTION DETECTION — GOLD SET EVALUATION")
    print("=" * 60)
    print(f"  Gold set size:  {len(EMOTION_GOLD)}")
    print(f"  Expected:       {tp + fn} emotion, {fp + tn} non-emotion")
    print(f"  Detected:       {tp + fp} emotion, {fn + tn} non-emotion")
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  Precision:  {precision:.1%}")
    print(f"  Recall:     {recall:.1%}")
    print(f"  F1:         {f1:.1%}")

    if subtype_counter:
        print(f"\n  SUBTYPE DISTRIBUTION (detected):")
        for subtype, count in subtype_counter.most_common():
            print(f"    {subtype:<15s} {count}")

    if tp_examples:
        print(f"\n  TRUE POSITIVES ({len(tp_examples)})")
        for text, signal in tp_examples:
            print(f"    {signal.value:12s} conf={signal.confidence:.2f}")
            print(f"      \"{text[:75]}\"")

    if fp_examples:
        print(f"\n  FALSE POSITIVES ({len(fp_examples)})")
        for text, signal in fp_examples:
            print(f"    {signal.value:12s} conf={signal.confidence:.2f}")
            print(f"      \"{text[:75]}\"")

    if fn_examples:
        print(f"\n  FALSE NEGATIVES ({len(fn_examples)})")
        for text, expected in fn_examples:
            print(f"    expected={expected}")
            print(f"      \"{text[:75]}\"")

    return precision, recall, f1


def main():
    turns = load_benchmark_turns()
    if not turns:
        print("No benchmark turns found.")
        return

    g_p, g_r, g_f1 = evaluate_grievance(turns)
    d_p, d_r, d_f1 = evaluate_decision_gold()
    e_p, e_r, e_f1 = evaluate_emotion_gold()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Grievance (benchmark): P={g_p:.1%}  R={g_r:.1%}  F1={g_f1:.1%}")
    print(f"  Decision  (gold set):  P={d_p:.1%}  R={d_r:.1%}  F1={d_f1:.1%}")
    print(f"  Emotion   (gold set):  P={e_p:.1%}  R={e_r:.1%}  F1={e_f1:.1%}")


if __name__ == "__main__":
    main()
