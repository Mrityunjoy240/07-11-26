# 05 — Industry Research & Evidence Log

> Consolidated, dated findings from the current (2026) ecosystem for each layer of the platform. Sources: vendor docs, benchmark announcements, ecosystem surveys, incident reports. This is a **living evidence log**: conclusions are re-examined, not defended.

## How to read this document

Every finding is classified one of two ways:

- **Invariant conclusion** — a property of the domain or a design principle established by evidence, expected to remain true for years. Invariants are owned by `08_target_architecture.md` and changing one is a versioned breaking change.
- **Implementation conclusion** — a current best pick for a layer. Replaceable when a better option appears; swaps are routine, gated by the conformance suite + benchmark (`08` §10, Adoption Triggers).

This revision **rejects several endorsements from the first version of this document** (see §8, "Corrections"). The earlier pass recommended frameworks before we had enough production evidence; the 2026 evidence points the other way.

---

## 1. Agent architecture & frameworks

**Evidence:**
- **Anthropic, "Building Effective Agents" (Dec 2024)** — simplest solution that works; start with a single agent (or a plain LLM call with retrieval), not a framework; use *workflows* when the decision tree is knowable and *agents* when routing is unpredictable; "optimizing single LLM calls with retrieval is usually enough."
- **Anthropic follow-up (Jan 2026)** — single agent first; prefer prompt additions over rebuilds; orchestrator-worker only under real pressure; don't build nested loops; evaluate often.
- **OpenAI, context engineering (Dec 2025)** — Write / Select / Compress / Isolate; **"traditional RAG is increasingly an anti-pattern"**; the context window should be the smallest working set for each step.
- **Uber + LangGraph (2026)** — 5,000 developers, ~21,000 engineer-hours saved, +10% test coverage, uReview analyzes 90%+ of ~65,000 weekly diffs. *Proves LangGraph at hyperscale; does not mean we need it.*
- **Microsoft Build (2026)** — Foundry Agent Service; the **agent harness is the flex point** (runtimes are swappable); tracing → eval closed loop; agent optimizer.
- **Google ADK + A2A (2026)** — orchestrator-worker pattern, distributed agents as services, judge agents; long-running agents as **durable state machines**.
- **AWS Bedrock AgentCore (2026)** — AgentOps with four pillars (governance/security, build/ops, evaluation, observability); online evaluations and A/B; framework-agnostic.
- **PydanticAI + Qualio case study (Jul 2026)** — regulated industry; chose PydanticAI over LangGraph/AG2/Bedrock Agents because **iteration speed wins**; gates every deploy on 160 test cases + 300 evaluations; human-in-the-loop is cheap.
- **LLM self-correction does not work (ICLR 2024 Huang et al.; ICLR 2025 Stechly et al.; Kamoi et al. survey; Tyen et al., ACL 2024)** — LLMs cannot reliably self-correct reasoning without external feedback; self-critique often *degrades* performance; LLMs are poor at even locating their own errors.

**Invariant conclusions**
1. **Single agent + explicit workflows**, not a multi-agent pipeline. Routed, deterministic business decisions are *workflows* (tools), not agents.
2. **No LLM self-review "verify" stage.** Verification is deterministic (guardrails + tests) or it doesn't happen.
3. **Runtimes are a flex point.** The application depends on an `AgentRuntime` contract; the framework underneath is an implementation.
4. **Context = smallest working set.** Fetch only what each step needs; retrieval is a means, not a product.

**Implementation conclusion**
- `AgentRuntime` implementation (2026): **PydanticAI** (fast iteration, typed tools, cheap human-in-loop). LangGraph and Google ADK are *conformance-tested candidates*, adopted only if benchmark evidence says so (Adoption Trigger: multi-agent/runtime, `08` §10). Vendor SDKs (OpenAI/Claude) rejected as lock-in.

## 2. Vector storage

**Evidence:**
- **pgvector + pgvectorscale** — 471 QPS vs Qdrant 41 QPS at 99% recall on 50M vectors (pgvectorscale benchmark).
- **Production run** — 340M chunks on Postgres 17 + pgvector 0.9 at p99 <15ms, under 1/5 the cost of a comparable Pinecone deployment.
- **Vector Benchmark Pulse (VB Pulse), Q1 2026** — standalone vector-DB category *lost* market share; **hybrid-retrieval intent tripled (10.3% → 33.3%)**; teams consolidating onto custom stacks up 35.6%.
- Qdrant publishes postgres→Qdrant migration guides — the industry already treats Postgres-with-vectors as the mainstream default.

**Invariant conclusions**
1. **Postgres is the primary store; vectors live beside the facts** (KB metadata, sessions, structured facts, vectors in one system). No standalone vector service by default.
2. **Hybrid retrieval (dense + sparse) is the standard**, not pure vector similarity.

**Implementation conclusion**
- Vector store (2026): **pgvector (HNSW) on Postgres 16**, behind the `VectorStore` contract. **Qdrant is the documented scale-out path only** — adopted when a measured pgvector bottleneck triggers (see `08` §10). Chroma remains dev/test-only.

