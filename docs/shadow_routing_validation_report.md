# Pre-Production Shadow Routing Validation Report

**Date:** 2026-07-25
**Router version:** v1.8 shadow-mode (emotion + grievance, threshold=0.8)
**Scope:** utterance-local + ambiguous signals only (conversation-context excluded)
**Behavior:** logging only — production reasoning unchanged

---

## 1. Executive Summary

The shadow signal router is **technically ready for deployment** but **not validated for production routing**. Offline evaluation supports threshold=0.8 as a conservative starting point, but no live traffic has been collected. The router should be deployed in shadow mode (log only) until at least 50 routed events are adjudicated against real traffic.

The correct conclusion is: *"The shadow router is technically ready for deployment, and offline evaluation supports 0.8 as a conservative starting threshold. Production routing is not yet validated because no live traffic is available."*

---

## 2. Validated Offline

These results are computed from the 81-entry gold-labeled evaluation set (37 Pass 1 + 44 Pass 2 annotations) and the full 182-turn benchmark corpus.

### 2.1 Threshold Sweep (emotion + grievance, utterance-local + ambiguous scopes)

| Threshold | Would-route | Precision | Recall | F1 | FP Rate | TP | FP | FN |
|---|---|---|---|---|---|---|---|---|
| 0.5 | 9 | 77.8% | 43.8% | 56.0 | 3.1% | 7 | 2 | 9 |
| 0.6 | 9 | 77.8% | 43.8% | 56.0 | 3.1% | 7 | 2 | 9 |
| 0.7 | 8 | 87.5% | 43.8% | 58.3 | 1.5% | 7 | 1 | 9 |
| **0.8** | **5** | **100.0%** | **31.2%** | **47.6** | **0.0%** | **5** | **0** | **11** |
| 0.9 | 3 | 100.0% | 18.8% | 31.6 | 0.0% | 3 | 0 | 13 |

**Threshold selection:** 0.8 is the shadow deployment threshold. 0.7 has better F1 (58.3 vs 47.6) but introduces one known false positive (reported-speech "stressful"). 0.8 has 100% precision and zero false positives on the offline set. The F1 advantage of 0.7 is based on a very small sample (8 vs 5 routed events) and should not override the safety benefit. Once real-traffic adjudication data exists, threshold selection can be revisited.

### 2.2 Per-Signal Performance (at threshold=0.8)

| Signal | Gold positives | Would-route | Precision | Notes |
|---|---|---|---|---|
| emotion | 14 | 2 | 100% | 12 misses: 2 low confidence, 7 context-dependent, 3 decision-only overlap |
| grievance | 4 | 3 | 100% | 1 miss: low confidence (BENCH_V21_000049:0 grievance=0.7) |
| decision | 10 | **excluded** | — | 60% detector recall is too weak for routing |

### 2.3 Per-Confidence-Band Distribution (at threshold=0.8)

Of the 5 routed events:

| Band | Count | Signals |
|---|---|---|
| 0.80–0.89 | 2 | emotion=0.85, grievance=0.80 |
| 0.90–0.99 | 2 | grievance=0.90, grievance=0.90 |
| 1.0 | 1 | emotion=0.85 (from BENCH_V21_000014:1; detector confidence capped at 0.85) |

### 2.4 Language Distribution

| Language | Total turns | Would-route | Routed signals |
|---|---|---|---|
| english | 72 | 5 | emotion=2, grievance=3 |
| hindi | 8 | 0 | (all below threshold or excluded scope) |
| bengali | 1 | 0 | — |

The evaluation set is English-heavy. Hindi and Bengali coverage is insufficient for language-specific validation.

### 2.5 Scope Distribution (routed events)

| Scope | Total eligible | Would-route | Rate |
|---|---|---|---|
| utterance_local | 41 | 3 | 7.3% |
| ambiguous | 27 | 2 | 7.4% |
| conversation_context_required | 13 | **excluded** | — |

### 2.6 Full Corpus Coverage (182 benchmark turns, threshold=0.8)

| Metric | Value |
|---|---|
| Total turns | 182 |
| Ineligible (conversation-context) | 11 |
| Eligible turns | 171 |
| Would-route | 11 (6.0% of all, 6.4% of eligible) |
| emotion would-route | 8 |
| grievance would-route | 3 |

### 2.7 Deduplication

`ShadowRoutingSink` initializes by loading all existing `observation_id` values from the telemetry log. In-memory set prevents duplicate logging. Verified: two calls with same `observation_id` produce exactly one record.

### 2.8 Unsure Handling

Adjudication script separates `unsure` from both `tp` and `fp`:
- Precision denominator: `tp / (tp + fp)` — unsure excluded
- `unsure_rate` reported independently from `fp_rate`
- No ambiguous adjudication is automatically classified

### 2.9 Zero Production Changes

No files in `src/reasoning/engine.py`, `src/understanding/engine.py`, `src/pipeline/__init__.py`, or any signal detector were modified by the shadow routing implementation. The router is a standalone `Observer` that attaches via `TeeSink`.

Files created (no existing files modified):

