# Runtime Investigation Report

**Date:** 2026-07-13
**Objective:** Determine why manual testing still sees old responses after code fixes.

---

## Executive Summary

**All modified source files ARE loaded at runtime.** The server was NOT properly restarted after the first start attempt (old Python processes survived Start-Job cleanup), but after a hard kill + restart the new code IS active. The remaining issues are:

1. Missing word `"hoyeche"` in `BANGLA_ROMAN_WORDS` → backlog query stays English
2. LLM ignores `lang=bn` hint and responds in Hindi for free-form Banglish queries
3. Typo `"scholership"` doesn't match `\bscholarship` regex

---

## Verification — Modified Files ARE Loaded

**Method:** Checked running server log timestamps and behavior.

**File on disk** — last modified:
- `language_detect.py`: 01:57:58
- `groq_service.py`: 01:58:24

**Server process** — started at 02:11 (PID 4804):
- `__pycache__` timestamps: 01:58:36 (groq_service) and 01:58:48 (language_detect) — both AFTER .py modifications

**Runtime evidence the code IS active:**

| Query | Log Evidence | Conclusion |
|-------|-------------|------------|
| `"akta help lagbe"` | `Language change: en → bn (reason: keyword markers=3 in short query)` | Language detection fix WORKS — 3 Bangla keywords detected |
| `"amar ki kono scholarship ache"` | `Language change: en → bn` + `Structured lookup hit` | Scholarship handler WORKS with Bangla input |
| `"Bangla ki bolte paren"` | Response: `Aami BCREC-er ek counselor...` | LLM responds in Banglish when lang=bn |

---

## Issue 1 — "amar backlog hoyeche" still returns English

### Log Evidence

```
HANDLER: academic_failure matched for query='amar backlog hoyeche' lang=en
Structured lookup hit (len=355)
```

The backlog handler fires with `lang=en` and returns the English template: `"Don't worry, backlogs are common..."`.

### Root Cause

The word `"hoyeche"` is **not** in `BANGLA_ROMAN_WORDS`. Only `"amar"` matches (1 Bangla keyword). For short queries (<=3 words), the language resolver requires >=2 keyword markers to switch from the default `en`. Since `bn_kw=1 < 2`, language stays `en`.

The word `"hoye"` IS in `BANGLA_ROMAN_WORDS` (I added it), but the query uses `"hoyeche"` (longer form). Bangla uses both forms interchangeably.

### Fix Needed

Add `"hoyeche"`, `"hoyechhe"`, `"hoyechilo"` to `BANGLA_ROMAN_WORDS`.

---

## Issue 2 — "akta help lagbe" returns Hindi despite Bangla detection

### Log Evidence

```
Language change: en → bn (reason: keyword markers=3 in short query)
structured_lookup 4.6ms → returned None (no handler matched)
llm_response 638ms → LLM returned Hindi text
```

### Root Cause (Double)

**Part A — No structured handler matches:** The query `"akta help lagbe"` is a general help request. No regex in `_structured_lookup` matches it (not fee, not admission, not backlog, etc.). So it falls through to the LLM.

**Part B — LLM ignores `lang=bn` hint:** The `_build_messages` method (line 1877) injects `"Reply in simple Banglish or Bengali (NOT Sanskritized Bengali)."` when `lang=bn`. However, the LLM responds in Hindi (`"Aapko kya help chahiye?"`) despite this instruction. This is an LLM compliance issue — the system prompt's first rule says "Answer ONLY in the user's language," and the lang_hint says Banglish, but the model still outputs Hindi.

### Fix Needed

This is an LLM behavior problem. Strengthening the `lang_hint` in `_build_messages` or adding a language instruction directly in the user message may help. Alternatively, a structured handler for general help requests could intercept these queries before the LLM.

---

## Issue 3 — "mera scholership cancel ho jayega" goes to LLM

### Log Evidence

```
Language: detected=hi, keeping en (weak evidence, kw markers bn=0 hi=1)
structured_lookup 0.4ms → returned None
llm_response 605ms → LLM hallucinated about scholarship
```

### Root Cause

The query contains `"scholership"` (typo with "e" instead of "a"). The regex at line 3754 is:
```python
re.search(r"\bscholarship", q)
```
`"scholership"` does **not** match `\bscholarship`. The handler returns `None`, and the LLM handles it — hallucinating about eligibility.

The original conversation example used `"scholership"` (with the typo). My fix was tested with correct spelling `"scholarship"`.

### Fix Needed

Add `"scholership"` as an STT mistake/alias match alongside `"scholarship"` in the regex pattern.

---

## Summary — What IS Working vs What Is NOT

| Fix Component | Status | Evidence |
|--------------|--------|----------|
| `language_detect.py` — new Bangla words (akta, lagbe, etc.) | ✅ **WORKING** | `"akta help lagbe"` → detected as Bengali |
| `groq_service.py` — backlog Bengali template (line 3509) | ✅ **CODE CORRECT** but NOT REACHED | Only fires when `lang=bn`, which doesn't happen for `"amar backlog hoyeche"` |
| `groq_service.py` — backlog Hindi template (line 3507) | ✅ **CODE CORRECT** but NOT REACHED | Same issue — `lang=en` for this query |
| `groq_service.py` — scholarship cancellation detection | ✅ **CODE CORRECT** | Works with `"scholarship cancel"` but not `"scholership cancel"` (typo mismatch) |
| `BANGLA_ROMAN_WORDS` — `"hoyeche"` word | ❌ **MISSING** | Needs to be added to fix backlog query |

## Conclusion

The running server IS using the modified files. The fixes partially work (language detection for "akta help lagbe" now correctly identifies Bengali). The three remaining gaps are:

1. **One missing Bangla word** (`"hoyeche"`) — affects `"amar backlog hoyeche"` language detection
2. **LLM ignores lang=bn hint** — affects free-form Banglish queries that don't match any structured handler
3. **Scholarship typo** (`"scholership"` vs `"scholarship"`) — affects cancellation detection for common misspellings
