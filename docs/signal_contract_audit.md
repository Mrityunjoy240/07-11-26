# Signal Contract Audit — Understanding → Reasoning Boundary

**Date:** 2026-07-23  
**Scope:** What `UnderstandingResult` carries to `ReasoningEngine` regarding signals, and what's missing for future behavioral routing.

---

## Current State

### UnderstandingResult fields (src/understanding/models.py:86-97)

```
text: str
language: str                          # "en" | "hi" | "bn"
intent: UnderstandingIntent            # primary + confidence + all_scores
profile: StudentProfile                # academic, personal, career
signals: ConversationSignals           # OLD: flat floats (anxiety, urgency, confusion, ...)
structured_signals: StructuredSignals  # NEW: typed Signal objects (grievance, decision, emotion)
missing_info: MissingInformation
references_previous: bool
confidence: float
metadata: dict[str, Any]
domain: DomainInterpretation
```

### Signal data types

| Type | Frozen | Fields | Notes |
|---|---|---|---|
| `Signal` | Yes | `value: str`, `confidence: float`, `source: str`, `target: Optional[str]` | Base unit |
| `StructuredSignals` | Yes | `grievance: Optional[Signal]`, `decision: Optional[Signal]`, `emotion: Optional[Signal]` | Container |
| `SignalInteraction` | Yes | `overlap_tags: tuple[str,...]`, `primary_dimension: str`, `confidence_ranking: tuple[str,...]` | Analysis result |

### What ReasoningEngine currently reads (src/reasoning/engine.py)

| Field accessed | Lines | Purpose |
|---|---|---|
| `understanding.signals.dominant` | 396, 472 | `(name, score)` — drives `needs_reassurance` / `needs_clarification` routing |
| `understanding.signals.anxiety` | 694 | Risk: `student_shows_anxiety` |
| `understanding.signals.confusion` | 696 | Risk: `student_shows_confusion` |
| `understanding.signals.frustration` | 698 | Risk: `student_shows_frustration` |
| `understanding.signals.financial_concern` | 729 | Knowledge needed: `scholarship_data` |

**ReasoningEngine reads ZERO structured signal fields.** It only reads the old flat-float `ConversationSignals`.

---

## Gap Analysis

### 1. `analyze_signals()` is never called

The function `analyze_signals(signals) -> SignalInteraction` is defined in
`interaction.py` and exported from `signals/__init__.py`, but no code in the
pipeline invokes it. There is no `UnderstandingResult.signal_interaction` field
to store the result.

**What's needed:**
- `UnderstandingResult.signal_interaction: SignalInteraction` field (default: `SignalInteraction(overlap_tags=(), primary_dimension="none", confidence_ranking=())`)
- `UnderstandingEngine.understand()` must call `analyze_signals(structured)` and attach the result

### 2. Two parallel signal systems

| System | Populated by | Consumed by | Coverage |
|---|---|---|---|
| `ConversationSignals` (flat floats) | `engine._detect_signals()` | `ReasoningEngine._identify_problem()`, `_identify_risks()`, `_determine_knowledge_needed()` | English + Hindi + Bengali (via `_SIGNAL_PATTERNS`) |
| `StructuredSignals` (typed Signal) | `detect_grievance()`, `detect_decision_intent()`, `detect_emotion()` | **Nobody** | English only |

**What's needed for routing:**
- ReasoningEngine must eventually migrate from `signals.dominant` to `structured_signals` + `signal_interaction`
- Structured detectors must extend to Hindi/Bengali (or the flat system must remain as fallback)
- Until migration, both systems must stay in sync (grievance detection vs `_INTENT_SIGNAL_BOOSTS`)

### 3. No cross-turn signal accumulation

`StructuredSignals` is per-utterance. There is no:
- History of signal detections across turns
- Signal escalation tracking (e.g., anxiety increasing over 3 turns)
- Cooldown detection (e.g., frustration resolved)
- Signal trend (stable / escalating / de-escalating)

