# Eval Spec — Golden Conversation Benchmark v1.1

**Version**: 1.1  
**Date**: 2026-07-19  
**Status**: Frozen

---

## 1. Purpose

Defines how the college admission counselor pipeline is evaluated against a set of golden conversations. The benchmark measures whether the pipeline extracts the correct facts, identifies the right intent, selects the appropriate action, and produces a response that covers the expected content.

## 2. Benchmark Structure

Each conversation is a JSON file with:
- `id`: Unique identifier (`{TOPIC}_{VARIANT}_{NNN}`)
- `tags`: Classification labels
- `difficulty`: 1-7 scale
- `ground_truth`: Canonical facts
- `turns`: Array of student-assistant exchanges with expected pipeline output
- `expected_end_state`: success | escalate | incomplete

### 2.1 Schema

Canonical schema: `data/benchmark/schema/conversation_v0.1.schema.json`

## 3. Evaluation Metrics

The evaluator (`scripts/evaluate.py`) checks 13 metrics across 5 pipeline stages:

### 3.1 Understanding (4 metrics)

| Metric | Check type | Notes |
|---|---|---|
| `understanding.intent.primary` | Exact match | Must match gold intent |
| `understanding.facts.{field}` | Exact match | Per-field; None values skipped |
| `understanding.missing` | Relaxed | See Section 4.1 |
| (facts count) | Derived | From facts iteration |

### 3.2 Reasoning (4 metrics)

| Metric | Check type | Notes |
|---|---|---|
| `reasoning.stage` | Exact match | Student journey stage |
| `reasoning.profile_completeness` | Tolerance | ±0.3 absolute |
| `reasoning.confidence` | Exact match | Mapped from float to string |
| `reasoning.current_problem` | Exact match | Problem category |

### 3.3 Brain (3 metrics)

| Metric | Check type | Notes |
|---|---|---|
| `brain.applicable` | Exact match | Boolean |
| `brain.eligible_branches` | Relaxed | See Section 4.2 |
| `brain.why` | Relaxed | See Section 4.3 |

### 3.4 Decision (1 metric)

| Metric | Check type | Notes |
|---|---|---|
| `decision.action` | Exact match | Action string |

### 3.5 Planner (N metrics, variable)

| Metric | Check type | Notes |
|---|---|---|
| `planner.turns[i].action` | Exact match | Per turn |
| `planner.turns[i].content_contains` | Substring | Each keyword in response |

## 4. Relaxation Rules

Some metrics allow partial matches to account for legitimate pipeline variation.

### 4.1 Missing Information

**Rule**: If the Jaccard-like overlap between actual and expected missing items ≥ 50%, the check passes.

```
overlap = |actual ∩ expected|
max_len = max(|actual|, |expected|)
pass = overlap / max_len ≥ 0.5
```

**Rationale**: The pipeline may legitimately identify additional missing fields or consider some fields satisfied that the gold standard marks as missing. A 50% overlap ensures the core missing items are present.

### 4.2 Eligible Branches

**Rule**: If the overlap between actual and expected branch sets ≥ 50% of expected branches, the check passes.

```
overlap = |actual ∩ expected|
pass = overlap ≥ |expected| × 0.5
```

**Rationale**: The brain engine may return a superset of branches (all branches the student could potentially get) or a subset (only the most likely branches). Both are valid.

### 4.3 Brain Why Conditions

**Rule**: Same as 4.2 — 50% overlap on condition name strings.

**Rationale**: The brain may apply additional eligibility rules not in the gold standard, or skip some that are in the gold standard. The key is that the majority of conditions are checked.

### 4.4 Profile Completeness

**Rule**: Absolute tolerance of ±0.3.

```
pass = |actual - expected| ≤ 0.3
```

**Rationale**: Completeness is a fuzzy metric. Different pipeline versions may count fields slightly differently. A 0.3 window accounts for this without being so loose as to be meaningless.

### 4.5 Metrics with No Relaxation

All other metrics use **exact match**:
- Intent classification
- Decision action
- Planner turn actions
- Reasoning stage
- Reasoning confidence
- Reasoning current_problem

**Rationale**: These are categorical decisions with a limited set of valid values. There is no legitimate reason for partial matching.

## 5. Scoring

### 5.1 Turn Score

```
turn_score = passed_checks / total_checks
```

### 5.2 Conversation Score

```
conversation_score = Σ(passed_checks) / Σ(total_checks)
conversation_pass = conversation_score ≥ 0.7 AND no must_not violations
```

### 5.3 Overall Benchmark Score

```
overall = Σ(passed_conversations) / total_conversations
```

## 6. Must-Not Violations

Each turn can specify `must_not` patterns. If any pattern appears in the pipeline response (case-insensitive, underscores normalized to spaces), the conversation fails regardless of score.

Common must_not patterns:
- `recommend_branch` — premature recommendation before profile complete
- `hallucinate_cutoff` — citing cutoff ranks not in knowledge base
- `switch_language` — responding in non-requested language

## 7. Evaluator Limitations

1. **No response quality scoring** — evaluator checks structural correctness, not response quality. A response can pass all checks but still be poorly written.
2. **No latency checking** — pipeline latency is recorded but not evaluated.
3. **No domain coverage** — evaluator doesn't verify that the pipeline covers all domain areas.
4. **8 schema fields unevaluated** — see evaluator audit (`docs/evaluator_audit.md`) for full list.

## 8. Versioning

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-07-19 | Initial release |
| 1.1 | 2026-07-19 | Frozen: gold standard fixes (profile_completeness, decision_actions, content_contains, exam_gold, brain_gold), pipeline fixes (rank extraction, multi-turn intent context), 74.8% overall |

Benchmark version tracked in `data/benchmark/VERSION`.
