# 10 — Risk Analysis

> Every material risk to the platform — current state, likelihood, impact, and the mitigation owned by a migration phase (`09_migration_plan.md`). Risk = Likelihood × Impact, scored L/M/H.

**Risk lens changed by the final architecture:** the biggest risks are no longer "does the code work" but (1) loss of uncommitted work, (2) security, (3) financial hallucination, (4) vendor dependence — and a new class introduced by contracts-first: **framework lock-in and benchmark drift**. The mitigations are invariants (contracts, benchmark gate, switch drill), not one-time fixes.

---

## 1. Risk register

| # | Risk | L | I | Score | Current evidence | Mitigation (phase) |
|---|---|---|---|---|---|---|
| 1 | **Loss of uncommitted `src/` work** (validation, reasoning, signals, composer, decision models) | M | H | **H** | 198 uncommitted paths; last commit `3dec397` | Phase A freeze/commit immediately |
| 2 | **Security breach via open endpoints / secrets in repo** | H | H | **H** | `/qa/*`, conversations, `/voice/call-me`, admin unauthenticated; empty `SARVAM_TOOL_API_TOKEN`; hardcoded JWT `admin/admin`; keys in `.env` | Phase A rotate + authenticate everything |
| 3 | **Fee answers hallucinated by LLM** (no deterministic engine) | H | H | **H** | Fee engine dead; LLM free-texts fees | Phase B deterministic `FeeCalculatorTool` + benchmark gate |
| 4 | **LiveKit import crash takes down `/voice/*`** | H | M | **H** | `voice.py:21` unguarded import; lib not in requirements | Phase A guard/flag |
| 5 | **Vendor lock-in: Sarvam/Groq exit or outage** | M | H | **H** | All voice + LLM via one vendor each | Invariant: contracts + switch drill (`08` §6) in CI |
| 6 | **Framework lock-in (agent runtime, e.g. PydanticAI)** | M | H | **H** | Agent runtime is the core execution layer | `AgentRuntime` contract + conformance suite + benchmark; runtime-swap drill (`08` §10) |
| 7 | **Benchmark drift / stale golden set** (gate becomes meaningless) | M | H | **H** | Benchmark v2.0 is the sole gate | Periodic golden review; production-trace sampling + drift detection (Phase C) |
| 8 | **Dual-maintenance drift (legacy vs `src/`)** | H | M | **M-H** | Both maintained; latest commit touched only legacy | Phase A stop dead code; Phase D decommission |
| 9 | **CI green-but-fake** (root `requirements.txt` missing) | M | M | **M** | benchmark.yml needs a file that doesn't exist | Phase A fix CI |
| 10 | **Retrieval inconsistency: Chroma + `combined_kb.json` double-source** | H | M | **M-H** | Both feed the prompt | Phase B retrieval-only answers |
| 11 | **Double SAFEPOINT / double-filtered answers** | M | L | **M** | `qa.py:141-147` + `groq_service.py:6377-6378` | Phase A consolidation |
| 12 | **Fake streaming UX** | M | L | **M** | word-replay with 0.02s sleeps | Phase B true streaming |
| 13 | **Bengali accent/STT quality risk** (incident history) | M | M | **M** | FastText runtime download, keyword fallback; prior backlog | Phase D fixed Bengali eval set + provider eval |
| 14 | **SQLite concurrency at scale** | M | M | **M** | WAL; sync DB calls in async handlers | Phase C Postgres + async SQLAlchemy |
| 15 | **`/monitoring` false-positive health** | L | M | **M** | always-ok stub | Phase A real health |
| 16 | **Rate-limiter gaps** | M | L | **M** | slowapi 10/min; `/tts`,`/stt` vary | Phase C Redis limiter |
| 17 | **Prompt bloat / token cost** | M | L | **M** | `combined_kb.json` ~8,700 entries in every prompt | Phase B remove dump |
| 18 | **DPDP non-compliance** (retention/consent/PII) | M | H | **M-H** | None today; no data policy | Phase C controls; `tenant_id` everywhere from day one |
| 19 | **Durable-execution deferral bites** (a workflow needs Temporal; logic not durable-ready) | L | M | **L-M** | No interrupt-driven flows yet | Invariant: durable-ready state machines (`08` §1.1.9); trigger monitored |
| 20 | **pgvector scale ceiling** | L | M | **L-M** | Proven to 340M chunks p99 <15ms | Qdrant scale-out path documented; trigger-gated (`08` §10) |

---

## 2. Top-5 must-fix (this week)

1. **#1 Loss of `src/` work** — commit now; largest irreplaceable asset (benchmark v2.0, 44-test suite, brain).
2. **#2 Open endpoints + live secrets** — rotate + authenticate; today anyone can call `/qa/query`, conversations, call-me.
3. **#3 Fee hallucination** — deterministic fee tool; financial answers must not be free-text.
4. **#4 Voice crash** — guard the LiveKit import; `/voice/*` is a live-fire trap.
5. **#5/#6 Vendor + framework lock-in** — the contracts + conformance suite + switch drill are invariants, not backlog.

## 3. Switch-drill definition (the independence test)

Pass criteria for "platform survives a vendor exit **and** a framework exit":
1. Change LLM provider (Groq → OpenAI) via config → benchmark ≤2% delta.
2. Change TTS provider (Sarvam → Google) → voice demo works.
3. Change vector store (pgvector → Qdrant) → retrieval parity.
4. Change agent runtime (PydanticAI → second conformance-tested runtime) → conformance suite + benchmark ≤2%.
5. All four behind config/contracts; **zero app-code edits**.
Scheduled as CI jobs in Phases C/D; **must be green before production cutover** and thereafter on every provider-sensitive change.

## 4. Watch items (non-blocking)

- Gemini/OpenRouter/Deepgram keys present but unused — rotate or remove (Phase A).
- `ollama_connected` in frontend type but no backend field.
- `next_gen/` has uncommitted changes — fold into archive decision.
- Legacy `core/`, `channel/`, `pipeline/`, `di.py` stay unwired — delete or wire; not left in limbo past Phase D.
- Adoption Trigger state (`08` §10) — queue / durable-execution / vector service / gateway / multi-agent: currently none fired; re-measure quarterly.

## 5. Residual risks (accepted)

- **No multi-tenant** → accepted for v1.
- **No long-term user memory** → accepted; trigger-gated (personalization becomes a product requirement).
- **No durable-execution engine initially** → accepted; logic is durable-ready by construction; trigger-gated.
- **No dedicated vector service initially** → accepted; pgvector is the default; trigger-gated.
- **LLM API dependency remains (commercial)** → accepted by design; mitigated by `LLMProvider` multi-vendor, never self-host.
- **OTel backend ops burden (Phoenix/OpenLIT/Logfire self-hosted)** → accepted; Docker + runbook.
- **OpenWebUI coupling risk** → accepted; internal-only scope + thin student UI; fallback to a minimal dashboard if assumptions fight us.

---

## 6. Conclusion

The dominant risks are **loss of uncommitted work, open security, financial hallucination, and single-vendor/single-framework dependence** — plus the new class that contracts-first introduces: **benchmark drift**. Phase A neutralizes the top-5; Phases B–D remove the structural causes (pipeline layers, monolith, no contracts, no evals). The platform is viable **if and only if** the benchmark stays a hard release gate and the switch drill stays a standing CI job. Every implementation is disposable; the contracts, the benchmark, and the domain rules are not.
