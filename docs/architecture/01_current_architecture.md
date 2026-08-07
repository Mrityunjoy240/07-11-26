# 01 — Current Architecture

> Status: **As-is snapshot**. This document describes what the project looks like today, what actually serves traffic, what is experimental, and what is abandoned. It is the ground truth that all subsequent documents (02–10) build upon.
> Date of analysis: 2026-08-07. No code was changed.

---

## 1. Executive Summary

The repository contains **three generations** of the BCREC college AI assistant:

1. **Legacy serving system** — `college_agent-master/backend/` (FastAPI). This is the **only code that serves real users today** (verified live at `http://127.0.0.1:8001`). A ~6,700-line monolith (`groq_service.py`) does normalization → retrieval → grounding → one Groq LLM call. Voice is a Sarvam TTS/STT bridge; telephony is a Twilio ↔ LiveKit experiment.
2. **`src/` — the active rewrite** — a staged pipeline (`understanding → reasoning → decision → planner → composer`) with a `College Brain`, capability registry, signal detection, validation, and benchmark v2.0+. It has **no serving entry point yet**; it runs in *shadow mode* against the legacy system via `src/dual/runner.py`.
3. **`next_gen/` — an abandoned demo** — a clean-room "free-tools-only" prototype (FastAPI + React + ChromaDB + edge-tts), committed once (2026-07-17) and never touched again.

**Bottom line:** production = legacy monolith; the future (per `ARCHITECTURE_ROADMAP.md`) = `src/`; `next_gen/` = dead weight.

---

## 2. Repository Layout

```
C:\Users\ANAMIKA\DEV\Temp\college_agent-master\     ← git root (17 commits, branch master)
├── college_agent-master\            ← GENERATION 1 — legacy production app (nested folder)
│   ├── backend\                     ← FastAPI app (THE LIVE SERVER)
│   │   ├── app\main.py              ← server entry point (uvicorn :8001)
│   │   ├── app\api\                 ← routers: qa, conversations, tts, stt, ws_voice,
│   │   │                               voice, voice_sdk, admin, knowledge_base, health,
│   │   │                               monitoring, auth_routes
│   │   ├── app\services\            ← llm\groq_service.py (6,700 ln), vector_store, sarvam_*,
│   │   │                               normalizer\, shadow_routing, tts_cache, document_processor,
│   │   │                               livekit_session, telephony\twilio_service
│   │   ├── app\core\  app\pipeline\  app\channel\   ← experimental, unwired
│   │   ├── app\data\                ← canonical\, fee_structures\, knowledge_base\, JSONs
│   │   ├── tests\  benchmarks\  scripts\
│   │   └── .env                     ← ALL live secrets (Groq, Sarvam, Twilio, LiveKit…)
│   └── frontend\                    ← React 18 + MUI + Vite (built to frontend\dist)
│
├── src\                             ← GENERATION 2 — active rewrite (no server yet)
│   ├── pipeline\  understanding\  reasoning\  decision\  planner\  composer\
│   ├── brain\  registry\  conversation\  validation\  evaluation\  telemetry\  llm\
│   ├── storage\  config\  prompts\  dual\  observability\
│   └── engine\  policies\           ← empty shells (DEAD)
│
├── next_gen\                        ← GENERATION 3 — abandoned demo
│   ├── src\main.py                  ← FastAPI app factory (frozen)
│   ├── src\{core,channels,handlers,retrieval,llm,session,voice,knowledge}\
│   ├── frontend\                    ← React 18 + Vite (Web Speech STT, edge-tts)
│   └── tests\test_pipeline.py
│
├── scripts\                         ← ~50 forensic/eval tools for the src\ pipeline + trace scripts
├── tests\                           ← 44 test files for src\
├── docs\                            ← benchmark/eval/annotation docs
├── data\                            ← sqlite conversations.db, telemetry\, benchmark\ (v2.0), evaluation\
├── chroma_db\                       ← ChromaDB persistence (chroma_db_v2)
├── backups\  logs\  uploads\
├── docker-compose.yml               ← redis:7-alpine + postgres:16-alpine (NOT in production path)
├── pyproject.toml                   ← NO dependencies declared (CI gap)
└── ARCHITECTURE_ROADMAP.md          ← 183 KB design source-of-truth
```

---

## 3. Generation 1 — The Live Production System

### 3.1 Stack

