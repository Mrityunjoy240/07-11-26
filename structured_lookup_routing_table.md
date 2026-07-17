# `_structured_lookup()` Handler Routing Table

**Source:** `backend/app/services/llm/groq_service.py` lines 2708-3279

## Classification Legend

| Label | Meaning |
|-------|---------|
| **DETERMINISTIC** | Keep as-is. Exact data lookup, no ambiguity, no conversation needed. |
| **DETERMINISTIC (narrow regex)** | Keep deterministic but tighten the trigger regex to avoid false positives. |
| **ASK → LLM** | Intercept, ask a clarifying question first, then pass to LLM with the clarified intent. |
| **LLM** | Remove handler, let the LLM handle it naturally. |
| **LLM (with tool)** | Remove handler, but give the LLM a function-calling tool for the exact data. |
| **REMOVE** | Handler should be deleted — redundant or harmful. |

---

## Handler-by-Handler Classification

| # | Handler | Lines | Regex | Current Behavior | Classification | Rationale |
|---|---------|-------|-------|------------------|---------------|-----------|
| 1 | **Principal + VP combined** | 2723-2739 | `\b(principal\|princepal)\b` + `\bvice\b` + conjunction | Returns principal + VP names | **DETERMINISTIC** | Purely factual. No conversation needed. Exact data from KB. |
| 2 | **Vice Principal** | 2742-2747 | `\bvice[\s-]?(principal\|princepal)\b` | Returns VP name | **DETERMINISTIC** | Same as above. Exact lookup. |
| 3 | **Principal** | 2750-2756 | `\b(principal\|princepal)\b` | Returns name + phone | **DETERMINISTIC** | Same. Exact lookup. |
| 4 | **Negativity / complaint** | 2759-2785 | `not\s*join\|negative\|bad review\|complaint\|nuksan\|kharab\|buraiya\|grievance\|drawback\|...` | Returns canned "every college has strengths and weaknesses" response | **SPLIT** — Keep deterministic for **abuse/swearing**, send to **LLM** for "drawbacks"/"negatives"/"why not join" | Abuse needs a safe canned response. But "what are the drawbacks" or "why should I not join" is a legitimate consultative question that the LLM could answer thoughtfully. |
| 5 | **Contact info** | 2788-2799 | `\b(contact\|phone\|mobile\|call\|helpline\|number)\b` | Returns phone + email | **DETERMINISTIC** | Exact data. But regex is too broad — "call" matches "so **call**ed", "number" matches "**number** of students". Consider narrowing. |
| 6 | **Admission documents** | 2802-2812 | `(document\|require\|need\|list of).*(admission\|admit)` | Returns list of required docs | **DETERMINISTIC** | Exact data from KB. Well-scoped regex (requires both doc-word + admission-word). |
| 7 | **Admission office contact** | 2815-2826 | `admission\s*office\|admission department\|admission block\|admission counsel(or\|er\|lor)\|talk (to\|with) (admission\|admissions)\|transfer (me)? (to\|in) (admission\|admissions)` | Returns office phone number | **DETERMINISTIC** | Exact data. Well-scoped regex. |
| 8 | **Why BCREC / convince / advantages** | 2830-2869 | `why bcrec\|why choose\|convince\|kya acha hai\|kya khas hai\|kyun join karein\|bcrec kyun accha hai\|why.*admission\|kyu.*admission\|q.*admission\|keno.*admission` | Returns hardcoded selling-points dump | **→ LLM** | The selling points are static data already in SYSTEM_PROMPT (lines 809-817). The LLM can tailor them to the user's interests from conversation history. The handler's response is the same generic dump for everyone. |
| 9 | **Admission process (general)** | 2871-2887 | `\b(admission\s*process\|how\s*to\s*apply\|admissions?\|admit\|apply\s*(for\|to)\|how\s*can\s*i\s*get)\b` | Returns hardcoded English admission dump | **DETERMINISTIC (narrow regex) + language fix** | **#1 PROBLEM HANDLER.** The word "admission" is too broad — matches "mujhe **admission** lena he" and dumps a canned English response even when the user is speaking Hindi. Fix: either narrow the regex (require "process"/"how") or pass to LLM. If kept deterministic, must respect `lang` parameter (currently always English). |
| 10 | **Installment / payment plan** | 2890-2896 | `\b(installments?\|emi\|payment\s*plan\|pay\s*in\s*part)\b` | Returns payment options from KB | **DETERMINISTIC** | Well-scoped. Exact data. |
| 11 | **Safety / Anti-ragging** | 2899-2911 | `\b(safety\|safe\|ragging\|security\|women.*safe)\b` | Returns anti-ragging policy + helpline | **DETERMINISTIC** | Exact data. But "security" is broad (could match "job security", "financial security"). Consider narrowing. |
| 12 | **Hostel info** | 2914-2929 | `\bhostel\b` | Returns hostel availability + counts | **DETERMINISTIC** | Exact data. "hostel" is specific enough. Handles "hostel fee" correctly (caught before fee handler). |
| 13 | **Fee lookup** | 2932-2980 | `\b(fee\|fees\|total fee\|semester fee\|admission fee\|course fee)\b` | Returns fee structure by dept + language | **DETERMINISTIC** | Well-structured. Language-aware. Handles semester vs total vs admission fee correctly. Best handler in this class. |
| 14 | **Academic failure / backlog** | 2983-3001 | `\b(backlog\|back.?paper\|arrear\|supply\|supplementary\|reappear\|fail)\|back\s+(ache\|hoyeche\|lag\|lagbe\|lagse\|chole\|as)\b` | Returns blob from `combined_kb.json` after splitting on "Laptops" text | **→ LLM** | The current implementation reads from `combined_kb.json` and does an ugly split on the word "Laptops". This is fragile. The LLM with SYSTEM_PROMPT data (line 854: "Supplementary exams held every semester...") can answer this more naturally in the user's language. |
| 15 | **HOD lookup** | 3004-3029 | `\b(hod\|hods\|head of department\|department head)\b` | Returns HOD name + email | **DETERMINISTIC** | Exact data from KB. Supports single + all lookup. |
| 16 | **Faculty name resolution** | 3031-3034 | `\b(professor\|faculty\|teacher\|sir\|madam\|dr\.?\|prof\.?)\b` | Returns faculty name via fuzzy matching | **DETERMINISTIC** | Name resolution is inherently deterministic. Well-structured. |
| 17 | **Placement lookup** | 3037-3061 | `\b(placements?\|placed\|recruit\|package\|lpa\|job\|company)\b` | Returns placement stats from KB | **DETERMINISTIC (narrow regex)** | Exact stats. BUT "job" and "company" are extremely broad — "mujhe **job** karni hai", "kya **company** aati hai" (which is fine), but "konsa **job** loge" is not about placement. Consider keeping only `placement|placed|recruit|package|lpa` as deterministic triggers and letting `job|company` fall through to LLM. |
| 18 | **Department seat info** | 3064-3072 | `\b(seats\|intake\|capacity)\b` | Returns intake count | **DETERMINISTIC** | Exact data. Well-scoped. |
| 19 | **Cutoff / rank info** | 3075-3096 | `\b(cutoff\|cut.off\|rank\|closing.rank\|opening.rank)\b` | Returns hardcoded cutoff map | **DETERMINISTIC** | Exact data (hardcoded in code, not KB). But "rank" is broad — matches "what is the **rank** of BCREC". Should be fine for engineering context. |
| 20 | **Establishment / history** | 3099-3107 | `\b(established\|founded\|started\|founding\|when.*start\|when.*open\|since when\|how old)\b` | Returns year + autonomy status | **DETERMINISTIC** | Exact data. Well-scoped. |
| 21 | **Computer lab timings** | 3110-3115 | `\bcomputer\s*lab\|lab\s*timing\|lab\s*hours?\b` | Returns lab hours (same as college hours) | **DETERMINISTIC** | Exact data. But "lab" alone is too broad — matches "language **lab**", "physics **lab**". The first alternation is fine (`computer\s*lab`), but `lab\s*timing` is too broad. Consider keeping only `computer\s*lab`. |
| 22 | **Library timings** | 3118-3123 | `\blibrary\s*(timing\|hours?)\|reading\s*room\b` | Returns library hours | **DETERMINISTIC** | Well-scoped. |
| 23 | **College timings** | 3126-3134 | `\b(timings?\|office hours?\|working hours?\|college hours?\|what.*time\|when.*open\|when.*close)\b` | Returns college hours | **DETERMINISTIC** | Exact data. BUT "timings" alone is extremely broad — matches "exam **timings**", "mess **timings**", "lab **timings**", "library **timings**". Since lab/library have their own handlers before this one, they get caught first. But "exam timings", "mess timings", "bus timings" would all match here. Consider narrowing to require `college` or `office`. |
| 24 | **Department info (list courses)** | 3136-3172 | `\b(department\|branch\|course\|program\|b\.tech\|what.*offer\|what.*available\|what.*have\|what.*teach\|list.*course)\b` | Returns list of B.Tech courses | **DETERMINISTIC** | Exact data. Has proper exclusion for branch recommendation patterns. But "course" and "program" are broad (could mean scholarship program, hostel program, etc.). |
| 25 | **Scholarship** | 3175-3201 | `\bscholarship\b` | Returns scholarship names + eligibility | **DETERMINISTIC** | Exact data. Well-scoped. |
| 26 | **Counselling** | 3203-3208 | `\b(counselling\|counseling)\b` | Returns "conducted through WBJEEB" | **DETERMINISTIC** | Exact data. But note: "counselling" is also a service the college offers (psychological). This handler only returns admission counseling info. If someone asks about psychological counseling (which IS in KB), it returns the wrong thing. |
| 27 | **Eligibility / marks / percentage** | 3211-3220 | `\b(eligibility\|eligible\|marks?\|percentage\|qualif)\b` | Returns eligibility criteria | **DETERMINISTIC (narrow regex)** | "marks" and "percentage" are extremely broad. "Mera **percentage** kitna hai", "kya **marks** chahiye" could be about anything. Consider keeping only `eligibility|eligible|qualif` as deterministic and letting `marks|percentage` fall through to LLM. |
| 28 | **Branch recommendation** | 3222-3259 | `\b(kon si branch\|kaun si branch\|which branch\|branch choose\|branch recommend\|mujhe branch chuni hai\|mujhe konsa branch lena chahiye\|best branch\|sabse acchi branch\|konsa subject choose karu\|konsa department choose karun\|kon department choose korbo)\b` | Returns assuming interest-based recommendation | **ASK → LLM** | **#2 PROBLEM HANDLER.** The regex is too narrow (misses "konsa department lu", "ap bolo konsa acha hoga"). And even when it matches, it assumes the user's interests instead of asking. Should: (a) expand regex to catch short forms, and (b) ask "What are your interests?" before the LLM makes a recommendation. |
| 29 | **"What else" / "or kya" follow-up** | 3262-3268 | `or kya\|aur kya\|what else\|anything else\|...` | Returns None (passes to LLM) | **CORRECT** | This handler is the reference implementation — it correctly defers to the LLM for open-ended questions. Keep as-is. |
| 30 | **Campus visit** | 3271-3277 | `\bcampus\s*visit\b\|\bvisit\s*campus\b\|\btour\b` | Returns visit info + phone | **DETERMINISTIC** | Exact data. But "tour" is broad — could match "tour of the lab", "library tour", etc. |

