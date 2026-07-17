# Current Architecture (2026-07-13)

## Project Overview

College Voice Agent — an AI-powered multi-channel voice/text assistant for **Dr. B.C. Roy Engineering College** admissions. Uses RAG (Retrieval-Augmented Generation) with Groq LLM + Sarvam AI TTS/STT to answer prospective student queries in English, Hindi, and Bengali.

- **Primary use case:** Admissions inquiries (fees, eligibility, placements, hostel, courses)
- **Target channels:** Web chat, browser voice, telephone (Twilio + LiveKit)
- **Scale:** Single-college demo (no multi-tenant)

---

## Folder Structure

```
college_agent-master/
├── backend/
│   ├── app/
│   │   ├── __init__.py                 # Package marker
│   │   ├── main.py                     # FastAPI app, startup, route registration
│   │   ├── config.py                   # Pydantic Settings (env vars)
│   │   ├── database.py                 # SQLite connection + schema init
│   │   ├── auth.py                     # JWT auth helpers
│   │   ├── limiter.py                  # slowapi rate limiter
│   │   ├── logging_config.py           # JSON + rotating file logging
│   │   ├── api/
│   │   │   ├── qa.py                   # POST /qa/query, /qa/query-stream, /qa/session/clear, /qa/health, /qa/debug
│   │   │   ├── conversations.py        # CRUD /api/conversations
│   │   │   ├── tts.py                  # POST /qa/tts, /qa/tts-direct, TTS cache mgmt
│   │   │   ├── stt.py                  # POST /qa/stt, GET /qa/stt/languages
│   │   │   ├── ws_voice.py             # WebSocket /qa/ws/voice (streaming LLM+TTS+audio)
│   │   │   ├── voice.py                # LiveKit token, Twilio call-me, Twilio Media Stream
│   │   │   ├── admin.py                # File upload, backup, KB FAQ management, cache ops
│   │   │   ├── auth_routes.py          # POST /token (JWT login)
│   │   │   ├── health.py               # GET /health, /health/tts
│   │   │   ├── monitoring.py           # GET /monitoring (stub)
│   │   │   └── knowledge_base.py       # POST /admin/reindex (full KB re-index)
│   │   ├── services/
│   │   │   ├── llm/
│   │   │   │   ├── groq_service.py     # Core engine (~5046 lines): LLM, RAG, fee, intent, session, guard
│   │   │   │   ├── fee_engine.py       # Data-driven fee computation (JSON-based)
│   │   │   │   ├── intent_classifier.py# Embedding+keyword intent routing
│   │   │   │   └── safe_point.py       # Hallucination guardrail, post-processing, handoff detection
│   │   │   ├── sarvam_service.py       # Sarvam AI TTS/STT client wrapper
│   │   │   ├── vector_store.py         # ChromaDB + all-MiniLM-L6-v2 embedding search
│   │   │   ├── document_processor.py   # PDF/Excel/Markdown chunking and parsing
│   │   │   ├── livekit_session.py      # LiveKit token generation
│   │   │   ├── twilio_service.py       # Twilio outbound call client
│   │   │   ├── tts_cache.py            # In-memory + disk TTS audio cache
│   │   │   ├── backup.py               # Placeholder backup service
│   │   │   └── normalization/
│   │   │       └── normalizer.py       # STT output normalization, entity resolution
│   │   ├── core/                       # Phase 0: New architecture foundation
│   │   │   ├── interfaces.py           # Abstract base classes for all major components
│   │   │   ├── models.py               # ConversationRequest / ConversationResponse dataclasses
│   │   │   ├── conversation_engine.py  # Single entry point for all channel adapters
│   │   │   ├── event_bus.py            # In-memory pub-sub event bus
│   │   │   ├── feature_flags.py        # Feature flag registry with migration deadline
│   │   │   └── di.py                   # Lightweight dependency injection container
│   │   ├── channel/
│   │   │   ├── base.py                 # BaseChannelAdapter abstract class
│   │   │   └── web_adapter.py          # Web channel adapter (uses ConversationEngine)
│   │   ├── pipeline/
│   │   │   ├── base.py                 # PipelineStage abstract base class
│   │   │   ├── runner.py               # PipelineRunner — stage orchestrator
│   │   │   └── stages/
│   │   │       ├── language.py         # LanguageDetectionStage
│   │   │       ├── intent.py           # IntentClassificationStage
│   │   │       ├── knowledge.py        # KnowledgeRetrievalStage
│   │   │       ├── llm.py              # LLMGenerationStage
│   │   │       ├── guard.py            # SafetyGuardStage
│   │   │       └── formatter.py        # ResponseFormatterStage
│   │   └── utils/
│   │       ├── conversation_logger.py  # Structured telemetry logger (JSON lines)
│   │       ├── language_detect.py      # FastText language detection (en/hi/bn)
│   │       ├── voice_utils.py          # TTS text normalization, abbreviation expansion
│   │       └── stage_profiler.py       # Per-stage latency profiler
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_fee_parity.py          # 109 fee parity tests
│   │   ├── test_fee_engine.py          # 70 fee engine tests
│   │   ├── test_fee_fuzz.py            # 500 noisy fee queries
│   │   ├── test_api_robustness.py
│   │   ├── test_groq_service.py
│   │   ├── test_async_groq.py
│   │   ├── test_language_consistency.py
│   │   ├── test_normalization.py
│   │   ├── test_session_isolation.py
│   │   ├── test_regression_ux.py
│   │   ├── test_structured_memory_regression.py
│   │   ├── multiturn_fee_audit.py      # 25 multi-turn conversations
│   │   ├── verify_demo_phases.py
│   │   └── red_team/
│   │       ├── cases.py                # 147 red-team test cases (P0 + P1)
│   │       ├── pipeline_hooks.py       # Stage capture hooks
│   │       ├── runner.py               # Automated red-team runner
│   │       └── report.py               # Report generator
│   ├── data/
│   │   ├── canonical/                  # Canonical entity data (JSON)
│   │   ├── fee_structures/             # Fee structure JSON files
│   │   ├── knowledge_base/             # Markdown KB + combined_kb.json
│   │   │   ├── departments/            # Department-specific KB (12 departments)
│   │   │   └── topics/                 # Topic-specific KB (admissions, fees, etc.)
│   │   └── models/                     # FastText language detection model
│   ├── scripts/
│   │   └── livekit_agent.py            # LiveKit agent for real-time voice
│   ├── requirements.txt
│   ├── Dockerfile
│   └── validate_blockers.py etc.       # Root-level audit/validation scripts
├── frontend/
│   ├── src/
│   │   ├── main.tsx                    # React entry point
│   │   ├── App.tsx                     # Router, theme, layout
│   │   ├── config.ts                   # API URL config
│   │   ├── types.ts                    # TypeScript type definitions
│   │   ├── components/
│   │   │   ├── Chatbot/
│   │   │   │   ├── Chatbot.tsx         # Floating chat button + window
│   │   │   │   ├── ChatWindow.tsx      # Chat message display
│   │   │   │   └── hooks/useChat.ts    # Chat state management
│   │   │   ├── VoiceChat/
│   │   │   │   └── VoiceChat.tsx       # Full voice assistant UI (602 lines)
│   │   │   ├── Admin/
│   │   │   │   └── AdminDashboard.tsx  # KB management dashboard
│   │   │   └── Sidebar.tsx             # Conversation list sidebar
│   │   └── hooks/
│   │       ├── useVoice.ts             # MediaRecorder + Audio playback
│   │       ├── useVoiceWS.ts           # WebSocket streaming voice client
│   │       └── useNoiseCancellation.ts # Noise gate + VAD
│   └── index.html, package.json, vite.config.ts, etc.
├── data/                                # Top-level data (KB JSON, models)
├── uploads/                             # Uploaded files for ingest
└── logs/                                # Server logs

---

## Request Flows

### Web Chat Flow (Default, Feature Flag OFF)

```
User types message in browser
  → POST /qa/query { message, conversation_id?, session_id? }
    → qa.py::query_endpoint()
      → GroqService.generate_response(query, session_id)
        → Session memory (in-memory dict) ← conversation history
        → Language detection (FastText)
        → Intent classification (embedding + keyword)
        → Fee engine check (if fee intent)
        → Vector store search (top 4 chunks, all-MiniLM-L6-v2)
        → LLM call (Groq Llama 3.3 with context)
        → Hallucination guard (entity extraction + context verification)
        → Safe point post-processing (if demo_safepoint enabled)
        → Response
      → QueryResponse { answer, voice_text, sources, intent, confidence }
  → Display in chat UI
