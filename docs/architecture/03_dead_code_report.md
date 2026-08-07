# 03 — Dead Code Report

> Every subsystem, module, and flag in the project that is either unreachable, uninvoked, superseded, or vestigial, with evidence. This is the cleanup backlog — but **do not delete anything yet**; migrate or archive per `09_migration_plan.md`.

---

## 1. Generation 1 — Dead / unreachable code

### 1.1 Fee engine (the biggest one)

| Item | Evidence | Why it's dead |
|---|---|---|
| `FeeEngine` class (`backend/app/services/llm/fee_engine.py:177`) | imported at `groq_service.py:38-46`; `_handle_fee_query`, `_handle_fee_query_new`, `_handle_fee_query_old`, `_structured_lookup` (`groq_service.py:3797-4191`) | Source comments at `groq_service.py:6294-6295` and `:6661` state: **"Structured lookup has been removed."** The LLM answers fee questions directly from retrieved context. |
| `USE_NEW_FEE_ENGINE` flag (`:753`) | default `"0"` | Only guards dead functions. |
| `CACHE_TTL_SECONDS` / `CACHE_MAX_ENTRIES` (`:800-801`) | — | Only used by dead cache code (below). |
| `backend/tests/test_fee_engine.py`, `test_fee_fuzz.py`, `test_fee_parity.py`, `test_parity_validation.py`, `multiturn_fee_audit.py` | — | ~3,200 lines of tests validating a **non-executed** engine. They still run green because they test the class in isolation. |

**Why this matters:** fee answers are deterministic math (admission + tuition + hostel, branch-specific). The current design lets the LLM free-text fees from RAG context — a hallucination risk on the most financially sensitive answers. The code is dead but the *capability* should be resurrected deterministically (see `08_target_architecture.md`, `src/brain`).

### 1.2 Intent classifier

| Item | Evidence |
|---|---|
| `IntentClassifier` (`intent_classifier.py:367`) | instantiated at `groq_service.py:1351`, **never invoked** in `generate_response`/`stream_response`. |

The system relies on regex short-circuits + the LLM, not the classifier. Its structured-vs-RAG intent vocabulary (`:7-14`) is exactly what `src/understanding` re-implements properly.

### 1.3 Query cache

| Item | Evidence |
|---|---|
| `_cache_key`, `_check_kb_changed`, `_cache` | maintained but never read/written in any live flow; `cache_hit: False` hardcoded in every payload (e.g. `groq_service.py:6370`). Only exposed via `/admin/cache/*`. |

### 1.4 Unused provider integrations

| Item | Evidence |
|---|---|
| `OPENROUTER_API_KEY` | in `.env`; no config field, no usage |
| `GEMINI_API_KEY` | config field only (`config.py:31`); zero runtime usage |
| `DEEPGRAM_API_KEY` | config field only (`config.py:32`); zero runtime usage |
| `AsyncGroq` client | created in `config.py:95-105`; only the sync client is used (via `to_thread`) |
| `ollama_connected` in frontend health type | `VoiceChat.tsx:48` — no backend field exists |

### 1.5 Duplicated / vestigial paths

| Item | Evidence |
|---|---|
| SAFEPOINT post-processing **applied twice** on `/qa/query` | `qa.py:141-147` + `groq_service.py:6377-6378` |
| `_init_sarvam()` lazy-init duplicated | `tts.py:39-43`, `stt.py:18-22`, `health.py:11-17` |
| `/qa/tts` vs `/qa/tts-direct` ~80% identical | `tts.py:46-118` vs `:121-197` |
| `stream_response` is not true streaming | full non-streaming LLM call, then word replay with `0.02s` sleeps (`groq_service.py:6716-6719`) |

### 1.6 Broken / risky wiring (not dead, but not functional)

| Item | Evidence |
|---|---|
| LiveKit import unguarded | `voice.py:21` `from livekit import api, rtc` — LiveKit absent from `requirements.txt` |
| Twilio↔LiveKit `/voice/stream` bridge | `voice.py:94-188`; `except Exception: pass` at `:159-162` and `:184-188` swallow failures |
| `/monitoring` always healthy | `monitoring.py:5-6` |
| FastText model runtime download | `language_detect.py:285-309`; fails silently to keyword fallback |

---

## 2. Generation 2 — `src/` dead/dormant

| Item | Evidence |
|---|---|
| `src/engine/` (empty `__init__.py`) | superseded by `src/engines/` |
| `src/policies/` (empty `__init__.py`) | superseded by `src/brain/` (CollegeBrain) |
| `src/observability/` | OTel wiring present but `use_otel=false`; zero tests — dormant |
| `src/storage/` Postgres/Redis adapters | `use_postgres_history=false`, `USE_REDIS_SESSIONS=false` — dormant but valuable |
| `src/dual/runner.py` "pipeline_mode=legacy" | new pipeline runs shadow-only by default — intentional, keep |

---

## 3. Generation 3 — `next_gen/` (whole tree)

Frozen demo, one commit (`5dfc8a9`), never evolved. `src/knowledge/loader.py` is the only uncommitted touch. **Archive the folder, keep the frontend as reference.**

---

## 4. Operational artifacts (not code to maintain)

`backend/`: `b3_evidence.py`, `b7_evidence.py`, `b8_evidence.py`, `_dead_code_audit.py`, `_impact.py`, `smoke_test_security.py`, `stress_test_reliability.py`, `validate_blockers.py`, `validate_remaining.py`, `test_query.py`, `perf_*.txt`, dozens of `server_*.log`.
Root: `trace_pipeline*.py`, `trace_retrieval.py`, `probe_queries.py`, `validate_fixes.py`, `verify_changes.py`, `test_*.json` — one-off forensics for the Bengali-backlog incident.

These are historical artifacts; they should move to an `archive/` folder, not be maintained.

---

## 5. Summary table

| # | Dead item | Generation | Action (proposal) |
|---|---|---|---|
| 1 | Fee engine + its 4 test files | G1 | **Resurrect** as deterministic tool in `src/brain`; delete legacy implementation |
| 2 | IntentClassifier (uninvoked) | G1 | Replace with `src/understanding` |
| 3 | Query cache + admin cache endpoints | G1 | Delete (replace with real caching via pgvector/Redis) |
| 4 | Unused provider keys (OpenRouter/Gemini/Deepgram) | G1 | Rotate/remove |
| 5 | AsyncGroq client | G1 | Delete or use (pick one path) |
| 6 | Double SAFEPOINT + triple `_init_sarvam` | G1 | Consolidate |
| 7 | Fake streaming | G1 | Replace with true token streaming (already in `src/` design) |
| 8 | LiveKit voice bridge | G1 | Replace with LiveKit Agents framework or Pipecat (see `07_recommended_stack.md`) |
| 9 | `src/engine`, `src/policies` | G2 | Delete empty shells |
| 10 | `src/observability` | G2 | Activate via OTel (see `08_target_architecture.md`) |
| 11 | `next_gen/` | G3 | Archive/delete |
| 12 | One-off audit scripts + logs | G1 | Move to `archive/` |
