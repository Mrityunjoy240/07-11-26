# 09 — Migration Plan

> Incremental, risk-controlled path from today (legacy monolith in production + `src/` in shadow) to the target architecture (`08_target_architecture.md`). No big-bang. Four phases, each with a **ship**, an **exit criteria**, and a **rollback**.

**Two kinds of work, kept separate:**
- **Invariant protection** (must be true in every phase): contracts-first boundaries, benchmark as the gate, provider independence, deterministic verification, OTel, DPDP. These are never negotiated by sequencing.
- **Implementation swaps** (the phase work): which concrete components run and which plumbing is deleted.

**A key difference from the earlier 8-phase plan:** we are **deleting** the pipeline layers (`src/pipeline` stages, capability registry/manifests, blame/dependency tooling, `src/dual/runner.py`), not promoting them. That is why this collapses to four phases. The domain assets (benchmark v2.0, KB data, normalizer, fee/eligibility rules) are retained throughout — they are the point of the migration.

---

## Phase A — Stop the bleeding (week 0)

| Task | Detail |
|---|---|
| Freeze working tree | Commit or stash all uncommitted work — **198 paths at risk** (`git status`); last commit `3dec397` |
| Rotate secrets | `SARVAM_TOOL_API_TOKEN`, JWT secret, any keys in `.env`; ensure `.env` is git-ignored; remove hardcoded `admin/admin` JWT |
| CI baseline | Create root `requirements.txt` (missing today); make `.github/workflows/ci.yml` actually build |
| Secure every endpoint | Auth on `/qa/*`, conversations, `/voice/call-me`, admin — all currently unauthenticated |
| Stop dead code loading | `fee_engine` calls, `intent_classifier`, query cache — stop loading at runtime; keep files for reference |
| Guard LiveKit import | `voice.py:21` unguarded import crashes `/voice/*`; guard or feature-flag |
| Fix double SAFEPOINT + triple `_init_sarvam` | Consolidate (`qa.py:141-147`, `groq_service.py:6377-6378`) |
| Backup | Snapshot DB + Chroma before any code change |
| Archive | Freeze `next_gen/`; move audit scripts/logs to `archive/` |

**Exit:** clean tree, CI green on master, secrets rotated, all endpoints authenticated, backup exists.
**Rollback:** restore snapshot.

## Phase B — Serve from the new shape (weeks 1–4)

| Task | Detail |
|---|---|
| Define contracts first | `AgentRuntime`, `LLMProvider`, `KnowledgeService`, deterministic tools, `VectorStore`, `Tracer`, `EvalStore` — our own typed definitions + conformance suite (`08` §1.2). No framework types at boundaries |
| Build the minimal serving path | Single agent (PydanticAI) + deterministic fee/eligibility/deadline tools + structured facts in Postgres + ~400-LOC hybrid retrieval (pgvector + tsvector) + deterministic guardrails |
| Retire pipeline layers | Registry/manifests, blame/dependency tooling, `src/dual/runner.py` — **delete, don't promote**, as the new path bypasses them |
| Remove prompt dump | `combined_kb.json` (~8,700 entries) out of prompts; retrieval-only answers |
| Canary | 5% live traffic on the new path → widen on parity; legacy stays as rollback target |
| Parity gate | **Benchmark v2.0, ≤2% delta vs legacy baseline** before widening beyond canary |
| True streaming | Replace word-replay fake streaming (0.02s sleeps) |

**Exit:** new path serves canary with parity pass; pipeline layers deleted; eval report in repo.
**Rollback:** flip `pipeline_mode` back to `legacy` (single switch) — legacy remains live through the phase.

## Phase C — Data plane, evals, observability (weeks 4–8)

| Task | Detail |
|---|---|
| Postgres 16 | Migrate conversations/messages/KB meta/facts from SQLite; SQLite stays dev-only |
| Redis | Rate limit (replace slowapi-only), session cache, TTS cache |
| pgvector | Re-embed KB; hybrid retrieval live; measure recall/quality vs baseline |
| Adapter lockdown | All DB/vector/LLM/speech access only through the contracts |
| Eval loop | Pydantic Evals / DeepEval in CI (unit + retrieval + guardrails); **Promptfoo** A/B + red-team; **benchmark v2.0 gate on every PR**; production-trace sampling + drift detection |
| Observability | OTel spans on every request → Phoenix/OpenLIT/Logfire; alerting (LLM error rate, latency p95, voice disconnects); retire JSONL-only telemetry |
| DPDP | Retention, consent, PII minimization, `tenant_id` in every table — from day one, not later |

**Exit:** CI gates every change; every request traced; DPDP controls live; no direct SQL in services.
**Rollback:** config flips (storage adapter, tracer backend).

## Phase D — Voice, UI, decommission (weeks 8–12)

| Task | Detail |
|---|---|
| Voice rebuild | LiveKit Agents + **Exotel SIP** (replace broken Twilio↔LiveKit bridge); `VoiceGateway` + `SpeechProvider` adapters; Sarvam default + one alternative; <800ms budget; Bengali fixed eval set |
| Admin shell | Deploy **OpenWebUI** as internal admin/ops (RAG management, benchmark review, trace inspection) |
| Student UI | Thin separate client; nothing from OpenWebUI's auth/UX in the product surface |
| Switch drill in CI | LLM swap ≤2% delta · TTS swap works · vector parity · agent-runtime conformance — **green before production cutover** |
| Load test | k6 against Postgres+pgvector+Redis+agent path |
| Decommission | Delete legacy monolith paths (`groq_service.py`, unwired `core/`/`channel/`/`pipeline/`/`di.py`); JSONL exporters off; unused providers dead |
| Docs & runbook | Update ARCHITECTURE_ROADMAP, ops runbook, incident doc (Bengali backlog) |

**Exit:** live voice call over Exotel + Sarvam; admin shell in use; legacy decommissioned; one codebase, no dual maintenance.
**Rollback:** keep old WS voice endpoint for a window.

---

## Sequencing summary

```
Phase A  stop the bleeding   ████
Phase B  serve new shape     ██████████████
Phase C  data/eval/obs       ██████████████
Phase D  voice/UI/retire     ██████████████
```

## What this plan does NOT do (by design)

- No queue, durable-execution engine, dedicated vector service, LLM gateway, or multi-agent is introduced during migration — none of the Adoption Triggers (`08` §10) fire at our scale. If one fires, it is added as a conformance-tested implementation, not a plan change.
- No build of: WebRTC/SIP, vector index, speech engines, trace UI, auth server, workflow engine, admin dashboard.
- No promotion of the old pipeline layers.

## Key risks this plan mitigates

- Uncommitted `src/` loss → Phase A freeze (198 paths).
- Dual-maintenance drift → Phase A stops dead code; Phase D ends dual maintenance.
- Vendor exit → contracts everywhere; Phase C/D drills the switch (invariant, not optional).
- Hallucinated fee answers → Phase B deterministic tools + benchmark gate.
- CI green-but-fake → Phase A fixes root requirements + real CI.
- Framework churn (PydanticAI etc.) → contracts + conformance suite make swaps routine; benchmark keeps them honest.
