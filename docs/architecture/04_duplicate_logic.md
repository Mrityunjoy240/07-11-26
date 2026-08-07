# 04 — Duplicate Logic Report

> Everywhere the same behavior is implemented in two or more places across the three generations. Duplication is the top maintenance-cost driver: fixes applied in one copy silently drift in the others.

---

## 1. Duplication inventory

### 1.1 `app/core/pipeline/` vs `src/pipeline/` (conceptual twin)

The legacy core has a `pipeline/` package (runner + 6 stages) that is **unwired**; `src/pipeline/` implements the same staged design but is the real one. Two designs, one implementation.

| | `backend/app/core/pipeline/` | `src/pipeline/` |
|---|---|---|
| Status | Experimental/unwired | Active (shadow mode) |
| Risk | Falls out of sync instantly | — |

**Decision:** the `core/pipeline/` copy is a mirror of intent. Either delete it or make it a thin re-export of `src/pipeline` (blocked by import boundary today — see §5).

### 1.2 Normalizer duplicated

- `backend/app/services/normalization/normalizer.py` — single-file clean room English + Bengali normalization.
- `src/pipeline/` includes its own normalization stage.
- `next_gen/src/core/postprocessors.py` + `next_gen/src/llm/provider.py` both embed their own normalization for TTS.

Three-four copies of "clean the text before feeding the model/TTS."

### 1.3 Language detection duplicated

- `backend/app/utils/language_detect.py` — FastText + keyword fallback.
- `src/understanding/language.py` — its own detection.
- `next_gen/src/handlers/*` — per-handler `is_english / is_bengali` checks.
- `sarvam_service.py` — Sarvam-side normalization also does language-aware cleaning.

### 1.4 Intent/short-circuit routing duplicated

- `backend/app/services/llm/intent_classifier.py` (dead) defines a 10-intent vocabulary.
- `src/understanding/signals/` re-implements intent detection.
- `next_gen/src/core/intent.py` defines a 14-intent regex router.
- `groq_service.py:6050-6248` — inline regex short-circuits for yes/no/continue/greeting.

Four vocabularies for "what is the user asking."

### 1.5 Safe-point / safety guard duplicated

- `groq_service.py:6377-6378` post-process safe-point **plus** `qa.py:141-147` runs safe-point again on the same response → double application.
- `safe_point.py` safe-point engine only runs when flag on.
- `src/brain/` has its own safe-point logic.

### 1.6 Voice/TTS helpers duplicated

- `utils/voice_utils.py` (abbreviations/acronyms) vs `sarvam_service.py` (Sarvam normalization) vs `next_gen/src/voice/tts.py` (edge-tts cleaners).
- `_init_sarvam()` lazy client init in 3 places: `tts.py:39-43`, `stt.py:18-22`, `health.py:11-17`.
- `/qa/tts` vs `/qa/tts-direct` ~80% identical handlers (`tts.py:46-118` vs `:121-197`).

### 1.7 Knowledge-base loading duplicated

- `document_processor.py` chunks admin uploads → ChromaDB.
- `combined_kb.json` (root, ~8,700 entries) is separately loaded and concatenated into the prompt at `groq_service.py:6274-6289`.
- `src/knowledge/` plans a loader that must reconcile both sources.
- `next_gen/src/knowledge/loader.py` — a third loader.

Result: the LLM sees **two** representations of the KB (ChromaDB retrieval + full JSON dump in prompt), which is the biggest prompt-bloat + inconsistency driver.

### 1.8 Telemetry duplicates

- `services/request_log.py` (JSONL ring) vs `utils/conversation_logger.py` (per-session JSONL) vs `utils/stage_profiler.py` (timings) vs `src/telemetry/` (its own, shadow-only) vs `src/observability/` (OTel, dormant).
- Same event logged in three different files with three schemas. No single source of truth.

### 1.9 Config/settings duplication

| Topic | G1 | G2 |
|---|---|---|
| Server port/paths | `backend/app/config.py` | `src/config.py` |
| Pipeline mode | `core/pipeline` runner | `dual/runner.py` `pipeline_mode=legacy` |
| Model name | `config.py` Groq default | `src/llm/config.py` default |

### 1.10 Fee logic (see `03_dead_code_report.md` §1.1)

`fee_engine.py` implements fee math **and** `groq_service.py` also free-forms fee answers via LLM → duplicate semantic domain with different (conflicting) results possible.

---

## 2. Cost of duplication (concrete)

| Duplicate | Real incident risk |
|---|---|
| Two KB representations | LLM retrieves Chroma chunk + full JSON dump → contradiction/hallucination on same question |
| Normalizer drift | Bengali accent normalization differs between `normalizer.py` and `src/pipeline` → inconsistent RAG query embedding vs stored chunks |
| Language detection drift | `language_detect.py` vs `src/understanding/language.py` → different language tag → different response language |
| Intent vocabulary drift | 4 vocabularies → classifier says one intent, short-circuit regex says another |
| Double safe-point | response filtered twice with same rules → dead-lettered or over-truncated answers |
| Triple `_init_sarvam` | 3 different failure modes for "no API key" |
| 5 telemetry backends | debugging requires reading 5 files |

---

## 3. Root cause

The project is three generations of *rewrites* rather than *refactors*. Each generation copied the good ideas forward and re-implemented shared primitives (normalization, language detect, intent, retrieval, telemetry) because there was no common package boundary to reuse.

## 4. Consolidation targets (proposal, in order)

1. **One shared primitives package** (`src/primitives/` or reuse `src/understanding`+`src/brain`): normalization, language detection, intent/signals — the ONLY implementations, imported by legacy-compat shim and new pipeline alike.
2. **One retrieval path** (`src/retrieval/`/`src/storage/`): kill the `combined_kb.json` prompt dump; rely on vector retrieval + rerank only.
3. **One telemetry pipeline** (`src/observability/` OTel), with `request_log`/`conversation_logger`/`stage_profiler` as legacy exporters for a migration window.
4. **One TTS init/voice util**; delete `/tts-direct`; keep `/tts` only.
5. **Delete `core/pipeline/` mirror** or convert to re-export.
6. **Archive `next_gen/`** (its only unique asset is the `en-IN` Web Speech frontend).

See `09_migration_plan.md` for sequencing; do **not** do this as a big-bang refactor.
