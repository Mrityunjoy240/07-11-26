# BCREC AI — Production Architecture Roadmap

**Classification:** Internal — Architecture Decision Record  
**Status:** Draft for Review  
**Date:** 2026-07-17  
**Authors:** Lead Software Architect / Principal AI Engineer  
**Recovery Point:** `v1-demo-stable` (tag), `release/demo-v1` (branch), `backup/v1-demo-2026-07-17` (branch)

---

# PRODUCT PHILOSOPHY

> **This document is not about software. It is about building an AI Admission Counselor.**

Everything below — every interface, every module, every migration phase — exists to serve one purpose:

> If tomorrow an experienced admission counselor leaves the college, this AI should counsel students almost as well as that counselor.

That is the only metric that matters.

### The Sentence

> **The purpose of this architecture is not to answer every question. The purpose is to help every student make the best possible admission decision with the least amount of confusion, anxiety, and effort.**

## Engineering Principles

These principles govern every architectural decision. A change that violates a principle must be rejected, even if it saves time or code.

```
Correctness over cleverness.
   No trick code. No premature optimization. Get the facts right first.

Architecture over patches.
   If a fix requires violating the layer boundaries, fix the architecture instead.

Understanding over keyword matching.
   The system must infer intent, not match keywords.

Reasoning over prompting.
   Make the model reason with tools and structure, not brute-force prompt instructions.

Structured knowledge over hallucination.
   Facts live in structured stores, never in LLM parameters. The LLM reads facts, it does not remember them.

Deterministic behavior where possible.
   If a fee lookup can be computed exactly, compute it exactly. Do not ask an LLM.

LLM only when reasoning is required.
   Classification, lookup, formatting — use deterministic code. Counseling, recommendation, planning — use LLM.

Every module has one responsibility.
   A module that does two things does neither well. Split it.

Every feature must be testable.
   If you cannot write a unit test for it, the architecture is wrong. Fix the architecture, not the test.

Every architectural change must reduce complexity.
   If the change adds more code than it removes, reconsider the approach.

Every dependency must be replaceable.
   Any third-party provider (LLM, STT, TTS, vector store, database) can fail or be replaced. The system must survive the swap.
```

## What This System IS

This is an **AI Admission Counselor** that happens to communicate through voice, chat, WhatsApp, web, and future channels.

The intelligence is the product.

The channel is only an interface.

## What This System is NOT

| ❌ Not This | ✅ This |
|------------|---------|
| A chatbot | An admission counselor |
| An FAQ bot | A guide through the admission journey |
| A voice assistant | Someone who understands hesitation, fear, and goals |
| A call center IVR | A counselor who remembers every conversation |
| A RAG demo | Someone who explains trade-offs, not just facts |
| An LLM wrapper | A system that solves problems, not answers questions |
| A Q&A engine | A reasoning engine that plans what to say next |

## Product Vision — How Every Interaction Should Feel

```
Student
│
├── Talks naturally (incomplete sentences, mixed language, hesitation)
│
├── AI understands:
│   • explicit words
│   • hidden intent ("I got 65%" → worried about eligibility)
│   • emotional state (anxious, confident, confused, curious)
│   • conversation history (remembered across sessions)
│   • academic profile (rank, PCM, board, category, interest)
│   • financial situation (budget concern, scholarship need)
│   • goals (admission, specific branch, hostel, placement)
│   • conversation stage (discovery → evaluation → decision → application)
│
├── AI reasons:
│   • What does this student actually need right now?
│   • What information is missing?
│   • What are the trade-offs?
│   • What should I recommend and why?
│
├── AI counsels:
│   • Guides step by step through the decision process
│   • Explains options with pros and cons
│   • Proactively identifies what the student hasn't asked but needs to know
│   • Adapts explanation to the student's knowledge level
│   • Never overwhelms with unnecessary information
│   • Knows when to answer directly and when to guide through a process
│
├── AI plans:
│   • What should I say next?
│   • Should I answer, probe, reassure, recommend, or escalate?
│   • What workflow should I start (admission, scholarship, hostel)?
│
├── AI remembers:
│   • This conversation
│   • Previous conversations with this student
│   • What was recommended
│   • What was left unresolved
│
└── AI responds:
    • Warm, empathetic, professional — like the college's best counselor
    • In the student's language
    • Concise but complete
    • With a clear next step
```

Notice what does NOT appear in this flow:

> search JSON · call Groq · query vector store · call STT/TTS API · fetch from Redis

Those are implementation details. The architecture must enable the vision above. The technology choices come second.

## The Core Principle: One Question Per Layer

Every layer of the architecture should answer exactly one question. Nothing more.

| Layer | The One Question It Answers |
|-------|----------------------------|
| **Voice Layer** | How do I hear and speak? |
| **Channel Adapter** | How do I normalize input from this channel? |
| **Conversation Layer** | What did the student say? (explicit + implicit) |
| **Reasoning Layer** | What does the student actually need? |
| **Decision Engine** | What should I do about it? |
| **College Brain** | How does this college actually work? |
| **Knowledge Layer** | What facts are true? |
| **Planning Layer** | What should I say next? |
| **Workflow Layer** | What process should I guide them through? |
| **Memory Layer** | What do I remember? |
| **Profile Layer** | Who is this student? |
| **Safety Layer** | Should I answer this? |

A layer that answers two questions is poorly designed.

A layer that answers someone else's question is a bug.

## What "Understanding" Means

Most AI agents do this:

> Student: "I got 48k rank."
> System: Store rank. Done.

This system must do this:

```
Student: "I got 48k rank."
│
├── Rank: 48k (explicit)
├── PCM: missing → probe needed
├── Interest: missing → probe needed
├── Fear: likely worried about eligibility (implicit)
├── Budget: unknown → monitor for cues
├── Parent concern: unknown → monitor for cues
├── Hostel requirement: unknown → monitor for cues
├── Career goal: unknown → monitor for cues
│
├── Reasoning:
│   • With 48k rank, eligible for most branches
│   • CSE cutoff was 35k last year, may be tight
│   • AIML/ECE/IT are realistic
│   • Should check if they have WBJEE or JEE rank
│
├── Recommendation pipeline:
│   • Immediate: reassure about eligibility
│   • Next: ask about PCM, interest, preferred branch
│   • If interest expressed: recommend branches with reasoning
│   • Then: fees, placement, scholarship for recommended branches
│   • Then: hostel, if needed
│   • Then: admission process, deadlines, documents
│   • Follow-up: did they apply? need help with next step?
│
└── Next step: probe for missing profile information
```

## What "Intelligence" Means

A bad AI answers questions. A good AI solves problems.

**Question answering:**
> Student: "What is CSE placement?"
> AI: "93.6%."

**Problem solving:**
> Student: "I got 50k rank and I like computers."
> AI: "Based on your rank of 50k, your interest in computer science, and the current cutoff trends at BCREC, here is your realistic counseling plan:
>
> **First choice:** CSE (cutoff ~35k, but worth trying in first round)
> **Safe choice:** IT (cutoff ~45k, excellent placement at 90%)
> **Very safe:** AIML (cutoff ~55k, new branch, good industry alignment)
>
> For each option, here are the fees, placement rates, and scholarship opportunities. I would recommend applying in this order. If counseling results don't go as expected, here's your backup plan..."

**That is intelligence.** Not because the model is bigger. Because the system understood the student's situation, reasoned about options with trade-offs, and produced a plan.

## The Ultimate Test

If this system were deployed tomorrow, would a student who spoke to it for 15 minutes feel like they had a real counseling session with an experienced admission officer?

If the answer is "almost" — we are on the right track.

If the answer is "no, it felt like talking to a chatbot" — the architecture has failed, regardless of how clean the code is.

## Success Metrics

### Product Metrics (Primary)

These are the metrics that determine whether the system is succeeding as a product.

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Counseling completion rate** | >80% | Student completes full admission cycle without human intervention |
| **Student satisfaction** | >90% | Post-interaction survey (NPS or 5-star) |
| **Recommendation confidence** | >90% | Branch recommendation matches counselor's recommendation for same profile |
| **Hallucination rate** | <0.1% | Any incorrect factual claim about college, fees, placement, or policies |
| **Wrong institution reference** | 0% | Never confuse BCREC with another college |
| **Language consistency** | >99% | Response language matches user's language |
| **Cross-session memory** | >90% | Student recognized on return, previous context used naturally |
| **Human handoff rate** | <5% | Escalation to human counselor |
| **Handoff quality** | >90% | Human counselor agrees handoff was necessary and summary was accurate |
| **Conversation length** | 10-20 min | Average counseling session duration |

### Technical Metrics (Secondary)

These support the product metrics but are not goals in themselves.

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| End-to-end latency (voice) | <3s p95 | Long pauses break conversation flow |
| End-to-end latency (text) | <1.5s p95 | Users expect fast web responses |
| Voice pipeline uptime | >99.5% | Phone calls must connect reliably |
| Cost per conversation | <$0.10 | College budget constraint |
| Provider failover time | <30s | LLM/STT/TTS provider failure must be invisible to user |

### Why Metrics Matter

Without measurable goals, different people optimize for different things:

- Engineers optimize for latency
- Product optimizes for features
- Business optimizes for cost
- AI researchers optimize for model quality

The product metrics above align everyone. Every change is measured against: *"Does this improve counseling completion rate? Does it reduce hallucination rate?"* If the answer to both is "no", the change is not a priority.

## AI Growth Roadmap — Maturity Levels

This system will not start at Level 6. It must evolve. Each level builds on the previous one.

```
Level 1: FAQ
   • Answers frequently asked questions
   • No conversation memory
   • No student profile
   • No counseling
   • Channel: web chat only
   ═══ We are here today

Level 2: Memory
   • Remembers conversation within session
   • Extracts basic student profile (rank, PCM)
   • Simple follow-up resolution
   • Channel: web + voice (telephone)
   ═══ Current V2/V3 capability

Level 3: Counselor
   • Multi-turn counseling with reasoning
   • Student profile persists across sessions
   • Branch recommendations with trade-offs
   • Emotional state detection
   • Goal tracking
   • Multi-language
   • Channels: web + voice + WhatsApp
   ═══ Target by end of Year 1

Level 4: Planner
   • Workflow engine operational
   • Can guide through admission process step by step
   • Proactive follow-up ("Did you apply? Need help?")
   • Scholarship recommendation
   • Human handoff when confidence drops
   • Channels: all
   ═══ Target by end of Year 2

Level 5: Advisor
   • Proactive outreach (deadline reminders)
   • Career trajectory prediction
   • Alumni connection suggestions
   • Cross-channel session continuity
   • Student can start on web → continue on phone → follow up on WhatsApp
   ═══ Target by end of Year 3

Level 6: Autonomous Admission Assistant
   • End-to-end admission processing without human intervention
   • Document verification
   • Fee payment assistance
   • Enrollment confirmation
   • Follow-up with incomplete applications
   • 95%+ student satisfaction
   • <0.01% error rate
   ═══ Target by Year 5
```

**Every architectural decision must not block reaching Level 6.** Even if we are at Level 2 today, the architecture must support Level 6 without redesign.

---

## Table of Contents