```

### Web Chat Flow (New Pipeline, Feature Flag ON)

```
User types message
  → POST /qa/query
    → qa.py::query_endpoint()
      → GroqService.generate_response()  ← STILL uses old path until migration complete
```

The new pipeline (ConversationEngine → PipelineRunner → stages) is wired in main.py but all `use_pipeline`, `use_channel_adapters`, `use_event_bus` flags default to `False`. The new code path is inactive.

### WebSocket Voice Flow (DEFAULT, active now)

```
User presses mic button in browser
  → WebSocket /qa/ws/voice
    → ws_voice.py::voice_pipeline()
      1. Receive text query from client
      2. Detect language (BCP47 via FastText)
      3. Create background TTS worker (Sarvam AI)
      4. Stream LLM response token-by-token (GroqService.stream_response)
      5. Detect sentence boundaries (. ! ? \n)
      6. Background TTS queue: generate audio for each complete sentence
      7. Stream audio chunks back to client as WAV base64
      8. Signal "done" when complete
```

### Telephony Flow (Twilio + LiveKit Bridge)

```
User calls Twilio phone number
  → Twilio → POST /voice/twiml/outbound?phone=...
    → TwiML <Connect><Stream> to /voice/stream WebSocket
  → WebSocket /voice/stream (twilio_stream)
    → Accept WebSocket
    → Create LiveKit room + token
    → Connect to LiveKit as publishing participant
    → Bi-directional audio bridge:
        ← Twilio → ulaw audio → LiveKit AudioSource
        → LiveKit AudioTrack → ulaw audio → Twilio
    → Real-time conversation via LiveKit agent
