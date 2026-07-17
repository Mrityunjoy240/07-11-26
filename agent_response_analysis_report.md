# Root-Cause Analysis: Why the Agent Responds Like a Data Dump Instead of a Counselor

## Executive Summary

The agent's non-conversational, fact-dump behavior is caused by **four interacting factors**, listed in order of impact:

1. **`_structured_lookup()` (line 2708) pre-empts the LLM for broad queries** — the admission handler regex (line 2873-2876) matches `"mujhe admission lena he"` and returns a hardcoded fact string before the LLM ever sees the query.

2. **The SYSTEM_PROMPT (line 775-859) is a flat data dump** — 60% of the prompt is raw college facts (lines 809-859), trained to be regurgitated; only 1 line says "be conversational" (line 780) with zero guidance on asking clarifying questions.

3. **No "clarify first" instruction exists anywhere** — neither the system prompt, the structured handlers, nor the conversation manager tell the agent to ask the user about their interests before making recommendations.

4. **The LLM temperature is 0.3 (line 1498/1507)** — this favors deterministic, conservative "safe" responses (regurgitating known facts) rather than creative, conversational exploration.

---

## 1. Example: `"mujhe admission lena he"` → Immediate Admission Dump

### Decision Path (all in `groq_service.py` unless noted)

| Step | Function | Line | What Happens | Outcome |
|------|----------|------|-------------|---------|
| 0 | `generate_response()` | 3850 | Entry point — receives `"mujhe admission lena he"` | |
| 1 | `normalize_query()` | 3879 | STT normalization (no-ops in this case) | query unchanged |
| 2 | Hinglish `q→kyu` fix | 3888 | `"q"` not present | no change |
| 3 | Yes/no continuation | 3898 | Not yes/no | skip |
| 4 | `_validate_transcript()` | 3934 | Not noise/fragment | pass |
| 5 | `_detect_noisy_transcript()` | 3960 | Not garbage | pass |
| 6 | `_resolve_language()` | 3988 | Detects Hindi | `lang="hi"` |
| 7 | `_is_lang_switch()` | 4012 | Not a switch command | skip |
| 8 | `_is_greeting()` | 4022 | Not a greeting | skip |
| 9 | `_is_out_of_domain()` | 4051 | Not off-topic | pass |
| 10 | `_detect_repeat_intent()` | 4078 | Not a repeat | skip |
| **11** | **`_structured_lookup()`** | **4114** | **HANDLER MATCH** | **↓** |
| 11a | `re.search(r"\b(admission...)", q)` | **2873-2876** | **`"mujhe admission lena he"` → matches `\badmissions?\b`** | **↓** |
| 11b | Exclusion check: `not re.search(r"\bhostel\b")` | 2876 | No "hostel" → pass | |
| 11c | Exclusion check: `not re.search(r"\b(convince|...)")` | 2876 | No convince → pass | |
| 11d | Exclusion check: `not re.search(r"\b(kon si branch|...)")` | 2876 | No branch query → pass | |
| 11e | **Builds response from KB** | **2877-2887** | Returns: `"B.Tech admission is through WBJEE or JEE Main. Eligibility is 10+2 with PCM, 50% marks. Seats: WBJEE 80%, JEE Main 10%, Management Quota 10%. Apply online at the WBJEEB website or the college portal."` | |
| 12 | Response appended to history | 4126 | Saved as assistant turn | |
| 13 | Returned to caller | 4127-4136 | **LLM never invoked** — `"source": "structured_lookup"` | |

### Why This Happens

The regex `\b(admission\s*process|how\s*to\s*apply|admissions?|admit|apply\s*(for|to)|how\s*can\s*i\s*get)\b` (line 2874) is **extremely broad**. The word `"admission"` alone triggers it. Any query containing the substring `"admission"` (e.g., `"mujhe admission lena he"`, `"admission ke baare mein batao"`, `"admission kaisa hai"`) will match.

The handler **never asks a clarifying question**. It immediately dumps: process + eligibility + seat distribution + portal. The response is hardcoded in English regardless of the user's language (note: the detected language is `"hi"` but the response is English — this is itself a bug).

**Confidence: 100%** — This is the primary reason for the first example's behavior.

---

## 2. Example: `"konsa department lu"` → Department List Dump

### Decision Path