## 3. LLM gateways

**Evidence:**
- **LiteLLM, March 2026 supply-chain compromise** — package compromised, credential-exfiltration class incident; erased "cheap gateway" calculus.
- **llm-adapters (2026)** — the anti-gateway pattern: ~2 deps, <2K LOC, one auditable file per provider, hash-pinned.
- **Bifrost (Go)** — ~11µs per call vs LiteLLM ~8ms; gateways solve a problem we may not have.
- **Maxim (2026)** — "most teams use 20% of LiteLLM."

**Invariant conclusion**
- **Direct SDKs behind an `LLMProvider` contract** (one file per provider, mirroring llm-adapters). No shared gateway in the default path.

**Implementation conclusion**
- A gateway (Bifrost, TensorZero) is an **Adoption Trigger**, not a default (`08` §10): adopted only when ≥2 providers are in real routing/budget/rate-sharing use.

## 4. Observability & LLMOps

**Evidence:**
- **OpenTelemetry GenAI SIG** — vendor-neutral standard for LLM span semantics; tracing/eval closed loop is the 2026 norm (AWS AgentCore, Microsoft Foundry both center on it).
- **Langfuse** — strong features but self-hosting it drags in ClickHouse + Postgres + Redis; heavy ops for our scale.
- **Phoenix / OpenLIT / Logfire** — OTel-native backends; single-store, lower ops burden.

**Invariant conclusion**
- **OTel-based tracing is the invariant** — every request emits standard spans; the backend is replaceable.

**Implementation conclusion**
- Trace backend (2026): **Phoenix or OpenLIT/Logfire**, whatever the spike favors. Langfuse remains a valid `Tracer` implementation, not the default.

## 5. Evaluation

**Evidence:**
- **Pydantic Evals / DeepEval / Ragas / Promptfoo** — all Apache/MIT-licensed, CI-friendly; **DeepEval** is pytest-native (fits our 44-file pytest suite); **Promptfoo** adds A/B + red-teaming; **Ragas** adds dataset-style metrics.
- **Qualio** gates every deploy on 160 test cases + 300 evaluations — the production pattern.
- **Production-trace sampling with drift detection** — AWS AgentCore / Microsoft Foundry pattern: evaluate real traffic, not just goldens.

**Invariant conclusions**
1. **The golden benchmark (`data/benchmark/` v2.0) is the hard release gate.** The dataset is our crown jewel; tools (DeepEval/Promptfoo) are interchangeable.
2. **Eval loop = CI gate + production-trace sampling + drift detection.** Vendor-switch drills are CI jobs.

**Implementation conclusion**
- 2026 harness: **Pydantic Evals / DeepEval** in CI, **Promptfoo** for A/B/red-team, benchmark v2.0 as the gate, production-trace sampling for drift.

## 6. Voice & telephony

**Evidence:**
- **LiveKit + Exotel (reference architecture)** — Indian PSTN via Exotel AgentStream, **<20ms media latency**, SIP bridge + dispatch rules, **<800ms end-to-end** voice-agent budget.
- **Prodinit** — self-hosted LiveKit at **90K+ calls/month**; the pipeline is a *runtime config value*, not code.
- **Vapi/Retell** — managed; ~$0.05–0.10/min; cheapest to launch, expensive above ~10–50K min/month; low control.
- Our current Twilio↔LiveKit bridge is broken (`voice.py:21` import crash); Twilio is a trial account.

**Invariant conclusions**
1. **Voice transport is behind a `VoiceGateway` contract** (WebRTC/SIP); the AI Core serves text and voice through the same single agent.
2. **<800ms end-to-end latency budget** for voice.

**Implementation conclusions**
- 2026: **LiveKit Agents** (transport) + **Exotel** (Indian PSTN via SIP). Sarvam = default STT/TTS. Managed platforms only on trigger (<~10K min/month AND time-to-market dominates).

## 7. Speech (STT/TTS)

**Evidence:**
- **Sarvam Bulbul** — best Indic TTS in our eval (Bengali ~4.3 MOS); Sarvam is an LLM company (sarvam.ai); **no open-weight license** — provider independence still required.
- **Deepgram Nova 3** — Hindi language detection broken in testing.
- **Canary-1B** — NVIDIA RIVA ASR/AST, English + Hindi only, **no Bengali**; STT fallback, not an LLM or synthetic-data generator.

**Invariant conclusion**
- **STT/TTS behind `SpeechProvider` contracts**; Sarvam is one of many, never the only one. **Bengali is the hard eval language** (fixed eval set).

**Implementation conclusion**
- 2026: **Sarvam** default (STT + TTS); one alternative registered (Google/Azure/Deepgram/ElevenLabs). Canary-1B only as STT fallback.

## 8. Memory & conversation state

**Evidence:**
- **Graphiti (Neo4j)** ~63.8% vs **Mem0** ~49.0% on LongMemEval (2026); both are heavy machinery for a college-Q&A assistant.
- No product requirement for user-specific personalization exists today.