0. [Product Philosophy](#0-product-philosophy)
1. [Current Architecture Diagram](#1-current-architecture-diagram)
2. [Current Architecture — Layer-by-Layer Breakdown](#2-current-architecture--layer-by-layer-breakdown)
3. [Current Problems & Technical Debt](#3-current-problems--technical-debt)
4. [Layer Boundaries — The Separation Contract](#4-layer-boundaries--the-separation-contract)
5. [Future Architecture — Complete Design](#5-future-architecture--complete-design)
6. [Module Responsibilities](#6-module-responsibilities)
7. [Interface Definitions](#7-interface-definitions)
8. [Data Flow & Sequence Diagrams](#8-data-flow--sequence-diagrams)
9. [Migration Strategy](#9-migration-strategy)
10. [Folder Structure — Target](#10-folder-structure--target)
11. [Development Phases & Milestones](#11-development-phases--milestones)
12. [Testing Strategy](#12-testing-strategy)
13. [Performance Strategy](#13-performance-strategy)
14. [Cost Strategy](#14-cost-strategy)
15. [Scalability Strategy](#15-scalability-strategy)
16. [Deployment Strategy](#16-deployment-strategy)
17. [Monitoring & Observability Strategy](#17-monitoring--observability-strategy)
18. [Disaster Recovery Strategy](#18-disaster-recovery-strategy)
19. [Risk Analysis](#19-risk-analysis)
20. [Rollback Strategy](#20-rollback-strategy)
21. [Versioning Strategy](#21-versioning-strategy)
22. [Production Readiness Checklist](#22-production-readiness-checklist)
23. [Estimated Timeline](#23-estimated-timeline)

---

## 1. Current Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                  │
│  ┌─────────┐  ┌────────────┐  ┌──────────┐  ┌──────────────┐        │
│  │ Phone   │  │ Browser    │  │ WhatsApp │  │ Mobile App   │        │
│  │ (PSTN)  │  │ (React)    │  │ (Future) │  │ (Future)     │        │
│  └────┬────┘  └─────┬──────┘  └──────────┘  └──────────────┘        │
│       │             │                                                 │
└───────┼─────────────┼─────────────────────────────────────────────────┘
        │             │
┌───────▼─────────────▼─────────────────────────────────────────────────┐
│                      TRANSPORT LAYER                                   │
│  ┌──────────────────┐  ┌───────────────────────────────────────────┐  │
│  │ Twilio (PSTN)    │  │ HTTP / WebSocket (FastAPI / Uvicorn)      │  │
│  │ Media Streams    │  │ REST / WS / SSE                           │  │
│  │ μ-law ↔ PCM      │  │ Port 8000                                 │  │
│  └────────┬─────────┘  └──────────────────┬────────────────────────┘  │
│           │                               │                           │
│  ┌────────▼───────────────────────────────▼────────────────────────┐  │
│  │                LiveKit Agent (scripts/livekit_agent.py)         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌───────┐  ┌──────────────────┐   │  │
│  │  │ Silero   │  │Deepgram/ │  │Groq   │  │Sarvam TTS        │   │  │
│  │  │ VAD      │  │Sarvam STT│  │LLM    │  │(bulbul v3)       │   │  │
│  │  └──────────┘  └──────────┘  └───────┘  └──────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
        │                               │
        ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER (FastAPI)                          │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     REST / WS API ROUTES                         │    │
│  │  /qa/query  /qa/stt  /qa/tts  /voice/token  /voice/stream        │    │
│  │  /api/conversations  /admin/*  /health                           │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │              GROQ SERVICE (groq_service.py — ~5200 lines)         │    │
│  │                                                                   │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐    │    │
│  │  │Intent Router  │  │Structured    │  │Fee Engine            │    │    │
│  │  │(regex, 30+    │  │Handlers      │  │(deterministic tier   │    │    │
│  │  │ handlers)     │  │(fee,contact, │  │  lookup)             │    │    │
│  │  └──────────────┘  │ HOD, etc.)   │  └──────────────────────┘    │    │
│  │                    └──────────────┘                               │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐    │    │
│  │  │OOD Detection  │  │Hallucination │  │Session State         │    │    │
│  │  │(12 categories)│  │Guard (Phase  │  │(in-memory dict +     │    │    │
│  │  │               │  │ 0)           │  │ domain slots)        │    │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘    │    │
│  │                                                                   │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐    │    │
│  │  │LLM Router     │  │Rate Limiter  │  │Query Cache           │    │    │
│  │  │(Groq only)    │  │(sliding      │  │(TTLCache, in-proc)   │    │    │
│  │  │               │  │ window)      │  │                      │    │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐    │
│  │SarvamService     │  │VectorStore       │  │ConversationTelemetry │    │
│  │(STT/TTS wrapper) │  │(ChromaDB +       │  │(JSONL event stream)  │    │
│  │                  │  │ all-MiniLM-L6-v2)│  │                      │    │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │              KNOWLEDGE BASE                                       │    │
│  │  college_facts.json  +  combined_kb.json  +  ChromaDB vectors     │    │
│  │  (maintained by editing JSON files directly)                      │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     STORAGE                                        │    │
│  │  SQLite (conversations.db)  +  In-memory dicts (sessions)         │    │
│  │  TTS Audio Cache (disk + in-memory)                               │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Current Architecture — Layer-by-Layer Breakdown

### 2.1 Transport Layer

| Component | Technology | Role | Coupling |
|-----------|-----------|------|----------|
| Twilio Bridge | WebSocket + μ-law | Converts PSTN audio ↔ LiveKit audio | Tight: Twilio-specific codec handling in `voice.py` |
| LiveKit Agent | `livekit.agents` SDK | Voice pipeline: VAD → STT → LLM → TTS | Tight: BCRECGroqLLM, SarvamSTT, SarvamTTS embedded in agent |
| FastAPI HTTP | Uvicorn | REST endpoints for text chat, admin, health | Standard |
| FastAPI WS | WebSocket | Real-time voice/text pipeline (`/qa/ws/voice`) | Standard |

**Key insight:** The LiveKit agent (`scripts/livekit_agent.py`, 716 lines) is a standalone process that imports the GroqService directly. It maintains its own prompt, its own STT/TTS configuration, and its own session lifecycle. Changes to the main application's behavior (e.g., prompt updates) must be manually replicated to the LiveKit agent. This is a **behavioral divergence risk**.

### 2.2 Application Layer

| Module | Lines | Responsibility | Health |
|--------|-------|----------------|--------|
| `services/llm/groq_service.py` | ~5200 | Intent routing, structured handlers, LLM calls, session management, caching, rate limiting, circuit breaker, hallucination guard, fee engine | **CRITICAL** — monolithic, untestable |
| `services/llm/fee_engine.py` | ~500 | Deterministic fee calculation | Good (isolated module) |
| `services/llm/intent_classifier.py` | ~200 | ML-based intent classification | Good (isolated) |
| `services/llm/safe_point.py` | ~300 | Demo safety net | Medium (feature flags via try/except) |
| `services/sarvam_service.py` | ~304 | Sarvam STT/TTS wrapper | Medium (tight to Sarvam API) |
| `services/vector_store.py` | ~151 | ChromaDB wrapper | Good |
| `services/tts_cache.py` | ~104 | TTS audio cache | Good |
| `core/conversation_engine.py` | ~200 | Pipeline orchestration (V2 redesign) | Good (underutilized) |
| `core/interfaces.py` | ~100 | Abstract interfaces | **CRITICAL** — exists but GroqService doesn't implement them |
| `core/models.py` | ~100 | Data models | Good |
| `core/event_bus.py` | ~80 | In-process event bus | Underutilized |
| `channel/base.py` | ~60 | Channel adapter base | Underutilized |
| `pipeline/stages/*.py` | ~50 each | Pipeline stages (intent, knowledge, llm, guard, language, formatter) | Incomplete — V2 has the pipeline stages but they're not wired into the main flow |

**Critical discovery:** The `core/` and `channel/` and `pipeline/` directories in V2 (`college_agent-master/backend/app/`) already represent a **partial architectural refactor** that was started but never completed. The pipeline stages exist. The interfaces exist. The event bus exists. But the main `groq_service.py` bypasses all of them.

### 2.3 Knowledge Layer

| Source | Format | Size | Maintainability |
|--------|--------|------|----------------|
| `college_facts.json` | JSON | ~100 KB | **Poor** — needs developer to edit |
| `combined_kb.json` | JSON | ~200 KB | **Poor** — needs developer to edit |
| `canonical_kb.json` | JSON | ~50 KB | **Poor** — needs developer to edit |
| ChromaDB vectors | Embeddings | ~15 MB | Auto-generated from markdown/PDF |
| `knowledge_audit/*.json` | JSON | ~20 files | Audit artifacts, not runtime |
| System prompt (in `groq_service.py`) | Hardcoded text | ~60 lines | **Worst** — embedded in code |
| LiveKit agent prompt (in `livekit_agent.py`) | Hardcoded text | ~50 lines | Different from main prompt |
| `next_gen/data/prompts/system.txt` | Text file | 48 lines | Third copy of prompt |

**The prompt is duplicated in four places:** `groq_service.py` (inline), `livekit_agent.py` (inline), `next_gen/data/prompts/system.txt` (separate file), and `rag.py` (inline default). Each has diverged slightly.

### 2.4 Storage Layer

| Data | Store | Format | Persistence | Scalability |
|------|-------|--------|-------------|-------------|
| Active sessions | In-memory dict | Python objects | **None** — lost on restart | **None** — single process |
| Conversation history | SQLite | Tables (conversations, messages) | Persistent | **Poor** — single file, no replication |
| Student profiles | In-memory dict | Python dataclass | **None** — lost on restart | **None** — single process |
| Query cache | `cachetools.TTLCache` | In-memory dict | **None** | **None** — per-process |
| TTS audio cache | Disk + in-memory | WAV files | Persistent | Medium — disk-backed |
| Vector store | ChromaDB (on disk) | Embeddings + metadata | Persistent | Medium — single node |

**Every in-memory data structure is a scaling blocker.** The system cannot have more than one server because sessions, profiles, and caches are process-local.

---

## 3. Current Problems & Technical Debt

### 3.1 Critical — Blocking Production Readiness

| # | Problem | Location | Impact | Fix Complexity |
|---|---------|----------|--------|----------------|
| P0 | **GroqService is a 5200-line monolith** | `services/llm/groq_service.py` | Every change risks breaking unrelated features. Cannot unit test. New engineers cannot understand it. | 3 weeks — refactor into specialized modules |
| P0 | **Session state is in-memory only** | `GroqService._sessions` (dict) | Lost on restart. Cannot scale horizontally. Active calls drop if process restarts. | 1 week — Redis session store |
| P0 | **Query cache is in-process only** | `GroqService._cache` (TTLCache) | Each replica has cold cache. Wasted LLM calls on repeated queries. | 2 days — Redis cache |
| P0 | **Prompt is duplicated 4+ ways** | `groq_service.py`, `livekit_agent.py`, `system.txt`, `rag.py` | Prompts drift apart. Voice behaves differently from text. Updating requires touching 4+ files. | 1 week — central prompt store |
| P0 | **Voice and text take different code paths** | `groq_service.py` vs `livekit_agent.py` | LiveKit agent has its own prompt, its own session management, its own rate limiting. Behavioral parity cannot be guaranteed. | 2 weeks — unified conversation engine |
| P0 | **No LLM provider fallback** | `groq_service.py` (hardcoded to Groq) | If Groq is down, the entire system is down. No graceful degradation. | 2 days — provider abstraction + fallback chain |

### 3.2 High — Design Debt

| # | Problem | Location | Impact | Fix Complexity |
|---|---------|----------|--------|----------------|
| P1 | **Interfaces exist but are not used** | `core/interfaces.py`, `core/conversation_engine.py` | The architectural refactor was started but not completed. Code bypasses the clean interfaces. | 2 weeks — wire pipeline stages into main flow |
| P1 | **`core/event_bus.py` is unused** | `core/event_bus.py` | In-process event bus defined but never published to. No decoupling. | 1 week — integrate into pipeline |
| P1 | **Three parallel codebases** | `21-06-26-college-agent/`, `college_agent-master/`, `next_gen/` | Duplicated effort. Unclear which is the source of truth. Bug fixes applied to one may not reach others. | 4 weeks — converge onto one |
| P1 | **Feature flags implemented as try/except imports** | `groq_service.py:38-95` | Missing modules silently disable features. Impossible to know what's enabled without reading logs. | 3 days — proper feature flag system |
| P1 | **No cold-start handling for embedding model** | `vector_store.py` | First request after deployment loads HuggingFace model (5-15s latency). | 2 days — warm on startup |
| P1 | **SQLite for conversation history** | `database.py` | Cannot be shared across replicas. Write contention at scale. | 2 weeks — PostgreSQL migration |

### 3.3 Medium — Quality Debt

| # | Problem | Impact | Fix Complexity |
|---|---------|--------|----------------|
| P2 | LiveKit agent's STT/TTS config differs from main app | Voice behavior inconsistency between web chat and phone | 1 week |
| P2 | Rate limiting only at application level (slowapi), not per-channel or per-user | Cannot prioritize admin vs. student vs. API traffic | 3 days |
| P2 | Client-provided session IDs (V3) | Security risk — session hijacking | 2 days (server-generated IDs) |
| P2 | No depth to health checks | `/health` returns "ok" without checking downstream dependencies | 1 day |
| P2 | Observability package empty in V3 | No metrics, traces, or monitoring in the clean architecture | 2 weeks |

### 3.4 Low — Polish Debt

| # | Problem | Impact |
|---|---------|--------|
| P3 | CORS `allow_origins=["*"]` in V3 | Security concern for production |
| P3 | `next_gen/server.log` tracked in git | Log file in source control |
| P3 | `nul` file in `college_agent-master/` | Reserved Windows filename causes git issues |
| P3 | Various audit reports (`audit/*.md`) mixed with source code | Repo clutter |

---

## 4. Layer Boundaries — The Separation Contract

### The One Question Principle

Every layer answers exactly one question:

| Layer | The One Question |
|-------|-----------------|
| **Voice Adapter** | How do I hear and speak? |
| **Channel Adapter** | How do I normalize this channel's input? |
| **Conversation Engine** | What did the student say and what is their state? |
| **Reasoning Engine** | What does the student actually need? |
| **Decision Engine** | What should I do about it? |
| **College Brain** | How does this college actually work? |
| **Planning Engine** | What should I say next? |
| **Specialist Agents** | What facts and recommendations apply to this domain? |
| **Workflow Engine** | What process should I guide them through? |
| **Knowledge Layer** | What facts are true? |
| **Memory Layer** | What do I remember about this student and conversation? |
| **Profile Layer** | Who is this student? |
| **Safety Layer** | Should I answer this? |

A layer that answers two questions is poorly designed. A layer that answers someone else's question is a bug.

### Current Violations

The fundamental problem is that **layers do not exist today**. The GroqService touches everything: transport concerns (rate limiting), business logic (intent routing, fee calculation), data access (session management), knowledge retrieval, AND safety rules — it answers at least six questions. 

The following separation contract defines how the system **must** be structured:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                              │
│                                                                          │
│  Responsibilities:                                                       │
│    • Accept input from any channel (HTTP, WS, Twilio, WhatsApp, etc.)   │
│    • Convert channel-native format to internal MessageEnvelope           │
│    • Send response back through channel                                  │
│    • Handle channel-specific concerns (auth, rate limiting, format)      │
│                                                                          │
│  MUST NOT know:                                                          │
│    • How the Conversation Engine works                                   │
│    • What LLM provider is being used                                     │
│    • How knowledge is retrieved                                          │
│    • How the student profile is managed                                  │
│                                                                          │
│  Channels:  Web (REST/WS) │ Voice (LiveKit adapter) │ WhatsApp adapter   │
│             Mobile (REST) │ Kiosk (REST) │ CRM (HTTP)                    │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      CHANNEL ADAPTER LAYER                               │
│                                                                          │
│  Responsibilities:                                                       │
│    • Thin normalization layer                                            │
│    • Publish MessageEnvelope to event bus                                │
│    • Subscribe to response events and route back to channel              │
│    • Handle channel-specific serialization                               │
│                                                                          │
│  MUST NOT know:                                                          │
│    • Business logic                                                      │
│    • LLM provider                                                        │
│    • Knowledge structure                                                 │
│                                                                          │
│  Contracts:  Input → MessageEnvelope → EventBus                          │
│              ResponseEvent → ChannelResponse → Output                    │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       CONVERSATION ENGINE                                │
│                                                                          │
│  Ownership:                                                              │
│    • Language detection & enforcement                                    │
│    • Intent detection & routing                                          │
│    • Entity extraction                                                   │
│    • Student profile management                                          │
│    • Conversation memory & context tracking                              │
│    • Goal tracking & conversation stage management                        │
│    • Clarification & disambiguation                                      │
│    • Follow-up resolution                                                │
│    • Response planning (observe → plan → act → remember)                 │
│    • Safety rules & guardrails                                           │
│    • Hallucination prevention                                            │
│                                                                          │
│  MUST NOT know:                                                          │
│    • Twilio, LiveKit, Dograh, Vapi, or any channel implementation        │
│    • HTTP, WebSocket, or any transport protocol                          │
│    • How knowledge is stored (JSON, graph, vector, SQL)                  │
│    • Which LLM provider is processing requests                           │
│    • How many replicas exist                                             │
│    • Deployment topology                                                 │
│                                                                          │
│  Interfaces:  process(MessageEnvelope) → ResponseEvent                   │
│               load_session(session_id) → ConversationState               │
│               save_session(session_id, state)                            │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         REASONING ENGINE                                 │
│                                                                          │
│  Responsibilities:                                                       │
│    • Route requests to appropriate LLM provider tier                     │
│    • Tool calling / function execution for deterministic lookups         │
│    • Multi-step reasoning planning                                       │
│    • Emotion detection from text                                         │
│    • Profile-driven recommendations (branch, career, scholarship)        │
│    • Workflow orchestration (admission process, scholarship process)     │
│                                                                          │
│  MUST NOT know:                                                          │
│    • Which specific LLM model is running (just the provider interface)   │
│    • How the conversation engine works                                   │
│    • Channel details                                                     │
│                                                                          │
│  Interfaces:  reason(Request) → Response                                 │
│               call_tool(ToolCall) → ToolResult                           │
│               detect_emotion(text) → EmotionState                        │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         KNOWLEDGE LAYER                                  │
│                                                                          │
│  Responsibilities:                                                       │
│    • Provide structured data (fees, HODs, contact info, scholarships)    │
│    • Provide unstructured data (policies, brochures, documents)         │
│    • Semantic search over college knowledge                              │
│    • Cache hot data                                                      │
│    • Knowledge base versioning and audit                                 │
│                                                                          │
│  MUST NOT know:                                                          │
│    • How the data is used                                                │
│    • Which channel requested the data                                    │
│    • LLM internals                                                       │
│                                                                          │
│  Modules:  KnowledgeGraph (Neo4j) │ VectorStore (Pinecone)               │
│            DocumentStore (S3) │ Cache (Redis) │ CMS (Staff UI)           │
│                                                                          │
│  Interfaces:  query_graph(query) → GraphResult                           │
│               vector_search(query, limit) → SearchResults                │
│               get_document(id) → Document                                │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          STORAGE LAYER                                   │
│                                                                          │
│  Responsibilities:                                                       │
│    • Session persistence (Redis)                                        │
│    • Conversation history (PostgreSQL)                                   │
│    • Student profiles (PostgreSQL)                                       │
│    • Caching (Redis)                                                     │
│    • File storage (S3/Minio)                                             │
│    • Vector embeddings (Pinecone/ChromaDB)                               │
│                                                                          │
│  MUST NOT know:                                                          │
│    • Business logic                                                      │
│    • LLM provider                                                        │
│                                                                          │
│  Interfaces:  SessionStore, HistoryStore, ProfileStore, Cache, FileStore │
└─────────────────────────────────────────────────────────────────────────┘
```

### The Golden Rule

> **A layer may only depend on layers below it. No layer may know the implementation details of another layer at the same level.**

Violations of this rule in the current codebase:
- `groq_service.py` (Conversation Engine) imports `Groq` SDK directly — it knows the LLM provider
- `groq_service.py` (Conversation Engine) manages rate limiting — a transport concern
- `livekit_agent.py` (Channel Adapter) contains the system prompt — a Knowledge Layer concern
- `groq_service.py` (Conversation Engine) opens SQLite connections — a Storage Layer concern

### Critical New Layers

#### Decision Engine

The Decision Engine sits between Reasoning and Planning. It answers one question:

> **What should I do about what the student needs?**

This is a separate concern because:

- Reasoning determines facts: "Student has 50k rank, 76% PCM, interested in CS."
- Decision determines action: "Recommend CSE as first choice, IT as safe choice, start admission workflow."

A real admission counselor does not just reason about the student — they *decide* what to do. A junior counselor might reason the same way as a senior one, but the senior makes better *decisions*.

**Decision Engine logic:**

```
Input: ReasoningResult
  • Student profile (rank, PCM, interest, goals, emotion)
  • Available options (branches, scholarships, hostels)
  • Constraints (budget, cutoff trends, eligibility rules)
  • Conversation stage (discovery, evaluation, decision, application)

Processing:
  • Score each option on multiple axes:
      - Rank match (does this branch historically accept this rank?)
      - Interest match (does this branch align with stated interest?)
      - Career match (placement rate, package, growth)
      - Financial match (fee vs budget, scholarship availability)
  • Weight scores based on student profile:
      - If placement is priority → placement weight = 0.5
      - If budget is priority → fee weight = 0.4
      - If unsure → balance all weights equally
  • Select top options and generate trade-off analysis
  • Attach confidence score to each recommendation

Output: Decision
  • Recommended action: "Recommend CSE, then IT"
  • Alternatives: "ECE as backup if CSE fills"
  • Confidence: 94%
  • Confidence breakdown:
      - Rank match: 85% (50k rank, CSE cutoff 35k — competitive)
      - Interest match: 95% (explicit interest in CS)
      - Career match: 92% (CSE placement 93.6%)
      - Financial match: 90% (within budget, scholarship available)
  • Next action: "Start admission workflow"
```

**Why this cannot live in the LLM prompt:**
The decision logic involves weighted scoring, constraint satisfaction, and confidence calculation. These are algorithmic, not linguistic. An LLM prompt cannot reliably compute weighted scores or maintain internal consistency across multiple axes.

#### Confidence

Every decision the system makes must include a **system confidence score** — not just LLM token probability, but a holistic confidence based on:

| Factor | Source | Weight |
|--------|--------|--------|
| Profile completeness | How many fields are filled vs missing | 0.3 |
| Data freshness | How recent are the cutoff/placement numbers | 0.1 |
| LLM confidence | Normalized token probability from the model | 0.2 |
| Knowledge coverage | Is the relevant data in our knowledge base? | 0.2 |
| Historical accuracy | How often have similar recommendations been correct? | 0.2 |

**Confidence thresholds:**

| Confidence Range | Behavior |
|-----------------|----------|
| >90% | Proceed autonomously. Full recommendation with trade-offs. |
| 70-90% | Proceed but qualify: "Based on current data, CSE is a good fit. However, last year's cutoff varied by round." |
| 50-70% | Probe for more information before deciding: "I can give you a general recommendation, but it would help if I knew your specific interest area." |
| <50% | Do not decide. Hand off to human counselor with context summary. |

**Confidence is not optional.** Without it, the system cannot know when to escalate. Every human counselor has a sense of "how sure am I about this?" The AI must too.

#### College Brain

Knowledge is not intelligence. The College Brain is a layer that understands **how this college actually works** — not just what facts are true.

**What the College Brain knows:**

```
Domain Knowledge (the "what"):
  • Fee structures for every branch
  • Placement data by company and year
  • HOD names and contact info
  ← This is the Knowledge Layer

Procedural Knowledge (the "how"):
  • How WBJEE counseling works
  • How MAKAUT affiliation affects syllabus
  • How scholarship applications are processed
  • How fee refunds work after withdrawal
  • How hostel allocation works
  • How branch change works after first year
  • How backlog exams are scheduled
  • How document verification works
  ← This is the College Brain

Tacit Knowledge (the "why"):
  • Which branches have the best peer culture for research
  • Which companies recruit which branches most aggressively
  • What students from specific boards typically struggle with
  • What scholarship schemes are commonly underutilized
  • What hidden costs students often miss
  ← This is also the College Brain (hardest to build)
```

**Implementation:**
The College Brain is not a single module. It is a collection of:

1. **Procedural rules** (deterministic: "If rank < cutoff, eligible")
2. **Workflow definitions** (state machines: admission process steps)
3. **Embedded policy documents** (vector search over official PDFs)
4. **LLM-accessible tools** (functions the LLM can call for procedural questions)
5. **Decision heuristics** (scoring rules for recommendations)

The College Brain draws from the Knowledge Layer but is not the same thing. The Knowledge Layer stores data. The College Brain knows what to *do* with it.

### Ownership Boundaries

Every module has exactly one owner — a responsibility that no other module may duplicate or override.

```
Module                Owns                      Does NOT Own
──────────────────────────────────────────────────────────────────
Voice Adapter         Audio in/out              Language detection
Channel Adapter       Channel normalization     Session management
Conversation Engine   Language, state, memory   LLM selection
Reasoning Engine      LLM routing, tool exec    Response formatting
Decision Engine       Option scoring, ranking   Knowledge retrieval
College Brain         Procedural college rules  Fact storage
Planning Engine       Response structure        Workflow state
Workflow Engine       Multi-step process mgmt   Decision making
Knowledge Layer       Fact storage, graph       LLM calling
Profile Layer         Student identity          Conversation memory
Safety Layer          Content filtering         Intent classification
Cache Layer           Hot data TTL              Data source of truth
```

A violation example: if the Conversation Engine starts modifying the student profile (Profile Layer's job), profile data will become inconsistent because two modules write to it without coordination. The rule is: **a module may read from any layer below it, but may only write to its own layer.**

### Evolution Requirements

This architecture must survive the following without redesign:

```
New departments added:
  → Add to Knowledge Graph data. College Brain rules extend automatically.

New regulations (NEP 2020, MAKAUT policy changes):
  → Update procedural rules in College Brain. No pipeline changes.

New fee structures introduced:
  → Update graph data. Cache invalidates automatically.

New admission policies (entrance exam changes):
  → Update cutoffs, eligibility rules in College Brain.

New campuses added:
  → New graph namespace. College Brain learns campus-specific rules.

New languages needed:
  → Add language model to Language Detector. Prompt translations in Prompt Store.

New AI models released:
  → Implement LLMProvider interface. Router picks best model per task.

New telephony provider (LiveKit → Dograh → future):
  → Implement VoiceAdapter interface. Conversation Engine unchanged.

New channels (kiosk, CRM, mobile app):
  → Implement Channel Adapter. Event bus handles routing.

Scaling from 1 to 10 colleges:
  → Tenant-aware Knowledge Graph. College Brain parameterized by college ID.
```

**The test for every architectural decision:**

> If I have to touch more than two modules to accommodate a change in college policy, the architecture is wrong.

---

## 5. Future Architecture — Complete Design

### 5.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        API GATEWAY                                       │
│              rate limiting · auth · routing · TLS · WAF                  │
│              (nginx / Caddy → Kong / Tyk as needed)                      │
└────────┬─────────────┬──────────────┬──────────────┬────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌──────────┐ ┌──────────────┐
│ Web Adapter │ │Voice Adapter│ │WhatsApp  │ │ Mobile/Kiosk │
│ (FastAPI)   │ │(LiveKit,    │ │Adapter   │ │ Adapter      │
│             │ │ later       │ │(Twilio   │ │ (FastAPI)    │
│             │ │ Dograh)     │ │ WhatsApp)│ │              │
└──────┬──────┘ └──────┬──────┘ └────┬─────┘ └──────┬───────┘
       │               │             │               │
       └───────────────┼─────────────┼───────────────┘
                       │             │
                       ▼             ▼
              ┌──────────────────────────┐
              │      EVENT BUS           │
              │   (Redis Streams)        │
              │                          │
              │ Topics:                  │
              │  counseling.request      │
              │  counseling.response     │
              │  telemetry.event         │
              │  system.cache.invalidate │
              │  voice.stt.ready         │
              │  voice.tts.request       │
              └────────────┬─────────────┘
                           │
              ┌────────────▼─────────────┐
               │   CONVERSATION ENGINE    │
               │   (stateless workers)    │
               │                          │
               │ ┌──────────────────────┐ │
               │ │   SUPERVISOR AGENT   │ │
               │ │  observe → plan →    │ │
               │ │  act → remember      │ │
               │ └────────┬──┬──┬───────┘ │
               │          │  │  │          │
               │ ┌────────▼──▼──▼───────┐ │
               │ │  SPECIALIST AGENTS    │ │
               │ │ Fees · Placement     │ │
               │ │ Admission · Counselling│ │
               │ │ College Info · Profile│ │
               │ └──────────────────────┘ │
               └────────────┬─────────────┘
                            │
               ┌────────────▼─────────────┐
               │     DECISION ENGINE      │
               │   What should I do?      │
               │   Score · Rank · Decide  │
               │   with Confidence        │
               └────────────┬─────────────┘
                            │
               ┌────────────▼─────────────┐
               │     REASONING ENGINE     │
               │                          │
               │ ┌──────┐ ┌──────┐ ┌────┐ │
               │ │LLM   │ │ Tool │ │Wkfl│ │
               │ │Router│ │Exec. │ │Eng.│ │
               │ └──────┘ └──────┘ └────┘ │
               └────────────┬─────────────┘
                            │
               ┌────────────▼─────────────┐
               │      COLLEGE BRAIN       │
               │  How this college works  │
               │  · Procedural rules      │
               │  · Workflow definitions  │
               │  · Policy understanding  │
               │  · Decision heuristics   │
               └────────────┬─────────────┘
                            │
               ┌────────────▼─────────────┐
               │      KNOWLEDGE LAYER     │
               │                          │
               │  Graph  Vector  Document │
               │  (Neo4j)(Pinecone) (S3)  │
               │         │ Cache (Redis)  │
               │         │ CMS (Staff UI) │
               └────────────┬─────────────┘
                           │
              ┌────────────▼─────────────┐
              │       STORAGE LAYER      │
              │                          │
              │ Redis  PostgreSQL  S3    │
              │ (caches,  (history,  (files,│
              │  sessions) profiles) audios)│
              └──────────────────────────┘
```

### 5.2 Detailed Subsystem Design

#### 5.2.1 Channel Adapters

Each channel adapter is a **thin, stateless** process that:

1. Accepts channel-native input
2. Normalizes to `MessageEnvelope`
3. Publishes to `counseling.request` event topic
4. Subscribes to `counseling.response` for that session
5. Converts response back to channel-native output

**Web Adapter (FastAPI):**
```
POST /api/query  →  MessageEnvelope  →  EventBus  →  HTTP Response
WS /ws/chat      →  MessageEnvelope  →  EventBus  →  WS Messages
```

**Voice Adapter (LiveKit Agent):**
```
Microphone → VAD → STT → MessageEnvelope → EventBus → 
EventBus → Response → TTS → Speaker
```

**Voice Adapter Contract:**
```python
class VoiceAdapter(ABC):
    """Any voice provider must implement this interface."""
    
    @abstractmethod
    async def transcribe(self, audio: AudioFrame) -> str: ...
    
    @abstractmethod
    async def synthesize(self, text: str, lang: str) -> AsyncIterator[AudioFrame]: ...
    
    @abstractmethod
    async def detect_vad(self, audio: AudioFrame) -> bool: ...
    
    @property
    @abstractmethod
    def supported_languages(self) -> List[str]: ...
```

**Why this matters:** When switching from LiveKit to Dograh, you only rewrite `VoiceAdapter` implementations. The Conversation Engine, Reasoning Engine, and Knowledge Layer are untouched.

#### 5.2.2 Event Bus

**Technology:** Redis Streams (primary) → RabbitMQ/NATS (future)

**Why Redis Streams:**
- No additional infrastructure (already adding Redis for sessions/cache)
- Consumer groups for competing workers
- Message acknowledgment and replay
- Dead-letter handling for failed messages
- Built-in TTL

**Event Catalog:**

| Event | Producer | Consumer(s) | Payload |
|-------|----------|-------------|---------|
| `counseling.request` | Channel Adapter | Conversation Engine Worker | `MessageEnvelope` |
| `counseling.response` | Conversation Engine | Channel Adapter (by session_id) | `ResponseEnvelope` |
| `counseling.supervisor.action` | Supervisor Agent | Specialist Agent | `AgentTask` |
| `counseling.specialist.result` | Specialist Agent | Supervisor Agent | `AgentResult` |
| `telemetry.event` | Any | Observability Service | `TelemetryEvent` |
| `system.cache.invalidate` | CMS / Admin | All workers | `CacheInvalidation` |
| `voice.stt.interim` | Voice Adapter | (logging/analytics) | `STTInterimResult` |
| `voice.stt.final` | Voice Adapter | Conversation Engine | `STTFinalResult` |
| `voice.tts.request` | Conversation Engine | Voice Adapter | `TTSRequest` |

#### 5.2.3 Conversation Engine (Supervisor Agent)

This is the most critical architectural change. Replace the flat pipeline with a **cognitive loop**.

```
process(message):
    1. Load session (Redis)
    2. Detect language
    3. Run OBSERVE phase:
       a. Extract explicit content
       b. Infer implicit intent ("65%" → eligibility concern)
       c. Detect emotional state (sentiment analysis)
       d. Determine conversation stage (discovery/evaluation/decision)
       e. Assess profile completeness
    4. Run PLAN phase:
       a. Based on observations + student profile + conversation history
       b. Generate a plan: [action, target, params]
       c. Possible actions:
          - ANSWER: respond directly (greeting, simple fact)
          - DELEGATE: send to specialist agent (fee query → Fees Agent)
          - PROBE: ask clarifying question ("Which branch are you interested in?")
          - REASSURE: respond empathetically to emotional content
          - COUNSEL: initiate counseling flow (branch recommendation)
          - WORKFLOW: start a multi-step process (admission workflow)
          - ESCALATE: hand off to human
    5. Execute ACT phase:
       a. If ANSWER → generate response directly
       b. If DELEGATE → publish AgentTask to specialist agent topic
       c. If PROBE → generate clarifying question
       d. etc.
    6. Execute REMEMBER phase:
       a. Update student profile with any new information
       b. Update conversation state (domain slots, resolved intents)
       c. Update goal tracking
       d. Persist to Redis + PostgreSQL
    7. Publish ResponseEnvelope to response topic
    8. Publish TelemetryEvent to telemetry topic
```

**Conversation State (Redis):**
```json
{
  "session_id": "uuid",
  "student_id": "extracted_or_null",
  "channel": "voice",
  "language": "en",
  "stage": "evaluation",
  "emotional_state": {
    "primary": "anxious",
    "confidence": 0.7
  },
  "profile": {
    "rank": 12500,
    "pcm_percentage": 76,
    "board": "WBCHSE",
    "state": "West Bengal",
    "category": "general",
    "preferred_branches": ["CSE", "AIML"],
    "interests": ["AI", "programming"],
    "financial_concern": true,
    "hostel_needed": true,
    "scholarship_needed": true,
    "goals": {
      "primary": "get_admission_in_CSE",
      "secondary": "avail_scholarship",
      "resolved": false
    }
  },
  "active_domain": "fees",
  "domain_slots": {
    "fees": {
      "branch": "CSE",
      "fee_type": "total",
      "resolved": false
    }
  },
  "visit_order": ["fees", "admission"],
  "history": [
    {"role": "user", "content": "I got 76% PCM", "timestamp": "..."},
    {"role": "assistant", "content": "That's a good score...", "timestamp": "..."}
  ],
  "created_at": "2026-07-17T10:00:00Z",
  "last_active": "2026-07-17T10:05:00Z",
  "session_timeout": 1800
}
```

#### 5.2.4 Specialist Agents

Each specialist agent is a **self-contained module** with:

- Its own system prompt (domain-specific)
- Its own subset of knowledge tools
- Its own state machine for multi-turn tasks

**Initial Specialist Agents:**

| Agent | Domain | Tools | State Machine |
|-------|--------|-------|---------------|
| **Fees Agent** | Fee structures, payment plans, installments, scholarships | `get_fee_by_branch()`, `get_scholarship_by_category()` | Branch→FeeType (total/semester/admission)→Installment→Scholarship |
| **Placement Agent** | Placement stats, recruiters, packages, preparation | `get_placement_by_branch()`, `get_top_recruiters()` | Branch→Stats→Companies→Preparation |
| **Admission Agent** | Eligibility, cutoffs, documents, process, deadlines | `get_eligibility()`, `get_cutoff()`, `get_documents()`, `get_process()` | Eligibility→Documents→Process→Deadline |
| **Counselling Agent** | Branch recommendations, career guidance | `get_branch_list()`, `get_career_prospects()`, `get_profile()` | Interest→Recommendation→Comparison→Decision |
| **College Info Agent** | HODs, faculty, facilities, hostel, safety, contact | `get_hod()`, `get_facility()`, `get_hostel_info()`, `get_contact()` | Category→Details |
| **Profile Agent** | Extract, update, persist student profile | `extract_from_conversation()`, `update_profile()`, `get_profile()` | Never finishes — runs continuously across sessions |
| **Escalation Agent** | Human handoff detection, summary generation | `detect_escalation()`, `generate_summary()` | Monitor→Detect→Summarize→Handoff |

**Agent Protocol (event-based):**

```python
@dataclass
class AgentTask:
    task_id: str
    session_id: str
    agent_name: str
    action: str
    params: dict
    context: dict  # conversation summary + student profile
    timestamp: float

@dataclass
class AgentResult:
    task_id: str
    session_id: str
    agent_name: str
    response: str
    profile_updates: dict
    state_updates: dict
    follow_up_suggestions: list[str]
    confidence: float
    timestamp: float
```

#### 5.2.5 Knowledge Layer

**Three-tier knowledge:**

| Tier | Technology | Data | Update Frequency | Maintained By |
|------|------------|------|-----------------|---------------|
| **Knowledge Graph** | Neo4j (AuraDB Free) | Entities + relationships: branches, HODs, fees, placements, scholarships | Monthly or when data changes | College staff via CMS UI |
| **Vector Store** | Pinecone Serverless | Unstructured documents: policies, brochures, faculty profiles | Quarterly or when documents are updated | College staff via document upload |
| **Cache** | Redis | Hot data: frequently accessed fee structures, contact info | Minutes (automatic TTL) | System (auto-populated) |

**Graph Schema (Neo4j):**

```
(:College {name, short_name, address, phone, email, website, established, naac, nirf})
  -[:OFFERS]-> (:Branch {code, full_name, intake, nba_accredited})
  -[:HAS_HOD]-> (:Faculty {name, email, qualification, specialization})
  -[:HAS_FEE]-> (:FeeStructure {total, per_semester, admission, tuition, development})
  -[:HAS_PLACEMENT]-> (:Placement {rate, avg_package, max_package, year})
  -[:HAS_RECRUITER]-> (:Company {name, sector, avg_package})
  -[:ELIGIBLE_FOR]-> (:Scholarship {name, amount, eligibility, category})
  -[:BELONGS_TO]-> (:Department {name, code})
  -[:HAS_FACILITY]-> (:Facility {type, name, capacity, timings})

(:Student {phone, name, rank, pcm, board, state, category, interest})
  -[:INQUIRED_ABOUT]-> (:Branch)
  -[:APPLIED_FOR]-> (:Scholarship)
  -[:HAS_SESSION]-> (:Conversation {session_id, timestamp, duration})
```

**Why a graph?**
- "Branches with placement > 90% AND fee < 6,00,000" → one Cypher query
- "Which HODs are in NBA-accredited departments?" → relationship traversal
- "What scholarships is this student eligible for?" → path query based on profile attributes
- College staff can visually explore: "Show me all branches, their placement rates, and HODs"

**Staff CMS (Knowledge Management UI):**
- Web-based form interface (separate React app or embedded in main frontend)
- CRUD operations for: branches, HODs, fees, placements, scholarships, facilities, policies
- No coding required — dropdowns, text inputs, auto-save
- All changes versioned and audited
- Changes propagate to cache within 60 seconds (cache invalidation event)
- Preview mode: see how the AI will respond with new data before committing

#### 5.2.6 Reasoning Engine (LLM Router)

**Tiered LLM Architecture:**

```
Request from Conversation Engine
              │
              ▼
       ┌──────────────┐
       │ TIER 1       │  Router Classifier
       │ Groq Llama   │  Intent detection, simple lookups
       │ 3.1 8B       │  Latency: <100ms, Cost: $0.05/M
       └──────┬───────┘
              │
      ┌───────┴───────┐
      │               │
      ▼               ▼
┌──────────────┐ ┌──────────────┐
│ TIER 2       │ │ TIER 3       │
│ GPT-4o-mini  │ │ Claude Sonnet│
│ Groq 70B     │ │ 4 / GPT-4o  │
│ Structured   │ │ Complex      │
│ lookups,     │ │ counseling,  │
│ tool calling │ │ emotion      │
│ Latency:     │ │ detection,   │
│ 200-500ms    │ │ multi-step   │
│ Cost:        │ │ reasoning    │
│ $0.30/M      │ │ Latency:     │
│              │ │ 500-2000ms   │
│              │ │ Cost: $3-15/M│
└──────────────┘ └──────────────┘
```

**Router Logic:**

```python
def route_request(request) -> LLMTier:
    """Decide which LLM tier to use based on request characteristics."""
    
    # Simple lookups → Tier 1 (fast, cheap)
    if request.intent in {GREETING, FEE_LOOKUP, CONTACT_INFO, HOD_INFO}:
        return TIER_1
        
    # Structured lookups with tool calling → Tier 2
    if request.intent in {BRANCH_COMPARISON, SCHOLARSHIP_CHECK, PLACEMENT_DETAILS}:
        return TIER_2
    
    # Complex reasoning → Tier 3
    if request.needs_counseling or request.has_emotional_content or request.needs_branch_recommendation:
        return TIER_3
    
    # Default to Tier 2 (safe middle ground)
    return TIER_2
```

**Provider Abstraction:**

```python
class LLMProvider(ABC):
    """Any LLM provider must implement this interface."""
    
    @abstractmethod
    async def complete(self, prompt: str, system: str, tools: list[ToolDef]) -> LLMResponse: ...
    
    @abstractmethod
    async def stream(self, prompt: str, system: str, tools: list[ToolDef]) -> AsyncIterator[str]: ...
    
    @abstractmethod
    async def is_available(self) -> bool: ...

class GroqProvider(LLMProvider): ...   # Groq API
class OpenAIProvider(LLMProvider): ...  # OpenAI API
class AnthropicProvider(LLMProvider): ...  # Anthropic API
class FallbackProvider(LLMProvider): ...  # Hardcoded fallback messages
```

**This enables:**
- Switch providers without changing business logic
- A/B test different providers on the same query
- Cost optimization (use cheap model for 80% of queries, expensive only for 20%)
- Graceful degradation (if GPT-4o is down, fall back to Groq 70B, then to Groq 8B)

#### 5.2.7 Workflow Engine

Certain admission processes follow a defined sequence of steps. The Workflow Engine manages these.

**Workflows to support:**

| Workflow | Steps | Duration |
|----------|-------|----------|
| Admission | Check eligibility → Submit documents → Pay fee → Confirm enrollment | Multi-session |
| Scholarship | Check eligibility → Apply → Document verification → Approval | Multi-session |
| Hostel | Check availability → Choose room type → Pay deposit → Move in | Single session |
| Backlog | Identify failed subjects → Supplementary exam schedule → Apply → Pay fee | Multi-session |
| Education Loan | Check eligibility → Document list → Bank application → Approval | Multi-session |

**Workflow State Machine:**

```python
class WorkflowState:
    workflow_type: str  # "admission", "scholarship", etc.
    current_step: int
    steps: list[WorkflowStep]
    completed: bool
    context: dict  # data collected during workflow
    
class WorkflowStep:
    name: str
    status: Literal["pending", "in_progress", "completed", "blocked"]
    required_documents: list[str]
    deadline: datetime | None
    dependencies: list[int]  # step indices that must be completed first
```

**Example — Admission Workflow:**
```
Step 1: Check Eligibility
  Required: rank, PCM%, board, category
  Action: query cutoff DB → eligible/not eligible
  
Step 2: Suggest Branches (if eligible)
  Action: based on rank + interest → recommended branches

Step 3: Document Verification
  Required: marksheet, id proof, rank card, photo
  Action: list documents, confirm student has them

Step 4: Fee Payment
  Action: show fee structure, offer payment plan options

Step 5: Enrollment Confirmation
  Action: confirm enrollment, share next steps
```

#### 5.2.8 Observability Stack

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│    Traces       │  │    Metrics      │  │     Logs        │
│ OpenTelemetry   │  │   Prometheus    │  │  Structured     │
│ → Jaeger/Grafana│  │ → Grafana       │  │  → Loki/ELK     │
│   Tempo         │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                   │                    │
         └───────────────────┼────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   LangFuse      │  LLM-specific observability
                    │  (self-hosted)  │  Prompt versions, token counts,
                    │                 │  cost tracking, quality scoring
                    └─────────────────┘
```

**Key metrics to track (per conversation, per channel):**

| Metric | What | Target |
|--------|------|--------|
| STT latency | Time from speech end to transcript | <500ms p95 |
| LLM TTFT | Time to first token | <300ms p95 (Tier 1), <1000ms (Tier 3) |
| TTS latency | Time from text to first audio chunk | <200ms p95 |
| End-to-end latency | Full round trip | <3000ms p95 |
| Token usage | Input + output tokens per conversation | <2000 average |
| Cost per conversation | API costs | <$0.10 average |
| Active sessions | Concurrent conversations | Monitor for scaling |
| Error rate | LLM failures, STT failures, TTS failures | <1% |
| Hallucination rate | Guard-flagged responses | <0.1% |
| Handoff rate | Escalation to human | <5% |
| Language distribution | % English, Hindi, Bengali | Varies |

---

## 6. Module Responsibilities

### 6.1 Presentation Layer

| Module | Responsibility |
|--------|---------------|
| `web/adapter.py` | FastAPI routes for web chat. Normalize HTTP/WS to MessageEnvelope. |
| `voice/adapter.py` | LiveKit agent implementation. Audio → STT → MessageEnvelope → EventBus → Response → TTS → Audio. |
| `voice/interface.py` | Abstract VoiceAdapter interface. STTProvider, TTSProvider, VADProvider abstractions. |
| `whatsapp/adapter.py` | Twilio WhatsApp webhook handler. Normalize to MessageEnvelope. |
| `mobile/adapter.py` | REST API for mobile app. JWT auth, MessageEnvelope normalization. |
| `kiosk/adapter.py` | Kiosk mode. Touch-friendly interaction, session management. |

### 6.2 Channel Adapter Layer

| Module | Responsibility |
|--------|---------------|
| `channel/message.py` | MessageEnvelope and ResponseEnvelope data models. |
| `channel/bus_publisher.py` | Publish to Redis Streams. Handle ack/nack. |
| `channel/bus_subscriber.py` | Subscribe to response events by session_id. |
| `channel/rate_limiter.py` | Per-channel, per-user rate limiting. |

### 6.3 Conversation Engine

| Module | Responsibility |
|--------|---------------|
| `engine/supervisor.py` | Observe → Plan → Act → Remember loop. The "brain." |
| `engine/state.py` | ConversationState data model. Session load/save operations. |
| `engine/language.py` | Language detection (script, FastText, fallback). Language enforcement. |
| `engine/intent.py` | Intent detection (regex + ML classifier). Combined approach. |
| `engine/emotion.py` | Emotional state detection from text. Sentiment + urgency + hesitation. |
| `engine/profile.py` | Student profile extraction, update, persistence. |
| `engine/goals.py` | Goal tracking. Conversation stage progression. |
| `engine/clarification.py` | Ambiguity detection. Clarifying question generation. |
| `engine/follow_up.py` | Cross-domain follow-up resolution. Recency-based context. |
| `engine/hallucination_guard.py` | Entity verification against knowledge. Reject fabricated data. |

### 6.4 Decision Engine

| Module | Responsibility |
|--------|---------------|
| `decision/scorer.py` | Score each option (branch, scholarship, etc.) on multiple weighted axes. |
| `decision/ranker.py` | Rank options by composite score. Generate trade-off analysis. |
| `decision/confidence.py` | Compute system confidence per recommendation. Profile completeness, data freshness, LLM confidence, knowledge coverage, historical accuracy. |
| `decision/thresholds.py` | Confidence threshold configuration. Autonomous vs qualified vs probe vs handoff. |

### 6.5 College Brain

| Module | Responsibility |
|--------|---------------|
| `brain/procedures.py` | Deterministic procedural rules: eligibility calculation, cutoff comparison, fee computation. |
| `brain/policies.py` | Policy document ingestion and query. Vector search over official PDFs (MAKAUT rules, AICTE approvals, scholarship schemes). |
| `brain/heuristics.py` | Decision heuristics for recommendations: branch ranking logic, scholarship matching, hostel allocation rules. |
| `brain/workflows.py` | Workflow definitions (shared with Workflow Engine). Admission process, scholarship application, hostel booking, backlog process. |

### 6.6 Specialist Agents
| `agents/counselling.py` | Branch recommendations, career guidance, interest-based advising. |
| `agents/college_info.py` | HODs, faculty, facilities, hostel, safety, contact info. |
| `agents/profile.py` | Continuous profile extraction from conversation. |
| `agents/escalation.py` | Human handoff detection and summary generation. |

### 6.5 Reasoning Engine

| Module | Responsibility |
|--------|---------------|
| `reasoning/router.py` | Route to appropriate LLM tier based on intent complexity. |
| `reasoning/providers/groq.py` | Groq LLM provider implementation. |
| `reasoning/providers/openai.py` | OpenAI LLM provider implementation. |
| `reasoning/providers/anthropic.py` | Anthropic LLM provider implementation. |
| `reasoning/providers/fallback.py` | Hardcoded fallback responses. |
| `reasoning/tools/registry.py` | Tool/function registry. Register, lookup, execute tools. |
| `reasoning/tools/fees.py` | Fee lookup tools (available to LLM via function calling). |
| `reasoning/tools/placement.py` | Placement lookup tools. |
| `reasoning/tools/contacts.py` | Contact info lookup tools. |
| `reasoning/prompts/manager.py` | Centralized prompt store. Versioned prompts. Template engine. |

### 6.6 Knowledge Layer

| Module | Responsibility |
|--------|---------------|
| `knowledge/graph.py` | Neo4j graph client. Query builder for college domain. |
| `knowledge/vector.py` | Pinecone/ChromaDB vector store client. Semantic search. |
| `knowledge/documents.py` | Document storage (S3/Minio). Upload, retrieve, index. |
| `knowledge/cache.py` | Redis cache client. Cache-aside pattern for hot data. |
| `knowledge/cms/` | Staff CMS UI. React frontend for knowledge management. |
| `knowledge/cms/api.py` | CMS REST API. CRUD for all knowledge domains. |
| `knowledge/cms/audit.py` | Change tracking. Version history. Rollback support. |

### 6.7 Storage Layer

| Module | Responsibility |
|--------|---------------|
| `storage/redis.py` | Redis client. Session store, cache, event bus. |
| `storage/postgres.py` | PostgreSQL client. Conversation history, student profiles. |
| `storage/minio.py` | S3-compatible storage. Audio files, uploaded documents. |

### 6.8 Observability

| Module | Responsibility |
|--------|---------------|
| `observability/tracing.py` | OpenTelemetry instrumentation. Spans for pipeline stages. |
| `observability/metrics.py` | Prometheus metrics. Histograms, counters, gauges. |
| `observability/logging.py` | Structured JSON logging. Correlation IDs. |
| `observability/llm.py` | LangFuse integration. Prompt tracking, cost calculation. |
| `observability/alerts.py` | Alert rules. Error rate, latency, cost thresholds. |

---

## 7. Interface Definitions

### 7.1 Channel Adapter → Event Bus

```python
@dataclass
class MessageEnvelope:
    """Universal message format that all channel adapters produce."""
    
    message_id: str                  # UUID
    session_id: str                  # Server-generated UUID
    student_id: str | None           # If identified (phone number, email)
    channel: Literal["web", "voice", "whatsapp", "mobile", "kiosk", "crm"]
    channel_metadata: dict           # Channel-specific (user-agent, phone number, etc.)
    
    # Content
    text: str                        # The user's message text
    audio: bytes | None              # Raw audio (voice channel only)
    audio_format: str | None         # "ulaw", "pcm16", "opus"
    
    # Context
    language: str | None             # Detected or provided language
    timestamp: float                 # Unix timestamp
    client_version: str | None       # For mobile app compatibility
```

```python
@dataclass
class ResponseEnvelope:
    """Universal response format that all channel adapters consume."""
    
    message_id: str                  # Correlates to request
    session_id: str
    channel: str
    
    # Response content
    text: str                        # Text response (all channels)
    audio: bytes | None              # Synthesized audio (voice channel only)
    audio_format: str | None
    
    # Metadata
    language: str
    source: Literal["structured", "rag_llm", "fallback", "agent"]
    latency_ms: int
    tokens_used: int | None
    cost: float | None
    
    # Confidence
    confidence: float | None             # System confidence score (0-1)
    confidence_breakdown: dict | None    # Per-factor confidence for transparency
    
    # Actions
    suggested_actions: list[dict] | None   # Buttons, quick replies (web/whatsapp)
    should_end_session: bool               # Goodbye, session complete
    should_escalate: bool                  # Human handoff needed (True if confidence < threshold)
    escalate_reason: str | None
```

### 7.2 Conversation Engine → Specialist Agents

```python
@dataclass
class AgentTask:
    """Task from Supervisor Agent to Specialist Agent."""
    
    task_id: str
    session_id: str
    agent_name: str
    action: str                         # "provide_info", "recommend", "compare", "inquire"
    params: dict                        # Domain-specific parameters
    language: str
    
    # Context for the specialist
    student_profile: dict
    conversation_summary: str           # Last N turns
    active_workflow: dict | None        # Current workflow state if any
    
    # Instructions
    max_tokens: int = 500
    tools_enabled: list[str] | None     # Which tools this agent can use
```

```python
@dataclass
class AgentResult:
    """Result from Specialist Agent to Supervisor Agent."""
    
    task_id: str
    session_id: str
    agent_name: str
    
    response: str                        # The agent's response text
    confidence: float                    # System confidence score (0-1)
    confidence_breakdown: dict           # {"rank_match": 0.85, "interest_match": 0.95, ...}
    
    profile_updates: dict               # New profile information discovered
    state_updates: dict                 # Updates to conversation state
    follow_up_suggestions: list[str]    # "Ask about scholarships", "Compare with EE"
    suggested_actions: list[dict]       # "I can help you apply for scholarship"
    
    needs_clarification: bool           # "Which branch?"
    clarification_question: str | None
    
    tools_called: list[ToolCall]        # For audit and cost tracking
    tokens_used: int
    cost: float
    latency_ms: int
```

### 7.3 Reasoning Engine → LLM Providers

```python
@dataclass
class LLMRequest:
    """Request to an LLM provider."""
    
    system_prompt: str
    messages: list[dict]               # [{"role": "user"/"assistant", "content": str}]
    tools: list[ToolDef]               # Function definitions for tool calling
    max_tokens: int = 1024
    temperature: float = 0.3           # Lower for factual queries
    timeout: float = 10.0
    stream: bool = False
```

```python
@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    
    content: str
    tool_calls: list[ToolCall] | None
    finish_reason: str
    usage: dict                        # {"prompt_tokens": N, "completion_tokens": N}
    latency_ms: int
    provider: str                      # "groq", "openai", "anthropic"
    model: str                         # "llama-3.1-8b", "gpt-4o", "claude-sonnet-4"
```

```python
# Abstract provider interface
class LLMProvider(ABC):
    async def complete(self, request: LLMRequest) -> LLMResponse: ...
    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMResponse]: ...
    async def is_available(self) -> bool: ...
    @property
    def name(self) -> str: ...
    @property
    def model(self) -> str: ...
    @property
    def cost_per_token(self) -> tuple[float, float]: ...  # (input, output)
```

### 7.4 Knowledge Layer

```python
@dataclass
class KnowledgeQuery:
    """Query to the knowledge layer."""
    
    query: str                          # Natural language query
    domain: str | None                  # "fees", "placement", "hods", etc.
    filters: dict | None                # {"branch": "CSE", "year": 2025}
    language: str
    max_results: int = 5
    
@dataclass
class KnowledgeResult:
    """Result from the knowledge layer."""
    
    source: Literal["graph", "vector", "document", "cache"]
    content: str
    confidence: float
    metadata: dict                      # Source references for audit
    query_latency_ms: int

class KnowledgeGraph(ABC):
    async def query(self, query: str, params: dict) -> list[KnowledgeResult]: ...
    async def get_entity(self, entity_type: str, id: str) -> dict: ...
    async def get_relationship(self, from_entity: str, to_entity: str) -> list: ...

class VectorStore(ABC):
    async def search(self, query: str, limit: int, filters: dict) -> list[KnowledgeResult]: ...
    async def index(self, documents: list[dict]): ...

class Cache(ABC):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int): ...
    async def invalidate(self, pattern: str): ...
```

### 7.5 Storage Layer

```python
class SessionStore(ABC):
    async def get(self, session_id: str) -> ConversationState | None: ...
    async def set(self, session_id: str, state: ConversationState, ttl: int): ...
    async def delete(self, session_id: str): ...
    async def touch(self, session_id: str, ttl: int): ...

class HistoryStore(ABC):
    async def append(self, session_id: str, turn: dict): ...
    async def get_history(self, session_id: str, limit: int) -> list[dict]: ...
    async def get_by_student(self, student_id: str, limit: int) -> list[dict]: ...

class ProfileStore(ABC):
    async def get(self, student_id: str) -> dict | None: ...
    async def upsert(self, student_id: str, profile: dict): ...
    async def search(self, query: dict) -> list[dict]: ...
```

---

## 8. Data Flow & Sequence Diagrams

### 8.1 Simple Query (Fee Lookup via Web Chat)

```
Web Browser                    Web Adapter               Event Bus             Conversation Engine           Knowledge Layer
    │                              │                        │                        │                          │
    │  POST /api/query             │                        │                        │                          │
    │  {text: "CSE fee"}           │                        │                        │                          │
    │─────────────────────────────>│                        │                        │                          │
    │                              │  MessageEnvelope       │                        │                          │
    │                              │  → counseling.request  │                        │                          │
    │                              │───────────────────────>│                        │                          │
    │                              │                        │  Pick up by worker     │                          │
    │                              │                        │───────────────────────>│                          │
    │                              │                        │                        │  OBSERVE                 │
    │                              │                        │                        │  ── detect language: en  │
    │                              │                        │                        │  ── route intent: fees  │
    │                              │                        │                        │  ── no emotion detected │
    │                              │                        │                        │                          │
    │                              │                        │                        │  PLAN                    │
    │                              │                        │                        │  ── action: DELEGATE    │
    │                              │                        │                        │  ── agent: Fees Agent   │
    │                              │                        │                        │                          │
    │                              │                        │  AgentTask             │                          │
    │                              │                        │  → Fees Agent          │                          │
    │                              │                        │──────────────────────────────────────────────────>│
    │                              │                        │                        │                          │
    │                              │                        │                        │                          │  get_fee("CSE")
    │                              │                        │                        │                        ──│───────>│
    │                              │                        │                        │                          │ │       │
    │                              │                        │                        │                          │ │ CSE:  │
    │                              │                        │                        │                          │<── ─ ─ │
    │                              │                        │                        │                          │ 604700 │
    │                              │                        │  AgentResult           │                          │        │
    │                              │                        │  ← Fees Agent          │                          │        │
    │                              │                        │<──────────────────────────────────────────────────│
    │                              │                        │                        │                          │
    │                              │                        │                        │  REMEMBER                │
    │                              │                        │                        │  ── update state        │
    │                              │                        │                        │  ── update profile (if  │
    │                              │                        │                        │      any new info)      │
    │                              │                        │                        │                          │
    │                              │                        │  ResponseEnvelope      │                          │
    │                              │                        │  ← counseling.response │                          │
    │                              │                        │<───────────────────────│                          │
    │                              │                        │                        │                          │
    │  200 OK                      │                        │                        │                          │
    │  {text: "CSE total fee      │                        │                        │                          │
    │   is 6,04,700..."}          │                        │                        │                          │
    │<────────────────────────────│                        │                        │                          │
```

### 8.2 Counseling Flow (Complex Multi-Turn)

```
Student                             Supervisor                    Profile Agent    Counselling Agent   Knowledge
  │                                      │                            │                  │                │
  │ "I got 65% PCM"                      │                            │                  │                │
  │─────────────────────────────────────>│                            │                  │                │
  │                                      │ OBSERVE                    │                  │                │
  │                                      │ text: "I got 65%"          │                  │                │
  │                                      │ implicit: worried about    │                  │                │
  │                                      │   eligibility              │                  │                │
  │                                      │ emotion: anxious (0.6)     │                  │                │
  │                                      │ stage: discovery           │                  │                │
  │                                      │ profile: missing rank,     │                  │                │
  │                                      │   board, interest          │                  │                │
  │                                      │                            │                  │                │
  │                                      │ PLAN: PROBE + COUNSEL      │                  │                │
  │                                      │ Need more profile info     │                  │                │
  │                                      │ before recommending        │                  │                │
  │                                      │                            │                  │                │
  │ "65% is a good score. Are you        │                            │                  │                │
  │  from West Bengal board? Do you      │                            │                  │                │
  │  have your WBJEE rank?"              │                            │                  │                │
  │<─────────────────────────────────────│                            │                  │                │
  │                                      │                            │                  │                │
  │ "Yes, WB board. My rank is 35000."   │                            │                  │                │
  │─────────────────────────────────────>│                            │                  │                │
  │                                      │ OBSERVE                    │                  │                │
  │                                      │ profile: rank=35000,       │                  │                │
  │                                      │   board=WBCHSE             │                  │                │
  │                                      │ emotion: still anxious     │                  │                │
  │                                      │                            │                  │                │
│                                      │ PLAN: COUNSEL              │                  │                │
│                                      │ Eligible for admission     │                  │                │
│                                      │ Recommend branches         │                  │                │
│                                      │ based on rank+interest     │                  │                │
│                                      │                            │                  │                │
│                                      │───────────────AgentTask──>│                  │                │
│                                      │                            │                  │                │
│                                      │<──────────────AgentResult─│                  │                │
│                                      │   confidence: 0.88         │   recommend      │                │
│                                      │   breakdown: {...}         │   branches ───>  │                │
│                                      │                            │                  │                │
│                                      │ DECIDE                     │                  │                │
│                                      │ ┌─ Confidence: 88%        │                  │                │
│                                      │ │  (rank=85%, interest=95%,│                  │                │
│                                      │ │   career=90%, finance=80%)│                 │                │
│                                      │ │  Above 70% → proceed    │                  │                │
│                                      │ │  with qualified rec.    │                  │                │
│                                      │ └─────────────────────────│                  │                │
│                                      │                            │                  │                │
│                                      │ REMEMBER                   │                  │                │
│                                      │ profile: rank=35000        │                  │                │
│                                      │ goal: get_admission        │                  │                │
│                                      │ stage: evaluation          │                  │                │
│                                      │                            │                  │                │
│ "With 35000 rank, you can            │                            │                  │                │
  │  get CSE, IT, or ECE at BCREC.       │                            │                  │                │
  │  What are you interested in?         │                            │                  │                │
  │  Computers? Electronics?"            │                            │                  │                │
  │<─────────────────────────────────────│                            │                  │                │
  │                                      │                            │                  │                │
  │ "I like computers. What about        │                            │                  │                │
  │  placements?"                        │                            │                  │                │
  │─────────────────────────────────────>│                            │                  │                │
  │                                      │ PLAN: DELEGATE to          │                  │                │
  │                                      │ Placement Agent for CSE    │                  │                │
```

### 8.3 Voice Call Lifecycle

```
Phone                        Twilio                 LiveKit Adapter       Event Bus        Conversation Engine
  │                            │                        │                    │                   │
  │ Call connects              │                        │                    │                   │
  │───────────────────────────>│                        │                    │                   │
  │                            │ SIP Media Stream       │                    │                   │
  │                            │───────────────────────>│                    │                   │
  │                            │                        │ session_start      │                   │
  │                            │                        │───────────────────>│                   │
  │                            │                        │                    │                   │
  │ ── "Hello, I want to       │                        │                    │                   │
  │     know about admission"  │                        │                    │                   │
  │───────────────────────────>│                        │                    │                   │
  │                            │ Audio frames (μ-law)   │                    │                   │
  │                            │───────────────────────>│                    │                   │
  │                            │                        │ VAD: speech end    │                   │
  │                            │                        │ STT: transcript    │                   │
  │                            │                        │                    │                   │
  │                            │                        │ MessageEnvelope    │                   │
  │                            │                        │──→ counseling.req ──>│                   │
  │                            │                        │                    │                   │
  │                            │                        │                    │    Process...     │
  │                            │                        │                    │                   │
  │                            │                        │<── counseling.resp──│                   │
  │                            │                        │                    │                   │
  │                            │                        │ TTS: synthesize    │                   │
  │                            │                        │ Audio frames (PCM) │                   │
  │                            │<───────────────────────│                    │                   │
  │ "Welcome to BCREC...      │                        │                    │                   │
  │  Let me help you with     │                        │                    │                   │
  │  admission information."  │                        │                    │                   │
  │<──────────────────────────│                        │                    │                   │
```

### 8.4 LLM Tier Selection Decision Tree

```
Request arrives
      │
      ▼
┌─────────────────┐
│ Intent detected │
│ by router       │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼
GREETING   FEE_LOOKUP  COUNSELING  UNKNOWN
    │         │          │          │
    ▼         ▼          ▼          ▼
Tier 1    Tier 1 +    Tier 3    Tier 2
Groq 8B   Tools       Claude    GPT-4o
                    Sonnet 4   mini
```

---

## 9. Migration Strategy

### 9.1 Principle: Strangler Fig Pattern

Do not rewrite. Instead, **strangle** — build new components alongside old ones, redirect traffic piece by piece, then remove the old code.

```
Phase 0: TODAY
  ┌─────────────────────────────────────┐
  │ Working Demo (monolith)             │
  │ All features in GroqService         │
  └─────────────────────────────────────┘

Phase 1-2: PARALLEL
  ┌──────────────┐    ┌─────────────────┐
  │ Working Demo │    │ New Components  │
  │ (unchanged)  │    │ (shadow mode)   │
  │              │    │                 │
  │ routes 90%   │    │ routes 10%      │
  └──────────────┘    └─────────────────┘

Phase 3-5: DOMINANT
  ┌──────────────┐    ┌─────────────────┐
  │ Legacy       │    │ New System      │
  │ (drain)      │    │ (primary)       │
  │              │    │                 │
  │ routes 10%   │    │ routes 90%      │
  └──────────────┘    └─────────────────┘

Phase 6: REMOVED
  ┌─────────────────────────────────────┐
  │ New System (only)                   │
  │ GroqService deleted                 │
  └─────────────────────────────────────┘
```

### 9.2 Migration Phases

#### Phase 0: Freeze (Week 0) — DONE

| Action | Status |
|--------|--------|
| Create git tag `v1-demo-stable` | ✅ DONE |
| Create `release/demo-v1` branch | ✅ DONE |
| Create `backup/v1-demo-2026-07-17` branch | ✅ DONE |
| Document current architecture | ✅ DONE |

#### Phase 1: Infrastructure (Weeks 1-3)

**Goal:** No behavior changes. Only infrastructure. All existing code continues to work.

| Step | What | Details | Risk |
|------|------|---------|------|
| 1.1 | Add Redis | Deploy Redis instance (Upstash or Docker). | Low — additive |
| 1.2 | Replace in-memory session store with Redis | Keep the same `SessionStore` interface but back with Redis instead of dict. | Low — same interface, different backend |
| 1.3 | Replace in-memory query cache with Redis cache | Move from `cachetools.TTLCache` to Redis cache. | Low — same interface |
| 1.4 | Add PostgreSQL | Deploy PostgreSQL (Neon free tier or Docker). | Low — additive |
| 1.5 | Move conversation history from SQLite to PostgreSQL | Write to both SQLite and PostgreSQL initially. Read from PostgreSQL after migration. | Medium — dual-write until verified |
| 1.6 | Add OpenTelemetry instrumentation | Instrument key functions with spans. No tracing backend yet. | Low — additive |
| 1.7 | Centralize prompts | Extract all prompts from code into Redis or PostgreSQL. Keep old prompt locations as fallback. | Medium — prompts must remain identical |

**Verification:** All existing tests pass. Demo works identically.

#### Phase 2: LLM Provider Abstraction (Weeks 4-5)

**Goal:** Decouple conversation engine from Groq.

| Step | What | Details | Risk |
|------|------|---------|------|
| 2.1 | Create `LLMProvider` interface | Abstract base class with `complete()` and `stream()`. | Low — additive |
| 2.2 | Wrap existing GroqService as `GroqProvider` | Adapter pattern: `GroqProvider` delegates to existing `GroqService`. | Low — wrapper only |
| 2.3 | Add `FallbackProvider` | Hardcoded responses for when LLM is unavailable. | Low — safety net |
| 2.4 | Add `LLMRouter` | Routes requests to appropriate provider. Start with simple: always Groq, fallback to FallbackProvider. | Low — not changing behavior yet |
| 2.5 | (Optional) Add OpenAI/Anthropic as Tier 3 | Only if quality improvement justifies cost. Start in shadow mode. | Medium — API key management |

**Verification:** System still uses Groq for everything. FallbackProvider only activates if Groq is down.

#### Phase 3: Channel Decoupling (Weeks 6-8)

**Goal:** Voice pipeline no longer depends on LiveKit-specific logic.

| Step | What | Details | Risk |
|------|------|---------|------|
| 3.1 | Create `VoiceAdapter` and `STTProvider`, `TTSProvider`, `VADProvider` interfaces | Abstract interfaces for all voice components. | Low — additive |
| 3.2 | Wrap existing Sarvam STT/TTS as implementations | Adapter pattern. | Low — wrapper only |
| 3.3 | Wrap existing LiveKit agent logic as `LiveKitVoiceAdapter` | Adapter pattern. | Medium — LiveKit agent is complex |
| 3.4 | Add event bus publishing to voice adapter | When STT completes, publish `voice.stt.final` event. When response is ready, publish `voice.tts.request`. | Medium — changes audio flow |
| 3.5 | **Critical:** Unify the system prompt | Voice and text channels must use the exact same prompt from the central prompt store. | Medium — behavioral parity |

**Verification:** Voice calls work identically. System prompt is identical for voice and text.

#### Phase 4: Supervisor Agent (Weeks 9-12)

**Goal:** Replace flat pipeline with Observe→Plan→Act→Remember loop.

| Step | What | Details | Risk |
|------|------|---------|------|
| 4.1 | Build Supervisor Agent | New code, runs in parallel with existing pipeline. Output comparison in shadow mode. | High — new architecture |
| 4.2 | Build Profile Agent | Extract student profile from conversation. Store in PostgreSQL. | Medium — profile extraction logic |
| 4.3 | Migrate one handler at a time to specialist agents | Start with simplest: ContactInfo → CollegeInfoAgent, Fee → FeesAgent | Medium — needs careful validation |
| 4.4 | Shadow mode: run both old and new, compare outputs | Log discrepancies. Fix until agreement rate > 95%. | Medium — comparison infrastructure |
| 4.5 | When confidence is high, switch primary traffic to Supervisor Agent | Keep old pipeline as fallback. | High — cutover |

**Verification:** Supervisor Agent matches or exceeds GroqService on all regression tests.

#### Phase 5: Knowledge Modernization (Weeks 13-16)

**Goal:** Replace JSON KB with maintainable knowledge graph + CMS.

| Step | What | Details | Risk |
|------|------|---------|------|
| 5.1 | Design Neo4j graph schema | Map all KB domains to graph. | Medium — schema design |
| 5.2 | Migrate data from JSON to Neo4j | Script to read JSON, create graph entities. | Low — one-time migration |
| 5.3 | Build CMS API + UI | CRUD endpoints + React forms for each domain. | High — new product |
| 5.4 | Add cache invalidation on data change | When CMS updates data, invalidate Redis cache. | Medium — cache consistency |
| 5.5 | Update Specialist Agents to query graph instead of JSON | Replace `KnowledgeBase.get(key)` with `graph.query()`. | Medium — query logic changes |

**Verification:** Staff can update fee structures without developer help. Changes propagate in <60 seconds.

#### Phase 6: Hardening & Scale (Weeks 17-20)

**Goal:** Production-grade reliability, performance, monitoring.

| Step | What | Details | Risk |
|------|------|---------|------|
| 6.1 | Load testing | k6/Locust at 50/100/200 concurrent users. | Low |
| 6.2 | Rate limiting per channel, per user | Application-level + gateway-level. | Low |
| 6.3 | Circuit breakers for all external dependencies | Groq, Deepgram, ElevenLabs, Neo4j, Redis, PostgreSQL. | Low |
| 6.4 | Security audit | Session ID entropy, API key rotation, input sanitization. | Low |
| 6.5 | Monitoring + alerting | Grafana dashboards, alert rules, notification channels. | Low |
| 6.6 | Delete old GroqService | Remove the 5200-line monolith. | Medium — ensure nothing depends on it |
| 6.7 | Documentation + runbooks | Architecture docs, operations runbooks, escalation procedures. | Low |

**Verification:** System passes all load tests. Old GroqService code is deleted. New system is the only system.

---

## 10. Folder Structure — Target

```
bcrec-ai/
├── .github/                       # CI/CD workflows
│   └── workflows/
│       ├── ci.yml                 # Test, lint, type-check
│       ├── deploy.yml             # Deploy to staging/production
│       └── release.yml            # Create release tag
│
├── src/
│   ├── __init__.py
│   │
│   ├── main.py                    # FastAPI app factory, DI wiring
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # Pydantic settings, env loading
│   │   └── feature_flags.py       # Centralized feature flag system
│   │
│   ├── channel/                   # Channel Adapter Layer
│   │   ├── __init__.py
│   │   ├── base.py                # ABC for channel adapters
│   │   ├── message.py             # MessageEnvelope, ResponseEnvelope
│   │   ├── web.py                 # FastAPI REST + WS routes
│   │   ├── voice.py               # LiveKit agent adapter
│   │   ├── whatsapp.py            # WhatsApp adapter
│   │   └── kiosk.py               # Kiosk adapter
│   │
│   ├── engine/                    # Conversation Engine
│   │   ├── __init__.py
│   │   ├── supervisor.py          # Observe → Plan → Act → Remember loop
│   │   ├── models.py              # ConversationState, DomainSlot, etc.
│   │   ├── language.py            # Language detection + enforcement
│   │   ├── intent.py              # Intent detection (regex + ML)
│   │   ├── emotion.py             # Emotional state detection
│   │   ├── goals.py               # Goal tracking + stage management
│   │   ├── clarification.py       # Ambiguity detection + clarification
│   │   └── guard.py               # Hallucination guard + safety rules
│   │
│   ├── agents/                    # Specialist Agents
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract agent base
│   │   ├── fees.py                # Fee structure agent
│   │   ├── placement.py           # Placement stats agent
│   │   ├── admission.py           # Eligibility + cutoffs + documents
│   │   ├── counselling.py         # Branch recommendation + career
│   │   ├── college_info.py        # HOD, faculty, facilities, hostel
│   │   ├── profile.py             # Student profile extraction
│   │   └── escalation.py          # Human handoff
│   │
│   ├── decision/                  # Decision Engine
│   │   ├── __init__.py
│   │   ├── scorer.py              # Multi-axis option scoring
│   │   ├── ranker.py              # Rank options, trade-off analysis
│   │   ├── confidence.py          # System confidence computation
│   │   └── thresholds.py          # Confidence thresholds config
│   │
│   ├── brain/                     # College Brain
│   │   ├── __init__.py
│   │   ├── procedures.py          # Deterministic procedural rules
│   │   ├── policies.py            # Policy document ingestion + query
│   │   ├── heuristics.py          # Decision heuristics for recommendations
│   │   └── workflows.py           # Workflow definitions
│   │
│   ├── reasoning/                 # Reasoning Engine
│   │   ├── __init__.py
│   │   ├── router.py              # LLM tier selection
│   │   ├── confidence.py          # LLM token confidence + normalization
│   │   ├── providers/             # LLM Provider implementations
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # ABC for LLM providers
│   │   │   ├── groq.py            # Groq provider
│   │   │   ├── openai.py          # OpenAI provider
│   │   │   ├── anthropic.py       # Anthropic provider
│   │   │   └── fallback.py        # Hardcoded fallback
│   │   ├── tools/                 # Tool registry + implementations
│   │   │   ├── __init__.py
│   │   │   ├── registry.py        # Tool registration + dispatch
│   │   │   ├── fees.py            # Fee lookup tools
│   │   │   ├── placement.py       # Placement lookup tools
│   │   │   └── contacts.py        # Contact info tools
│   │   └── prompts/               # Centralized prompt management
│   │       ├── __init__.py
│   │       ├── manager.py         # Prompt store + versioning
│   │       ├── system/            # System prompts by agent
│   │       │   ├── supervisor.txt
│   │       │   ├── fees_agent.txt
│   │       │   ├── placement_agent.txt
│   │       │   └── ...
│   │       └── templates/         # Reusable prompt fragments
│   │
│   ├── knowledge/                 # Knowledge Layer
│   │   ├── __init__.py
│   │   ├── graph.py               # Neo4j client + query builder
│   │   ├── vector.py              # Pinecone/ChromaDB client
│   │   ├── documents.py           # S3/Minio document storage
│   │   ├── cache.py               # Redis cache client
│   │   └── cms/                   # Staff CMS
│   │       ├── __init__.py
│   │       ├── api.py             # CMS REST API
│   │       ├── models.py          # CMS data models
│   │       └── ui/                # React frontend
│   │           ├── src/           # CMS React app
│   │           └── package.json
│   │
│   ├── workflow/                  # Workflow Engine
│   │   ├── __init__.py
│   │   ├── base.py                # Workflow state machine
│   │   ├── admission.py           # Admission workflow
│   │   ├── scholarship.py         # Scholarship workflow
│   │   ├── hostel.py              # Hostel workflow
│   │   └── backlog.py             # Backlog workflow
│   │
│   ├── storage/                   # Storage Layer
│   │   ├── __init__.py
│   │   ├── interfaces.py          # Store interfaces (ABCs)
│   │   ├── redis.py               # Redis session store + cache
│   │   ├── postgres.py            # PostgreSQL history + profiles
│   │   └── minio.py               # S3/Minio file storage
│   │
│   ├── bus/                       # Event Bus
│   │   ├── __init__.py
│   │   ├── events.py              # Event type definitions
│   │   ├── publisher.py           # Event publisher
│   │   ├── subscriber.py          # Event subscriber
│   │   └── consumer.py            # Background worker
│   │
│   ├── observability/             # Observability
│   │   ├── __init__.py
│   │   ├── tracing.py             # OpenTelemetry setup
│   │   ├── metrics.py             # Prometheus metrics
│   │   ├── logging.py             # Structured logging
│   │   ├── llm_obs.py             # LangFuse integration
│   │   └── alerts.py              # Alert rule definitions
│   │
│   └── utils/                     # Shared utilities
│       ├── __init__.py
│       ├── normalizer.py          # Text normalization (numbers, phone, TTS)
│       ├── number_to_words.py     # Indian number system (lakh, crore)
│       └── acronyms.py            # Acronym expansion (BCREC, CSE, etc.)
│
├── worker/                        # Background workers
│   ├── __init__.py
│   ├── conversation_worker.py     # Consumes counseling.request events
│   ├── voice_worker.py            # Consumes voice.stt/tts events
│   └── telemetry_worker.py        # Consumes telemetry events
│
├── tests/
│   ├── unit/                      # Unit tests
│   │   ├── test_intent.py
│   │   ├── test_language.py
│   │   ├── test_fees_agent.py
│   │   └── ...
│   ├── integration/               # Integration tests
│   │   ├── test_pipeline.py
│   │   ├── test_voice_adapter.py
│   │   └── test_knowledge_graph.py
│   ├── regression/                # Regression test suite
│   │   ├── test_fee_accuracy.py
│   │   ├── test_language_consistency.py
│   │   └── test_cross_channel_parity.py
│   ├── red_team/                  # Adversarial testing
│   │   ├── cases.py
│   │   ├── runner.py
│   │   └── report.py
│   └── load/                      # Load tests
│       ├── locustfile.py
│       └── scenarios.py
│
├── scripts/                       # Utility scripts
│   ├── migrate_kb_to_graph.py     # JSON → Neo4j migration
│   ├── seed_test_data.py          # Generate test conversations
│   ├── validate_prompts.py        # Check prompt parity across agents
│   └── backup.py                  # Database backup script
│
├── docker/                        # Docker infrastructure
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   ├── Dockerfile.cms
│   └── docker-compose.yml         # Local development stack
│
├── k8s/                           # Kubernetes manifests
│   ├── namespace.yaml
│   ├── deployment-api.yaml
│   ├── deployment-worker.yaml
│   ├── service-api.yaml
│   ├── configmap.yaml
│   └── hpa.yaml                   # Horizontal Pod Autoscaler
│
├── docs/                          # Documentation
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── DEPLOYMENT.md
│   ├── RUNBOOK.md
│   └── CONTRIBUTING.md
│
├── .env.example                   # Environment template
├── .gitignore
├── pyproject.toml                 # Python project config
├── requirements.txt               # Python dependencies
├── requirements-dev.txt           # Dev dependencies
└── Makefile                       # Common commands
```

---

## 11. Development Phases & Milestones

### Phase 1: Infrastructure (Weeks 1-3)

| Week | Milestone | Deliverable | Verification |
|------|-----------|-------------|--------------|
| 1 | Redis deployed, session store migrated | All sessions in Redis | Existing demo works, no session loss on restart |
| 2 | PostgreSQL deployed, conversation history migrated | All history in PostgreSQL | SQLite and PostgreSQL return identical histories |
| 3 | OpenTelemetry instrumented, prompts centralized | All spans working, all prompts in central store | Prompts are identical across channels |

**Go/No-Go:** Can we restart the server and active sessions survive? Are prompts identical?

### Phase 2: LLM Provider Abstraction (Weeks 4-5)

| Week | Milestone | Deliverable | Verification |
|------|-----------|-------------|--------------|
| 4 | LLMProvider interface created, Groq wrapped | Old GroqService behind interface | All tests pass |
| 5 | LLMRouter + FallbackProvider working | System degrades gracefully if Groq is down | Simulate Groq outage, verify fallback |

**Go/No-Go:** Can we fail Groq and the system still responds?

### Phase 3: Channel Decoupling (Weeks 6-8)

| Week | Milestone | Deliverable | Verification |
|------|-----------|-------------|--------------|
| 6 | VoiceAdapter interface + LiveKit wrapper | LiveKit behind adapter | Voice calls work identically |
| 7 | Event bus for voice pipeline | STT→Event→Counseling→Event→TTS | Voice calls work through event bus |
| 8 | Unified system prompt | Voice and web use same prompt | Behavioral parity verified |

**Go/No-Go:** Do voice and web responses match given the same input?

### Phase 4: Supervisor Agent (Weeks 9-12)

| Week | Milestone | Deliverable | Verification |
|------|-----------|-------------|--------------|
| 9 | Supervisor Agent prototype | Observe→Plan→Act→Remember loop running | Shadow mode shows comparable quality |
| 10 | Profile Agent + one specialist agent | Student profile extraction working | Profile data persists across conversations |
| 11 | All agents migrated, shadow mode running | 95%+ agreement with old system | Regression tests pass |
| 12 | **Cutover: Supervisor Agent becomes primary** | Old GroqService is fallback only | All demos work with new system |

**Go/No-Go:** Does the Supervisor Agent match or exceed the old system on 100+ regression tests?

### Phase 5: Knowledge Modernization (Weeks 13-16)

| Week | Milestone | Deliverable | Verification |
|------|-----------|-------------|--------------|
| 13 | Neo4j schema + data migration | All KB data in graph | Queries return same results as JSON |
| 14 | CMS API | CRUD endpoints for all domains | Staff can update fee structure via API |
| 15 | CMS UI | React frontend for knowledge management | Non-developer can update data |
| 16 | Cache invalidation pipeline | Updates propagate in <60s | Update → invalidate → requery → fresh data |

**Go/No-Go:** Can a non-developer update the fee structure and see it in the AI's response within 60 seconds?

### Phase 6: Hardening (Weeks 17-20)

| Week | Milestone | Deliverable | Verification |
|------|-----------|-------------|--------------|
| 17 | Load test at 50 concurrent users | p95 latency < 3s | k6 report |
| 18 | Load test at 200 concurrent users | p95 latency < 5s | k6 report, no errors |
| 19 | All circuit breakers, rate limits, security | Full hardening | Security scan, penetration test |
| 20 | **Old GroqService deleted** | Codebase cleaned | No references to old monolith |

**Go/No-Go:** Can we delete `groq_service.py`? (The entire file. Every line.)

---

## 12. Testing Strategy

### 12.1 Test Pyramid

```
         ┌──────────┐
         │   E2E    │  Few: 5-10 full end-to-end tests
         │  (5-10)  │  Voice→STT→Engine→TTS→Audio
         └──────────┘
        ┌────────────┐
        │ Integration│  Some: 20-50 tests
        │ (20-50)    │  Pipeline + adapters + storage
        └────────────┘
       ┌──────────────┐
       │   Unit Tests  │  Many: 200+ tests
       │   (200+)      │  Agents, handlers, utilities
       └──────────────┘
```

### 12.2 Test Categories

| Category | Tool | What | Frequency |
|----------|------|------|-----------|
| Unit | pytest | Individual agents, handlers, utilities | Every PR |
| Integration | pytest + testcontainers | Pipeline with real Redis, PostgreSQL, Neo4j | Every PR |
| Regression | pytest + snapshot tests | 100+ Q&A pairs, verify exact responses | Every PR |
| Language | pytest | Multi-language input/output, no mixing | Every PR |
| Voice | pytest + synthetic audio | STT pipeline with known audio files | Weekly |
| Load | k6 / Locust | 50/100/200 concurrent users | Before every release |
| Red-team | Custom framework | Edge cases, abusive language, OOD | Monthly |
| A/B | LangFuse | Compare prompt versions, agents | Continuous |

### 12.3 Regression Test Suite (100+ Q&A Pairs)

The existing regression tests in `backend/tests/` are valuable. They should be:

1. **Preserved** — moved to `tests/regression/` in the new structure
2. **Expanded** — add test cases for counseling flows, not just Q&A
3. **Automated** — run on every PR in CI

**Example regression test cases:**

| Category | Input | Expected Behavior |
|----------|-------|-------------------|
| Fee | "CSE fee kya hai?" | Return exact CSE fee structure in Hindi |
| Fee (multi-turn) | "Fee?" → "CSE" → "Total kya?" | Maintain branch context, return total |
| Placement | "CSE placement rate?" | Return exact 93.6% |
| Language | "Ami CSE niye janate chai" | Bengali response |
| Language enforcement | Mixing English and Hindi | Respond in user's primary language |
| Out-of-scope | "Weather kya hai?" | Polite "I don't know" with phone number |
| Emotional | "Mujhe bahut tension hai" | Emotional detection + reassurance |
| Incomplete | "Mera rank..." | Probe for missing information |
| Profile extraction | "Mera rank 15000 hai, 80% PCM" | Profile extracted, remembered, used |
| Counseling | "Konsi branch lu?" | Interest probing → recommendation |
| Workflow | "Mujhe admission lena hai" | Start admission workflow |

---

## 13. Performance Strategy

### 13.1 Latency Budgets

| Stage | Current (approx) | Target p50 | Target p95 |
|-------|------------------|------------|------------|
| STT (end of speech to transcript) | ~800ms (Sarvam file-based) | <300ms | <500ms |
| VAD + STT streaming | N/A | <500ms (including VAD) | <800ms |
| Intent detection | ~50ms (regex) | <50ms | <100ms |
| Structured lookup | ~10ms (JSON) | <10ms (Redis) | <20ms |
| LLM Tier 1 (Groq 8B) | ~200ms | <200ms | <400ms |
| LLM Tier 2 (GPT-4o-mini) | N/A | <500ms | <1000ms |
| LLM Tier 3 (Claude Sonnet 4) | N/A | <1000ms | <2000ms |
| TTS (text to first audio) | ~500ms (Sarvam) | <200ms | <300ms |
| End-to-end (simple, TTS) | ~1800ms | <1000ms | <2000ms |
| End-to-end (complex, TTS) | ~2500ms | <2000ms | <3000ms |

### 13.2 Optimization Strategies

1. **Cache aggressively**: Fee structures, contact info, HOD names (change rarely). Cache LLM responses for 24h.
2. **Pre-warm workers**: Keep STT/TTS connections alive between conversations. Pre-warm embedding model on startup.
3. **Stream everything**: Never wait for full response before starting TTS. Sentence-by-sentence pipelining.
4. **Connection pooling**: Reuse HTTP connections to LLM providers (aiohttp session pool).
5. **Sentence boundary detection during LLM streaming**: As soon as a sentence boundary is detected, start TTS for that sentence while LLM continues generating the next one.

---

## 14. Cost Strategy

### 14.1 Cost Projections

| Component | Current | Phase 1-2 | Phase 3-4 | Phase 5-6 |
|-----------|---------|-----------|-----------|-----------|
| Groq LLM | $0.20/mo | $0.50/mo | $2/mo | $5/mo |
| Sarvam STT | $6/mo | $6/mo | $10/mo | $5/mo (fallback) |
| Sarvam TTS | $6/mo | $6/mo | $10/mo | $5/mo (fallback) |
| Deepgram STT | N/A | $0 | $20/mo | $40/mo |
| ElevenLabs TTS | N/A | $0 | $15/mo | $30/mo |
| OpenAI/Anthropic | N/A | $0 | $10/mo | $30/mo (20% of calls) |
| Redis (Upstash) | N/A | $5/mo | $5/mo | $10/mo |
| PostgreSQL (Neon) | N/A | $0 (free tier) | $0 | $0 |
| Neo4j (AuraDB) | N/A | $0 | $0 (free tier) | $20/mo |
| Pinecone | N/A | $0 | $0 | $10/mo |
| LiveKit Cloud | $0 (self-host) | $0 | $0 | $30/mo |
| LangFuse (self-host) | N/A | $0 | $0 | $0 |
| Grafana Cloud | N/A | $0 | $0 | $0 (free tier) |
| **Total** | **~$12/mo** | **~$17/mo** | **~$72/mo** | **~$190/mo** |

### 14.2 Cost Optimization Rules

1. **Use structured knowledge first** — Never call LLM if the answer exists in the knowledge graph. Structured lookups cost $0.000001 vs LLM at $0.0001-0.015.
2. **Cache aggressively** — 80% of queries are repeats (fees, placement, contact). Cache first response for 24h.
3. **Route to cheapest capable model** — 60% of queries can be handled by Groq 8B ($0.05/M). Only 20% need Tier 3 ($3-15/M).
4. **Batch TTS** — If multiple students ask the same question, cache the TTS audio.
5. **Set per-conversation cost budget** — Alert if any single conversation exceeds $0.50.

### 14.3 Budget Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Monthly API cost | > $100 | > $200 |
| Cost per conversation | > $0.15 | > $0.30 |
| Tier 3 call percentage | > 30% | > 50% |

---

## 15. Scalability Strategy

### 15.1 Horizontal Scaling Model

```
                 ┌──────────────┐
                 │  Load        │
                 │  Balancer    │
                 └──────┬───────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
   ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
   │ Channel  │    │ Channel  │    │ Channel  │    ... (stateless)
   │ Adapter  │    │ Adapter  │    │ Adapter  │
   │ Replica  │    │ Replica  │    │ Replica  │
   └──────────┘    └──────────┘    └──────────┘
        │               │               │
        └───────────────┼───────────────┘
                        │
                 ┌──────▼───────┐
                 │  Event Bus   │
                 │  (Redis)     │
                 └──────┬───────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
   ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
   │ Engine  │    │ Engine  │    │ Engine  │    ... (stateful: session
   │ Worker  │    │ Worker  │    │ Worker  │        pinned to 1 worker)
   └──────────┘    └──────────┘    └──────────┘
```

**Channel Adapters:** Stateless. Scale horizontally behind load balancer. Each adapter maintains its own WebSocket connections.

**Engine Workers:** Stateful per session. Each session is pinned to one worker (via consistent hashing on session_id). Workers subscribe to `counseling.request` from the event bus.

**Voice Pipeline:** Separate worker pool. STT workers, TTS workers, and VAD components are independent.

### 15.2 Session Pinning

Each session is handled by exactly one engine worker at a time:
- Consistent hashing: `hash(session_id) % num_workers` → worker assignment
- If a worker fails, sessions are rebalanced to remaining workers (using session state from Redis)
- Worker processes one session at a time (sequential turn processing within a session)

### 15.3 Scaling Limits

| Component | Bottleneck | Max (single) | Scaling Strategy |
|-----------|-----------|--------------|------------------|
| Web Adapter | Number of open WebSocket connections | ~10K per node | Horizontal (stateless) |
| Voice Adapter | Audio processing CPU | ~20 concurrent calls per GPU | Horizontal (stateless) |
| Engine Worker | LLM API rate limits | ~5 concurrent sessions per worker | Horizontal (stateful but recovery from Redis) |
| Redis | Memory | ~100K sessions (1GB) | Clustering |
| PostgreSQL | Write throughput | ~5K conversations/sec | Read replicas |

---

## 16. Deployment Strategy

### 16.1 Environment Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Development │────>│  Staging     │────>│  Production  │
│              │     │              │     │              │
│ • Local      │     │ • Same infra │     │ • LiveKit    │
│ • Hot reload │     │ • Isolated   │     │ • Twilio     │
│ • Mock APIs  │     │ • Test calls │     │ • Real APIs  │
│              │     │ • CI/CD gate │     │ • Monitoring │
└──────────────┘     └──────────────┘     └──────────────┘
```

### 16.2 Development Environment

```
docker-compose.yml:
  - api: FastAPI with hot reload
  - worker: Engine worker
  - redis: Redis for sessions + cache
  - postgres: PostgreSQL for history + profiles
  - neo4j: Neo4j for knowledge graph
  - minio: S3-compatible storage
  - langfuse: LLM observability (optional)
  - grafana: Metrics visualization (optional)
```

### 16.3 Production Environment (Target)

```
Production:
  nginx / Caddy (API gateway)
  │
  ├── 2+ Channel Adapter replicas (Docker/K8s)
  │   └── Behind load balancer
  │
  ├── 2+ Engine Worker replicas
  │   └── Session-pinned via Redis
  │
  ├── Managed Redis (Upstash / ElastiCache)
  ├── Managed PostgreSQL (Neon / RDS)
  ├── Neo4j AuraDB (managed)
  ├── Pinecone (managed vector store)
  └── MinIO / S3 (file storage)
```

### 16.4 CI/CD Pipeline

```
Git push → GitHub Actions / GitLab CI:
  1. Lint (ruff)
  2. Type-check (mypy/pyright)
  3. Unit tests (pytest)
  4. Integration tests (with testcontainers)
  5. Regression tests (100+ Q&A pairs)
  6. Build Docker images
  7. Push to registry
  8. Deploy to staging
  9. Smoke tests on staging
  10. (Manual approval)
  11. Deploy to production (blue-green or canary)
```

---

## 17. Monitoring & Observability Strategy

### 17.1 Dashboard Structure (Grafana)

**Real-time Operations Dashboard:**
- Active sessions (by channel)
- Requests per second
- p50/p95/p99 latency (total + per stage)
- Error rate (by type)
- Cost per minute

**Conversation Quality Dashboard:**
- Average conversation duration
- User satisfaction (sentiment trend)
- Handoff rate
- Language distribution
- Intent distribution

**Cost Dashboard:**
- Cost per provider
- Cost per conversation
- Token usage trend
- Cache hit rate

**System Health Dashboard:**
- Redis memory/CPU
- PostgreSQL connections/query time
- Neo4j query time
- LLM provider availability
- API key usage

### 17.2 Alert Rules

| Alert | Condition | Severity | Response |
|-------|-----------|----------|----------|
| High error rate | Error rate > 2% in 5 minutes | Critical | Page on-call |
| High latency | p95 > 5s in 5 minutes | Critical | Investigate bottleneck |
| Provider down | 100% error rate to provider | Critical | Switch to fallback provider |
| Cost spike | Daily cost > 2x normal | Warning | Investigate cause |
| Redis memory high | > 80% used | Warning | Increase TTL or scale |
| Session loss | Session not found in Redis | Warning | Investigate eviction |

### 17.3 LLM Observability (LangFuse)

Every LLM call is logged with:
- Prompt (exact version)
- Response
- Token counts
- Cost
- Latency
- Provider + model
- Session ID (for correlation)
- Rating (optional — user feedback)

This enables:
- **Prompt debugging**: "Why did the agent say X?"
- **Cost tracking**: "Which model is costing the most?"
- **Quality scoring**: "Are responses getting better or worse?"
- **A/B testing**: "Does prompt A or B produce better results?"

---

## 18. Disaster Recovery Strategy

### 18.1 Recovery Point Objectives

| Data | RPO | Strategy |
|------|-----|----------|
| Active sessions | 0 (real-time) | Redis persistence (AOF + RDB) |
| Conversation history | 5 minutes | PostgreSQL continuous WAL archiving |
| Student profiles | 5 minutes | PostgreSQL continuous WAL archiving |
| Knowledge graph | 1 hour | Neo4j periodic backup |
| Vector embeddings | 24 hours | Regenerate from documents |
| TTS/audio cache | 24 hours | S3/MinIO bucket replication |

### 18.2 Recovery Time Objectives

| Scenario | Target RTO | Recovery Procedure |
|----------|-----------|-------------------|
| Single API server failure | 30 seconds | Load balancer routes to healthy replica |
| Full AZ/region failure | 15 minutes | DNS failover to secondary region |
| Redis failure | 5 minutes | Replica promotion or new instance from AOF |
| PostgreSQL failure | 15 minutes | Point-in-time recovery from WAL archive |
| Neo4j failure | 30 minutes | Restore from latest backup |
| LLM provider outage | 1 minute | Automatic fallback to secondary provider |

### 18.3 Rollback Procedure

1. Deploy change (canary: 10% traffic)
2. Monitor for 10 minutes (error rate, latency, cost)
3. If any metric exceeds threshold:
   - Immediately roll back canary traffic to previous version
   - Identify and fix the issue
   - Re-deploy with fix
4. If metrics are healthy:
   - Incrementally increase traffic to 100%
   - Tag release
   - Archive previous version

---

## 19. Risk Analysis

### 19.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Phase 4 Supervisor Agent doesn't match old system quality | Medium | HIGH | Shadow mode + extensive regression testing before cutover |
| Redis session store latency adds to response time | Low | MEDIUM | Redis <1ms typical, monitor and optimize |
| Neo4j query complexity slows down simple lookups | Medium | LOW | Cache hot queries in Redis, benchmark graph queries |
| LangFuse overhead impacts LLM latency | Low | LOW | Async telemetry — don't block on observability |
| Event bus becomes bottleneck at high load | Low | MEDIUM | Redis Streams handles 100K msg/s. Monitor consumer lag. |

### 19.2 Business Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Staff cannot/will not use CMS | Medium | HIGH | Invest in UI/UX of CMS. Provide training. Make ROI clear (no more asking developers for data updates) |
| Students prefer human counselors | Medium | MEDIUM | Hybrid: AI handles 80%, humans handle 20%. Track satisfaction. Improve AI based on human corrections |
| College leadership changes priorities | Medium | HIGH | Keep demo always working. Each phase should deliver standalone value, not just "architectural purity" |
| Budget cuts | Low | HIGH | Architecture supports cheap deployment: $12/mo baseline, $200/mo full production |

### 19.3 Migration Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Regression in behavior during migration | Medium | CRITICAL | Every phase has a "shadow mode" where old and new run in parallel. Compare outputs before switching |
| Data loss during migration | Low | CRITICAL | All migrations are one-way: old source of truth is preserved until new is verified |
| Migration takes longer than planned | High | MEDIUM | Scope each phase independently. Don't waterfall — each phase is a working deliverable |

---

## 20. Rollback Strategy

### 20.1 Architecture Rollback

If the new architecture fails in production:

1. **Switch traffic back to old GroqService** (always running in shadow mode during migration)
2. Keep new infrastructure (Redis, PostgreSQL) — they don't break the old system
3. Investigate failure cause while old system handles traffic
4. Fix and re-deploy new architecture

### 20.2 Deployment Rollback

```
Current deployment:
  - Green: v2.0 (new architecture, 100% traffic)
  - Blue: v1.0 (old architecture, 0% traffic, ready)

Rollback:
  1. Switch load balancer from Green to Blue
  2. Verify Blue is healthy (30 seconds)
  3. Keep Green running for investigation
  4. Tag Green as failed: release/failed-v2.0
  5. Restore from v1-demo-stable if needed
```

### 20.3 Data Rollback

| Data | Rollback Method |
|------|----------------|
| Session state | None needed — sessions expire. Old sessions are lost on rollback |
| Conversation history | PostgreSQL PITR to pre-deployment timestamp |
| Student profiles | PostgreSQL PITR to pre-deployment timestamp |
| Knowledge graph | Neo4j backup restore to pre-deployment |
| Cache | Redis flush + repopulate from source of truth |

---

## 21. Versioning Strategy

### 21.1 Code Versioning

| Type | Format | Example | When |
|------|--------|---------|------|
| Release | `v<major>.<minor>.<patch>` | `v2.0.0` | Stable, deployable |
| Release candidate | `v<major>.<minor>.<patch>-rc.<N>` | `v2.0.0-rc.1` | Testing before release |
| Release branch | `release/<version>` | `release/v2.0.0` | Branch for release |
| Backup | `backup/<name>-<date>` | `backup/v1-demo-2026-07-17` | Recovery point |
| Tag | `v<version>` | `v2.0.0` | Immutable release marker |

### 21.2 Knowledge Versioning

Every change to the knowledge graph is:
- **Versioned**: Each update creates a new revision
- **Audited**: Who changed what, when
- **Revertible**: Any change can be rolled back
- **Previewable**: See AI response with new data before publishing

### 21.3 Prompt Versioning

Every prompt change is:
- **Versioned**: Stored in PostgreSQL with version number
- **Tagged**: `system/supervisor/v1`, `system/fees_agent/v3`
- **Traceable**: LangFuse records which prompt version was used for each LLM call
- **A/B testable**: Route 10% of traffic to new prompt, compare quality

### 21.4 API Versioning

| Version | Status | Notes |
|---------|--------|-------|
| v1 (current) | Deprecated | Existing endpoints, maintained for backward compatibility |
| v2 (future) | Active | New endpoints with new response format |

API versioning via URL prefix: `/api/v1/query`, `/api/v2/query`

---

## 22. Production Readiness Checklist

### Prerequisites

- [ ] Git tag `v1-demo-stable` exists → ✅ DONE
- [ ] Release branch `release/demo-v1` exists → ✅ DONE
- [ ] Backup branch `backup/v1-demo-2026-07-17` exists → ✅ DONE
- [ ] All code is in git (no untracked critical files)
- [ ] `.env` files are in `.gitignore` (secrets not in repo)

### Phase 1 Gate

- [ ] Redis deployed and configured
- [ ] Sessions survive server restart
- [ ] PostgreSQL deployed and connected
- [ ] Conversation history in PostgreSQL (dual-write verified)
- [ ] OpenTelemetry spans emitted for all major operations
- [ ] Prompts centralized in storage (not hardcoded)
- [ ] All existing tests pass

### Phase 2 Gate

- [ ] LLMProvider interface defined
- [ ] GroqService wrapped as GroqProvider
- [ ] LLMRouter routes to provider
- [ ] FallbackProvider returns graceful degradation responses
- [ ] Simulated Groq outage → system responds with fallback

### Phase 3 Gate

- [ ] VoiceAdapter interface defined
- [ ] LiveKit agent wrapped as LiveKitVoiceAdapter
- [ ] Event bus voice pipeline working
- [ ] Voice and text use identical system prompt
- [ ] Behavioral parity verified (same input → same output)

### Phase 4 Gate

- [ ] Supervisor Agent prototype working
- [ ] Profile Agent extracting and persisting profiles
- [ ] All specialist agents implemented
- [ ] Shadow mode: 95%+ agreement with old system
- [ ] Regression tests pass with Supervisor Agent

### Phase 5 Gate

- [ ] Neo4j knowledge graph deployed and populated
- [ ] CMS API functional for all domains
- [ ] CMS UI usable by non-developers
- [ ] Cache invalidation pipeline working (<60s propagation)
- [ ] Staff can update a fee structure and verify in AI response

### Phase 6 Gate

- [ ] Load test: 200 concurrent users, p95 <5s
- [ ] Circuit breakers for all external dependencies
- [ ] Rate limiting per channel
- [ ] Security audit completed
- [ ] Monitoring dashboards operational
- [ ] Alert rules configured
- [ ] Old GroqService deleted
- [ ] Runbooks written
- [ ] Team trained on new architecture

---

## 23. Estimated Timeline

| Phase | Duration | Effort | Personnel | Dependencies |
|-------|----------|--------|-----------|--------------|
| 0: Freeze | ✅ 0 days | ✅ DONE | ✅ | None |
| 1: Infrastructure | 3 weeks | 1 senior backend engineer | Redis experience | Redis + PostgreSQL access |
| 2: LLM Abstraction | 2 weeks | 1 senior backend engineer | None | Phase 1 |
| 3: Channel Decoupling | 3 weeks | 1 senior + 1 mid backend | LiveKit + audio experience | Phase 1-2 |
| 4: Supervisor Agent | 4 weeks | 1 senior + 1 AI engineer | LLM + agent architecture experience | Phase 1-3 |
| 5: Knowledge Modernization | 4 weeks | 1 full-stack + 1 backend | React + Neo4j experience | Phase 4 |
| 6: Hardening | 4 weeks | 1 DevOps + 1 backend | K8s + monitoring experience | Phase 1-5 |

**Total: 20 weeks (~5 months)**

**Critical path:** Phase 4 (Supervisor Agent) is the highest-risk, highest-reward item. It should be prioritized even if other phases are delayed.

### Resource Requirements

| Role | Phase 1-2 | Phase 3-4 | Phase 5-6 |
|------|-----------|-----------|-----------|
| Senior Backend Engineer | 1.0 FTE | 1.0 FTE | 0.5 FTE |
| Mid Backend Engineer | 0 FTE | 1.0 FTE | 1.0 FTE |
| AI/ML Engineer | 0 FTE | 1.0 FTE | 0 FTE |
| Full-Stack Engineer (CMS) | 0 FTE | 0 FTE | 1.0 FTE |
| DevOps Engineer | 0.25 FTE | 0.25 FTE | 0.5 FTE |

**Total effort:** ~7 engineer-months over 5 calendar months.

---

## Appendix A: Key Decisions Summary

| Decision | Choice | Alternative Considered | Rationale |
|----------|--------|----------------------|-----------|
| Session store | Redis | PostgreSQL, Memcached | Speed + TTL + pub/sub for event bus |
| Conversation history | PostgreSQL | MongoDB, SQLite | Structured queries + joins with profiles |
| Event bus | Redis Streams | RabbitMQ, Kafka | Simplicity + no new infra + 0->1 quickly |
| Knowledge graph | Neo4j | PostgreSQL with CTEs | Complex queries need graph traversal |
| Vector store | Pinecone | ChromaDB, Weaviate | Zero maintenance + scale on demand |
| LLM Tier 1 | Groq Llama 3.1 8B | Any small model | Currently free/fast, good enough for routing |
| LLM Tier 3 | Claude Sonnet 4 / GPT-4o | GPT-4o only | Best reasoning for counseling quality |
| STT | Deepgram (primary) + Sarvam (fallback) | Azure Speech, Google STT | Accuracy on Indian English |
| TTS | ElevenLabs (primary) + Azure (fallback) | Sarvam, Google TTS | Naturalness gap is worth the cost |
| Audio transport | LiveKit (keep) | Vapi, Retell, Dograh | Already works + full-duplex + self-hostable |
| Migration pattern | Strangler Fig | Big Bang rewrite | Risk mitigation + continuous value delivery |
| Agent architecture | Supervisor + Specialists | Flat pipeline, Single agent | Scalable reasoning + specialized quality |

## Appendix B: Acronyms

| Acronym | Meaning |
|---------|---------|
| VAD | Voice Activity Detection |
| STT | Speech-to-Text |
| TTS | Text-to-Speech |
| TTFT | Time to First Token |
| PITR | Point-in-Time Recovery |
| RPO | Recovery Point Objective |
| RTO | Recovery Time Objective |
| HPA | Horizontal Pod Autoscaler |
| WAF | Web Application Firewall |
| KB | Knowledge Base |
| OOD | Out-of-Domain (or Out-of-Distribution) |
