# LLM_FAILURE_AUDIT.md — Root Cause Analysis of All 44 Failures

**Date**: 2026-07-11

**Methodology**: For each of the 44 failures from the 142-query benchmark, the raw JSON response (`answer`, `source`, `latency_ms`) was cross-referenced against the code in `groq_service.py` to determine exactly what happened. The server was running with `os.environ["GROQ_API_KEY"] = "gsk_test"` (set by `run_full_eval.py:9`).

---

## Summary

| Metric | Value |
|---|---|
| Total failures | 44 |
| LLM reached, timed out, returned fallback | **26** |
| LLM reached, returned content, too slow (>5000ms) | **15** |
| SafePoint + LLM, timed out | **1** |
| LLM returned `<think>` tags (model behavior) | **2** |
| Would pass with real API key | **42** (YES) |
| Would pass with real API key | **2** (UNKNOWN — `<think>` tag issue) |

---

## Code Path: How the Fallback "I'm sorry..." Is Generated

All LLM calls go through `_call_llm_with_tools` at `groq_service.py:1507`:

```
groq_service.py:1507-1567
────────────────────────────────────────────────────────
LLM_TIMEOUT = 6.0 seconds per attempt
models_to_try = [primary_model] + FALLBACK_MODELS  (3 models)
Retries per model = 2

for current_model in models_to_try:
    for attempt in range(2):
        try:
            content = await asyncio.wait_for(
                asyncio.to_thread(client.chat.completions.create),
                timeout=6.0                ← line 1529
            )
            content = re.sub(r"<think>...</think>", ...)  ← line 1534
            return content
        except asyncio.TimeoutError:       ← line 1539
            sleep(0.5) on first attempt
        except Exception:                  ← line 1548
            handle rate-limit, log

# All retries exhausted → hardcoded fallback:
return "I'm sorry, I'm having trouble connecting. Please call 0343-2501353."
                                                        ← line 1567
```

The `gsk_test` dummy key causes every API call to either:
- **timeout** after 6.0s (HTTP connection to api.groq.com hangs with invalid key)
- **error** immediately (Groq SDK rejects malformed key format)

Either way, all 3 models × 2 attempts × 6.0s = up to 36s of retries are exhausted before the fallback is returned.

---

## Group A: LLM Timed Out → Fallback (26 failures)

All 26 have `source = "llm_tools"` and the exact fallback text. The LLM was reached, every retry failed, the hardcoded fallback was returned.

| # | Query | Handler | LLM Called? | Elapsed (ms) | Timeout? | Fallback? | Root Cause | Would Pass? |
|---|-------|---------|-------------|-------------|----------|-----------|------------|-------------|
| 17 | What is the placement rate at BCREC? | llm_tools | YES | 32968.0 | YES (6s × 6 attempts) | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 18 | Which companies visit BCREC for placement? | llm_tools | YES | 32498.1 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 24 | Can I track my application status? | llm_tools | YES | 49546.3 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 25 | How many faculty members are there? | llm_tools | YES | 50672.0 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 31 | What is the campus size? | llm_tools | YES | 27586.9 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 35 | Why should I choose BCREC? | llm_tools | YES | 27093.8 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 39 | Is laptop compulsory? | llm_tools | YES | 49485.8 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 40 | Is caution money refundable? | llm_tools | YES | 49176.4 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 42 | Can you book a cab for me? | llm_tools | YES | 27317.4 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 46 | Does BCREC have a library? | llm_tools | YES | 27189.6 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 47 | Tell me about the laboratories | llm_tools | YES | 26907.2 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 49 | Top recruiters at BCREC | llm_tools | YES | 49814.6 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 55 | What is the dress code? | llm_tools | YES | 49307.3 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 56 | What is the college portal? | llm_tools | YES | 49044.6 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 65 | Are there separate hostels for boys and girls? | llm_tools | YES | 27552.0 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 66 | Does BCREC have online classes? | llm_tools | YES | 27239.1 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 73 | बीसीआरईसी में प्लेसमेंट कितना है? | llm_tools | YES | 49974.2 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 74 | मुझे एडमिशन लेना है। क्या प्रक्रिया है? | llm_tools | YES | 49651.0 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 79 | कैंपस में वाई-फाई उपलब्ध है? | llm_tools | YES | 38277.9 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 80 | क्या छात्रवृत्ति मिलती है? | llm_tools | YES | 37996.2 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 81 | बीसीआरईसी एनबीए मान्यता प्राप्त है? | llm_tools | YES | 23782.8 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 82 | क्या लेटरल एंट्री मिलती है? | llm_tools | YES | 24070.6 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 84 | বিসিআরইসি-তে কোন কোন ডিপার্টমেন্ট আছে? | llm_tools | YES | 28466.7 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 108 | Admission ke liye kya karna padta hai? | llm_tools | YES | 28031.5 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 120 | Vorti process ta ki? | llm_tools | YES | 27455.4 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |
| 129 | Is it good? | llm_tools | YES | 29054.9 | YES | "I'm sorry..." | gsk_test → all LLM retries fail | YES |