```

### RAG Flow (in GroqService)

```
query
  → language detection (FastText: en/hi/bn)
  → intent_classifier.classify()
    → if fee_intent: FeeEngine or FEE_GROUP_MAP lookup → return structured answer
    → if placement/hostel/admission: structured_lookup()
    → if handoff detected: return agent transfer message
    → if unknown/FAQ: fall through to LLM
  → vector_store.search(query, top_k=4) with relevance threshold 0.15
  → build prompt with:
      - system prompt (role, tone, restrictions)
      - conversation history (last 10 turns)
      - retrieved context chunks
      - language hint
  → _call_llm_with_tools() (Groq Mixtral/Llama with tool definitions)
      - can call structured_lookup tool mid-response
  → post_process_response():
      - extract entities from LLM response
      - verify entities exist in retrieved context
      - if entity not in context → polite fallback
      - repeat detection → rephrase unique message
      - banned phrase patterns → sanitize
  → return { answer, voice_text, source, intent }
```

### FeeEngine Flow

```
query with fee intent
  → FeeEngine (if _USE_NEW_FEE_ENGINE=True):
    1. Extract program, category, year, components from query
    2. Load fee structure JSON (mtime-cached)
    3. Compute fee from components (compulsory + optional)
    4. Format response in natural language
    5. If validation fails → silent fallback to FEE_GROUP_MAP
  → FEE_GROUP_MAP (legacy, _USE_NEW_FEE_ENGINE=False):
    - 27+ hardcoded fee entries in groq_service.py
    - Direct string lookup → formatted answer
```

### Session Flow

```
GroqService maintains:
  - _sessions: Dict[str, SessionData]  ← in-memory, lost on restart
  - SessionData:
    - history: deque (maxlen=30)
    - last_intent: str
    - language: str
    - context_used: str
    - follow_up_count: int
    - tuition_answer: str (cached fee response)
  
Database (SQLite, for conversation persistence):
  - conversations table: id, phone_number, title, created_at, updated_at
  - messages table: id, conversation_id, role, content, created_at
  - Used only for: sidebar conversation list, message history reload
  - NOT used for: LLM context (uses in-memory session)
```

### Database Flow

```
init_db(): Called on startup in main.py
  - Creates data/conversations.db (SQLite, WAL mode)
  - Creates conversations + messages tables