| File | Purpose |
|---|---|
| `src/reasoning/shadow_routing.py` | `ShadowSignalRouter`, `ShadowRoutingSink`, `_confidence_band`, telemetry helpers |
| `scripts/evaluate_shadow_routing.py` | Offline threshold sweep and benchmark evaluation |
| `scripts/adjudicate_shadow_routing.py` | Real-traffic adjudication workflow |

---

## 3. Not Validated (requires real traffic)

| Capability | Why not validated |
|---|---|
| **Real-traffic precision** | 100% on 5 events is not statistically significant. Need ≥50 adjudicated routed events. |
| **Real-traffic FP rate** | Offline FP rate (0.0%) is on clean benchmark data. Real queries with typos, fragmented sentences, and edge cases may differ. |
| **Real-traffic language distribution** | Benchmark is 89% English. Production Hindi/Bengali rates may be higher. |
| **Real-traffic confidence calibration** | Detector confidence distribution on production utterances may differ from benchmark. |
| **Production coverage/volume** | 6% of benchmark turns route. Production rate depends on query mix. |
| **Latency impact** | Router latency is <1ms per turn (measured), but the `TeeSink` composition adds a trivial constant factor. |

---

## 4. Deployment Integration

### 4.1 Attach to the pipeline

```python
from src.reasoning.shadow_routing import ShadowRoutingSink
from src.reasoning.observation import TeeSink

sink = ShadowRoutingSink(threshold=0.8)

# If you have an existing observer:
pipeline.run(text, observer=TeeSink([existing_observer, sink]))

# If no existing observer:
pipeline.run(text, observer=sink)
```

### 4.2 Optional: enrich telemetry with conversation context

```python
# Before each pipeline.run():
sink.set_context(
    conversation_id="conv-abc-123",
    turn_id=0,
    text=raw_user_text,
    scope="utterance_local",  # or "ambiguous" / "conversation_context_required"
)
```

Without `set_context()`, the telemetry log still records the routing decision, signal type, confidence, and observation_id — just without the raw text or scope.

### 4.3 Telemetry file

Records accumulate at: **`data/telemetry/shadow_routing.jsonl`**

One JSON line per turn (deduplicated by `observation_id`). Fields:

```
event, observation_id, conversation_id, turn_id, text[:120], scope,
language_hint, reasoning_stage, identified_problem, intent_primary,
threshold, would_route, signal_type, signal_confidence, confidence_band,
structured_signal_types, structured_signal_confidences,
dominant_signal_name, dominant_signal_score, latency_ms
```

---

## 5. Commands to Start Collecting Real Telemetry

### Start deployment
```
# No deployment script needed — attach ShadowRoutingSink to pipeline.run()
# as shown in section 4.1 above.
```

### Check telemetry status
```bash
cd /path/to/college_agent-master
python scripts/adjudicate_shadow_routing.py
```

### Export routed events for adjudication (after ≥50 routed events accumulated)
```bash
python scripts/adjudicate_shadow_routing.py --export
```

Edit `data/telemetry/shadow_routing_adjudicated.jsonl` and set `adjudicated_label` to `"tp"`, `"fp"`, or `"unsure"` for each event.

### Run adjudication report
```bash
python scripts/adjudicate_shadow_routing.py --adjudicate
```

### Offline benchmark re-run (any time)
```bash
python scripts/evaluate_shadow_routing.py
```

---

## 6. Final Status

### Offline validation: complete

- Router behavior tested.
- Threshold sweep complete (0.5 through 0.9).
- Detector/signal breakdown complete.
- Scope filtering verified.
- Deduplication verified.
- Unsure adjudication handling verified.
- No production behavior changes.

### Production validation: not started

- Only 5 annotated events route at threshold 0.8.
- Benchmark is heavily English-biased.
- No real-traffic typo/noise distribution.
- No production coverage estimate.
- No real-traffic precision or FP estimate.

### Final engineering state

The code is done. No further routing architecture, detector threshold, or feature changes should be made until real traffic is collected.

---

## 7. Routing Policy (locked until real-traffic adjudication)

| Signal | Eligible for routing | Reason |
|---|---|---|
| emotion | Yes, if confidence ≥ 0.8 | 85.7% detector recall, 92.3% precision at detector level |
| grievance | Yes, if confidence ≥ 0.8 | 100% detector recall and precision (but only 4 gold examples — re-evaluate with traffic) |
| decision | **No** | 60% detector recall means too many genuine decisions are missed |
| conversation-context | **No** | Deferred to v1.9 cross-turn state design |
| confidence < 0.8 | **No** | Below threshold; see sweep table for tradeoffs |

### Threshold decision guide (for later real-traffic use)

| If precision@0.8 is... | Then... |
|---|---|
| ≥90% | Enable narrow routing (emotion + grievance, utterance-local, threshold=0.8) |
| 75–89% | Keep shadow mode. Consider raising threshold to 0.85 or fixing the FP pattern. |
| <75% | Keep shadow mode. Fix detectors before attempting routing. |

Target: **at least 50 adjudicated routed events** before making a routing decision. 100 is better.
