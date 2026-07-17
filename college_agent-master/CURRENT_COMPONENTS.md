# Current Components

---

## Backend Components (app/)

### main.py
**Purpose:** Application entry point. FastAPI app creation, middleware, route registration, static file serving, Phase 0 initialization.
**Why it exists:** Standard FastAPI pattern. Wires all routers, CORS, rate limiting, and recently Phase 0 components.
**Size:** 187 lines
**Dependents:** None (it's the root)

---

### config.py
**Purpose:** Centralized configuration via Pydantic Settings. Loads from `.env`, `local.env`, or environment variables.
**Why it exists:** All API keys, credentials, and runtime configuration in one place. Initializes Groq + Sarvam clients.
**Key settings:** `groq_api_key`, `sarvam_api_key`, `demo_safepoint`, `college_name`, admin credentials, Twilio/LiveKit credentials.
**Dependents:** EVERY component imports `settings` from here.

---

### database.py
**Purpose:** SQLite connection management + schema creation.
**Why it exists:** Persistent storage for conversations and messages. WAL mode for demo-scale concurrency.
**Tables:** `conversations`, `messages` (with foreign key + index)
**Dependents:** `api/conversations.py`

---

### auth.py
**Purpose:** JWT authentication helpers: password verification, token creation, admin validation.
**Why it exists:** Protects admin endpoints. Uses `python-jose` + `passlib`.
**Dependents:** `api/admin.py`, `api/auth_routes.py`, `api/knowledge_base.py`

---

### limiter.py
**Purpose:** Rate limiter (slowapi, 10 requests/minute/IP default).
**Why it exists:** Prevents abuse on public endpoints.
**Dependents:** `main.py`, `api/admin.py`, `api/auth_routes.py`

---

### logging_config.py
**Purpose:** Structured logging setup with JSON formatter + rotating file handlers.
**Why it exists:** Structured logs for production debugging. Separate error log file for monitoring.
**Output:** `logs/app.log` (JSON), `logs/error.log` (JSON only errors), console (human-readable)

---

## API Components (app/api/)

### qa.py
**Size:** 145 lines
**Endpoints:** `/qa/query`, `/qa/query-stream`, `/qa/session/clear`, `/qa/health`, `/qa/debug`
**Dependencies:** `GroqService`, `settings`, `safe_point` (via demo_safepoint flag), `language_detect`
**Why it exists:** Main user-facing Q&A interface. Both synchronous and streaming response paths.

### conversations.py
**Size:** 273 lines
**Endpoints:** Full CRUD for conversations + messages
**Dependencies:** SQLite via `database.py`
**Why it exists:** Conversation persistence for the frontend sidebar. Also serves message history for conversation reload.
**Note:** This is the OLD conversation system. The frontend VoiceChat loads messages via these endpoints but the LLM uses in-memory sessions, not these persisted messages.

### tts.py
**Size:** 250 lines
**Endpoints:** `/qa/tts`, `/qa/tts-direct`, `/qa/tts/voices`, `/qa/tts/languages`, TTS cache endpoints
**Dependencies:** `SarvamService`, `tts_cache`
**Why it exists:** Text-to-Speech for voice responses. Direct endpoint bypasses disk I/O. Auto-selects native speakers per language.

### stt.py
**Size:** 110 lines
**Endpoints:** `/qa/stt`, `/qa/stt/languages`
**Dependencies:** `SarvamService`
**Why it exists:** Speech-to-Text for voice input. Supports 22 Indian languages.

### ws_voice.py
**Size:** 117 lines
**Endpoints:** WebSocket `/qa/ws/voice`
**Dependencies:** `GroqService`, `SarvamService`, `language_detect`
**Why it exists:** Full voice pipeline: text → LLM stream → sentence detection → TTS → audio chunks. Single-turn only.

### voice.py
**Size:** 186 lines
**Endpoints:** `/voice/token`, `/voice/call-me`, `/voice/twiml/outbound`, WebSocket `/voice/stream`
**Dependencies:** `LiveKitService`, `TwilioService`, `audioop`, `livekit`
**Why it exists:** Telephone integration. LiveKit token generation, Twilio outbound calls, bi-directional audio bridge.

### admin.py
**Size:** 318 lines
**Endpoints:** File upload, backup, FAQ CRUD, cache management, semantic anchor updates
**Dependencies:** `GroqService`, `DocumentProcessor`, `BackupService`, auth
**Why it exists:** Admin dashboard backend for KB management. Replaces manual script execution.

### auth_routes.py
**Size:** 45 lines
**Endpoints:** `POST /token`
**Dependencies:** `auth.py`, `settings`
**Why it exists:** JWT login endpoint for admin authentication.

### health.py
**Size:** 45 lines
**Endpoints:** `GET /health/`, `GET /health/tts`
**Dependencies:** `SarvamService`
**Why it exists:** Health check endpoints for monitoring.

### knowledge_base.py
**Size:** 94 lines
**Endpoints:** `POST /admin/reindex`
**Dependencies:** `VectorStoreService`, `DocumentProcessor`, auth
**Why it exists:** Full KB re-index without manual script execution.

### monitoring.py
**Size:** 7 lines
**Endpoints:** `GET /monitoring/`
**Dependencies:** None
**Why it exists:** Stub for future monitoring integration.

---

## Service Components (app/services/)

### GroqService (services/llm/groq_service.py)
**Size:** ~5046 lines (the largest file in the project)
**Pattern:** Singleton via `get_groq_service()`
**Key responsibilities:**
- LLM generation (sync + streaming via Groq API)
- Session management (in-memory per session_id)
- Intent classification integration
- Fee query handling (dual: FeeEngine + FEE_GROUP_MAP)
- RAG: vector store search + context injection
- Hallucination guard: entity extraction + context verification
- Repeat detection (identical queries within 3 turns)
- Follow-up expansion (short queries → full intent)
- Multilingual prompts (EN/HI/BN/Banglish)
- LRU cache for responses (512 entries)
- KB management (load, reload, cache)
- Structured lookup for admissions, placement, hostel, principal/HOD info

**Why it's large:** It's a God Object. Every business concern (fee, admission, placement, language, session, cache, guard) lives in one file. This works but is hard to test, extend, or parallelize.

### FeeEngine (services/llm/fee_engine.py)
**Size:** 874 lines
**Pattern:** Standalone class
**Responsibilities:**
- Parse fee queries (program, category, year, components)
- Load fee structure from JSON files (mtime-cached)
- Component-based fee computation
- Versioned structures (active/superseded/archived/draft)
- Silent fallback on validation failure (never breaks the user experience)

### IntentClassifier (services/llm/intent_classifier.py)
**Size:** ~500 lines (estimated from file count)
**Pattern:** Singleton with embedding + keyword classification
**Responsibilities:**
- Classify query into: fee_query, admission_query, placement_query, hostel_query, general_query, handoff, etc.
- Embedding-based semantic matching
- Keyword pattern fallback
- Multi-language support

### SafePoint (services/llm/safe_point.py)
**Size:** 246 lines
**Pattern:** Module-level functions
**Responsibilities:**
- Hallucination guard: extract entities from LLM response → verify against retrieved context
- Response post-processing: personality enforcement, banned phrase patterns
- Handoff detection (human/operator/live person requests)
- Variable greeting generation (10 rotating variations in EN/HI/BN)
- Demo mode: response simplification for the demo audience

### SarvamService (services/sarvam_service.py)
**Size:** 304 lines
**Pattern:** Singleton
**Responsibilities:**
- TTS: Bulbul v3 model, 30+ voices, 22 languages
- STT: Saaras v3 model, streaming and non-streaming
- Speaker selection per language (native accents)
- Response normalization

### VectorStoreService (services/vector_store.py)
**Size:** 151 lines
**Pattern:** Singleton
**Responsibilities:**
- ChromaDB-backed semantic search
- all-MiniLM-L6-v2 embeddings (fast startup, ~2s)
- Relevance threshold filtering (0.15)
- Document management (add, clear, fallback recreate)
- Similarity search with relevance scores

### DocumentProcessor (services/document_processor.py)
**Size:** 214 lines
**Responsibilities:**
- File parsing: PDF (pypdf), Excel (pandas+openpyxl), CSV, Markdown, TXT
- Text chunking with overlap
- Structured metadata extraction

### LiveKitService (services/livekit_session.py)
**Size:** 71 lines
**Pattern:** Singleton
**Responsibilities:**
- LiveKit access token generation
- Room + participant management

### TwilioService (services/telephony/twilio_service.py)
**Size:** 49 lines
**Pattern:** Singleton
**Responsibilities:**
- Outbound call initiation via Twilio API
- Webhook URL configuration

### TTSCache (services/tts_cache.py)
**Size:** 104 lines
**Pattern:** Module-level functions (no class)
**Responsibilities:**
- 128-entry in-memory cache + disk cache for TTS audio
- MD5 keyed by (text, language, speaker)
- Cache statistics (memory entries, disk files, bytes)

### BackupService (services/backup.py)
**Size:** 37 lines
**Pattern:** Class
**Responsibilities:**
- **Stub only.** Creates a dummy text file. No real backup functionality.

### Normalizer (services/normalization/normalizer.py)
**Size:** 504 lines
**Pattern:** Module-level functions exported via `__init__.py`
**Responsibilities:**
- Unicode normalization (NFKC)
- Mixed-language word mapping (Bengali/Hindi → English)
- STT mistake correction from entity dictionary
- Exact alias replacement
- Fuzzy entity resolution (SequenceMatcher, thresholds at 0.75/0.55)
- Normalization logging for debugging

---

## Core Components (app/core/) — NEW, NOT YET ACTIVE

### ConversationEngine
**Size:** 60 lines
**Pattern:** Class, instantiated in main.py
**Responsibilities:**
- Single entry point for all channels
- Routes to either new pipeline or legacy GroqService based on `use_pipeline` flag
- Migration deadline warning on legacy path
- Error containment

### PipelineRunner
**Size:** 65 lines
**Pattern:** Class with stage list
**Responsibilities:**
- Orchestrate stages sequentially
- Per-stage latency tracking
- Short-circuit support (`_short_circuit` flag)
- Error containment (one stage failure doesn't crash the pipeline)
- Build ConversationResponse from context

### Pipeline Stages (pipeline/stages/)
**6 stages, all ~10-20 lines each, all delegate to existing services:**

| Stage | Delegates To |
|---|---|
| LanguageDetectionStage | `language_detect.detect_language()` |
| IntentClassificationStage | `intent_classifier.classify()` |
| KnowledgeRetrievalStage | `vector_store.search()` |
| LLMGenerationStage | `GroqService.generate_response()` or `LLMProvider.generate()` |
| SafetyGuardStage | `safe_point.post_process_response()` |
| ResponseFormatterStage | Builds `ConversationResponse` |

### ChannelAdapter (channel/)
- `BaseChannelAdapter`: Abstract class with `enrich_context` helper
- `WebChannelAdapter`: Concrete adapter for web channel. Uses ConversationEngine.

### EventBus
**Size:** 40 lines
**Pattern:** Class, in-memory
**Status:** Zero subscribers. Interface retained for future observability use.

---

## Frontend Components (frontend/src/)

### App.tsx
**Purpose:** Root React component. Router, MUI theme, layout (header/nav/footer), routes.
**Routes:** `/` → VoiceChat with Sidebar, `/admin` → AdminDashboard (lazy loaded)

### VoiceChat/VoiceChat.tsx
**Size:** 602 lines
**Purpose:** Main user interface. Text input, mic button, message display, audio queue, TTS playback, streaming mode (WebSocket), continuous hands-free mode.
**Key states:** `conversationId`, `messages`, `isProcessing`, `isSpeaking`, `continuousMode`, `pipelineMode`, `streamingAnswer`
**Dependencies:** `useVoice`, `useVoiceWS`, `useNoiseCancellation` hooks

### Chatbot/Chatbot.tsx + ChatWindow.tsx + hooks/useChat.ts
**Purpose:** Floating chat widget (alternative to full VoiceChat). Fixed-position FAB button → popup chat window.
**Dependencies:** `POST /qa/query` for all messages.

### Admin/AdminDashboard.tsx
**Purpose:** KB management UI: upload files, manage FAQs, re-index, cache management, backup.

### Sidebar.tsx
**Purpose:** Conversation list sidebar. Shows recent conversations, allows selection and new chat creation.
**Dependencies:** CRUD `/api/conversations`

### hooks/useVoice.ts
**Purpose:** MediaRecorder wrapper. Handles mic access, audio recording, STT API calls, audio playback.
**States:** `isSupported`, `isRecording`, `transcript`, `interimTranscript`, `error`

### hooks/useVoiceWS.ts
**Purpose:** WebSocket client for `/qa/ws/voice`. Streams tokens, receives audio chunks, handles connection lifecycle.
**Callbacks:** `onToken`, `onAudio`, `onError`, `onDone`

### hooks/useNoiseCancellation.ts
**Purpose:** Audio processing with noise gate + high-pass filter. Disabled by default (inactive code path).
