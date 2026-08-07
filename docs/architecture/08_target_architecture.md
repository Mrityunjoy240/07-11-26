# 08 — Target Architecture

> The desired end-state. Two parts:
>
> **§1–§2 Architectural invariants** — stable contracts and design principles; expected to remain true for years. Changing an invariant is a versioned breaking change.
>
> **§3–§6 Implementation choices** — the 2026 bindings for each contract, replaceable without changing the architecture.
>
> **§10 Adoption Triggers** — the measurable thresholds that turn "currently not using X" into "now using X." No absolute never/always; every future architectural decision is evidence-driven.

---

## 1. Architectural invariants

### 1.1 Design principles
1. **Single agent + explicit workflows.** One agent (via the `AgentRuntime` contract) handles all interactions. Deterministic business decisions (fees, eligibility, deadlines) are *workflows* expressed as tools, not agents.
2. **Structured-first knowledge.** Facts live in Postgres fact tables and are read by deterministic tools; retrieval is used only for the unstructured remainder.
3. **Deterministic business tools.** Fee/eligibility/deadline answers are computed from data, never free-texted by an LLM.
4. **Deterministic verification only.** No LLM self-review "verify" stage (LLMs cannot reliably self-correct — `05` §1). Guardrails + tests do the verification.
5. **Provider independence.** Every provider sits behind a contract in the Provider Fabric; a provider swap is a config change, not a code change. The switch drill is a hard release gate.
6. **Benchmark as the release gate.** `data/benchmark/` v2.0 + the conformance suite gate every change.
7. **OTel-based observability.** Every request emits standard spans; the trace backend is replaceable.
8. **Contracts-first boundaries.** No framework type leaks past a contract. Contracts are our own Protocol/dataclass definitions, semver-versioned, each with a conformance suite.
9. **Durable-ready business logic.** Explicit state machines persisted in Postgres; any wait for an external event yields a stored intent, never holds a process.

### 1.2 Stable contracts (the long-lived assets)

| Contract | Owns | Stable since |
|---|---|---|
| `AgentRuntime` | turn-taking, tool dispatch, streaming, interrupts | v1 |
| `LLMProvider` | chat completion, streaming, structured output | v1 |
| `KnowledgeService` | fact tables + hybrid retrieval | v1 |
| `FeeCalculatorTool` / `EligibilityTool` / `DeadlineTool` / `ContactsTool` | deterministic business computation | v1 |
| `NormalizerService` | input normalization | v1 |
| `EmbeddingProvider` | embeddings | v1 |
| `VectorStore` | vector storage/query | v1 |
| `SpeechProvider` (STT/TTS) | speech | v1 |
| `VoiceGateway` | transport + telephony | v1 |
| `Tracer` | OTel span export | v1 |
| `EvalStore` / `BenchmarkRunner` | evaluation + release gate | v1 |

**Stability rules:** a contract change = versioned breaking change, reviewed like a product decision. An implementation swap behind a contract = routine, gated only by that contract's conformance suite + benchmark.

---

## 2. Implementation matrix (2026)

The bindings chosen today. Swap any row without touching the architecture.

| Contract / layer | 2026 implementation |
|---|---|
| `AgentRuntime` | PydanticAI |
| `LLMProvider` | Groq (direct SDK), one file per provider |
| Knowledge + retrieval | Postgres fact tables + ~400-LOC hybrid (pgvector + tsvector), Docling + PaddleOCR ingest |
| `VectorStore` | pgvector (HNSW) on Postgres 16 |
| `EmbeddingProvider` | `all-MiniLM-L6-v2` → `bge-m3`/`multilingual-e5-large` at eval time |
| `SpeechProvider` | Sarvam default + one alternative |
| `VoiceGateway` | LiveKit Agents + Exotel SIP |
| `Tracer` | OTel → Phoenix/OpenLIT/Logfire |
| `EvalStore`/`BenchmarkRunner` | Pydantic Evals / DeepEval + Promptfoo + benchmark v2.0 |
| Web framework | FastAPI |
| Admin/ops shell | OpenWebUI (internal only) |
| Async jobs | FastAPI BackgroundTasks (Arq on trigger) |
| Durable execution | none (Temporal on trigger) |
| Deployment | single VPS Docker Compose → Fly/Railway/Cloud Run |

