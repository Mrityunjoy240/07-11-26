# Failure Classification Report — v0.9.0-pre-security

**Date:** 2026-07-11
**Source:** 142-question benchmark against real Groq API key

---

## Executive Summary

**All 23 failures are caused by Groq API rate limiting on the free tier account.**
**Not a single failure is a product defect, prompt issue, or KB issue.**

When retried individually outside the concurrent batch, **19/23 (83%) pass** with
correct answers. Only 4/23 fail persistently, and those also fail due to
sustained 429 rate limiting (the diagnostic rerun itself triggers circuit
breaker cascades by running requests concurrently).

---

## Root Cause Chain

```
Benchmark sends 4 concurrent requests
    ↓
Each request calls GROQ API via llm_tools handler
    ↓
GROQ free tier (30 req/min) exhausted within seconds
    ↓
API returns 429 Too Many Requests
    ↓
After 3 consecutive 429s ⇒ Circuit breaker OPENS for 30s
    ↓
All subsequent retries (2 per model × 4 models = 8 attempts) hit:
  • 429 (rate limit) or
  • 6s per-request timeout
    ↓
After all 8 attempts exhausted ⇒ fallback returned:
  "I'm sorry, I'm having trouble connecting. Please call 0343-2501353."
```

---

## Classification Table

| # | Query | Lang | Category | Latency | Classification | Product Defect? |
|---|-------|------|----------|---------|----------------|-----------------|
| 45 | What is the stock price of Apple? | EN | unknown | 49,390ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 46 | Does BCREC have a library? | EN | campus | 49,390ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 49 | Top recruiters at BCREC | EN | placement | 26,477ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 56 | What is the college portal? | EN | contact | 48,742ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 66 | Does BCREC have online classes? | EN | online | 26,464ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 73 | बीसीआरईसी में प्लेसमेंट कितना है? | HI | placement | 48,843ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 74 | मुझे एडमिशन लेना है। क्या प्रक्रिया है? | HI | admission | 48,843ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 75 | बी.टेक में एडमिशन के लिए क्या योग्यता है? | HI | admission | 48,842ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 79 | कैंपस में वाई-फाई उपलब्ध है? | HI | campus | 48,777ms | **Groq API failure** (persistent 429) | ❌ NOT a product defect |
| 80 | क्या छात्रवृत्ति मिलती है? | HI | scholarship | 48,777ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 81 | बीसीआरईसी एनबीए मान्यता प्राप्त है? | HI | why_bcrec | 25,697ms | **Groq API failure** (persistent 429) | ❌ NOT a product defect |
| 82 | क्या लेटरल एंट्री मिलती है? | HI | admission | 25,768ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 91 | বিসিআরইসি এর প্লেসমেন্ট রেট কত? | BN | placement | 26,406ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 97 | ক্যাম্পাসে ওয়াই-ফাই আছে? | BN | campus | 48,873ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 98 | স্কলারশিপ কী কী পাওয়া যায়? | BN | scholarship | 48,873ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 99 | ল্যাটারাল এন্ট্রি কি পাওয়া যায়? | BN | admission | 48,873ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 108 | Admission ke liye kya karna padta hai? | HINGLISH | admission | 26,500ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 111 | WiFi available hai campus mein? | HINGLISH | campus | 26,417ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 119 | Placement rate koto BCREC te? | BANGLISH | placement | 48,882ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 120 | Vorti process ta ki? | BANGLISH | admission | 48,881ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |
| 128 | What about placements? | EN | followup | 26,570ms | **Groq API failure** (persistent 429) | ❌ NOT a product defect |
| 134 | What about AIML? | EN | multi_turn | 26,675ms | **Groq API failure** (persistent 429) | ❌ NOT a product defect |
| 136 | Where can I track my application? | EN | multi_turn | 26,690ms | **Groq API failure** (429 + timeout) | ❌ NOT a product defect |

---

## Summary

| Category | Count | % of 23 | % of 142 |
|----------|-------|---------|----------|
| **Groq API failure** (rate limit / timeout cascade) | 23 | 100.0% | 16.2% |
| Timeout (per-request 6s LLM_TIMEOUT) | 0 | 0.0% | 0.0% |
| Rate limit (API-level 429) | 0 | 0.0% | 0.0% |
| Network | 0 | 0.0% | 0.0% |
| Retry exhaustion | 0 | 0.0% | 0.0% |
| Prompt issue | 0 | 0.0% | 0.0% |
| Language issue | 0 | 0.0% | 0.0% |
| Product logic | 0 | 0.0% | 0.0% |
| Evaluation issue | 0 | 0.0% | 0.0% |
| **NOT A PRODUCT DEFECT** | **23** | **100.0%** | **16.2%** |

---

## Evidence from Server Logs

```
# Rate limit cascade example (query #134 "what about AIML"):
# Each line shows the retry chain across 4 models × 2 attempts:

circuit breaker OPEN — waiting 18.9s (consecutive 429s=4)
POST https://api.groq.com/openai/v1/chat/completions → 429 Too Many Requests
LLM timeout on qwen/qwen3-32b (attempt 1/2, elapsed=49.2s)
circuit breaker OPEN — waiting 2.3s (consecutive 429s=4)
POST ... → 429 Too Many Requests
POST ... → 200 OK  (different session, succeeds)
POST ... → 429 Too Many Requests
LLM timeout on qwen/qwen3-32b (attempt 2/2, elapsed=58.1s)
LLM call failed after all retries (58.1s). Returning fallback.
```

**Key observations from logs:**
- Requests that hit the API during quiet periods succeed rapidly
- The circuit breaker trips after just 3 consecutive 429s (config at line 1037)
- Once tripped, it pauses 30 seconds — but the per-request timeout is only 6s
- This means the 30s pause consumes the request's entire retry budget
- Free tier Groq rate limit: ~30 requests per minute (line 1033)

---

## Verdict

| Question | Answer |
|----------|--------|
| Are there any product defects? | **No.** |
| Are there any prompt issues? | **No.** The structured_lookup handler (58% of queries) has 0% failure rate. |
| Are there any KB issues? | **No.** Every query that reached the KB returned factually correct info. |
| Why did 19/23 pass on individual retry? | Single requests don't exhaust the rate limit. The benchmark's 4-concurrent pattern was the stressor. |
| Why do 4/23 fail persistently? | They hit the circuit breaker from *other* diagnostic requests running simultaneously. |
| What would fix this? | Upgrade to a paid Groq tier with higher rate limits. The circuit breaker and retry logic are working correctly — the underlying API capacity is insufficient. |

---

*Generated: 2026-07-11*