API endpoints (conversations.py):
  POST /api/conversations → INSERT conversation
  GET  /api/conversations → SELECT with LEFT JOIN message count
  GET  /api/conversations/{id} → SELECT conversation + messages
  POST /api/conversations/{id}/messages → INSERT message
  PATCH /api/conversations/{id} → UPDATE title
  DELETE /api/conversations/{id} → DELETE messages + conversation cascading
```

### Knowledge Flow

```
Data sources:
  1. data/knowledge_base/combined_kb.json — FAQ entries (voice_ready_answers)
     - Loaded by GroqService._load_kb() into _kb_cache dict
     - Reloadable via POST /admin/kb/reload
  2. data/knowledge_base/departments/*.md — Department markdown files
  3. data/knowledge_base/topics/*.md — Topic markdown files
  4. Uploaded files (uploads/) — PDF, Excel, CSV, TXT

Ingestion pipeline:
  POST /admin/reindex
    → vector_store.clear_collection()
    → document_processor.process_file() for each file
    → Convert to LangChain Document objects
    → vector_store.add_documents() in batches of 50
    → ChromaDB persistence at chroma_db/chroma_db_v2/

Search:
  → vector_store.search(query, top_k=4)
    → HuggingFaceEmbeddings(all-MiniLM-L6-v2)
    → ChromaDB similarity_search_with_relevance_scores
    → Filter by relevance threshold (0.15)
    → If all filtered out, fallback to top 3 unfiltered
```

---

## Architecture Diagrams (Text)

### Request/Response Pipeline (New Architecture, NOT YET ACTIVE)

```
Channel (Web/Voice/Telephony)
  │
  ▼
ChannelAdapter.handle_message()
  │
  ▼
ConversationRequest { text, session_id, channel, ... }
  │
  ▼
ConversationEngine.handle(request)
  │
  ├── (if use_pipeline=True) → PipelineRunner.run()
  │     ├── LanguageDetectionStage     (FastText)
  │     ├── IntentClassificationStage  (embedding + keyword)
  │     ├── KnowledgeRetrievalStage    (ChromaDB)
  │     ├── LLMGenerationStage         (Groq Provider)
  │     ├── SafetyGuardStage           (Safe Point)
  │     └── ResponseFormatterStage     (build ConversationResponse)
  │
  └── (if use_pipeline=False) → _legacy_handle()
        └── GroqService.generate_response()
  │
  ▼
ConversationResponse { text, voice_text, intent, ... }
  │
  ▼
ChannelAdapter.format_response()
  │
  ▼
Channel-specific output (JSON, audio, TwiML, etc.)
```

### Voice Pipeline (ACTIVE via WebSocket)

```
Browser mic → MediaRecorder → PCM audio
  → (future: STT API)
  → User sends text query
  → WebSocket /qa/ws/voice
  → GroqService.stream_response(query)
  → Token-by-token LLM streaming
  → Sentence boundary detection
  → Background TTS worker (Sarvam AI)
  → Audio chunks → base64 WAV → WebSocket → browser Audio element
```

### Telephony Pipeline (ACTIVE via Twilio + LiveKit)

```
Phone → PSTN → Twilio → POST /voice/twiml/outbound
  → TwiML: <Connect><Stream>
  → WebSocket /voice/stream
  → LiveKit room (bi-directional audio)
  → LiveKit Agent (scripts/livekit_agent.py)
  → (future: ASR → LLM → TTS loop)
```

---

## Key Design Decisions

1. **GroqService as God Object:** The entire conversation logic lives in one ~5046-line file. This is the project's biggest technical debt but works correctly for the current scale.

2. **In-memory sessions:** Session history is stored in a Python dict — lost on every restart. SQLite stores conversations for the UI sidebar but is not used for LLM context.

3. **Feature flags disabled by default:** All new architecture (pipeline, channel adapters, event bus) has `False` defaults. The app behaves identically to the pre-Phase 0 version.

4. **Synchronous persistence:** SQLite writes are synchronous — no queue, no batching. WAL mode mitigates contention for demo scale.

5. **JSON knowledge base:** FAQ entries use a static JSON file (`combined_kb.json`) loaded into memory. Changes require admin API to reload.

6. **Single-LLM design:** Only Groq is supported. No provider abstraction, no failover, no fallback chain.