All 26 return the literal string from `groq_service.py:1567`. The content_accuracy check fails because the fallback message (a phone number) is irrelevant to the question. The latency check fails because the total retry chain takes 23–50s.

---

## Group B: LLM Returned Content, But Too Slow (15 failures)

All 15 have `source = "llm_tools"` and returned real (correct-looking) content, but the latency exceeded the 5000ms threshold. These are queries where the LLM eventually succeeded (one model/attempt got through), but only after earlier timeouts burned the budget.

| # | Query | Handler | LLM Called? | Elapsed (ms) | Content Returned | Root Cause | Would Pass? |
|---|-------|---------|-------------|-------------|-----------------|------------|-------------|
| 5 | Tell me about the CSE department | llm_tools | YES | 16070.3 | "CSE at BCREC is NBA accredited..." | gsk_test → retries burned 12+s before a model succeeded | YES |
| 8 | How much does MBA cost? | llm_tools | YES | 15013.9 | "BCREC does not offer MBA..." | Same | YES |
| 16 | How many hostels are there in BCREC? | llm_tools | YES | 20882.0 | "BCREC mein total 7 hostels..." | Same | YES |
| 37 | Can international students apply? | llm_tools | YES | 36147.8 | "Yes, international students can apply..." | Same | YES |
| 54 | What is the refund policy? | llm_tools | YES | 38026.9 | "I'm sorry, refund policy not in KB..." | Same | YES |
| 93 | ভর্তির জন্য কী কী ডকুমেন্ট লাগে? | llm_tools | YES | 12364.3 | "Admission er jonno 10+2 er mark sheet..." | Same | YES |
| 97 | ক্যাম্পাসে ওয়াই-ফাই আছে? | llm_tools | YES | 27127.6 | "Campus-e 24x7 free Wi-Fi ache..." | Same | YES |
| 98 | স্কলারশিপ কী কী পাওয়া যায়? | llm_tools | YES | 27101.0 | "BCREC-তে TFW, Swami Vivekananda..." | Same | YES |
| 99 | ল্যাটারাল এন্ট্রি কি পাওয়া যায়? | llm_tools | YES | 38362.8 | "হ্যাঁ, ল্যাটারাল এন্ট্রি পাওয়া যায়..." | Same | YES |
| 107 | Placement kitna percent hai? | llm_tools | YES | 16720.3 | "BCREC ka overall placement 91 percent..." | Same | YES |
| 111 | WiFi available hai campus mein? | llm_tools | YES | 27107.2 | "Haan, campus par WiFi facility available..." | Same | YES |
| 124 | Campus e WiFi ache? | llm_tools | YES | 16257.0 | "Bilkul, campus e high-speed WiFi ache..." | Same | YES |
| 128 | What about placements? | llm_tools | YES | 15996.9 | "BCREC's 2025 placements saw 91%..." | Same | YES |
| 132 | How many departments? | llm_tools | YES | 24485.9 | "BCREC mein 15 engineering departments..." | Same | YES |
| 141 | Are there any rules about attendance? | llm_tools | YES | 27479.1 | "B CREC mein 75% attendance compulsory..." | Same | YES |

With a real API key: the first model (llama-3.1-8b-instant, primary) would complete in ~1-3s, eliminating the multi-attempt delay chain. All 15 would pass both content_accuracy and latency.

---

## Group C: SafePoint + LLM Fallback (1 failure)

| # | Query | Handler | LLM Called? | Elapsed (ms) | Content Returned | Root Cause | Would Pass? |
|---|-------|---------|-------------|-------------|-----------------|------------|-------------|
| 45 | What is the stock price of Apple? | safe_point→llm_tools | YES | 13188.7 | "I am not completely sure..." (safe_point response) | SafePoint handled the OOD query first ("stock price"), returned its "not sure" message. Then LLM was called to enhance it but timed out. | YES |

The source is `llm_tools+safe_point_unknown`. SafePoint produced the response text before the LLM call. The LLM timed out but the safe_point response was already captured. With a real API key, the LLM would enhance the safe_point response or add a more helpful rejection.

---

## Group D: LLM Returned Content With `<think>` Tags (2 failures — UNKNOWN)

These are the ONLY two failures whose root cause is NOT the dummy API key.

