# Current API Reference

---

## Core Q&A

### POST /qa/query
**Purpose:** Main Q&A endpoint. Returns complete answer.
**Feature Flag:** None (always active)

**Request:**
```json
{
  "message": "string (required)",
  "conversation_id": "string (optional)",
  "session_id": "string (optional, defaults to 'default')"
}
```

**Response (QueryResponse):**
```json
{
  "answer": "string",
  "voice_text": "string (optional)",
  "sources": [],
  "session_id": "string",
  "conversation_id": "string (optional)",
  "source": "groq_rag | faq_deterministic",
  "intent": "llm_generated | faq_deterministic",
  "confidence": 0.95
}
```

**Dependencies:** `GroqService.generate_response()` → language detection → intent classifier → vector store → LLM call → safe point
**Consumers:** Frontend VoiceChat component (`handleQuery`)

---

### POST /qa/query-stream
**Purpose:** Streaming Q&A. Server-sent events (SSE).
**Feature Flag:** None (always active)

**Request:** Same as `/qa/query`

**Response:** SSE stream
```
data: {"text": "chunk"}\n\n
...
data: [DONE]\n\n
```

**Dependencies:** `GroqService.stream_response()` → same pipeline as non-streaming but token-by-token
**Consumers:** Frontend (not currently used by default — uses non-streaming endpoint)

---

### POST /qa/session/clear
**Purpose:** Clear in-memory session history for a session ID.

**Request:**
```json
{ "session_id": "string" }
```

**Response:** `{ "status": "ok", "session_id": "string" }`

**Dependencies:** `GroqService.clear_session()`
**Consumers:** Admin/debug tools

---

### GET /qa/health
**Purpose:** Health check for Q&A service.

**Response:**
```json
{
  "status": "healthy",
  "service": "BCREC Voice Brain",
  "engine": "Groq Llama 3.3",
  "groq_available": true,
  "sarvam_available": true
}
```

**Dependencies:** `settings.groq_api_key`, `settings.sarvam_api_key`
**Consumers:** Frontend VoiceChat component (health monitor chips)

---

### POST /qa/debug
**Purpose:** Debug endpoint — returns language, context, cache stats without LLM call.
**Auth:** None (should be restricted)

**Request:** Same as `/qa/query`

**Response:**
```json
{
  "query": "string",
  "lang": "string",
  "context_preview": "string",
  "context_len": 0,
  "cache": { "...": "..." }
}
```

**Dependencies:** `GroqService._retrieve_context()`, `detect_language()`, `GroqService.get_cache_stats()`

---

## Text-to-Speech

### POST /qa/tts
**Purpose:** Convert text to speech. Returns audio file URL.
**Feature Flag:** None (requires SARVAM_API_KEY)

**Request:**
```json
{
  "text": "string (required)",
  "language": "en-IN (default)",
  "speaker": "shubh (default)",
  "pace": 1.0,
  "session_id": "string (optional)"
}
```

**Response (TTSResponse):**
```json
{
  "audio_url": "/audio/tts_xxx.wav",
  "format": "wav",
  "language": "en-IN",
  "speaker": "shubh"
}
```

**Dependencies:** `SarvamService.text_to_speech()`, writes WAV file to disk
**Consumers:** Frontend VoiceChat (`speakAnswer` function)

---

### POST /qa/tts-direct
**Purpose:** TTS returning audio bytes directly (no disk I/O).
**Feature Flag:** None

**Request:** Same as `/qa/tts`
**Response:** Raw WAV bytes with `Content-Type: audio/wav` and `X-TTS-Cache: hit|miss` header.

**Dependencies:** `SarvamService.text_to_speech()`, `tts_cache.get_cached_audio()`
**Consumers:** Frontend VoiceChat (preferred over /qa/tts for lower latency)

---

### GET /qa/tts/voices
**Purpose:** List available TTS voices.

**Response:** `{ "voices": [...], "default": "shubh" }`

**Dependencies:** `SarvamService.get_available_voices()`

---

### GET /qa/tts/languages
**Purpose:** List supported TTS languages.

**Response:** `{ "languages": {...}, "default": "en-IN" }`

**Dependencies:** `SarvamService.get_supported_languages()`

---

## Speech-to-Text

### POST /qa/stt
**Purpose:** Transcribe audio to text.
**Feature Flag:** None (requires SARVAM_API_KEY)

**Request:** `multipart/form-data`
- `audio`: File (WAV, MP3, WebM, OGG, AAC, FLAC, M4A)
- `language`: string (default `"en-IN"`)
- `model`: string (default `"saaras:v3"`)

