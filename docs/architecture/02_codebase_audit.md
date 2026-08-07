# 02 — Codebase Audit

> Companion to `01_current_architecture.md`. A per-file inventory of all three generations with an explicit verdict per file: **ACTIVE / EXPERIMENTAL / DEAD**. Line references point into the repo at time of analysis (2026-08-07).

---

## 1. Generation 1 — Legacy backend (`college_agent-master/backend/app/`)

### 1.1 App core

| File | Verdict | Notes |
|---|---|---|
| `main.py` | ACTIVE | Server entry; wires all routers, middleware, rate limiter (`main.py:16-108`) |
| `config.py` | ACTIVE | pydantic-settings; Groq/AsyncGroq clients (`:87-102`); Twilio, auth, dirs |
| `core/auth.py` | ACTIVE | JWT HS256, bcrypt w/ plaintext fallback (`:27-31`) |
| `core/database.py` | ACTIVE | SQLite WAL; conversations/messages tables (`:26-50`) |
| `core/limiter.py` | ACTIVE | slowapi, 10/min default |
| `core/feature_flags.py` | EXPERIMENTAL | imported nowhere outside `core/` |
| `core/di.py` | EXPERIMENTAL | unwired DI container |
| `core/interfaces.py` | EXPERIMENTAL | unwired interfaces |
| `core/models.py` | EXPERIMENTAL | unwired models |
| `core/conversation_engine.py` | EXPERIMENTAL | unwired |
| `core/event_bus.py` | EXPERIMENTAL | unwired |
| `channel/web_adapter.py` | EXPERIMENTAL | unwired |
| `pipeline/*` (runner + 6 stages) | EXPERIMENTAL | unwired (mirrors `src/` design) |

### 1.2 API routers

| File | Verdict | Notes |
|---|---|---|
| `api/qa.py` | ACTIVE | `/qa/query`, `/qa/query-stream`, debug, session, health |
| `api/conversations.py` | ACTIVE | full CRUD on SQLite (sync DB calls in async handlers) |
| `api/tts.py` | ACTIVE | `/tts` and `/tts-direct` are ~80% duplicated (`:46-118` vs `:121-197`) |
| `api/stt.py` | ACTIVE | `saaras:v3`; 503 without key |
| `api/ws_voice.py` | ACTIVE | text→TTS WebSocket pipeline |
| `api/voice.py` | ACTIVE (broken) | LiveKit import unguarded (`:21`), LiveKit NOT in requirements.txt |
| `api/voice_sdk.py` | EXPERIMENTAL | gated on `SARVAM_SDK_ENABLED` |
| `api/admin.py` | ACTIVE | upload/backup/KB/FAQ/cache admin (5–10/min limits) |
| `api/knowledge_base.py` | ACTIVE | `/admin/kb/reindex` |
| `api/health.py` | ACTIVE | `/health`, `/health/tts` |
| `api/monitoring.py` | ACTIVE (stub) | always returns healthy (`:5-6`) |
| `api/auth_routes.py` | ACTIVE | POST `/token` |

### 1.3 Services

| File | Verdict | Notes |
|---|---|---|
| `services/llm/groq_service.py` | ACTIVE | 6,745-line monolith; the entire brain |
| `services/llm/fee_engine.py` | **DEAD (unreachable)** | not called by any flow; `USE_NEW_FEE_ENGINE` default off (`:753`) |
| `services/llm/intent_classifier.py` | **DEAD (unreachable)** | instantiated at `groq_service.py:1351`, never invoked |
| `services/llm/safe_point.py` | EXPERIMENTAL | `demo_safepoint=false` default; active only when flag set |
| `services/normalization/normalizer.py` | ACTIVE | called at `groq_service.py:273` |
| `services/vector_store.py` | ACTIVE | ChromaDB singleton, k=10, 0.15 threshold |
| `services/shadow_routing.py` | ACTIVE | `record_shadow` at `:387`; emotion/grievance regex |
| `services/request_log.py` | ACTIVE | JSONL + 100-entry ring |
| `services/tts_cache.py` | ACTIVE | memory + disk WAV cache |
| `services/sarvam_service.py` | ACTIVE (key-gated) | TTS voices + normalization |
| `services/sarvam_sdk.py` | EXPERIMENTAL | SDK session bridge, env-gated |
| `services/livekit_session.py` | EXPERIMENTAL | guarded imports, token gen only |
| `services/document_processor.py` | ACTIVE | PDF/spreadsheet chunking (admin uploads) |
| `services/backup.py` | EXPERIMENTAL | admin-only, no scheduler |
| `services/telephony/twilio_service.py` | ACTIVE (thin) | Twilio client wrapper |

### 1.4 Utils

| File | Verdict | Notes |
|---|---|---|
| `utils/voice_utils.py` | ACTIVE | abbreviations/acronyms/speaker-map for TTS |
| `utils/language_detect.py` | ACTIVE | FastText lid.176.ftz runtime download (`:285-309`), keyword fallback |
| `utils/conversation_logger.py` | ACTIVE | per-session JSONL telemetry |
| `utils/stage_profiler.py` | ACTIVE | per-request stage timings |

---

## 2. Generation 1 — Frontend (`college_agent-master/frontend/`)