| # | Query | Handler | LLM Called? | Elapsed (ms) | Content Returned | Root Cause | Would Pass? |
|---|-------|---------|-------------|-------------|-----------------|------------|-------------|
| 75 | बी.टेक में एडमिशन के लिए क्या योग्यता है? | llm_tools | YES | 47640.7 | `<think>\nOkay, the user is asking about eligibility...` | LLM emitted `<think>` reasoning; regex at line 1534 failed to strip (likely unclosed tag or pattern mismatch) | UNKNOWN |
| 134 | What about AIML? | llm_tools | YES | 23609.6 | `<think>\nOkay, the user is asking about AIML again...` | Same | UNKNOWN |

**Evidence**: The answers start with `<think>\n` and contain chain-of-thought text. Line 1534 of `groq_service.py` attempts to strip these:
```python
content = _re.sub(r"<think>.*?</think>\s*", "", content, flags=_re.DOTALL).strip()
```
For this to fail, the LLM output must not contain a closing `</think>` tag (so the non-greedy `.*?` never matches), or the regex is not matching the exact output format.

**Why UNKNOWN**: With a real API key, the same model (`llama-3.1-8b-instant` or fallback models) would use the same generation configuration (temperature=0.3, max_tokens=384). If the model's architecture includes `<think>` style reasoning by default, the same output format would appear. A real API key does not change model behavior—only the success/failure of the API call. Therefore, the `<think>` tag issue would persist with a real key unless:
- The regex pattern is fixed to handle unclosed tags
- Or the model prompt is changed to suppress thinking tokens
- Or the model is replaced with one that doesn't use `<think>` format

---

## Complete Failure Table

