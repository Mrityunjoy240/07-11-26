# BCREC AI Admission Assistant

## Project Report — Detailed Technical & Project Overview

**Prepared for:** Faculty Guide (Project Evaluation)
**Project domain:** Artificial Intelligence / Natural Language Processing
**Target college:** Dr. B. C. Roy Engineering College, Durgapur (BCREC)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Project Objective](#3-project-objective)
4. [What We Built](#4-what-we-built)
5. [System Architecture](#5-system-architecture)
6. [Technology Stack](#6-technology-stack)
7. [Core Technical Concepts](#7-core-technical-concepts)
8. [Key Features](#8-key-features)
9. [The New "Understanding" Layer (Research Focus)](#9-the-new-understanding-layer-research-focus)
10. [Testing & Validation](#10-testing--validation)
11. [Live Demo Walkthrough](#11-live-demo-walkthrough)
12. [Version Comparison — Stable vs. Research Branch](#12-version-comparison--stable-vs-research-branch)
13. [Challenges & Solutions](#13-challenges--solutions)
14. [Known Issues & Limitations](#14-known-issues--limitations)
15. [Future Roadmap](#15-future-roadmap)
16. [Conclusion](#16-conclusion)

---

## 1. Executive Summary

We built an **AI-powered admission counselor** for Dr. B. C. Roy Engineering College (BCREC) that answers prospective students' questions about **fees, courses, placements, hostels, eligibility, faculty, and the admission process** in a natural conversation — over **text chat and voice**, in **English, Hindi, and Bengali**.

The system uses **Retrieval-Augmented Generation (RAG)**: every factual answer is grounded in a verified knowledge base rather than guessed by the AI. This prevents the "hallucinations" (confident but false answers) typical of plain chatbots.

The project has two strands:

1. **A working, deployable system** — a FastAPI backend + React web frontend, live on the local network, answering real queries today.
2. **An ongoing research upgrade** — a layered architecture that replaces the single large "do-everything" module with separate, testable components (Understanding → Reasoning → Decision → Planning), plus a hybrid NLU layer that understands informal, mixed-language queries and maintains a student profile.

**Validation evidence:** the full automated test suite currently passes **1585 tests**, including a dedicated semantic-understanding test suite (77 tests) and performance tests. The live demo is running and responds to real queries in under ~1.2 seconds with a correct answer.

---

## 2. Problem Statement

Every admission season, BCREC receives hundreds of calls and visits from students asking the same questions repeatedly:

- *"What is the CSE fee?"*
- *"Do you have hostel facilities?"*
- *"What is the placement record?"*
- *"Am I eligible with my rank?"*

This consumes staff time, is available only during office hours, and students often get inconsistent answers depending on whom they ask. Meanwhile, students ask questions **informally and in mixed languages** ("fee koto?", "hote ke achhe"), and they expect **personalized guidance**, not just facts.

### The two problems we target

| Problem | Impact |
|---|---|
| **Information availability** | No 24/7 source of accurate, consistent college information |
| **Understanding informal/mixed-language queries** | Generic bots fail on Hinglish/Banglish ("Banglish"), incomplete sentences, and follow-ups like "fee koto?" without context |

---

## 3. Project Objective

> Build an AI system that helps every student make the best possible admission decision — with accurate facts, in their language, any time — so well that it behaves like the college's best admission counselor.

Measurable goals set for the project:

| Metric | Target |
|---|---|
| Answer accuracy (no wrong facts about the college) | > 95% |
| Hallucination rate (false claims) | < 0.1% |
| Response language matches user's language | > 99% |
| Text response latency | < 1.5 s |
| Wrong institution reference (confusing BCREC with another college) | 0% |

---

## 4. What We Built

### 4.1 The Product (working today)

A web application where a student:

1. Opens the chat interface (or presses the mic button to speak).
2. Types/speaks in English, Hindi, or Bengali — including romanized Banglish/Hinglish.
3. Receives a spoken/text answer grounded in the official college knowledge base.

### 4.2 The Knowledge Base

A curated, structured knowledge base about BCREC:

- **~550+ FAQ entries** in JSON (fees, contacts, HODs, hostel, placement, scholarships).
- **12 department documents** (CSE, IT, AIML, ECE, EE, ME, CE, etc.) in Markdown.
- **Topic documents**: admissions, fees, placements, hostel, faculty, student life, contacts.
- A **vector index** (ChromaDB + embeddings) for fuzzy semantic search over the documents.

### 4.3 The Research Upgrade (in progress)

A redesigned pipeline that breaks the old single-module "black box" into layered, testable engines (Section 9).

---

## 5. System Architecture

### 5.1 High-Level Data Flow (Current Production System)

```
 User (browser/voice)
      │
      ▼
 React Web Frontend ──────────────┐
      │ (REST / WebSocket / audio) │
      ▼                            ▼
 FastAPI Backend (port 8001)    LiveKit Voice Agent
      │                            │  (VAD → STT → LLM → TTS)
      ▼                            ▼
 GroqService  ──►  RAG Engine
      │            ├── Deterministic FAQ lookup (JSON) — ~5 ms
      │            ├── Fee Engine (exact computed answers)
      │            ├── ChromaDB vector search (fuzzy)
      │            └── Groq LLM (Llama 3.3 70B) — only for reasoning
      │
      ├── Language detection & enforcement (EN/HI/BN)
      ├── Hallucination guard (answer must match retrieved facts)
      ├── Session memory & follow-up resolution
      │
      ▼
 Sarvam AI TTS (text → speech) → user hears the answer
```

**Key design idea — "answer directly, reason only when needed":**

| Query type | Handled by | Speed |
|---|---|---|
| Common FAQ ("What is CSE fee?") | Deterministic JSON lookup | **4–6 ms** |
| Exact fee computation | Fee Engine (computed, not guessed) | ms |
| Ambiguous / conversational / multi-step | LLM + retrieved context | ~0.5–1.5 s |

### 5.2 Target Architecture (Research Branch)

The long-term architecture separates each question the system must answer into its own layer — each with one responsibility:

```
Channel → Conversation → Understanding → Reasoning → Decision →
          Planner → College Brain → Knowledge → Workflow → Memory → Response
```

Implemented so far in `src/`:

| Module | One question it answers | Status |
|---|---|---|
| `understanding/` | What did the student mean (including hidden intent, profile, emotion)? | Implemented + tested |
| `reasoning/` | What does the student actually need? | Implemented + tested |
| `decision/` | What should the system do about it? | Implemented + tested |
| `planner/` | What should be said next? | Implemented + tested |
| `brain/` | Domain logic: fees, admission, placement, hostel, scholarship | Implemented |
| `knowledge/` | What facts are true? (grounded retrieval) | Implemented + tested |
| `conversation/` | Session state, context, memory | Implemented |
| `composer/`, `pipeline/` | Response assembly and orchestration | Implemented |

---

## 6. Technology Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI (Python 3.10) |
| LLM | Groq — Llama 3.3 70B (free tier, sub-second inference) |
| Voice (STT/TTS) | Sarvam AI (Saaras v3 STT, Bulbul v3 TTS, 22 languages) |
| Vector search | ChromaDB + `all-MiniLM-L6-v2` embeddings |
| Frontend | React 18 + TypeScript + Material-UI |
| Speech in browser | Web Speech API, MediaRecorder |
| Real-time voice | LiveKit Agents (VAD → STT → LLM → TTS pipeline) |
| Databases | SQLite (conversations), ChromaDB (vectors), in-memory sessions |
| Testing | pytest (1585 tests passing) |
| Linting | Ruff |
| Version control | Git (tagged stable release `v1-demo-stable`) |

**Cost advantage:** runs on free-tier services — a comparable commercial setup costs far more (target < ₹2,500/month).

---

## 7. Core Technical Concepts

### 7.1 Retrieval-Augmented Generation (RAG)

Instead of letting the LLM "remember" facts, we **retrieve** the relevant fact from the knowledge base and feed it to the LLM inside the prompt, instructing it to answer *only* from that context. This is the core defense against hallucination.

### 7.2 Deterministic-First Routing

The system decides *before* calling the LLM whether the question needs the LLM at all:

1. Greeting? → fixed polite reply (few ms).
2. Exact FAQ match? → JSON answer (few ms).
3. Fee question? → Fee Engine computes exact figure.
4. Otherwise → vector search → LLM generates grounded answer.

### 7.3 Hallucination Guard

For every LLM answer, the system cross-checks entities (fees, names, numbers) in the answer against the retrieved context. If the answer cannot be supported, it returns a polite fallback instead of a fabricated fact.

### 7.4 Trilingual Language Pipeline

- Language detection (English / Hindi / Bengali) including romanized Hinglish and Banglish.
- Language-specific system prompts: *"Answer ONLY in the user's language. NEVER mix languages."*
- Explicit language-switch detection ("bolchi bangla te kotha bola jabe" → switch to Bengali).
- Number-to-words conversion for TTS in the detected language.

**How weak-signal language detection actually works (final design):**

Romanized / code-mixed text ("fee koto?", "CSE ka fee kitna hai?") defeats statistical detectors: `fasttext` lid.176 mis-classified our romanized corpus as `id`/`es`/`it`/`en`, and `lingua` defaulted Latin script to English. So we use a **"LLM decides when the signal is weak"** strategy:

1. **Deterministic fast path** — keyword/lexicon scoring classifies the query with zero cost *when the signal is strong* (clear Bangla/Hindi tokens, explicit switch phrases, script, or an established session language). This stays offline and instant.
2. **LLM verdict only on weak signal** — when deterministic scoring is ambiguous (short/romanized queries, mixed evidence), the backend calls a **cached, structured JSON verdict** from **Llama 3.3 70B** (`_llm_language_verdict`). A smaller model was unreliable; the 70B model classified our 9-sample romanized/code-mixed corpus **9/9 correct**.
3. **Graceful fallback** — if the LLM call times out (4 s) or errors, the system falls back to the deterministic result + session-language inheritance, so the chat never breaks.

This means the admission assistant handles romanized Banglish/Hinglish **without maintaining any hardcoded spelling list** — the LLM is the generalizing decider, called only when rules are uncertain.

### 7.5 Hybrid NLU (research)

The new understanding layer combines:

- **Deterministic intent detection** — domain vocabulary, token scoring, entity extraction (rank, PCM%, branch, budget) → fast, zero-cost, no LLM.
- **Semantic NLU classifier** — normalized scoring over token classes, prefix/ratio tolerances to avoid false positives.
- **LLM fallback** — only when the deterministic layer is genuinely uncertain; parsed into the same structured output.
- **Student profile + conversation stage tracking** — remembers rank, PCM, branch interest, budget across turns.

---

## 8. Key Features

| Feature | Status |
|---|---|
| Text Q&A with RAG (grounded answers) | **Production Ready** |
| Deterministic FAQ bypass (4–6 ms) | **Production Ready** |
| Exact fee computation (Fee Engine) | **Production Ready** |
| Multilingual: English, Hindi, Bengali + Banglish/Hinglish | **Production Ready** |
| Hallucination guard | **Production Ready** |
| Voice input & speech output (browser) | **Experimental** |
| Real-time voice call agent (LiveKit) | **Fully Implemented** |
| Session memory & follow-up resolution ("fee koto?" after branch talk) | **Experimental** |
| Conversation history (SQLite) | **Production Ready** |
| Admin APIs (KB hot-reload, file upload, re-index) | **Production Ready** |
| Student profile extraction (rank, PCM, branch interest) | **Research branch** |
| Layered pipeline (understanding → reasoning → decision → planner) | **Research branch** |
| Operator-curated document knowledge base with grounded retrieval | **Research branch** |

---

## 9. The New "Understanding" Layer (Research Focus)

This is the most recent and central piece of the research upgrade. It directly addresses the hardest observed failures: informal, mixed-language, and context-dependent questions.

### 9.1 What it does

Given any raw query, it produces a **structured understanding**:

```
Input:  "rank 48k ase, ece te ki chance ache?"
        (Banglish: "I have a 48k rank, what are my chances in ECE?")

Output: Intent        = admission_eligibility
        Entities      = { rank: 48000, branch: ECE }
        Language      = Bengali (Banglish)
        Confidence    = 0.92
        Ambiguous     = False
        Needs-LLM     = False   ← answered deterministically
        Follow-up     = resolves branch/entity from conversation history
```

### 9.2 Why hybrid (not pure LLM, not pure rules)

| Approach | Problem |
|---|---|
| Pure rules / regex | Misses paraphrases, breaks on typos and mixed language |
| Pure LLM intent | Slow (~1 s), costs money, inconsistent (can answer "hi" as an intent query) |
| **Hybrid (ours)** | Deterministic layer handles the common 90% fast & free; LLM only on genuine uncertainty |

### 9.3 What was hardened (recent fixes)

Through systematic testing we fixed subtle false-positive bugs in the deterministic classifier:

- Token confidence guards with length-tolerance ratios — stopped `hote` (hostel) from matching `hotel`, `btech` vs `biotech` confusion.
- Removed misleading aliases (e.g., `"me"` was matching Mechanical Engineering).
- Rank-regex accepts both orders ("rank 48k" and "48k rank") including shorthand (`48k`).
- Hindi & Banglish help/greeting detection ("madad chahiye", "back ase").
- Multi-word greeting detection, `institution` intent triggers, deterministic tie-breaks.

### 9.4 Operator-curated document knowledge base

A knowledge base curated by domain operators (documents reviewed/edited by a human expert), combined with **grounded retrieval** — the answer must cite the retrieved document — measurably reducing fabrication.

---

## 10. Testing & Validation

### 10.1 Automated test suite

| Suite | Result |
|---|---|
| Full repository test suite (`pytest`) | **1585 passed, 2 skipped, 6 xfailed** |
| Semantic NLU suite (`tests/test_semantic_nlu.py`) | **77 tests** — intent matrix, off-topic/ambiguity, context follow-ups, LLM fallback, LLM-output parsing |
| Performance suite (`tests/test_perf_semantic.py`) | **5 tests** — p50/p95 latency budgets, zero-LLM-call guarantee on clear corpus |
| Code quality | Our new files pass Ruff clean (repo has a pre-existing baseline of style debt) |

The performance tests enforce that clear queries never call the LLM and stay within latency budgets — this is how we keep the "fast & free" promise while adding understanding.

### 10.2 Live functional verification (as tested today)

| User query (Banglish) | System behavior |
|---|---|
| `hi` | Deterministic greeting (`greeting_deterministic`), ~40 ms |
| `ece te ki porano hoy` ("what is taught in ECE?") | Grounded answer with real KB data: 93.6% placement, 7.0 LPA highest, 3.78 LPA average — **no fabrication** |
| `bolchi bangla te kotha bola jabe` ("can you speak in Bangla?") | Detects language switch → re-answers in Banglish |
| `fee koto?` ("how much is the fee?") | Correct: "ECE er total fee holo six lakh seventeen thousand seven hundred taka" |

### 10.3 What testing caught (examples)

- **Auth regression (production branch):** a hardening commit added a required API token that the web frontend never sends → every chat request failed with a generic error while the old stable version worked. Root-caused and fixed (auth now only enforced when a token is actually configured). This is the difference the professor may see between "broken" and "working" states of the demo.
- **Language mixing:** the LLM sometimes mixes Hindi into Banglish replies despite prompt rules — an LLM-compliance issue tracked as a known limitation.
- **Fabrication on old version:** the previous stable version invented "rank 1000, PCM 92%" when asked to review eligibility. The research branch's grounded retrieval eliminates this.

---

## 11. Live Demo Walkthrough

### 11.1 Running the demo

```powershell
# Start the backend server
college_agent-master/start_server.ps1
# Opens at http://127.0.0.1:8001/  (chat UI)
# Health check: http://127.0.0.1:8001/health/  → {"status":"ok", ...}
```

### 11.2 Suggested script for the demonstration

1. **Basic facts:** "What is the CSE fee?" → exact amount.
2. **Placement:** "What about placements in ECE?" → rates and packages from KB.
3. **Multilingual:** ask in Hindi ("CSE ka fee kitna hai?"), then in Banglish ("CSE er fee koto?").
4. **Language switch:** "bolchi bangla te kotha bola jabe" → replies in Bengali/Banglish.
5. **Follow-up context:** ask about a branch, then simply "fee koto?" → answers for that branch.
6. **Voice (optional):** use the mic button to speak a question.
7. **Custom query (proves grounding):** an unusual question → grounded, no fabrication.

### 11.3 How to show "it's not hallucinating"

Ask something, then point out that the numbers come from the knowledge-base documents, and demonstrate the offline FAQ path (4–6 ms) vs. LLM path (0.5–1.5 s) visible in the server log under `backend/server_err.log`.

---

## 12. Version Comparison — Stable vs. Research Branch

| Aspect | `v1-demo-stable` (tag) | `brain-v2-research` (current) |
|---|---|---|
| Architecture | Monolithic `groq_service.py` (~5,200 lines) | Layered modules (`src/`) + hybrid NLU |
| Grounding | RAG, but weaker guard | Operator-curated KB + grounded retrieval (no fabrication observed) |
| Understanding | Regex intent routing only | Hybrid NLU: deterministic + LLM fallback, profile, stage tracking |
| Testability | Difficult (monolith) | 1585 tests incl. dedicated semantic/performance suites |
| Auth guard | None (open) | Token enforced only when configured (fixed regression) |

---

## 13. Challenges & Solutions

| Challenge | Solution |
|---|---|
| Hallucination (AI inventing fees/ranks) | RAG + retrieval grounding + hallucination guard + curated KB |
| Banglish/Hinglish informal queries | Hybrid NLU with Bangla/Hindi vocabulary, token scoring, LLM fallback |
| Short follow-ups ("fee koto?") without context | Session state + follow-up resolution using last intent/entities |
| Language mixing in replies | Language detection + per-language system prompts (known residual issue) |
| Auth regression blocking the demo | Root-cause analysis; auth enforced only when token configured |
| Performance vs. accuracy | Deterministic-first routing: FAQ/fee in ms; LLM only when needed |
| Unmaintainable monolith | Refactor into one-responsibility engines, each with unit tests |

---

## 14. Known Issues & Limitations

1. **Language mixing (LLM compliance):** the model sometimes mixes Hindi words into Banglish replies despite prompt instructions. Candidate fixes: stricter post-generation language validation.
2. **Session memory is in-memory:** lost on server restart; a persistent store is planned.
3. **Single LLM provider (Groq):** no automatic failover if Groq is unavailable.
4. **Voice pipeline is single-turn** in the WebSocket path (history not yet passed).
 5. **Short-query language detection** — weak-signal romanized queries ("fee koto?") are now resolved by an on-demand 70B LLM verdict with timeout/fallback, instead of relying solely on imperfect statistical detectors (`fasttext`/`lingua`) which mis-classify romanized text. Session-language inheritance remains the offline fallback.
6. **Prompt duplication** across four places in the codebase — consolidated prompt store planned.

---

## 15. Future Roadmap

The project follows a 6-level maturity roadmap:

```
Level 1 FAQ            ✅ working today
Level 2 Memory         ✅ profile extraction + follow-ups (research)
Level 3 Counselor      🔜 branch recommendations with trade-offs, emotional-state detection
Level 4 Planner        🔜 admission workflow guidance, proactive follow-up, scholarship advice
Level 5 Advisor        🔜 cross-channel continuity (web → phone → WhatsApp)
Level 6 Autonomous     🔜 end-to-end admission processing
```

Near-term next steps:

- Fix residual language-mixing (post-generation language check).
- Persistent session/profile store (survives restarts).
- LLM provider failover (Groq + fallback).
- Wire the new understanding layer into the live backend and re-benchmark.

---

## 16. Conclusion

We delivered a **working, deployable AI admission assistant for BCREC** that answers real student questions accurately in English, Hindi, and Bengali over chat and voice — grounded in a verified knowledge base to prevent hallucination.

On the research side, we are replacing the fragile "one big module" with a **layered, testable pipeline** whose core is a **hybrid natural-language understanding layer** that handles the informal, mixed-language, context-dependent questions real students ask — validated by **1585 automated tests** including dedicated semantic-understanding and performance suites, plus live end-to-end verification.

The system is demonstrably working today at `http://127.0.0.1:8001/`, and the architecture is positioned to grow from a factual FAQ assistant into a genuine AI admission counselor.
