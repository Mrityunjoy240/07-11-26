# 06 — Build vs Buy Decision Record

> For every layer of the platform: **Build ourselves / Reuse (OSS behind a contract) / Buy (SaaS).** The rule: build only the intelligence layer (contracts, tools, facts, benchmark); reuse the boring; buy only what per-unit economics beat self-hosting.
>
> Aligned with `05`–`10`. Every decision is expressed as **architectural invariant → current implementation (2026) → adoption trigger for change**, so this document stays valid as implementations rotate. The decision table in §7 and the freeze rule in §8 make this the final baseline document.

---

## 1. Decision framework

| Layer | Build | Reuse (behind contract) | Buy |
|---|---|---|---|
| Contracts (Provider Fabric) | **core build** | — | — |
| Knowledge layer (facts, tools, retrieval) | **core build** | Docling + PaddleOCR (ingest); LlamaIndex = *optional library, not infrastructure* | — |
| AI Core (single agent, guardrails, verification) | **core build** | PydanticAI (`AgentRuntime`) | — |
| Provider Adapter Layer (LLM/STT/TTS) | **thin build** (one file per provider) | Sarvam SDK, provider SDKs | — |
| Voice/telephony transport | **thin build** | LiveKit Agents + Exotel SIP | Vapi/Retell (trigger only) |
| LLM model | — | — | **Yes** (always; never self-host) |
| Observability | thin build (OTel wiring) | OTel → Phoenix/OpenLIT/Logfire | — |
| Storage | — | Postgres 16 + pgvector, Redis | — |
| Vector index | — | pgvector (primary); Qdrant = scale-out path (trigger) | — |
| Admin/ops UI | — | OpenWebUI (internal only) | — |
| Eval tooling | benchmark v2.0 + conformance suites | DeepEval / Pydantic Evals / Promptfoo | — |
| Async jobs / durable execution | durable-ready logic | BackgroundTasks → Arq / Temporal (trigger) | — |

## 2. What must be BUILT (differentiators)

1. **The contracts** (`08` §1.2) — `AgentRuntime`, `LLMProvider`, `KnowledgeService`, deterministic tools, `VectorStore`, `SpeechProvider`, `VoiceGateway`, `Tracer`, `EvalStore`. The contracts are the product's nervous system and the only long-lived runtime assets. Do not hand them to a vendor.
2. **Knowledge layer** — college-specific KB lifecycle: structured fact tables (fees, eligibility, deadlines, contacts), deterministic tools, ~400-LOC hybrid retrieval (pgvector + tsvector), ingestion from mixed formats via Docling + PaddleOCR. Nobody ships a "college admissions KB" product; this is ours.
3. **AI Core** — single agent + explicit workflows, guardrails, refusal rules, deterministic verification (no LLM self-review), Bengali/English/multilingual routing. This is the product's personality; it cannot be bought.
4. **Benchmark & eval harness** — `data/benchmark/` v2.0 + one conformance suite per contract. DeepEval/Promptfoo help; the *dataset and the gates* are ours and are the hard release gate.

## 3. What must be REUSED (not differentiated, expensive to build)

1. **Agent runtime** — PydanticAI, as the initial `AgentRuntime` implementation.
2. **Vector index** — pgvector on Postgres 16. Don't build a vector index.
3. **Voice transport/telephony** — LiveKit Agents + Exotel SIP. Don't build WebRTC/SIP.
4. **Speech** — Sarvam + one alternative behind `SpeechProvider`. Don't build STT/TTS.
5. **Observability** — OTel → Phoenix/OpenLIT/Logfire behind `Tracer`. Don't build a trace UI.
6. **Ingestion** — Docling + PaddleOCR. Don't build document parsing.
7. **Admin/ops shell** — OpenWebUI (internal only). Don't build a dashboard.
8. **Web framework + storage** — FastAPI, Postgres 16, Redis.
9. **Eval tooling** — DeepEval / Pydantic Evals / Promptfoo behind `EvalStore`.
10. **Jobs** — FastAPI `BackgroundTasks` now; Arq on trigger.

## 4. What can be BOUGHT (and when)

| Component | Buy option | Threshold / note |
|---|---|---|
| LLM API | Groq (now); Anthropic/OpenAI/Gemini via `LLMProvider` | Always bought — never self-host at our scale |
| Managed voice agents | Vapi/Retell | Trigger only: < ~10K min/month AND time-to-market dominates; reverse when volume grows |
| Managed observability | LangSmith / managed OTel | Only if we won't self-host the OTel backend |

## 5. Rejected builds / buys