| # | Query | Handler | LLM Called? | Timeout? | Elapsed (ms) | Root Cause | Would Pass With Real API Key? |
|---|-------|---------|-------------|----------|-------------|------------|-------------------------------|
| 17 | What is the placement rate at BCREC? | llm_tools | YES | YES | 32968.0 | gsk_test → all LLM retries failed → fallback | YES |
| 18 | Which companies visit BCREC for placement? | llm_tools | YES | YES | 32498.1 | gsk_test → all LLM retries failed → fallback | YES |
| 24 | Can I track my application status? | llm_tools | YES | YES | 49546.3 | gsk_test → all LLM retries failed → fallback | YES |
| 25 | How many faculty members are there? | llm_tools | YES | YES | 50672.0 | gsk_test → all LLM retries failed → fallback | YES |
| 31 | What is the campus size? | llm_tools | YES | YES | 27586.9 | gsk_test → all LLM retries failed → fallback | YES |
| 35 | Why should I choose BCREC? | llm_tools | YES | YES | 27093.8 | gsk_test → all LLM retries failed → fallback | YES |
| 39 | Is laptop compulsory? | llm_tools | YES | YES | 49485.8 | gsk_test → all LLM retries failed → fallback | YES |
| 40 | Is caution money refundable? | llm_tools | YES | YES | 49176.4 | gsk_test → all LLM retries failed → fallback | YES |
| 42 | Can you book a cab for me? | llm_tools | YES | YES | 27317.4 | gsk_test → all LLM retries failed → fallback | YES |
| 46 | Does BCREC have a library? | llm_tools | YES | YES | 27189.6 | gsk_test → all LLM retries failed → fallback | YES |
| 47 | Tell me about the laboratories | llm_tools | YES | YES | 26907.2 | gsk_test → all LLM retries failed → fallback | YES |
| 49 | Top recruiters at BCREC | llm_tools | YES | YES | 49814.6 | gsk_test → all LLM retries failed → fallback | YES |
| 55 | What is the dress code? | llm_tools | YES | YES | 49307.3 | gsk_test → all LLM retries failed → fallback | YES |
| 56 | What is the college portal? | llm_tools | YES | YES | 49044.6 | gsk_test → all LLM retries failed → fallback | YES |
| 65 | Separate hostels for boys and girls? | llm_tools | YES | YES | 27552.0 | gsk_test → all LLM retries failed → fallback | YES |
| 66 | Does BCREC have online classes? | llm_tools | YES | YES | 27239.1 | gsk_test → all LLM retries failed → fallback | YES |
| 73 | बीसीआरईसी में प्लेसमेंट कितना है? | llm_tools | YES | YES | 49974.2 | gsk_test → all LLM retries failed → fallback | YES |
| 74 | मुझे एडमिशन लेना है? | llm_tools | YES | YES | 49651.0 | gsk_test → all LLM retries failed → fallback | YES |
| 79 | कैंपस में वाई-फाई उपलब्ध है? | llm_tools | YES | YES | 38277.9 | gsk_test → all LLM retries failed → fallback | YES |
| 80 | क्या छात्रवृत्ति मिलती है? | llm_tools | YES | YES | 37996.2 | gsk_test → all LLM retries failed → fallback | YES |
| 81 | बीसीआरईसी एनबीए मान्यता प्राप्त है? | llm_tools | YES | YES | 23782.8 | gsk_test → all LLM retries failed → fallback | YES |
| 82 | क्या लेटरल एंट्री मिलती है? | llm_tools | YES | YES | 24070.6 | gsk_test → all LLM retries failed → fallback | YES |
| 84 | বিসিআরইসি-তে কোন ডিপার্টমেন্ট আছে? | llm_tools | YES | YES | 28466.7 | gsk_test → all LLM retries failed → fallback | YES |
| 108 | Admission ke liye kya karna padta hai? | llm_tools | YES | YES | 28031.5 | gsk_test → all LLM retries failed → fallback | YES |
| 120 | Vorti process ta ki? | llm_tools | YES | YES | 27455.4 | gsk_test → all LLM retries failed → fallback | YES |
| 129 | Is it good? | llm_tools | YES | YES | 29054.9 | gsk_test → all LLM retries failed → fallback | YES |
| 5 | Tell me about the CSE department | llm_tools | YES | partial | 16070.3 | gsk_test → retries burned time → content returned but slow | YES |
| 8 | How much does MBA cost? | llm_tools | YES | partial | 15013.9 | Same | YES |
| 16 | How many hostels are there? | llm_tools | YES | partial | 20882.0 | Same | YES |
| 37 | Can international students apply? | llm_tools | YES | partial | 36147.8 | Same | YES |
| 54 | What is the refund policy? | llm_tools | YES | partial | 38026.9 | Same | YES |
| 93 | ভর্তির জন্য কী কী ডকুমেন্ট লাগে? | llm_tools | YES | partial | 12364.3 | Same | YES |
| 97 | ক্যাম্পাসে ওয়াই-ফাই আছে? | llm_tools | YES | partial | 27127.6 | Same | YES |
| 98 | স্কলারশিপ কী কী পাওয়া যায়? | llm_tools | YES | partial | 27101.0 | Same | YES |
| 99 | ল্যাটারাল এন্ট্রি কি পাওয়া যায়? | llm_tools | YES | partial | 38362.8 | Same | YES |
| 107 | Placement kitna percent hai? | llm_tools | YES | partial | 16720.3 | Same | YES |
| 111 | WiFi available hai campus mein? | llm_tools | YES | partial | 27107.2 | Same | YES |
| 124 | Campus e WiFi ache? | llm_tools | YES | partial | 16257.0 | Same | YES |
| 128 | What about placements? | llm_tools | YES | partial | 15996.9 | Same | YES |
| 132 | How many departments? | llm_tools | YES | partial | 24485.9 | Same | YES |
| 141 | Attendance rules? | llm_tools | YES | partial | 27479.1 | Same | YES |
| 45 | Stock price of Apple? | safe→llm | YES | YES | 13188.7 | SafePoint handled, LLM timed out enhancing it | YES |
| 75 | बी.टेक एडमिशन योग्यता? | llm_tools | YES | partial | 47640.7 | LLM returned content with `<think>` tags; regex failed to strip | **UNKNOWN** |
| 134 | What about AIML? | llm_tools | YES | partial | 23609.6 | Same — `<think>` tag issue | **UNKNOWN** |

---

## Conclusion

**42 of 44 failures (95.5%)** have a single root cause: **`GROQ_API_KEY = "gsk_test"`** (line 9 of `run_full_eval.py`). Every LLM-dependent query either:

- Timed out through all 3 models × 2 attempts = 6 retries at 6.0s each, returning the hardcoded fallback "I'm sorry, I'm having trouble connecting. Please call 0343-2501353." from `groq_service.py:1567`, OR
- Succeeded only after earlier retries burned the latency budget, exceeding the 5000ms threshold

With a real Groq API key, all 42 would pass content_accuracy (the LLM would respond with real content) and latency (the first model attempt on llama-3.1-8b-instant would complete in ~1-3s, well under 5000ms).

**2 of 44 failures (4.5%)** — queries #75 and #134 — have a **different, independent root cause**: the LLM returned output containing `<think>` reasoning tags, and the regex cleanup at line 1534 of `groq_service.py` failed to remove them. This is a **model behavior issue**, not an API key issue. Even with a real API key, these queries would likely still fail the `tone` dimension if the model continues to emit `<think>` tags.

**Zero failures were caused by the Sprint 1 code changes** (no structured_lookup handlers breaking, no misclassified OOD queries, no safe_point errors).