| Concern | Technology |
|---|---|
| API framework | FastAPI + uvicorn, port **8001** |
| LLM provider | **Groq** — model `llama-3.1-8b-instant`, `max_tokens=384` (`groq_service.py:1297-1298`); fallback chain `llama-3.1-8b-instant / groq/compound-mini / qwen/qwen3.6-27b` (`:1072`); sync client via `asyncio.to_thread` (`:1376-1384`), 6.0s hard timeout (`:1365`) |
| Vector search | **ChromaDB** `chroma_db_v2`, embedder `all-MiniLM-L6-v2`, `k=10`, score ≥ 0.15 |
| Voice (TTS) | **Sarvam** `bulbul:v3`, speakers shubh/aditya/ritu (hi→aditya, bn→ritu, en→shubh) |
| Voice (STT) | **Sarvam** `saaras:v3` |
| Telephony | **Twilio** outbound + **LiveKit** WebRTC media bridge (experimental, broken import) |
| LLM observability | None (bespoke JSONL logs only) |
| Datastores | SQLite `conversations.db` (only written by `/api/conversations`), ChromaDB, JSON KB files |
| Frontend | React 18 + MUI 5 + react-router + react-markdown + Vite 5 |

### 3.2 Registered routes (from `main.py:135-155`)

| Prefix | Router | Auth |
|---|---|---|
| `/qa/query`, `/qa/query-stream`, `/qa/debug/*`, `/qa/session/*`, `/qa/health` | qa | `require_tool_auth` — **no-op, token empty** |
| `/qa/tts*`, `/qa/tts/voices`, `/qa/tts/languages`, `/qa/tts/cache/*` | tts | none |
| `/qa/stt*` | stt | none |
| `/qa/ws/voice` (WebSocket) | ws_voice | none |
| `/api/conversations*` | conversations | `require_tool_auth` — **no-op** |
| `/admin/*` | admin | JWT (admin/admin) |
| `/voice/token`, `/voice/call-me`, `/voice/twiml/*`, `/voice/stream` | voice | LiveKit/Twilio |
| `/sdk/*` | voice_sdk | **only if `SARVAM_SDK_ENABLED`** |
| `/health`, `/monitoring`, `/token` | health/monitoring/auth | — |

**Security finding:** `SARVAM_TOOL_API_TOKEN` is empty (`.env:16`), so `/qa/*`, `/api/conversations/*` and `/voice/call-me` are effectively **unauthenticated**.

### 3.3 The live question flow (`POST /qa/query`)

Traced through `groq_service.generate_response` (`groq_service.py:5825-6406`):

```
User message
  → observability middleware (request_id, request_log)          main.py:61-100
  → require_tool_auth (no-op)
  → normalize_query (Hinglish/Banglish fixes)                    :5854-5869
  → yes/no continuation?  → ack, re-ask last Q                   :5873-5921
  → short follow-up resolution ("kitna?", "36 lpa?")             :5952-5960
  → transcript validation / noise detection                      :5963-6010
  → language detect (FastText lid.176.ftz)                       :6013
  → SAFEPOINT pre-check (handoff / bengali low-confidence)       :6020-6027
  → language switch detection (re-runs previous question)
  → deterministic short-circuits (no LLM):
       greeting / ack / open-intent / backlog-open /
       out-of-domain / exit / thanks / repeat                    :6050-6248
  → SHADOW ROUTING record (emotion/grievance regex)              :6251
  → GROUNDING / RETRIEVAL:
       _retrieve_context → detect_language → _normalize_query
       → _expand_query → vector_store.search_with_scores(k=10)   :6254-6291
       → refusal guards: grounded / existence / low-confidence    :1692/1895/2061
  → SINGLE LLM PATH (no structured lookup — comment at :6294):
       prompt = lang-prefix + SYSTEM_PROMPT + combined_kb.json
                + verified docs + profile + last 4 turns + query  :6299-6346
       _call_llm_with_tools → rate limit → to_thread(Groq) → 6s
       timeout → 2 attempts → <think> strip                       :1361-1424
  → TTS cap (400 chars, sentence boundary)                        :6353-6359
  → SAFEPOINT post-process ("I don't know" rewriting)             :6377-6378
  → telemetry (StageProfiler, QA_OK log)                          :6401-6406
  → response (source, intent, retrieval_score, confidence_tier)   qa.py:149-168
```

**Key structural fact:** the **LLM does everything**. The fee engine, intent classifier, and structured lookup are dead code (see `03_dead_code_report.md`). Retrieval quality is the only guard against hallucination.

### 3.4 Telemetry (all bespoke)