---

## 3. Layered diagram

```
┌───────────────────────────────────────────────────────────────────┐
│ 1. PRODUCT SURFACE (ours)                                          │
│    Student-facing UI (thin client) · Voice (LiveKit + Exotel SIP)  │
├───────────────────────────────────────────────────────────────────┤
│ 2. API + APP (FastAPI)                                             │
│    AgentRuntime (PydanticAI) — single agent, tool-calling          │
│    Deterministic guardrails (input → refusal → citation → response)│
├───────────────────────────────────────────────────────────────────┤
│ 3. CONTRACTS (Provider Fabric)                                     │
│    LLMProvider · AgentRuntime · EmbeddingProvider · VectorStore    │
│    · KnowledgeService · SpeechProvider · VoiceGateway · Tracer ·   │
│    EvalStore                                                       │
├───────────────────────────────────────────────────────────────────┤
│ 4. KNOWLEDGE LAYER (ours)                                          │
│    Structured facts (Postgres): fees, eligibility, deadlines,      │
│    contacts · deterministic tools · hybrid retrieval (~400 LOC)    │
├───────────────────────────────────────────────────────────────────┤
│ 5. OPS / ADMIN (reuse, internal only)                              │
│    OpenWebUI — RAG management · benchmark review · trace inspection│
├───────────────────────────────────────────────────────────────────┤
│ 6. INFRA (reuse)                                                   │
│    Postgres 16 (+pgvector) · Redis · OTel → Phoenix/OpenLIT        │
│    · Docling/PaddleOCR sidecars · Docker Compose → Cloud Run       │
└───────────────────────────────────────────────────────────────────┘
```

Classification: **ours** = layers 1, 2, 4 (intelligence: agent, tools, facts, guardrails, benchmark). **Reuse** = layers 5, 6 and every implementation behind a contract in layer 3. **Buy** = LLM API itself (always; never self-host at our scale).

---

## 4. Data flow (happy path, text)

```
User → UI / Voice → API
  → guardrails (input validation, refusal, DPDP checks)
  → AgentRuntime.turn()
      → known-fact query?  → deterministic tools (FeeCalculatorTool, EligibilityTool, …) → facts
      → open query?        → KnowledgeService hybrid retrieval (pgvector + tsvector) → top-k
      → LLMProvider composes answer with citations (tool-calling)
  → deterministic verification (citation check, sensitivity, refusal) — NOT LLM self-review
  → response (text, or TTS-ready for voice)
  → OTel trace; Postgres session write
```

There is no 6-stage pipeline. The agent + deterministic tools + deterministic verification *is* the pipeline. Routing to "fact query vs open query" happens inside the agent via tool selection.

## 5. Voice flow (happy path)

```
Phone → Exotel SIP → LiveKit session → SpeechProvider.STT (Sarvam, Indic)
  → API → AgentRuntime (same single agent as text)
  → SpeechProvider.TTS (Sarvam, language-aware) → speaker
Transport-agnostic: text (REST/WS) and voice (LiveKit/SIP) hit the same agent.
Latency budget: <800ms end-to-end; Exotel AgentStream <20ms media.
```

## 6. Provider independence guarantee

- **LLM**: `LLMProvider` config key. Groq → OpenAI = one env var; benchmark ≤2% delta = pass.
- **Agent runtime**: `AgentRuntime` contract + conformance suite. PydanticAI → LangGraph/ADK = suite + benchmark gate.
- **Vector store**: `VectorStore` contract; pgvector ↔ Qdrant parity drill.
- **STT/TTS**: `SpeechProvider` contract; Sarvam → Google = config.
- **Voice transport**: `VoiceGateway` contract; LiveKit ↔ Pipecat interchangeable.
- **Rule**: any provider disappearing = config/implementation swap, not an architecture change.

---

## 7. Non-goals for v1