**Invariant conclusion**
- **Structured short-term context + a fact store** is the memory layer; **no episodic/long-term memory until personalization is a product requirement** (Adoption Trigger).

**Implementation conclusion**
- 2026: Postgres sessions + Redis cache. Mem0-class memory deferred by trigger.

## 9. Background jobs & durable execution

**Evidence:**
- **Arq vs Dramatiq vs Celery vs RQ** — Arq is the lightest async/Redis-native option for a FastAPI codebase.
- **Temporal–LangGraph plugin (Jul 2026)** — explicitly: **"LangGraph checkpoints are not durable execution."** Durable execution is a first-class runtime concern (Temporal, Google durable state machines).
- Anthropic/Google long-running-agent guidance — long waits are state machines, not held processes.

**Invariant conclusions**
1. **Business logic is durable-ready by construction**: explicit state machines persisted in Postgres; any wait for an external event (human approval, async doc review, phone callback) **yields a stored intent**, never holds a process.
2. **No queue and no durable-execution engine are defaults** — they are Adoption Triggers (`08` §10), not rules.

**Implementation conclusion**
- 2026: FastAPI `BackgroundTasks`; **Arq** when the trigger fires; **Temporal** when the first interrupt-driven workflow demands guaranteed progress.

## 10. Admin / ops UI

**Evidence:**
- **OpenWebUI (MIT)** — SvelteKit + FastAPI + Postgres + Redis; pgvector factory default with hybrid search; Docling/Tika ingest sidecars; MCP; SSO/RBAC; OTel. A mature, self-hostable admin/RAG shell.

**Invariant conclusions**
1. **Admin/ops shell is reused, not built** (don't build the boring dashboard).
2. **Student-facing UI is separate and thin** — OpenWebUI's auth/session/UX assumptions must never leak into the product surface.

**Implementation conclusion**
- 2026: **OpenWebUI** as the internal admin/ops shell only; student UI is our own thin client. Fallback to a minimal internal dashboard if OpenWebUI's assumptions fight us.

## 11. AuthZ / security (context)

- OSS options verified: **OpenFGA** (CNCF), **Cerbos + OPA**, embedded **Oso + Casbin**. Rule: no auth server build; integrate when multi-tenant admin is actually required (not v1).

---

## 8. Corrections to the first version of this document

| Earlier claim (rejected) | What the evidence says now |
|---|---|
| Use LlamaIndex for the retrieval/Knowledge OS layer | Retrieval is a ~400-LOC deterministic function (pgvector + tsvector), not a subsystem. LlamaIndex adds abstraction without capability at our scale; "traditional RAG is increasingly an anti-pattern" (OpenAI). |
| Use LangGraph for orchestration; wrap `src/pipeline` later | Single agent + explicit workflows first (Anthropic). LangGraph is proven at Uber scale — not ours. It becomes a conformance-tested `AgentRuntime` implementation, gated by benchmark. |
| Standardize on LiteLLM as the gateway | Rejected: March 2026 supply-chain compromise. Direct SDKs behind `LLMProvider` (llm-adapters pattern); gateway is an Adoption Trigger. |
| Migrate to Qdrant (primary) or pgvector | pgvector is the default (benchmarks + VB Pulse Q1 2026). Qdrant = scale-out path, trigger-gated. |
| Langfuse self-hosted as primary LLMOps | Rejected as default (ClickHouse + Postgres + Redis ops burden). OTel → Phoenix/OpenLIT/Logfire; Langfuse remains an alternative `Tracer`. |
| "add Mem0-class long-term memory only when personalization is a product requirement" | Kept — deferral stays, now formalized as an Adoption Trigger. |
| LiveKit Agents or Pipecat (spike) | LiveKit confirmed; add **Exotel** for Indian PSTN (not Twilio trial). Prodinit shows 90K+ calls/month self-hosted. |
| STT/TTS: "test Bengali quality against all candidates" | Evidence sharpened: Sarvam Bulbul best Indic TTS; Deepgram Nova 3 Hindi detection broken; Canary-1B has no Bengali. |

---

## 9. Key takeaways

**Invariants** (design properties, not products): single agent + explicit workflows; no LLM self-review; structured-first knowledge with deterministic business tools; provider independence behind contracts; benchmark as the hard release gate; OTel-based observability; contracts-first boundaries; durable-ready business logic.

**Implementations** (2026 picks): PydanticAI · pgvector on Postgres 16 · OpenWebUI (admin only) · FastAPI · Phoenix/OpenLIT · LiveKit + Exotel · Sarvam · Docling + PaddleOCR · DeepEval/Promptfoo · Arq/Temporal only on trigger.

> The long-lived assets are the **contracts and the domain data** — `AgentRuntime`, `KnowledgeService`, `LLMProvider`, the benchmark, the fee/eligibility rules. Frameworks are disposable. This document will be wrong about *implementations* in a few years; it should stay right about *invariants*.
