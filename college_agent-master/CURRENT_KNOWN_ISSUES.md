# Current Known Issues

---

## P0 — Must Fix Before Production (2 items)

### Issue 1: Missing `intent_classifier` attribute in GroqService
**File:** `app/services/llm/groq_service.py:__init__`
**Description:** The `__init__` method does not set `self.intent_classifier`. When `_INTENT_CLASSIFIER_AVAILABLE` is True, the `_classify_intent` method accesses `self.intent_classifier` which raises `AttributeError`.
**Impact:** CRITICAL. Any query that triggers intent classification will crash at runtime with `AttributeError: 'GroqService' object has no attribute 'intent_classifier'`.
**Fix:** Add `self.intent_classifier = _IntentClassifier()` after the try/except block for intent_classifier import, guarded by `_INTENT_CLASSIFIER_AVAILABLE`.
**Found by:** Static code audit (2026-07-13)

### Issue 2: Undefined `fee_intent` variable in GroqService
**File:** `app/services/llm/groq_service.py:3689` (approximate)
**Description:** A variable `fee_intent` is referenced in the fee handling section but was never defined (likely renamed in a refactor). Will raise `NameError` at runtime.
**Impact:** CRITICAL. Any fee-related query will crash at runtime with `NameError: name 'fee_intent' is not defined`.
**Fix:** Declare `fee_intent = False` (or the correct boolean) before it's referenced.
**Found by:** Static code audit (2026-07-13)

---

## P1 — Should Fix Before Production (5 items)

### Issue 3: Duplicate clarify-repeat messages
**Files:** `app/services/llm/groq_service.py:698-701`
**Description:** Lines 698-699 define clarify/repeat message arrays, then lines 700-701 redefine them (overwriting the first set). The second set is the correct one, but the dead code should be removed.
**Impact:** Low (second definition wins). Cleanliness issue.

### Issue 4: Dead `except ImportError` block referencing wrong variable
**File:** `app/services/llm/groq_service.py` (near ImportError handler)
**Description:** An `except ImportError` block references a variable name that doesn't match the try block's import target.
**Impact:** Low (block would never execute correctly if triggered).

### Issue 5: Principal alias missing in entity dictionary
**File:** `app/services/normalization/normalizer.py` (entity dictionary)
**Description:** "principal" (and Hindi/Bengali equivalents) are not in the entity alias list. Queries mentioning "principal" may not resolve to the principal's name.
**Impact:** Medium. Users asking "who is the principal" may get a "I don't know" or irrelevant response instead of the actual principal name.

### Issue 6: BCREC expansion missing in normalization
**File:** `app/services/normalization/normalizer.py` (entity dictionary)
**Description:** "BCREC" is not mapped to its full form "Dr. B.C. Roy Engineering College" in the normalization pipeline.
**Impact:** Medium. The abbreviation may not be understood by all users. The LLM may still resolve it from context.

### Issue 7: Hindi principal mapping missing
**File:** `app/services/normalization/normalizer.py` (entity dictionary)
**Description:** Principal entity mapping for Hindi aliases is incomplete.
**Impact:** Low. Hindi users asking about the principal may not get entity resolution.

---

## P2 — Technical Debt & Known Limitations (12 items)

### Issue 8: Hardcoded CORS origins
**File:** `app/main.py:66-80`
**Description:** CORS `allow_origins` is a hardcoded list of localhost URLs. Does not read from `CORS_ORIGINS` env var.
**Impact:** Deployment to non-localhost domains will fail with CORS errors. Each deployment requires a code change.
**Fix:** Read `CORS_ORIGINS` from env var (comma-separated), fallback to localhost list.

### Issue 9: `nul` file in repository root
**File:** `nul` (Windows reserved name)
**Description:** Windows reserved name "nul" exists as a file in the repo root. Blocks `git add -A` on Windows because PowerShell interprets "nul" as `NUL` device.
**Impact:** Low. Only affects Windows developers running `git add -A`. Workaround: `git add --ignore-errors` or avoid `-A`.

### Issue 10: `voice_session.py` dead code with broken import
**File:** `app/services/voice_session.py` (referenced in codebase but file may not exist)
**Description:** References to `voice_session.py` exist but the file may have been deleted or never created. The import will fail if the code path is triggered.
**Impact:** Low (code path is likely unreachable). Cleanup item.