| Sink | Path | Contents |
|---|---|---|
| App log | `logs/app.log` | JSON lines, rotating 10MB×5, `REQ`/`QA_OK`/`QA_ERR`, per-request stage timings |
| Request log | `data/telemetry/request_log.jsonl` + in-memory ring (100) | per-HTTP-request JSONL |
| Conversation telemetry | `data/logs/conversations/session_{id}_{date}.jsonl` | TURN_INPUT, TURN_RETRIEVAL, TURN_PROMPT, TURN_LLM_START/COMPLETE, TURN_VALIDATION, TURN_ERROR, SESSION_SUMMARY |
| Shadow routing | `data/telemetry/shadow_routing.jsonl` | emotion/grievance regex hits, dedup key session+text |
| SQLite | `chroma_db/conversations.db` | conversations + messages — **written only by `/api/conversations`, never by the Q&A path** |

There is **no trace UI, no span correlation, no eval-on-traces**. This is the single biggest production observability gap.

### 3.5 Data & knowledge content

- `backend/data/knowledge_base/combined_kb.json` (~86 KB) — primary KB fed to the LLM.
- `backend/data/canonical/canonical_kb.json` (~77 KB) + `entity_dictionary.json` (used by normalizer).
- `backend/data/fee_structures/` — btech/hostel/mba/mca/mtech fee JSON.
- `backend/data/` — `college_facts.json`, `admin_faq.json`, `knowledge_gaps.json`, `dept_files.json`.
- 12 department `.md` + 10 topic `.md` markdown files, ingestible into ChromaDB via `/admin/kb/reindex`.

### 3.6 Frontend (Generation 1)

- `VoiceChat` → `POST /qa/query` + WebSocket `/qa/ws/voice` (`useVoiceWS.ts:39`); `sessionId` is **hardcoded null** (`VoiceChat.tsx:49`) so session state never scopes correctly.
- `Chatbot` → `POST /qa/query`, greeting + 5 quick replies.
- `Sidebar` → `/api/conversations` CRUD; `AdminDashboard` → `/admin/files`, uploads.
- Built with `tsc && vite build` → served statically by backend at `/`.

---

## 4. Generation 2 — `src/` (the active rewrite)

### 4.1 What it is

A staged, opinionated pipeline architecture built to replace the monolith. **Everything in `src/` is wired only to its own tests and the dual-runner; it does not serve requests.**

### 4.2 Package map & verdicts (evidence in `02_codebase_audit.md`)