- No multi-tenant, no full SSO/auth server, no knowledge-graph memory, no self-hosted LLMs, no k8s, no horizontal scale-out (single Postgres + single VPS is fine).
- **No queue, no durable-execution engine, no dedicated vector service, no LLM gateway, no multi-agent** until an Adoption Trigger fires (§10).
- No student-facing functionality inside OpenWebUI (admin/ops shell only).

---

## 8. Acceptance criteria

1. `pipeline_mode` and the 6-stage pipeline are gone; the single agent serves production behind a 5%→100% canary (`09`).
2. **Benchmark v2.0 gate green on every PR**; conformance suite green for every contract.
3. **Switch drill green in CI before production cutover**: LLM provider swap ≤2% delta; TTS provider swap works; vector store parity; agent-runtime swap passes conformance (run in CI).
4. 100% of `/qa/*`, conversation, voice, and admin endpoints authenticated; zero secrets in repo.
5. pgvector serves production retrieval; Qdrant/queue/durable-execution/gateway not deployed (no trigger fired).
6. DPDP controls live: retention, consent, PII minimization, `tenant_id` everywhere.
7. Voice: live call via LiveKit + Exotel SIP, Sarvam default, <800ms budget, Bengali eval set.
8. OTel trace on every request → Phoenix/OpenLIT/Logfire; no JSONL-only telemetry.
9. OpenWebUI runs as the internal admin shell; student UI is separate and thin.
10. CI runs unit + eval + integration; root `requirements.txt` fixed.

---

## 9. What is deliberately NOT built

- WebRTC / SIP / telephony (LiveKit + Exotel)
- Vector index (pgvector; Qdrant on trigger)
- Speech engines (Sarvam + alternatives)
- Trace UI (Phoenix/OpenLIT/Logfire)
- LLM gateway (direct SDKs; gateway on trigger)
- Message queue (BackgroundTasks; Arq on trigger)
- Auth server (app-level auth; OpenFGA/Cerbos only if multi-tenant admin arrives)
- Workflow/durable-execution engine (Temporal on trigger)
- Admin/RAG dashboard (OpenWebUI)
- Multi-agent orchestration (single agent; multi-agent on benchmark evidence)

---

## 10. Appendix A — Adoption Triggers

Adoption is **evidence-driven, not opinion-driven**. Each row: the measurable threshold that justifies adopting the listed technology, and what we run in the meantime. Triggers are revisited when measurements say so; none of these are "never," none are "always."

| Technology | Adopt when (measurable trigger) | While inactive |
|---|---|---|
| **Queue (Arq)** | Sustained async workload > ~1,000 jobs/day, OR retry/backoff/visibility becomes a requirement, OR background work consistently > ~30s of request time | FastAPI `BackgroundTasks` (fire-and-forget) |
| **Durable execution (Temporal)** | First interrupt-driven workflow that outlives a process and needs guaranteed progress (human approval, async doc review, phone callback) | Durable-ready state machines in Postgres; waits yield stored intents |
| **Dedicated vector service (Qdrant)** | Measured pgvector bottleneck: retrieval p99 > ~150ms at load, OR > ~50–100M vectors, OR hybrid recall regression vs baseline | pgvector HNSW on Postgres 16 (proven to 340M chunks, p99 <15ms) |
| **LLM gateway (Bifrost/TensorZero)** | ≥2 providers in real routing/budget/rate-sharing use (not just failover config) | Direct SDKs behind `LLMProvider`, one file per provider |
| **Multi-agent** | Benchmark demonstrates a **statistically significant** improvement over the single-agent baseline on the golden set | Single agent + explicit workflows |
| **Managed voice (Vapi/Retell)** | Only if < ~10K min/month AND time-to-market dominates; reverse when volume grows | Self-hosted LiveKit + Exotel (Prodinit: 90K+ calls/month) |
| **Long-term memory (Mem0-class)** | User-specific personalization becomes a product requirement | Structured short-term context + fact store |
| **Horizontal scale-out / k8s / fleet machinery** | Measured single-VPS saturation with headroom gone | Single VPS Docker Compose → Fly/Railway/Cloud Run |

**Standing rule:** no adoption without a measured trigger. Every adoption becomes a new conformance-tested implementation, never a bypass of a contract.
