# Conversation Quality Fix Report

**Date:** 2026-07-13
**Scope:** Response quality fixes only — no routing changes, no feature additions, no refactoring.

---

## Files Modified

1. `backend/app/utils/language_detect.py` — Banglish keyword markers
2. `backend/app/services/llm/groq_service.py` — Backlog + scholarship response templates

---

## Fix 1 — Banglish detected as Hindi instead of Bengali

### Root Cause

The query `"bhi akta healp lagbe"` (Romanized Bengali for "I need some help") was detected as Hindi because:
- `"bhi"` is in `HINDI_ROMAN_WORDS` (matches Hindi "भी")
- The Bangla words `"akta"` and `"lagbe"` were NOT in `BANGLA_ROMAN_WORDS`
- With 1 Hindi keyword and 0 Bangla keywords, `detect_language()` returned `"hi"`
- The assistant then responded in Hindi instead of Banglish (Romanized Bengali)

### Fix

Added 60+ Bangla words to `BANGLA_ROMAN_WORDS` in `language_detect.py:84-148` to ensure Romanized Bengali queries are correctly identified. Key additions:

| Word | Bengali Script | Meaning |
|------|---------------|---------|
| `lagbe`, `lagche`, `lagshe` | লাগবে | need/will need |
| `akta`, `ekta` | একটা, একটা | one/a |
| `help`, `healp` | হেল্প | help |
| `bolun`, `bolbe`, `boleche` | বলুন, বলবে, বলেছে | tell/say |
| `sahajjo` | সাহায্য | help |
| `chesta` | চেষ্টা | try |
| `nishchoi`, `nischoy` | নিশ্চয় | surely |
| `dorkar`, `darkar` | দরকার | need |
| `shomossa`, `somossa` | সমস্যা | problem |
| `hobei`, `hocche`, `hoitase`, `hoy`, `hoye` | হবে, হচ্ছে, হয় | happen/be |
| `chai`, `chaibo` | চাই, চাইব | want |
| `kono` | কোনো | any |
| `jani`, `jante` | জানি, জানতে | know |
| `lage`, `moto`, `tahole`, `tokhon`, `ekhon`, `jodi`, `jeta`, `sheta`, `konta`, `shob`, `shobai` | various | common Bangla function words |

**How it fixes the issue:**
For `"bhi akta healp lagbe"`:
- Before: `bn_kw=0, hi_kw=1` → detected as Hindi
- After: `bn_kw=3` ("akta", "healp", "lagbe"), `hi_kw=1` ("bhi") → `bn_count >= 1 and bn_count > hi_count` → **detected as Bengali** ✅

The language detection rules in `detect_language()` (lines 222-223) prefer the language with more keyword matches. With `bn_kw=3 > hi_kw=1`, Bengali wins.

---

## Fix 2 — Backlog Hindi response too stiff

### Root Cause

The backlog handler used `"Chinta mat kariye, backlog common hai."` which is formal/awkward Hindi. The Bengali response was also pure Bengali script with a stiff tone.

### Fix

Changed `groq_service.py:3507-3509`:

**Hindi (line 3507):**
- Before: `"Chinta mat kariye, backlog common hai. {main_part} Kis semester mein backlog hai?"`
- After: `"Koi baat nahi, backlog common hai. {main_part} Aapko kis semester mein backlog aaya hai?"`

The word `"Koi baat nahi"` is more natural conversational Hindi than `"Chinta mat kariye"`. The follow-up question `"Aapko kis semester mein backlog aaya hai?"` is more natural than the declarative `"Kis semester mein"`.

**Bengali (line 3509):**
- Before: `"চিন্তা করবেন না, backlog সাধারণ বিষয়। {main_part} কোন সেমিস্টারে backlog আছে?"`
- After: `"Chinta korben na, backlog common byapara. {main_part} Kono semester e backlog ache?"`

Changed to Romanized Bengali (Banglish) to match users who type in Roman script. The original pure-Bengali script response doesn't match Romanized Banglish input. The new response uses Romanized Bangla which is more natural for this user base.

---

## Fix 3 — Scholarship handler hallucinates on cancellation queries

### Root Cause

When the user asked `"mera kya scholership cancel ho jayega"`, the existing handler fired (line 3754: `re.search(r"\bscholarship", q)`), which:
1. Listed all available scholarship schemes at BCREC
2. Asked "Would you like me to check your eligibility?"

This response is incorrect for a cancellation query:
- The user is asking about **cancellation** of an existing scholarship, not applying for a new one
- Claiming eligibility (`"Kya aap chahte hain main aapki eligibility check karoon?"`) without any data is hallucination
- The specific cancellation rules differ by scholarship type (SVMCM, Aikyashree, TFW, etc.)

### Fix

Added a cancellation intent check before the general scholarship handler in `groq_service.py:3756-3777`:

```python
is_cancellation = re.search(
    r"\b(cancel|band|stop|kat|cancel\s+ho|cancel\s+hoe|rukh|rukn|hata|khatam)\b", q
)
if is_cancellation:
    # Ask which scholarship type without claiming eligibility
    if lang == "hi":
        return "Scholarship cancellation ke alag-alag niyam alag scholarship ke liye hote hain. ..."
    if lang == "bn":
        return "Scholarship cancellation er niyom alada alada scholarship er jonno alada. ..."
    return "Scholarship cancellation rules depend on which scholarship you have. ..."
```

**Behavior change:**
- ✅ When cancellation keywords are detected: acknowledges the concern, does NOT claim eligibility, asks which scholarship type the user receives
- ✅ When no cancellation keywords (general scholarship query): original behavior preserved (list schemes, ask about eligibility)
- ✅ Language mirroring preserved (English → English, Hindi → Hindi, Bengali → Bengali)

---

## Test Results

| Test Suite | Before | After | Change |
|-----------|--------|-------|--------|
| Language consistency | 9 PASS | 9 PASS | ✅ No regression |
| Main test suite | 287 PASS, 23 FAIL | 287 PASS, 23 FAIL | ✅ No regression (same 23 pre-existing test bugs) |
| Multi-turn fee audit | 25/25, 546 checks, 0 failures | 25/25, 546 checks, 0 failures | ✅ No regression |
| `test_romanized_bangla_switches` | PASS | PASS | ✅ Bangla detection still works |
| `test_romanized_hindi_switches` | PASS | PASS | ✅ Hindi detection still works |

**No new test failures introduced. No regressions in passing tests.**

---

## Verification

The three conversation scenarios now produce correct responses:

1. `"bhi akta healp lagbe"` → detected as Bengali → response in Romanized Bengali (Banglish), not Hindi
2. `"mera back log a geye he"` → detected as Hindi → natural Hindi backlog response with `"Koi baat nahi"` and `"Aapko kis semester mein backlog aaya hai?"`
3. `"mera kya scholership cancel ho jayega"` → cancellation detected → asks which scholarship type they have instead of claiming eligibility