| Package | Role | Verdict |
|---|---|---|
| `pipeline` | `PipelineOrchestrator`, `PIPELINE_VERSION="1.0.0"` | ACTIVE |
| `understanding` | intent + concepts + signals (emotion/grievance/decision) + student profile + pathway eligibility; 1,393+ lines | ACTIVE |
| `reasoning` | `ReasoningEngine` (intent-aware readiness), baseline/context/observation/shadow_routing (uncommitted) | ACTIVE |
| `decision` | `DecisionEngine` + rule table | ACTIVE |
| `planner` | `MinimalPlanner` v2 + behavioral content map | ACTIVE |
| `composer` | `ResponseComposer` v2 | ACTIVE |
| `brain` | `CollegeBrain` v1 — 5 executable policies (admission/fees/hostel/placement/scholarship), WBJEE 2026 cutoffs | ACTIVE |
| `registry` | `CapabilityRegistry` + manifests | ACTIVE |
| `conversation` | state/session/context/service/interfaces | ACTIVE |
| `validation` | ground-truth validation, dependency graph, blame attribution (entirely uncommitted) | ACTIVE (uncommitted) |
| `evaluation` | `EvaluationEngine` (completed/abandoned/escalated/clarified/error) | ACTIVE |
| `telemetry` | sqlite `pipeline_runs` table | ACTIVE |
| `storage` | SessionStore InMemory/Redis/Postgres (feature-flagged off) | ACTIVE (flags off) |
| `llm` | `GroqLLM` + `MockLLM`; `HAS_GROQ` optional | ACTIVE |
| `prompts` | `PromptManager` (system/*, templates/*) | ACTIVE |
| `dual` | `runner.py` — runs legacy vs new side-by-side → telemetry | ACTIVE (bridge) |
| `observability` | OTel (flag off) | DORMANT |
| `engine` | empty `__init__.py` | DEAD |
| `policies` | empty `__init__.py` | DEAD |
| `config` | `Settings`; **`pipeline_mode` defaults to `"legacy"`** | ACTIVE |

### 4.3 Testing & evaluation assets (the crown jewels of this generation)

- **44 test files** covering brain, composer, config, conversation, decision, dual, engines, evaluation, llm, pipeline, planner, prompts, reasoning, registry, storage, telemetry, understanding, validation.
- **Benchmark v2.0**: `data/benchmark/` — 100+ golden conversations across 17 categories (admission, fees, hostel, grievance, placement, multilingual…), schema v2, CI workflow `.github/workflows/benchmark.yml`.
- Eval tooling in `scripts/`: `benchmark.py`, `compare.py`, `adjudicate.py`, `inter_rater.py`, `mismatch_classifier.py`, `failure_triage.py`, etc.

### 4.4 Known gaps

- **No server, no channel layer, no frontend** — the legacy frontend cannot talk to `src/`.
- `pipeline_mode=legacy` ⇒ new pipeline is shadow-only.
- Uncommitted work in `src/` (validation, signals, reasoning modules) is **at risk** — a commit is overdue.
- CI runs `pip install -r requirements.txt`, but **no root `requirements.txt` exists** (CI gap).
- `observability` package has zero test coverage.

---

## 5. Generation 3 — `next_gen/` (abandoned demo)

- Committed **once** (root commit `5dfc8a9`, 2026-07-17); zero commits since; branch `backup/v1-demo-2026-07-17`.
- Clean-room demo: FastAPI + React + ChromaDB RAG + structured handlers (fee/contact/department/HOD/placement/hostel/scholarship) + trilingual templates + **edge-tts** (free Microsoft voices) + Web Speech STT.
- Its `server.log` shows a partial run 2026-07-13 (no GROQ_API_KEY, `langchain_chroma` missing, but server booted).
- The project pivoted from `next_gen` to the `src/` architecture. Its **frontend and handler patterns were not ported** into `src/`.

**Verdict: throw away (or archive), with salvage rights on the frontend.**

---

## 6. Deployment Reality

- The only thing deployed/served is Generation 1 via uvicorn on port 8001 (verified healthy `{"status":"ok"}` at `/health/`).
- `docker-compose.yml` (redis:7-alpine, postgres:16-alpine) exists but is **not in the production path** — it supports the `src/` storage adapters.
- No container image is built for the legacy app in this snapshot (Dockerfiles exist but are not wired to a pipeline).
- Secrets: live provider keys committed in `backend/.env` (Groq, OpenRouter, Gemini, Sarvam, Deepgram, LiveKit, Twilio) + hardcoded JWT `SECRET_KEY` + `admin/admin` — **must be rotated**.

---

## 7. Summary Diagram

```
                      ┌───────────────────────────────┐
  USERS (web chat, admin, phone)                        │
                      └──────────────┬────────────────┘
                                     │
   ┌─────────────────────────────────┼────────────────────────────────┐
   │   GENERATION 1 (LIVE)           │                               │
   │   FastAPI :8001                 │                               │
   │   ┌────────────────────────────┼────────────────────────────┐  │
   │   │  /qa/query ─→ groq_service (6,700-line monolith)        │  │
   │   │   normalize → short-circuit policies → shadow           │  │
   │   │   → retrieve(k=10) → refusal guards → LLM → safe point  │  │
   │   │   → telemetry (bespoke JSONL)                           │  │
   │   ├─────────────────────────────────────────────────────────┤  │
   │   │  Voice: Sarvam TTS/STT ── WS /qa/ws/voice               │  │
   │   │  Telephony: Twilio ↔ LiveKit bridge (broken import)     │  │
   │   │  Admin: uploads, backups, KB reindex, FAQ, cache        │  │
   │   └─────────────────────────────────────────────────────────┘  │
   │   data: ChromaDB (chroma_db_v2) · SQLite conversations.db      │
   │         JSON KB (combined_kb.json, canonical, fee_structures)  │
   └────────────────────────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────────────────────┐
   │ GENERATION 2  src/  (shadow/dual only, no server)            │
   │  understanding → reasoning → decision → planner → composer   │
   │  + brain (policies) + registry + validation + evaluation     │
   │  + dual/runner.py (legacy vs new comparison)                 │
   └──────────────────────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────────────────────┐
   │ GENERATION 3  next_gen/  (frozen demo, 1 commit)             │
   └──────────────────────────────────────────────────────────────┘
```

---

## 8. Key Takeaways for the Architecture Proposal

1. **The product brain and knowledge assets are valuable** (golden benchmark, canonical KB, bilingual normalizer, grounding guards, College Brain policies).
2. **The serving layer is a monolith with dead subsystems and no observability** — it must be replaced by the `src/` pipeline, not endlessly patched.
3. **Provider coupling is already two-deep** (Groq for LLM, Sarvam for voice) and several more providers are half-wired (OpenRouter, Gemini, Deepgram, OpenAI, LiveKit). The Provider Adapter Layer is the single highest-leverage investment.
4. **The knowledge layer is fragmented** (JSON + ChromaDB + SQLite + markdown + PDFs). It should consolidate behind one Knowledge OS.
5. **`next_gen/` is dead weight** and should be archived/deleted.
6. **Security and secret hygiene is critical and currently broken.**

See `08_target_architecture.md` for the proposed end-state and `09_migration_plan.md` for how to get there.