**Response:**
```json
{
  "text": "transcribed text",
  "language": "en-IN",
  "confidence": 0.95,
  "model": "saaras:v3"
}
```

**Dependencies:** `SarvamService.speech_to_text()`
**Consumers:** Frontend (via useVoice hook → MediaRecorder → STT API)

---

### GET /qa/stt/languages
**Purpose:** List supported STT languages.

**Response:**
```json
{
  "languages": { "en-IN": "English (India)", ... },
  "default": "en-IN"
}
```

---

## WebSocket Voice

### WebSocket /qa/ws/voice
**Purpose:** Full-duplex voice pipeline: text → LLM stream → TTS → audio.
**Feature Flag:** None (active)

**Protocol:**
1. Client sends: `{ "type": "text", "data": "query text", "language": "optional bcp47" }`
2. Server streams: `{ "type": "token", "data": "token text" }` (for display)
3. Server streams: `{ "type": "audio", "data": "base64_wav", "format": "wav" }` (per sentence)
4. Server sends: `{ "type": "done" }` when complete
5. On error: `{ "type": "error", "message": "..." }`

**Dependencies:** `GroqService.stream_response()`, `SarvamService.text_to_speech_streamed()`, `detect_language_bcp47()`
**Consumers:** Frontend `useVoiceWS` hook

---

## Voice / Telephony

### POST /voice/token
**Purpose:** Generate LiveKit access token.

**Request:**
```json
{
  "room_name": "string (required)",
  "participant_identity": "string (optional)"
}
```

**Response:**
```json
{
  "token": "jwt_token",
  "identity": "user_xxxx",
  "server_url": "wss://..."
}
```

**Dependencies:** `LiveKitService.generate_token()`
**Consumers:** Frontend (for LiveKit client connections)

---

### POST /voice/call-me
**Purpose:** Initiate an outbound Twilio phone call.
**Auth:** None (requires TWILIO_* env vars)

**Request:**
```json
{
  "phone_number": "string (required, E.164 format)",
  "base_url": "string (required, for Twilio webhook)"
}
```

**Response:**
```json
{
  "success": true,
  "call_sid": "CAxxxx"
}
```

**Dependencies:** `TwilioService.make_outbound_call()`

---

### POST /voice/twiml/outbound
**Purpose:** Twilio webhook — returns TwiML for outbound call.
**Auth:** Called by Twilio (should validate Twilio signature)

**Response:** `application/xml` — TwiML with `<Connect><Stream>` to `/voice/stream`

**Dependencies:** `host` header for stream URL construction

---

### WebSocket /voice/stream
**Purpose:** Twilio Media Stream bridge → LiveKit room.
**Protocol:** Twilio Media Stream protocol (JSON messages):
- `event: "start"` — initial connection metadata
- `event: "media"` — audio payload (ulaw, base64)
- `event: "stop"` — end of stream

**Dependencies:** `livekit.api`, `audioop`, resampling (8kHz → 16kHz)

---

## Auth

### POST /token
**Purpose:** Admin JWT login.
**Rate Limit:** 5/minute

**Request:** `application/x-www-form-urlencoded` (OAuth2 Password flow)
- `username`: string
- `password`: string

**Response:**
```json
{
  "access_token": "jwt",
  "token_type": "bearer"
}
```

**Dependencies:** `settings.admin_username`, `settings.admin_password`, `settings.secret_key`
**Consumers:** AdminDashboard frontend, API clients

---

## Conversation Management

### POST /api/conversations
**Purpose:** Create new conversation.

**Response:**
```json
{
  "id": "uuid",
  "title": "New Chat",
  "created_at": "ISO8601"
}
```

**Dependencies:** SQLite `conversations` table

---

### GET /api/conversations
**Purpose:** List all conversations (most recent first).

**Response:**
```json
[
  {
    "id": "uuid",
    "title": "string",
    "created_at": "ISO8601",
    "updated_at": "ISO8601",
    "message_count": 0
  }
]
```

**Dependencies:** SQLite LEFT JOIN query

---

### GET /api/conversations/{id}
**Purpose:** Get single conversation with all messages.

**Response:**
```json
{
  "id": "uuid",
  "title": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "messages": [
    {
      "id": "uuid",
      "role": "user | assistant",
      "content": "string",
      "created_at": "ISO8601"
    }
  ]
}
```

**Dependencies:** SQLite query with JOIN
**Consumers:** Frontend `loadConversationMessages()`

---

