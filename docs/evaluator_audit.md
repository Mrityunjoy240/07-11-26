# Evaluator Audit — Stage A Findings

**Date**: 2026-07-19  
**Evaluator file**: `scripts/evaluate.py`  
**Schema file**: `data/benchmark/schema/conversation_v0.1.schema.json`  
**Pipeline output builder**: `scripts/benchmark.py` lines 240-305

---

## 1. Metrics vs Real Pipeline Output

| Metric path in evaluator | Pipeline output field | Status |
|---|---|---|
| `understanding.intent.primary` | `understanding.intent.primary` | ✅ Correct |
| `understanding.facts.{field}` | `understanding.facts.{field}` | ✅ Correct |
| `understanding.missing` | `understanding.missing` | ✅ Correct (relaxed to 50% overlap) |
| `reasoning.stage` | `reasoning.stage` (`student_stage`) | ✅ Correct |
| `reasoning.profile_completeness` | `reasoning.profile_completeness` | ✅ Correct (tol=0.3) |
| `reasoning.confidence` | `reasoning.confidence` | ✅ Correct (mapped to string) |
| `reasoning.current_problem` | `reasoning.current_problem` | ✅ Correct |
| `brain.applicable` | `brain.applicable` | ✅ Correct |
| `brain.eligible_branches` | `brain.eligible_branches` | ✅ Correct (relaxed to 50% overlap) |
| `brain.why` | `brain.why` (condition strings) | ✅ Correct (relaxed to 50% overlap) |
| `decision.action` | `decision.action` | ✅ Correct (exact match) |
| `planner.turns[i].action` | `plan.turns[i].action` | ✅ Correct |
| `planner.turns[i].content_contains` | `plan.turns[i].content` | ✅ Correct (substring match) |

**Verdict**: All 13 evaluated metric paths map to real pipeline output fields. No dangling or legacy field references in the evaluator.

---

## 2. Schema Fields NOT Evaluated

The benchmark schema defines these fields, but the evaluator never checks them:

| Schema field | In evaluator? |
|---|---|
| `understanding.confidence` (high/med/low) | ❌ Not evaluated |
| `understanding.inference` (anxiety, confusion, urgency, etc.) | ❌ Not evaluated |
| `reasoning.problems` (array of strings) | ❌ Not evaluated |
| `decision.priority` (high/normal/low) | ❌ Not evaluated |
| `decision.confidence` (high/med/low) | ❌ Not evaluated |
| `decision.why` (array of strings) | ❌ Not evaluated |
| `planner.confidence` (high/med/low) | ❌ Not evaluated |
| `planner.dependency_chain` (array of strings) | ❌ Not evaluated |

**Impact**: These are optional quality signals. The evaluator focuses on the minimum viable contract (intent, facts, action, turns). Not a bug, but a coverage gap to note in the benchmark documentation.

---

## 3. Evaluator Field NOT in Schema

| Evaluator field | In schema? |
|---|---|
| `reasoning.current_problem` | ❌ Not in schema (schema has `reasoning.problems` instead) |

**Status**: This is a known intentional divergence. `current_problem` was added during Phase 2 reasoning fixes. The schema was never updated to include it. The benchmark JSON files DO include `current_problem` in expected output, and the evaluator correctly checks it. **Action**: Update the schema to include `current_problem`.

---

## 4. Relaxation Rules (Subset/Superset Behavior)

| Metric | Relaxation | Allowed direction |
|---|---|---|
| `understanding.missing` | 50% overlap threshold | Bidirectional — pipeline can have extra or miss items |
| `brain.eligible_branches` | 50% overlap threshold | Bidirectional — pipeline can return superset or subset |
| `brain.why` | 50% overlap on condition strings | Bidirectional — pipeline can have extra or missing conditions |
| `reasoning.profile_completeness` | ±0.3 absolute tolerance | Bidirectional |
| All other metrics | Exact match | Neither |

**Verdict**: Superset/subset is only allowed for branch lists, missing info, brain why conditions, and completeness. All of these are appropriate — the pipeline legitimately may return more branches than the gold standard considers, or may ask for more info than the minimum. The 50% overlap threshold is a reasonable minimum bar.

---

## 5. Known Issues

1. **Schema out of date**: Missing `current_problem` in reasoning, missing `exam` in facts.
2. **Schema says `inference`** but pipeline output has `signals` — evaluator doesn't check either, so no runtime issue.
3. **`mock_pipeline_result`** in evaluator is only used for self-testing, not production evaluation — correct behavior.

---

## Recommended Fixes

1. **Update `conversation_v0.1.schema.json`** to add `current_problem` to reasoning and `exam` to facts.
2. **Document the relaxation rules** in the benchmark spec (`eval_spec`).
3. **Leave the 8 unevaluated fields as-is** for now — they're optional quality signals, not required for the minimum viable contract.