### Issue 11: `GEMINI_API_KEY` environment variable unused
**File:** `app/config.py:31`
**Description:** `gemini_api_key` is defined in Settings but never used anywhere in the codebase.
**Impact:** None. Dead configuration.

### Issue 12: Backup service is a stub
**File:** `app/services/backup.py`
**Description:** `create_backup()` writes a dummy text file. `list_backups()` returns filenames. No actual data backup occurs.
**Impact:** Admin backup feature is non-functional. User may think data is being backed up.

### Issue 13: Port inconsistency (8000 vs 8001)
**Files:** `app/main.py:165` (uvicorn on 8000), `scripts/start_server.ps1` (may use 8001 elsewhere)
**Description:** Some documentation/scripts reference port 8001. The app runs on 8000.
**Impact:** Low. Confusion during setup.

### Issue 14: WebSocket voice pipeline is single-turn only
**File:** `app/api/ws_voice.py`
**Description:** The WebSocket voice pipeline connects, processes one query, then signals "done". No mechanism for follow-up queries on the same connection. No conversation history passed to the LLM.
**Impact:** Medium. Voice chat cannot have back-and-forth conversations. Each query is independent.

### Issue 15: FastText model URL may 404
**File:** `app/utils/language_detect.py:22`
**Description:** The FastText model download URL (`https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz`) is a third-party URL that may become unavailable.
**Impact:** Medium. Without the model, language detection falls back to keyword-based heuristics with reduced accuracy.

### Issue 16: Intent classification duelling (regex vs embedding)
**File:** `app/services/llm/intent_classifier.py`
**Description:** The intent classifier uses both regex keyword patterns and embedding-based semantic matching. When these disagree, the result is unpredictable (whichever code path executes last wins).
**Impact:** Medium. Some queries may be misclassified if patterns and embeddings disagree.

### Issue 17: No LLM streaming timeout
**File:** `app/services/llm/groq_service.py`
**Description:** The LLM streaming response has no timeout. If Groq API hangs, the user's request hangs indefinitely.
**Impact:** Medium. Voice/telephony channels cannot tolerate unbounded waits.

### Issue 18: Session memory lost on restart
**File:** `app/services/llm/groq_service.py` (`_sessions: dict`)
**Description:** All in-memory sessions are lost when the server restarts. SQLite database is not used for session restoration.
**Impact:** Medium. Users lose conversation context after any deployment.

### Issue 19: `/qa/debug` endpoint has no auth
**File:** `app/api/qa.py:130-145`
**Description:** The debug endpoint returns internal state (context content, cache stats, language detection) without authentication.
**Impact:** Low for demo. Should be restricted in production.

---

## P3 — Cosmetic & Nice-to-Have (8 items)

### Issue 20: Server log files accumulate in project root
**Description:** ~15 server log files (`server.log`, `server_err.log`, `server_out.log`, etc.) in the backend root directory.
**Impact:** Low. Aesthetic and makes `git status` noisy.

### Issue 21: `README.md` walkthrough link broken
**Description:** The README may reference a walkthrough guide URL that no longer works.
**Impact:** Low. Development convenience.

### Issue 22: `.env.example` may be missing variables
**Description:** The `.env.example` file may not include all required environment variables (e.g., new Phase 0 settings).
**Impact:** Low. New developers may miss configuration.

### Issue 23: No structured error responses
**Description:** API errors return plain HTTPException messages. No consistent error schema with codes, details, or request IDs.
**Impact:** Low. Frontend can only show generic error messages.

### Issue 24: `fasttext-wheel` dependency is Windows-specific
**File:** `requirements.txt:22`
**Description:** `fasttext-wheel` is needed for Windows compatibility. Linux/Mac users need `fasttext`.
**Impact:** Low. Cross-platform development requires different requirements files.

### Issue 25: Groq API key may be visible in logs
**File:** `app/config.py:78-79`
**Description:** The `mask()` function is called for logging but the actual key may be logged in error traces.
**Impact:** Low. Key is masked in normal operation but may appear in exception traces.

### Issue 26: No request ID tracking
**Description:** No unique request ID is generated per API call. Correlating logs across services is difficult.
**Impact:** Low at demo scale. Critical at production scale.

### Issue 27: No health check for ChromaDB status
**File:** `app/api/health.py`
**Description:** The health endpoint checks TTS and Groq availability but does not check whether the vector store is accessible.
**Impact:** Low. A failed vector store would only be noticed when a query fails.