| Step | Function | Line | What Happens | Outcome |
|------|----------|------|-------------|---------|
| 0-10 | Same pre-checks as above | | All pass | |
| **11** | **`_structured_lookup()`** | **4114** | **No handler matches → returns None** | **↓** |
| 11a | Admission check | 2873 | `"konsa department lu"` — no "admission" keyword | miss |
| 11b | Why BCREC check | 2830 | No match | miss |
| 11c | Department info check | **3137-3146** | `\bdepartment\b` **matches** BUT then: `and not re.search(r"\b(kon si branch\|...\|konsa (subject\|department\|branch))\b", q)` — `"konsa department"` **matches the exclusion pattern** `konsa (subject|department|branch)` | **excluded!** |
| 11d | Branch recommendation | 3223-3228 | Pattern: `r"\b(kon si branch|kaun si branch|which branch|branch choose|branch recommend|mujhe branch chuni hai|mujhe konsa branch lena chahiye|best branch|sabse acchi branch|konsa subject choose karu|konsa department choose karun|kon department choose korbo)\b"` — `"konsa department lu"` does NOT match (the pattern expects `"konsa department choose karun"` or similar, not the short form `"konsa department lu"`) | miss |
| | → **No handler matches** | | `_structured_lookup()` returns `None` | |
| **12** | **LLM path** | **4143** | **Builds messages + call LLM** | **↓** |
| 12a | Build messages | 4144-4151 | `SYSTEM_PROMPT` (85 lines of data) + history + `"konsa department lu"` | |
| 12b | `_call_llm_with_tools()` | 1480 | Temperature=0.3, max_tokens=512 | |
| 12c | **LLM response** | | The LLM sees SYSTEM_PROMPT lines 852-859 (all B.Tech branches) and the instruction "Give the most important answer first" (**line 779**). With temperature 0.3, it plays it safe: **regurgitates the full department list from the prompt**. | |

### Why This Happens

Two interacting causes:

**Cause A: Narrow regex gap (line 3223-3228)**: The branch recommendation handler's regex requires specific phrasing like `"konsa department choose karun"` or `"kon si branch"`. But the user said `"konsa department lu"` (short, colloquial Hindi). This falls **between two handlers**: the department info handler **excludes** it (because `konsa (department)` is in the exclusion list), and the branch recommendation handler doesn't **include** it (because `"lu"` is not `"choose karun"`).

**Cause B: SYSTEM_PROMPT data overload (line 775-859)**: When the query falls through to the LLM, the LLM receives a prompt that is:
- 10% role description + rules (lines 775-808)
- 5% selling points (lines 809-817)
- **60% raw data dump** (lines 822-859: fees, placement, hostel, scholarships, cutoff, HODs, campus facilities, clubs, sports, ragging)
- The only conversational guidance is line 780: "Be conversational and natural — like a helpful campus counselor on the phone." — but this is a single line competing against 50 lines of "here are all the facts."

**Confidence: 95%** — The regex gap is the trigger, but the SYSTEM_PROMPT structure is the enabler.

---

## 3. Example: `"ap bolo konsa acha hoga"` → Placement-Based Recommendation

### Decision Path