| Option | Why rejected |
|---|---|
| OpenAI Agents SDK / Claude Agent SDK as orchestration | Vendor lock-in; violates the `AgentRuntime` contract rule |
| Building our own vector DB | Never |
| Building our own speech-to-text / TTS | Budget/quality impossible |
| **LiteLLM as a baseline gateway** | **Rejected as baseline**: March 2026 supply-chain compromise; direct SDKs behind `LLMProvider` (llm-adapters pattern) are simpler. Gateway = adoption trigger only (`08` §10) |
| Qdrant as primary vector store | pgvector is the default (benchmarks, VB Pulse Q1 2026); Qdrant = trigger-gated scale-out path |
| Langfuse as default observability | OTel-first; Langfuse is a valid `Tracer` implementation, not the default (ops burden) |
| LlamaIndex as architectural infrastructure | Optional library at most; the architecture owns the `KnowledgeService` contract, not a retrieval framework |
| Building our own admin/RAG dashboard | Use OpenWebUI (internal only) |
| Building our own trace UI | Use an OTel backend |
| Building our own workflow/durable-execution engine | Adoption trigger only (Temporal); logic stays durable-ready |
| Buying full "college chatbot as a service" | Doesn't exist as an Indian-college-specific product; KB Q&A too domain-specific |
| Self-hosting LLMs (Llama-70B etc.) | No GPU infra; commercial latency is far better |

## 6. Effort & risk summary

| Path | Effort | Risk | Result |
|---|---|---|---|
| **Reuse-heavy (recommended)** | Medium | Low | Production platform in weeks, vendor- and framework-independent |
| Build-heavy (current state: hand-rolled everything) | High | High | We already see it: monolith, dead code, drift |
| Buy-heavy (managed everything) | Low | High | Per-minute/seat costs + loss of control; kills the "survive any vendor" goal |

**Conclusion:** the strategy is *reuse the boring, build the differentiators*. The current codebase over-built the boring parts (retrieval, telemetry, intent, pipeline) and under-built the differentiators (deterministic fee tools, eval harness, provider abstraction).

---

## 7. Final decision table

> Capability → architectural invariant → current implementation (2026) → adoption trigger for change.

| Capability | Architectural invariant | Current implementation (2026) | Adoption trigger for change |
|---|---|---|---|
| LLM access | Provider independence behind `LLMProvider`; one file per provider; no gateway baseline | Direct SDKs (Groq) | ≥2 providers in real routing/budget/rate-sharing use → gateway (Bifrost/TensorZero) |
| Agent runtime | `AgentRuntime` contract; single agent + explicit workflows; no framework in app code | PydanticAI | Conformance-tested alternative + benchmark evidence; multi-agent only on statistically significant golden-set gain |
| Knowledge & retrieval | `KnowledgeService` contract; structured-first; hybrid retrieval | Postgres fact tables + ~400-LOC hybrid (pgvector + tsvector); Docling + PaddleOCR | Retrieval quality regression vs baseline → evaluate a library *inside* the contract |
| Vector storage | Postgres primary; vectors beside facts | pgvector (HNSW) on Postgres 16 | Measured bottleneck (p99 > ~150ms at load, > ~50–100M vectors, recall regression) → Qdrant scale-out |
| Observability | OTel-first; `Tracer` contract; backend replaceable | OTel → Phoenix/OpenLIT/Logfire | Ops/feature gap in chosen backend → swap within the `Tracer` contract |
| Voice transport | `VoiceGateway` contract; <800ms budget | LiveKit Agents + Exotel SIP | < ~10K min/month AND time-to-market dominates → Vapi/Retell; reverse on growth |
| Speech | `SpeechProvider` contract; Sarvam one of many; Bengali eval set | Sarvam + one alternative | Fixed voice eval set regression → switch provider |
| Admin/ops UI | Reuse the shell; student UI separate and thin | OpenWebUI (internal only) | OpenWebUI assumptions fight us → minimal internal dashboard |
| Async jobs | Durable-ready logic; no queue baseline | FastAPI `BackgroundTasks` | > ~1,000 jobs/day, or retry/backoff/visibility needed, or > ~30s of request time → Arq |
| Durable execution | Durable-ready state machines; no engine baseline | None (Postgres state machines) | First interrupt-driven workflow needing guaranteed progress → Temporal |
| Multi-agent | Single agent baseline | Single agent | Statistically significant benchmark improvement over baseline |
| LLM model | Never self-host; buy via contract | Groq | Price/quality/latency per benchmark eval |

---

## 8. Architecture freeze & change governance

**This document completes the architecture baseline (05–10). The architecture is frozen as of this commit.**

Further architectural changes are permitted only under one of the following conditions:

1. **Benchmark evidence** — the change demonstrates a statistically significant improvement on the golden set (`data/benchmark/` v2.0), measured by the eval harness, not opinion.
2. **A measurable adoption trigger** — one of the thresholds in `08` §10 (Appendix A) is reached with measurements.
3. **Invalidated assumption** — new production evidence invalidates an architectural assumption; the evidence is documented, dated, and linked before the change proceeds.

**What this prevents:** repeated architectural rewrites every few months, framework-hopping, and introducing new framework-specific assumptions outside the contracts.

**What is NOT an architecture change (no freeze exception needed):**
- Swapping an implementation behind an existing contract, gated by that contract's conformance suite + benchmark (e.g., PydanticAI → LangGraph, pgvector → Qdrant on trigger, Sarvam → Google).
- Bug fixes, security hardening, DPDP compliance work, CI improvements.
- Contract changes remain versioned breaking changes reviewed like product decisions (`08` §1.2).

> From this point onward, changes flow through the documented contracts and adoption triggers — never by reintroducing framework-specific assumptions into the architecture.