### GET /api/conversations/{id}/messages
**Purpose:** Get recent messages (newest first, reversed to chronological).
**Query:** `?limit=N` (default 10)

**Response:** `[{ Message }, ...]`

---

### POST /api/conversations/{id}/messages
**Purpose:** Add message to conversation.

**Request:**
```json
{
  "role": "user | assistant",
  "content": "string"
}
```

**Response:** `{ Message }`

---

### PATCH /api/conversations/{id}
**Purpose:** Update conversation title.

**Request:** `{ "title": "string" }`
**Response:** `{ "status": "ok", "title": "string" }`

---

### DELETE /api/conversations/{id}
**Purpose:** Delete conversation and its messages.
**Response:** `{ "status": "deleted" }`

---

### DELETE /api/conversations
**Purpose:** Delete ALL conversations (privacy/reset).
**Response:** `{ "status": "all deleted" }`

---

## Admin

### POST /admin/upload
**Purpose:** Upload files for KB ingestion.
**Auth:** JWT required
**Rate Limit:** 5/minute

**Request:** `multipart/form-data` — `files[]` (multiple)
**Response:** `{ "message": "...", "files": ["filename1", ...] }`

**Dependencies:** `DocumentProcessor.process_file()`, background task

---

### GET /admin/files
**Purpose:** List uploaded files with processing status.
**Auth:** JWT required
**Response:** `{ "files": [{"filename": "...", "size": N, "processed": bool, "uploaded_at": timestamp}, ...] }`

---

### POST /admin/reindex
**Purpose:** Full KB re-index (clear + re-ingest all).
**Auth:** JWT required

**Response:** `{ "message": "...", "chunks": N }`

**Dependencies:** `VectorStoreService.clear_collection()`, `DocumentProcessor.process_file()` for every file

---

### POST /admin/kb/faq/{key}
**Purpose:** Add or update a FAQ entry. Reloads KB immediately.
**Auth:** JWT required
**Rate Limit:** 10/minute

**Request:**
```json
{
  "keywords": ["list"],
  "answers": { "en": "answer", "hi": "answer" },
  "sub_answers": {}
}
```

**Response:** `{ "message": "...", "key": "string", "faq_count": N }`

**Dependencies:** `combined_kb.json` file, `GroqService.reload_kb()`

---

### DELETE /admin/kb/faq/{key}
**Purpose:** Delete a FAQ entry.
**Auth:** JWT required
**Rate Limit:** 10/minute

---

### GET /admin/kb/faq
**Purpose:** List all FAQ entries.

---

### POST /admin/kb/reload
**Purpose:** Force-reload KB from disk.
**Auth:** JWT required
**Rate Limit:** 5/minute

**Response:** `{ "message": "...", "faq_count": N }`

---

### POST /admin/kb/update-anchor
**Purpose:** Update semantic anchor for KB entry.
**Auth:** JWT required
**Rate Limit:** 10/minute

**Query Params:** `section`, `subsection` (optional), `new_anchor`
**Dependencies:** Triggers re-ingestion via `ingest_kb()`

---

### POST /admin/cache/invalidate
**Purpose:** Clear in-memory query cache.
**Auth:** JWT required
**Rate Limit:** 5/minute

**Response:** `{ "message": "...", "entries_cleared": N }`

---

### GET /admin/cache/stats
**Purpose:** Show cache hit/miss stats.
**Auth:** JWT required

---

### POST /admin/backup/create
**Purpose:** Create backup (stub — creates dummy file).
**Auth:** JWT required

---

### GET /admin/backups
**Purpose:** List backups (stub).

---

### DELETE /admin/backup/{filename}
**Purpose:** Delete a backup file (stub).

---

## Monitoring & Health

### GET /health/
**Purpose:** Basic health check.

**Response:** `{ "status": "ok", "service": "BCREC Voice Agent" }`

---

### GET /health/tts
**Purpose:** TTS provider health check.

**Response:** `{ "sarvam_available": bool, "active_provider": "sarvam|none", "status": "healthy|degraded", "key_configured": bool }`

---

### GET /monitoring/
**Purpose:** Monitoring stub.

**Response:** `{ "status": "healthy" }`

---

### GET /qa/tts/cache/stats
**Purpose:** TTS cache statistics.

**Response:** `{ "memory_entries": N, "memory_max": 128, "disk_files": N, "disk_bytes": N, "cache_dir": "..." }`

---

### POST /qa/tts/cache/invalidate
**Purpose:** Clear TTS cache (memory + disk).
**Auth:** None (should require auth)

**Response:** `{ "in_memory_cleared": N, "on_disk_cleared": N }`