**What's needed for FSM routing:**
- A `SignalHistory` or `SignalTimeline` on `ConversationState` that accumulates per-turn `SignalInteraction` + `StructuredSignals`
- Trend computation: `escalating`, `stable`, `resolved`, `new`

### 4. No severity classification

`SignalInteraction.primary_dimension` names the dimension but not its severity:
- Is a frustration signal at 0.3 "mild" or at 0.9 "critical"?
- Should anxiety at 0.6 trigger reassurance but anxiety at 0.9 trigger escalation?
- No `severity: "low" | "medium" | "high"` field exists

**What's needed for routing:**
- `SignalInteraction.severity: str` derived from primary confidence thresholds
- Or separate severity mapping function used by the FSM

### 5. No signal → intent interaction metadata

`SignalInteraction.overlap_tags` identifies co-occurrence but doesn't describe the interaction:
- Does the grievance amplify the emotion, or are they independent?
- Does the decision intent modify the emotion (e.g., "I'm anxious but I need to choose")?
- No `modifiers: dict[str, str]` or `interaction_type: str` field

**What's needed for nuanced routing:**
- Interaction semantics: `amplifying`, `competing`, `independent`
- Per-pair interaction analysis (grievance×decision, decision×emotion, grievance×emotion)

### 6. Structured signals are English-only

The structured detectors (`detect_grievance`, `detect_decision_intent`, `detect_emotion`) match English-only patterns. The old `_SIGNAL_PATTERNS` and `_INTENT_SIGNAL_BOOSTS` cover Hindi/Bengali.

**What's needed:**
- Hindi/Bengali patterns for structured detectors, OR
- Fallback to flat signals for non-English text until structured detectors expand

---

## Immutable Contract (Frozen Invariants)

### What must never change

1. **`Signal` is frozen.** `value`, `confidence`, `source`, `target` are immutable after construction.
2. **`StructuredSignals` is frozen.** Once constructed, the three signal fields cannot be reassigned.
3. **`SignalInteraction` is frozen.** Once computed from a `StructuredSignals`, it cannot be modified.
4. **`analyze_signals()` is pure.** It must not mutate its input or produce different output for the same input.
5. **Confidence bounds.** All `Signal.confidence` values are in `[0.0, 1.0]`.
6. **Deterministic tie-breaking.** `SignalInteraction.confidence_ranking` always orders ties as: grievance > decision > emotion.
7. **No routing side-effects.** `analyze_signals()` does not suppress signals, choose responses, or modify detector outputs.

### Required UnderstandingResult fields for future routing

```python
@dataclass(frozen=True)  # or mutable — depends on whether we want to freeze the result
class UnderstandingResult:
    # ... existing fields ...
    
    # ADD: Interaction analysis (computed from structured_signals)
    signal_interaction: SignalInteraction  # default: empty interaction
```

### Required ConversationState additions (not implemented yet)

```python
# Future additions to ConversationState for FSM routing:
signal_history: list[dict]  # per-turn signal snapshots
# Each entry: {
#   "turn": int,
#   "structured_signals": StructuredSignals.as_dict(),
#   "signal_interaction": SignalInteraction (as dict),
#   "timestamp": float,
# }
```

---

## Summary of Missing Pieces

| # | Gap | Severity | Blocks FSM? |
|---|---|---|---|
| 1 | `SignalInteraction` not stored on `UnderstandingResult` | High | Yes |
| 2 | `analyze_signals()` never called in pipeline | High | Yes |
| 3 | ReasoningEngine reads only flat floats, not structured signals | Medium | Yes (partial) |
| 4 | No cross-turn signal history in ConversationState | High | Yes |
| 5 | No severity classification on SignalInteraction | Medium | Yes |
| 6 | No signal×intent interaction semantics | Low | No (can add later) |
| 7 | Structured detectors are English-only | Medium | No (can use flat fallback) |
