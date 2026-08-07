# 07 — Recommended Stack (2026)

> The concrete technology stack for the target architecture, organized into two lists that must never be confused:
>
> **Architectural invariants** — the contracts and design principles the platform depends on; expected to stay stable for years. Changing an invariant is a versioned breaking change.
>
> **Implementation choices** — the 2026 best picks for each contract; replaceable without touching the architecture. If PydanticAI is superseded in 2029, or pgvector is out-performed, this document stays valid and only the implementation column changes.

The contract definitions live in `08_target_architecture.md` §2; the thresholds that govern swapping implementations live in `08` §10 (Adoption Triggers). This document is the "what we run today" view.

---

## 1. Stack overview

```
PRODUCT SURFACE (ours)          student-facing UI (thin client) · voice (LiveKit + Exotel SIP)
API + APP (FastAPI)             single agent (AgentRuntime) · deterministic guardrails
CONTRACTS (Provider Fabric)     LLMProvider · AgentRuntime · EmbeddingProvider · VectorStore
                                · KnowledgeService · SpeechProvider · VoiceGateway · Tracer · EvalStore
KNOWLEDGE LAYER (ours)          structured facts (Postgres) + deterministic tools + ~400-LOC hybrid retrieval
OPS / ADMIN (reuse)             OpenWebUI (internal only)
INFRA (reuse)                   Postgres 16 + pgvector · Redis · OTel → Phoenix/OpenLIT ·
                                Docling/PaddleOCR · Docker Compose → Cloud Run
```

## 2. Contract → current implementation

Every contract below is an **invariant**. The implementation column is the 2026 choice. "Conformance gate" = what must pass before any implementation swap is accepted.

| Contract | Responsibility | Current implementation (2026) | Alternatives considered | Conformance gate |
|---|---|---|---|---|
| **LLMProvider** | chat completion, streaming, structured output | Groq `llama-3.3-70b-versatile` (small model for intent/guards) via **direct SDK, one file per provider** (llm-adapters pattern) | OpenAI / Anthropic / Gemini via same contract; Bifrost/TensorZero gateway only on trigger | Switch drill: provider change = config; benchmark ≤2% delta |
| **AgentRuntime** | turn-taking, tool dispatch, streaming, interrupts | **PydanticAI** | LangGraph, Google ADK (conformance-tested candidates); OpenAI/Claude SDKs rejected (lock-in) | Runtime conformance suite + benchmark ≤2% |
| **KnowledgeService** | structured facts + hybrid retrieval | Postgres fact tables + **~400-LOC hybrid retrieval** (pgvector + tsvector); **Docling + PaddleOCR** ingest | LlamaIndex (rejected: over-abstraction) | KB eval gate; retrieval parity drill |
| **FeeCalculatorTool / EligibilityTool / DeadlineTool / ContactsTool** | deterministic computation from data | Typed functions + Postgres fact tables | — (never LLM free-text on financial/eligibility answers) | Golden-set regression |
| **NormalizerService** | input normalization | Existing normalizer logic (retained domain asset) | — | Unit tests |
| **EmbeddingProvider** | embeddings | `all-MiniLM-L6-v2` now → evaluate **`bge-m3` / `multilingual-e5-large`** for Bengali at eval time | Cohere (cost/latency) | Embedding quality eval on the Bengali set |
| **VectorStore** | vector storage/query | **pgvector (HNSW) on Postgres 16** | Qdrant = documented scale-out path (trigger-gated); Milvus rejected (overkill) | Retrieval parity on switch drill |
| **SpeechProvider (STT/TTS)** | speech-to-text, text-to-speech | **Sarvam** default (Indic); one alternative registered (Google/Azure/Deepgram/ElevenLabs); Canary-1B = STT fallback only | Deepgram Nova 3 rejected for Hindi detection; Canary-1B rejected for Bengali | Fixed Bengali voice eval set |
| **VoiceGateway** | transport + telephony | **LiveKit Agents**; **Exotel SIP** for Indian PSTN | Pipecat; Vapi/Retell (buy only on trigger) | <800ms end-to-end; live call demo |
| **Tracer** | OTel spans → backend | **OTel → Phoenix / OpenLIT / Logfire** (spike to pick) | Langfuse (valid alternative, heavier ops); LangSmith rejected (SaaS-only) | Every request has a trace |
| **EvalStore / BenchmarkRunner** | eval + release gate | **Pydantic Evals / DeepEval** in CI; **Promptfoo** A/B + red-team; **benchmark v2.0** as the gate; production-trace sampling + drift detection | Ragas metrics | CI gate green on every PR |
| **JobRunner** | async jobs | **FastAPI BackgroundTasks** (in-process) | **Arq** (adopt on trigger) | — |
| **WorkflowRuntime** (durable execution) | long-lived state machines | **None** (durable-ready logic in Postgres) | **Temporal** (adopt on trigger) | — |

