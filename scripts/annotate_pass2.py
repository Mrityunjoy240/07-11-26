"""Apply structured-signal annotations to Pass 2 candidates.

This script writes the filled annotations directly into
data/evaluation/structured_signals/annotations_new.jsonl.
"""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    inpath = Path("data/evaluation/structured_signals/annotations_new.jsonl")
    entries = [json.loads(l) for l in inpath.read_text(encoding="utf-8").strip().split("\n")]

    # ── Annotation decisions ─────────────────────────────────────────────
    # For each entry: (conversation_id, turn_id) → structured-signal label.

    NONE = {"present": False, "subtype": None, "confidence": 0.0}

    def _em(s: str, conf: float) -> dict:
        return {"present": True, "subtype": s, "confidence": conf}

    def _gr(s: str, conf: float) -> dict:
        return {"present": True, "subtype": s, "confidence": conf}

    def _dc(s: str, conf: float) -> dict:
        return {"present": True, "subtype": s, "confidence": conf}

    LABELS: dict[tuple[str, int], dict] = {
        # ── Entry 0: pure factual ──
        ("BENCH_000001", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Pure factual opening: rank, percentage, profile.",
        },
        # ── Entry 1: pure factual (Hindi) ──
        ("BENCH_000002", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual query about admission process and hostel (Hindi).",
        },
        # ── Entry 2: factual course options ──
        ("BENCH_000014", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: asking about CSE options in distance education. 'Kya options hain' means available courses, not a decision between alternatives.",
        },
        # ── Entry 3: factual profile statement ──
        ("BENCH_V21_000006", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual profile + 'I want CSE' is a stated goal, not a decision between options.",
        },
        # ── Entry 4: pure factual ──
        ("BENCH_V21_000010", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Simple factual seat-count query.",
        },
        # ── Entry 5: factual ──
        ("BENCH_V21_000011", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual opening: rank query about CSE admissions.",
        },
        # ── Entry 6: pure factual ──
        ("BENCH_V21_000011", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Pure profile statement: percentage, category.",
        },
        # ── Entry 7: factual cutoff query ──
        ("BENCH_V21_000011", 4): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual cutoff query for OBC category.",
        },
        # ── Entry 8 (MINER-FLAGGED): Hindi implied anxiety? ──
        ("BENCH_000013", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "'Ab batao kya hoga' = 'now tell me what will happen'. In admissions context this is a neutral information request, not genuine anxiety. Rest of utterance is purely factual. NO signal.",
        },
        # ── Entry 9: confirmation question ──
        ("BENCH_V21_000011", 5): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Confirmation question: 'so ECE at 12000 rank OBC looks safe?' Mild implied checking but primarily factual confirmation. NO signal present.",
        },
        # ── Entry 10: factual ──
        ("BENCH_V21_000012", 3): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: asking about similar branches to CSE.",
        },
        # ── Entry 11: closing ──
        ("BENCH_V21_000012", 6): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Thank-you closing statement. No signal.",
        },
        # ── Entry 12: factual (Bengali) ──
        ("BENCH_V21_000014", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual (Bengali): 'What are my chances in ECE?' Pure profile + chance inquiry.",
        },
        # ── Entry 13: factual seat inquiry ──
        ("BENCH_V21_000015", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: 'Will I get a seat?' Standard admission eligibility question.",
        },
        # ── Entry 14: factual ──
        ("BENCH_V21_000016", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: 'What about ECE specifically?' Follow-up on a specific branch.",
        },
        # ── Entry 15: factual fee query ──
        ("BENCH_V21_000021", 2): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: hostel fee inclusion question.",
        },
        # ── Entry 16: factual (Hindi) ──
        ("BENCH_V21_000022", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual (Hindi): requesting IT branch fee structure.",
        },
        # ── Entry 17: factual correction ──
        ("BENCH_V21_000023", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Parent correcting earlier rank information. Mild implied uncertainty but primarily factual correction, not confusion or anxiety signal.",
        },
        # ── Entry 18: factual placement query ──
        ("BENCH_V21_000027", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual placement statistics query.",
        },
        # ── Entry 19 (MINER-FLAGGED): decision via recommendation request ──
        ("BENCH_V21_000029", 0): {
            "emotion": NONE, "grievance": NONE,
            "decision": _dc("recommend", 0.7),
            "evidence_type": "explicit",
            "annotator_notes": "Explicit recommendation request: 'which colleges have the best CSE placements.' The user is deciding between colleges; asking for placement-based recommendation is a decision signal. Miner correctly flagged (decision=contextual).",
        },
        # ── Entry 20: factual comparison ──
        ("BENCH_V21_000029", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: asking if NIT Delhi placement claims are true and about IIIT Delhi. Pure information verification.",
        },
        # ── Entry 21 (MINER-FLAGGED): factual ──
        ("BENCH_V21_000030", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: 'Tell me about placement in Civil Engineering. Which companies come for CE placement?' Miner false positive — asking about which companies recruit is factual, not a decision between options.",
        },
        # ── Entry 22 (MINER-MISSED): decision via contingency question ──
        ("BENCH_V21_000030", 2): {
            "emotion": NONE, "grievance": NONE,
            "decision": _dc("alternative", 0.85),
            "evidence_type": "explicit",
            "annotator_notes": "Explicit contingency/alternative decision: 'if I don't get good placement in CE, can I switch to IT or CSE?' Weighing options (stay in CE vs switch) based on placement outcome. Detector correctly caught this as decision=compare (0.9). Miner missed it entirely (score=0).",
        },
        # ── Entry 23: factual hostel query ──
        ("BENCH_V21_000031", 3): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: single vs shared room + room fee. No signal.",
        },
        # ── Entry 24: factual (Bengali) ──
        ("BENCH_V21_000033", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual (Bengali): asking about hostel accommodation.",
        },
        # ── Entry 25 (MINER-FLAGGED): factual ──
        ("BENCH_V21_000033", 2): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: 'Is there an option for 2-person sharing?' 'Is there an option' = 'do you offer', not a decision between alternatives. Miner false positive (decision=0.9 from 'option' pattern).",
        },
        # ── Entry 26: factual ──
        ("BENCH_V21_000034", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: query about hostel facilities.",
        },
        # ── Entry 27: factual future planning ──
        ("BENCH_V21_000034", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: 'Just asking for future reference.' No signal.",
        },
        # ── Entry 28: factual ──
        ("BENCH_V21_000035", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: profile + 'I want CSE.' Stated goal, not a decision.",
        },
        # ── Entry 29: factual scholarship query ──
        ("BENCH_V21_000036", 2): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: scholarship application process question.",
        },
        # ── Entry 30: factual ──
        ("BENCH_V21_000038", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: college affiliations query.",
        },
        # ── Entry 31: factual lateral entry query ──
        ("BENCH_V21_000040", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: lateral entry and direct admission query.",
        },
        # ── Entry 32: factual distance learning query ──
        ("BENCH_V21_000042", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: asking about distance education options.",
        },
        # ── Entry 33 (MINER-FLAGGED): decision via mode-of-study choice ──
        ("BENCH_V21_000042", 2): {
            "emotion": NONE, "grievance": NONE,
            "decision": _dc("choose", 0.7),
            "evidence_type": "explicit",
            "annotator_notes": "Explicit choice between study modes: 'Actually, what about regular admission?' follows turn where user asked about distance options. The switch from distance to regular signals a decision between the two modes. 'What are my chances for IT' is the factual follow-up to the chosen mode. Miner correctly flagged (decision=0.9).",
        },
        # ── Entry 34: factual budget + eligibility query ──
        ("BENCH_V21_000043", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: which colleges accept management quota at given budget. Implicitly decision-adjacent but the question itself is factual eligibility inquiry. No signal.",
        },
        # ── Entry 35: factual NRI query ──
        ("BENCH_V21_000044", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: NRI admission process query.",
        },
        # ── Entry 36: factual budget + loan query ──
        ("BENCH_V21_000045", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: family contribution + loan eligibility query.",
        },
        # ── Entry 37: factual scholarship query ──
        ("BENCH_V21_000045", 2): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: scholarship + loan combination query.",
        },
        # ── Entry 38: factual safety query (Hindi) ──
        ("BENCH_V21_000046", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual (Hindi): 'tell me about safety.' Safety concern is common domain topic, not an emotion signal in this purely factual context.",
        },
        # ── Entry 39: factual lateral entry ──
        ("BENCH_V21_000047", 0): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: lateral entry eligibility query.",
        },
        # ── Entry 40: factual ──
        ("BENCH_V21_000047", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: lateral entry possibility query with profile.",
        },
        # ── Entry 41: factual ──
        ("BENCH_V21_000050", 1): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: sports quota availability for CSE.",
        },
        # ── Entry 42: factual ──
        ("BENCH_V21_000050", 5): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Factual: which Kolkata colleges accept cricket players + chances for CSE. Decision-adjacent but phrased as factual questions.",
        },
        # ── Entry 43: closing + factual ──
        ("BENCH_V21_000050", 7): {
            "emotion": NONE, "grievance": NONE, "decision": NONE,
            "evidence_type": None, "annotator_notes": "Thank-you closing + factual documents query. No signal.",
        },
    }

    # ── Apply labels ────────────────────────────────────────
    for e in entries:
        key = (e["conversation_id"], e["turn_id"])
        label = LABELS.get(key)
        if label is None:
            print(f"WARNING: No label for {key}")
            continue
        e["labels"] = {
            "emotion": label["emotion"],
            "grievance": label["grievance"],
            "decision": label["decision"],
            "evidence_type": label["evidence_type"],
        }
        e["annotator_notes"] = label["annotator_notes"]

    # ── Write ────────────────────────────────────────────────
    outpath = Path("data/evaluation/structured_signals/annotations_new.jsonl")
    with open(outpath, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"Written: {outpath} ({len(entries)} entries annotated)")

    # ── Summary ──────────────────────────────────────────────
    sig_counts = {"emotion": 0, "grievance": 0, "decision": 0}
    multi = 0
    none_count = 0
    for e in entries:
        l = e["labels"]
        present = [k for k in ["emotion", "grievance", "decision"] if l[k]["present"]]
        if len(present) >= 2:
            multi += 1
        if len(present) == 0:
            none_count += 1
        for k in present:
            sig_counts[k] += 1

    print(f"\n=== Pass 2 Annotation Summary ===")
    print(f"Total: {len(entries)}")
    print(f"Signals found: emotion={sig_counts['emotion']}, grievance={sig_counts['grievance']}, decision={sig_counts['decision']}")
    print(f"Multi-signal: {multi}")
    print(f"No signal (negatives): {none_count}")
    print(f"Total positive signals: {sum(sig_counts.values())}")


if __name__ == "__main__":
    main()
