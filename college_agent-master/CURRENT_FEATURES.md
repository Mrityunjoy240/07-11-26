# Current Features & Status

## Legend
- **Production Ready** = works reliably, tested, no known crashes
- **Experimental** = works in demo conditions, known gaps
- **Stub/Placeholder** = interface exists, no real implementation
- **Not Yet Active** = code exists behind feature flag, not in use

---

## Core Features

| Feature | Status | Details |
|---|---|---|
| **Text Q&A (RAG)** | **Production Ready** | GroqService with vector search, intent classification, context injection. 400+ tests passing. |
| **Fee Query (deterministic)** | **Production Ready** | Dual engine: FeeEngine (JSON-driven) and FEE_GROUP_MAP (hardcoded). 109 parity tests passing. |
| **Multilingual (EN/HI/BN)** | **Production Ready** | FastText detection + language-specific prompts + Banglish/Hinglish romanized support. 95%+ accuracy. |
| **Hallucination Guard** | **Production Ready** | Entity extraction → context cross-reference → polite fallback on mismatch. |
| **Streaming Response** | **Production Ready** | `/qa/query-stream` endpoint, token-by-token SSE, sentence-aware TTS pipeline. |
| **Session Memory** | **Experimental** | In-memory dict (max 30 turns). Lost on restart. No persistence to SQLite for context. |
| **Repeat Detection** | **Production Ready** | Detects identical queries within 3 turns → varies response. |
| **Follow-up Expansion** | **Experimental** | Expands "how much" → "how much is CSE tuition fee" using last intent. Basic implementation. |

## Voice Features

| Feature | Status | Details |
|---|---|---|
| **WebSocket Voice Pipeline** | **Experimental** | `/qa/ws/voice` — streaming LLM → TTS → audio. Single-turn only (no conversation history). |
| **Sarvam AI TTS** | **Production Ready** | 30+ Indian voices, 22 languages, Bulbul v3 model. Cached in memory + disk. |
| **Sarvam AI STT** | **Production Ready** | Saaras v3, 22 languages. Auto-format detection. 50MB limit. |
| **TTS Cache** | **Production Ready** | 128-entry memory cache + disk cache. Eliminates repeat TTS latency. |
| **Browser Voice (MediaRecorder)** | **Experimental** | Mic button → record → STT → query. Chrome/Edge/Safari only. |
| **Barge-in Detection** | **Experimental** | Browser-side: if mic picks up audio during playback, stop speaking. |
| **Noise Cancellation** | **Experimental** | Noise gate + high-pass filter. Disabled by default. |

## Telephony Features

| Feature | Status | Details |
|---|---|---|
| **Twilio Outbound Call** | **Experimental** | `POST /voice/call-me` — initiates call, returns TwiML. Requires LiveKit + Twilio credentials. |
| **Twilio Media Stream** | **Experimental** | WebSocket bridge: Twilio audio ↔ LiveKit. Bi-directional. |
| **LiveKit Token Gen** | **Production Ready** | JWT token generation for LiveKit rooms. |
| **LiveKit Agent** | **Fully Implemented** | `scripts/livekit_agent.py` (712 lines). Full STT(Sarvam) → LLM(Groq) → TTS(Sarvam) pipeline with Silero VAD, interruption handling, telemetry, prewarming. |

## Admin Features

| Feature | Status | Details |
|---|---|---|
| **File Upload** | **Experimental** | PDF, Excel, CSV, TXT. Background processing. Rate-limited (5/min). |
| **KB Re-index** | **Production Ready** | Clears ChromaDB, re-processes all markdown + uploads. |
| **FAQ Management** | **Experimental** | CRUD for JSON KB entries. Admin auth required. |
| **Cache Invalidation** | **Production Ready** | Clear in-memory query cache. |
| **Backup** | **Stub** | Creates dummy text file only. No real data backup. |
| **Admin JWT Auth** | **Production Ready** | `POST /token` → Bearer JWT. Username/password from env vars. |

## Conversation Management

| Feature | Status | Details |
|---|---|---|
| **Conversation CRUD** | **Production Ready** | SQLite-backed. Create, list, get, delete. |
| **Message History** | **Production Ready** | Per-conversation message list. Chronological ordering. |
| **Conversation Persistence** | **Experimental** | Saved to SQLite on /qa/query. Not used for LLM context. |
| **Conversation Telemetry** | **Experimental** | JSON-lines logging of every turn. Granular lifecycle events. |

## New Architecture (Phase 0 — Behind Feature Flags)

| Feature | Status | Details |
|---|---|---|
| **ConversationEngine** | **Not Yet Active** | Single entry point. `use_pipeline=False` by default. |
| **PipelineRunner** | **Not Yet Active** | 6-stage orchestrator. All stages delegate to existing services. |
| **ChannelAdapter** | **Not Yet Active** | Web adapter implemented. Voice/Telephony adapters not yet built. |
| **Event Bus** | **Not Yet Active** | In-memory pub-sub. Zero subscribers registered. |
| **DI Container** | **Not Yet Active** | Lightweight registry. Not used by any active code. |
| **Feature Flags** | **Active** | Registry with env-based loading. All Phase 0-4 flags exist. Migration deadline support. |

## Knowledge Base

| Feature | Status | Details |
|---|---|---|
| **Combined JSON KB** | **Production Ready** | ~550+ FAQ entries. Used for deterministic lookups. |
| **Department Markdown** | **Production Ready** | 12 departments documented. |
| **Topic Markdown** | **Production Ready** | Admissions, fees, hostel, placements, faculty, etc. |
| **Vector Search** | **Production Ready** | ChromaDB + all-MiniLM-L6-v2. ~45MB index. |
| **Semantic Anchors** | **Production Ready** | Section-based KB organization. Admin editable. |

## Known Non-Features (Gaps)

| Missing Feature | Why It's Missing | Required For |
|---|---|---|
| LLM Provider Failover | Only Groq is supported | Production reliability |
| Prompt Versioning | No versioned prompt system | Regulatory compliance |
| Cost Tracking | No token/API usage tracking | Budget management |
| Full-duplex Telephony | Agent implemented, needs end-to-end testing | Telephone demo |
| Multi-tenant Isolation | Single college only | SaaS expansion |
| Circuit Breaker | No timeouts for external APIs | Voice reliability |
| Retry Policy | No retry on LLM failure | Production reliability |
| Context Window Management | No summarization for long sessions | Production conversations |