## 3. Per-layer notes

### 3.1 Language / runtime
- **Python 3.12+**, **FastAPI** (framework of record in both generations — keep). Async everywhere; SQLAlchemy 2 + asyncpg.
- Pydantic v2 for typed contracts at boundaries. **No framework type leaks past a contract** — the contracts are our own Protocol/dataclass definitions.

### 3.2 LLM access
- Direct SDKs behind `LLMProvider`; one auditable file per provider. **No LiteLLM** (supply-chain incident, `05` §3). Model name in config, never hardcoded.
- Intent/guard model (small, fast) vs answer model (large) split is a routing concern inside the agent, not a separate pipeline stage.

### 3.3 Knowledge & retrieval
- **Structured-first**: fees, eligibility, deadlines, contacts live in Postgres fact tables, read by deterministic tools. Retrieval is only for the unstructured remainder.
- Hybrid retrieval: pgvector (dense) + tsvector (sparse) in one ~400-LOC module. No `combined_kb.json` prompt dump — retrieval-only answers.

### 3.4 Orchestration
- **Single agent** (PydanticAI) that calls deterministic tools. No multi-stage pipeline, no capability registry, no manifests, no blame/dependency tooling.

### 3.5 Voice
- **LiveKit Agents** + **Exotel SIP** (Indian PSTN). <800ms end-to-end budget. Sarvam STT/TTS default; the pipeline is a config value, not code (Prodinit pattern, `05` §6).

### 3.6 Observability
- **OTel spans on every request** → Phoenix/OpenLIT/Logfire. Kill the 5-way bespoke telemetry; keep a thin legacy exporter only during migration (`09`).

### 3.7 Evaluation
- Pydantic Evals/DeepEval (unit + retrieval + guardrails) in CI; Promptfoo for A/B + red-team; benchmark v2.0 as the hard gate; production-trace sampling + drift detection.

### 3.8 Storage / sessions
- **Postgres 16** (single instance): conversations, messages, KB metadata, fact tables, eval results, vectors. **Redis**: rate limit, session cache, TTS cache. SQLite/Chroma only in dev.

### 3.9 Security / ops
- All endpoints authenticated (API key/JWT with rotation); secrets manager; `.env` out of git.
- **DPDP compliance from day one**: retention, consent, PII minimization, `tenant_id` in every table.
- Single VPS **Docker Compose** for parity with prod; GitHub Actions CI/CD (fix missing root `requirements.txt`).
- OpenWebUI deployed as the internal admin/ops shell (RAG management, benchmark review, trace inspection) — **never the student-facing UI**.

## 4. What we keep vs change (summary)

| Keep (domain assets, invariants) | Change (implementations/plumbing) |
|---|---|
| Benchmark v2.0 (`data/benchmark/`) as the gate | Pipeline stages, registry/manifests, blame/dependency tooling → delete |
| KB data, normalizer logic, fee/eligibility rules | `combined_kb.json` prompt dump → retrieval-only |
| 44-file `src` pytest suite | Bespoke 5-way telemetry → OTel |
| Sarvam provider | Twilio↔LiveKit bridge → LiveKit + Exotel SIP |
| FastAPI + Postgres direction | Chroma prod usage → pgvector; SQLite → dev only |
| OTel wiring (`src/observability`) | LiteLLM intent → direct SDKs behind `LLMProvider` |
| | `src/dual/runner.py` → gateway traffic split, then delete |

## 5. Non-negotiable rules

1. Never build what a maintained OSS component already does well (vector index, trace UI, telephony, queue, workflow engine, auth server).
2. Never build for a multi-tenant future (no multi-tenancy, no scale-out, no fleet machinery).
3. The benchmark is the gate. A change that regresses the golden set does not ship.

> Implementation swaps are routine and expected. The conformance suite + benchmark make them cheap. That is the point of contracts-first.