| File | Verdict | Notes |
|---|---|---|
| `src/main.tsx`, `src/App.tsx` | ACTIVE | BrowserRouter; VoiceChat `/`, Admin `/admin` |
| `src/components/VoiceChat/VoiceChat.tsx` | ACTIVE | `sessionId` hardcoded null (`:49`) |
| `src/hooks/useVoiceWS.ts` | ACTIVE | WS to `/qa/ws/voice` (`:39`) |
| `src/hooks/useVoice.ts` | ACTIVE | MediaRecorder + silence detection |
| `src/components/Chatbot/*` | ACTIVE | greeting, quick replies, chat window |
| `src/components/Sidebar.tsx` | ACTIVE | conversation CRUD |
| `src/components/Admin/AdminDashboard.tsx` | ACTIVE | file uploads |
| `dist/` | ACTIVE | built bundle served by backend |

---

## 3. Generation 1 — Tests / Benchmarks / Scripts

| Area | Verdict | Notes |
|---|---|---|
| `backend/tests/` (19 files) | ACTIVE | groq_service (1,298 ln), fee parity, fee fuzz, regression, session isolation, language consistency… |
| `backend/benchmarks/` | ACTIVE | run_full_eval, continue_eval, resume_eval, demo_stress_test… |
| `backend/scripts/sdk_chat.py` | EXPERIMENTAL | SDK console |
| `backend/{b3,b7,b8}_evidence.py`, `smoke_test_security.py`, `stress_test_reliability.py`, `validate_*.py`, `_dead_code_audit.py` | OPERATIONAL ARTIFACTS | one-off audit/evidence scripts, not maintained |

---

## 4. Generation 2 — `src/` (see `01_current_architecture.md` §4 for the package table)

Highlights of risk-bearing findings:

| Item | Verdict |
|---|---|
| `src/engine/__init__.py` (empty) | DEAD — superseded by `src/engines/` |
| `src/policies/__init__.py` (empty) | DEAD — superseded by `src/brain/` |
| `src/observability/` | DORMANT — OTel flag off, zero tests |
| `src/validation/`, `src/reasoning/{baseline,context,observation,shadow_routing}.py`, `src/understanding/signals/`, `src/composer/models.py`, `src/decision/models.py` | **UNCOMMITTED** — high loss risk |
| `tests/` (44 files) | ACTIVE — all green-by-design; `__pycache__` shows a deleted `test_generalization*` |
| `docs/` (8 files) | ACTIVE — benchmark versioning, eval spec, signal contract audit |
| `scripts/` (~50 tools) | ACTIVE for pipeline development |
| `.github/workflows/{ci,benchmark}.yml` | ACTIVE, but benchmark.yml needs root `requirements.txt` that **does not exist** |

---

## 5. Generation 3 — `next_gen/`

| Component | Verdict | Notes |
|---|---|---|
| `src/main.py` | FROZEN | `create_app()` factory, CORS open |
| `src/core/{pipeline,intent,models,postprocessors}.py` | FROZEN | single orchestrator, 14-intent regex router |
| `src/handlers/*` (8) | FROZEN | trilingual structured handlers |
| `src/llm/*` | FROZEN | LLMProvider ABC + GroqProvider + fallback router |
| `src/retrieval/*` | FROZEN | Chroma singleton + RAGEngine |
| `src/session/memory.py` | FROZEN | in-memory, 1800s TTL, "demo, single process" (docstring) |
| `src/voice/tts.py` | FROZEN | edge-tts (free) |
| `src/knowledge/loader.py` | TOUCHED (uncommitted) | only modified next_gen file |
| `src/channels/*` | FROZEN | REST + WS, voice-over-WS "not yet supported" |
| `frontend/` | FROZEN | React + Vite, Web Speech `en-IN` |
| `tests/test_pipeline.py` | FROZEN | quick-script, 7 keyword assertions |

**Verdict: whole generation = DEAD/ABANDONED (archive it).**

---

## 6. Git hygiene

- 17 commits on `master`; branches `release/demo-v1`, `backup/v1-demo-2026-07-17`.
- Legacy tree was originally committed as `21-06-26-college-agent/` and later tracked as `college_agent-master/` (path rename in git).
- Latest commit `3dec397` (2026-08-03) = Sarvam Agents SDK bridge + request observability, **touching only the legacy backend** — evidence of dual maintenance.
- Uncommitted working tree ≈ 177 paths outside the legacy dir (new `src/validation/`, reasoning modules, signals…).

---

## 7. Audit scorecard (density of signals)

| Dimension | Gen 1 (legacy) | Gen 2 (src/) | Gen 3 (next_gen) |
|---|---|---|---|
| Serves production | ✅ | ❌ (shadow) | ❌ |
| Test coverage | Good (unit) | Excellent (44 files + benchmark) | Minimal |
| Observability | Bespoke JSONL | OTel dormant + sqlite telemetry | None |
| Security | **Broken** (secrets, no auth) | Flag-driven, no secrets yet | Open CORS, demo-grade |
| Docs | Many one-off `.md` reports | Roadmap + eval docs | README |
| Maintainability | Low (monolith) | High (staged, typed) | High (small) but abandoned |

---

## 8. Conclusion

- The legacy backend is **the production system and the maintenance problem**. Its core flow is ~50% real logic and ~50% dead/vestigial paths.
- `src/` is **the intended future** and holds the valuable intellectual property (pipeline, brain, benchmark, validation).
- `next_gen/` is **salvage/archive only**.
- The transition risk is that both Gen 1 and Gen 2 are being maintained simultaneously while neither is production-grade at the same time.