| Step | Function | Line | What Happens | Outcome |
|------|----------|------|-------------|---------|
| 0-10 | Same pre-checks | | All pass | |
| **11** | **`_structured_lookup()`** | **4114** | **No handler matches → returns None** | **↓** |
| 11a | Branch recommendation | 3223-3228 | `"ap bolo konsa acha hoga"` — "konsa" matches NO pattern (patterns require `"kon si"`, `"kaun si"`, `"konsa department choose karun"`, etc.) | miss |
| | → **No handler matches** | | returns `None` | |
| **12** | **LLM path** | **4143** | **Builds messages + call LLM** | **↓** |
| 12a | LLM receives `SYSTEM_PROMPT` | 775 | The prompt includes: "Selling points: 91% overall placement, CSE 93.6%, Average package 4.25 LPA" (lines 813-815) and "In terms of placement demand, CSE, IT, and AIML have the highest packages" (implied by the branch recommendation handler's fallback text) | |
| 12b | **LLM decision** | | The LLM has **no instruction to ask about the user's interests**. It has instructions to "Give the most important answer first" (line 779) and a data block showing placement stats. With temperature 0.3, it defaults to the safest, most "informative" response: `"CSE and IT have better placement..."` | |

### Why This Happens

**The SYSTEM_PROMPT (line 775-859) lacks counseling behavior rules.** Specifically:

1. **No "clarify before recommend" instruction** (lines 775-808): The prompt tells the LLM what data to use but never tells it to ask questions first. A real counselor would ask: "What subjects do you enjoy? Are you interested in coding, hardware, or something else?" The prompt has zero such guidance.

2. **The "Selling Points" section (lines 809-817) emphasizes placement** as the #1 selling point. The LLM naturally latches onto this as the primary recommendation criterion.

3. **Temperature 0.3 (line 1498/1507)**: This low temperature makes the LLM conservative. It will choose the most statistically likely response given the prompt — which is a data dump of the most prominent facts (placement stats).

4. **The branch recommendation handler (lines 3223-3259) itself demonstrates the problem**: When it DOES match, it immediately says "If you like coding take CSE, if you like AI take AIML, if you like hardware take ECE" — **it never asks what the user's interests are.** Lines 3231-3258: each language variant starts with "BCREC mein kai branches hain..." and lists recommendations by user interest, but the assumption of interest is built into the recommendation structure itself (the LLM assumes the user already stated their interest).

**Confidence: 90%** — The SYSTEM_PROMPT's lack of counseling guidance + low temperature + placement-emphasis in selling points combine to produce this behavior.

---

## 4. Complete Decision Path Diagram

```
User: "mujhe admission lena he"
    │
    ▼
groq_service.py:3850  generate_response()
    │
    ├── 3879 normalize_query()             → no change
    ├── 3888 Hinglish q→kyu fix            → no change
    ├── 3898 Yes/No continuation check     → no match
    ├── 3934 _validate_transcript()         → pass
    ├── 3960 _detect_noisy_transcript()     → pass
    ├── 3988 _resolve_language()           → lang="hi"
    ├── 4012 _is_lang_switch()             → no match
    ├── 4022 _is_greeting()                → no match
    ├── 4051 _is_out_of_domain()           → pass
    ├── 4078 _detect_repeat_intent()       → no match
    │
    ├── 4114 _structured_lookup()          → MATCHES
    │   └── 2873 admission handler
    │       └── Returns hardcoded KB dump
    │       └── LLM NEVER CALLED
    │
    └── 4178 _append_session_turn() → done


User: "konsa department lu"
    │
    ▼
groq_service.py:3850  generate_response()
    │
    ├── same checks 1-10 → all pass
    │
    ├── 4114 _structured_lookup()
    │   ├── 2873 admission → no match
    │   ├── 2830 why_bcrec → no match
    │   ├── 3137 department info → EXCLUDED (neg pattern)
    │   ├── 3223 branch rec → no match (narrow regex)
    │   └── → returns None
    │
    ├── 4143 LLM path
    │   ├── 4144 SYSTEM_PROMPT (85 lines data)
    │   ├── 4146 history + query
    │   └── 1480 _call_llm_with_tools()
    │       ├── Temperature: 0.3
    │       └── LLM dumps department list from prompt
    │
    └── 4178 _append_session_turn()


User: "ap bolo konsa acha hoga"
    │
    ▼
groq_service.py:3850  generate_response()
    │
    ├── same checks 1-10 → all pass
    │
    ├── 4114 _structured_lookup()
    │   ├── 3223 branch rec → no match ("konsa" ≠ patterns)
    │   └── → returns None
    │
    ├── 4143 LLM path
    │   ├── 4144 SYSTEM_PROMPT
    │   │   ├── 779: "Give the most important answer first"
    │   │   ├── 813: "91% overall placement, CSE 93.6%"
    │   │   └── no: "ask the user what they're interested in"
    │   ├── 4146 history + query
    │   └── 1480 _call_llm_with_tools()
    │       ├── Temperature: 0.3
    │       └── LLM defaults to placement-based rec
    │
    └── 4178 _append_session_turn()
```

---

## 5. Every Component That Influences Response Style

| Component | File | Lines | Influence | Confidence |
|-----------|------|-------|-----------|------------|
| **`_structured_lookup()` — admission handler** | `groq_service.py` | 2871-2887 | **PRIMARY** for example 1. Regex `\badmissions?\b` catches broad queries, returns fact dump, LLM never called. | 100% |
| **`_structured_lookup()` — branch rec handler regex** | `groq_service.py` | 3223-3228 | **PRIMARY** for examples 2-3. Regex too narrow; `"konsa department lu"` falls through gap between "department info" (excluded) and "branch recommendation" (not matched). | 95% |
| **`SYSTEM_PROMPT` — data overload** | `groq_service.py` | 775-859 | **PRIMARY** for LLM path. 60% raw facts, 0% "ask clarifying questions" instruction. The LLM is trained to regurgitate, not consult. | 95% |
| **`SYSTEM_PROMPT` — "Give most important answer first"** | `groq_service.py` | 779 | Drives the LLM to lead with the most prominent data (placement stats) rather than ask questions. | 80% |
| **`_call_llm_with_tools()` — temperature 0.3** | `groq_service.py` | 1498, 1507 | Low temperature makes the LLM conservative, favoring safe fact-regurgitation over creative conversational exploration. | 70% |
| **`SYSTEM_PROMPT` — "Be conversational" is 1 line** | `groq_service.py` | 780 | This 10-word instruction is buried under 50 lines of data. It's outnumbered and out-prioritized. | 85% |
| **No "counselor" role instruction** | `groq_service.py` | 775-859 | The prompt says "admission assistant" (line 775) — this frames the role as an **information dispenser**, not a **guidance counselor**. | 75% |
| **Conversation history (in-memory)** | `groq_service.py` | 3619-3631 | Stores raw turns, feeds last 10 to LLM (line 4146). Only 12 turns max. Not a cause of the issue but doesn't help — there's no mechanism to use history to drive conversational behavior. | 10% |
| **`safe_point.py` `_add_personality()`** | `safe_point.py` | 120-124 | Explicit no-op: `return text.strip()`. Comment says "structured handlers already produce complete sentences." Disabled personality layer. | 40% |
| **`_validate_answer()` (hallucination guard)** | `groq_service.py` | 3736 | Only validates entity existence — doesn't affect style. | 0% |
| **`normalize_for_tts()`** | `normalizer.py` | 427 | Only converts acronyms to spoken form (CSE → "C S E"). No style impact. | 0% |
| **`clean_for_voice()`** | `voice_utils.py` | ~50 | Abbreviation expansion only. No style impact. | 0% |
| **RAG vector store (ChromaDB)** | `vector_store.py` | 74 | **NOT USED** in the current main path. RAG context is NOT injected into the prompt. All data comes from `SYSTEM_PROMPT`. | 0% |

---

## 6. Root Cause Summary

```
Problem: Agent behaves like a data dump, not a counselor
    │
    ├── ROOT CAUSE #1: _structured_lookup() pre-empts the LLM
    │   └── File: groq_service.py:2871-2887
    │   └── Regex "admissions?" catches "mujhe admission lena he"
    │   └── Returns hardcoded KB dump → LLM never consulted
    │   └── Impact: 100% of these queries get canned responses
    │
    ├── ROOT CAUSE #2: SYSTEM_PROMPT is a data dump, not a counselor guide
    │   └── File: groq_service.py:775-859
    │   └── 50 lines of raw facts vs 1 line saying "be conversational"
    │   └── No instruction to ask clarifying questions
    │   └── Impact: when LLM IS called, it regurgitates facts
    │
    ├── ROOT CAUSE #3: Branch recommendation regex gap
    │   └── File: groq_service.py:3223-3228
    │   └── Short forms like "konsa department lu" fall through cracks
    │   └── No handler catches it, LLM has no counselor training
    │   └── Impact: user gets unprompted placement advice
    │
    └── ROOT CAUSE #4: Low temperature (0.3) discourages conversation
        └── File: groq_service.py:1498
        └── LLM plays it safe → picks most statistically likely response
        └── Impact: conservative fact-dump over creative exploration
```

## 7. Key Files and Line Numbers (Cheat Sheet)

| What | File | Lines |
|------|------|-------|
| System prompt (the data dump) | `groq_service.py` | 775-859 |
| Admission handler (pre-empts LLM) | `groq_service.py` | 2871-2887 |
| Branch recommendation handler | `groq_service.py` | 3222-3259 |
| Department info handler | `groq_service.py` | 3136-3172 |
| Structured lookup (all handlers) | `groq_service.py` | 2708-3278 |
| Structured lookup call site | `groq_service.py` | 4114 |
| LLM prompt assembly | `groq_service.py` | 4144-4151 |
| LLM call (temperature=0.3) | `groq_service.py` | 1480-1514 |
| Stream prompt assembly | `groq_service.py` | 4367-4377 |
| Conversation history (12 turns) | `groq_service.py` | 3619-3631 |
| Personality (no-op) | `safe_point.py` | 120-124 |
| Post-processing | `safe_point.py` | 245-274 |
| Tool definitions (function calling) | `groq_service.py` | 861-999 |