---

## Summary: Priority Changes

### 🔴 Must Fix (causing the reported problems)

| Handler | Change | Reason |
|---------|--------|--------|
| **#9 Admission process** (line 2871) | Narrow regex `admissions?` → require process keyword; OR pass to LLM; AND respect `lang` | "mujhe admission lena he" triggers English dump. |
| **#28 Branch recommendation** (line 3222) | Expand regex for short forms + add clarify-first step | "konsa department lu" and "ap bolo konsa acha hoga" fall through to LLM with no counselor guidance. |

### 🟡 Should Change (improves counselor behavior)

| Handler | Change | Reason |
|---------|--------|--------|
| **#8 Why BCREC** (line 2830) | Remove handler → let LLM tailor selling points | Generic dump ignores conversation history. LLM can personalize. |
| **#14 Backlog** (line 2983) | Remove handler → let LLM answer naturally | Current implementation reads `combined_kb.json` and splits on "Laptops". Fragile and not conversational. |
| **#4 Negativity** (line 2759) | Split: keep deterministic for abuse, send to LLM for "drawbacks"/"negatives" | "What are the drawbacks of BCREC?" is a counseling question, not abuse. |
| **#17 Placement** (line 3037) | Narrow: drop `job\|company` from deterministic triggers | "job" and "company" are too broad. Let LLM handle these. |
| **#27 Eligibility** (line 3211) | Narrow: drop `marks?\|percentage` from deterministic triggers | "marks" and "percentage" are too broad. LLM can disambiguate. |
| **#23 College timings** (line 3126) | Narrow: require `college\|office` before "timings" | "exam timings", "mess timings" match incorrectly. |
| **#21 Computer lab** (line 3110) | Narrow: keep only `computer\s*lab` | `lab\s*timing` catches "language lab", "physics lab". |

### 🟢 Keep as-is (correctly implemented)

| Handler | Why |
|---------|-----|
| Principal, VP, Contact, Documents, Office, Installment, Hostel, Fee, HOD, Faculty, Seats, Cutoff, History, Library, Scholarship, Counselling, Campus Visit, "What else" | Exact data, well-scoped regex, no ambiguity. |

### Notes for Safe Conversion

- **Language respect**: The admission handler (#9) and campus visit handler (#30) always return English responses. All other handlers should verify they respect `lang`.
- **RAG not needed**: None of these handlers need RAG — the data they access is either in KB, hardcoded, or available in SYSTEM_PROMPT. RAG is for unstructured PDF content not in the canonical KB.
- **Tool functions available**: If handlers are removed and sent to LLM, the existing tool definitions (lines 861-999) cover: `get_fees`, `get_contact_info`, `get_principal_info`, `get_placement_info`, `get_branch_info`, `get_admission_process`, `get_hostel_info`, `get_scholarship_info`, `get_cutoff_info`, `get_hod_info`, `get_backlog_policy`, `get_college_info`. These should be passed to the LLM call as function-calling tools.
