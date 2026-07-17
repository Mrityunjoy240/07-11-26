# Final Response Score Report — v0.9.0-pre-security

**Date:** 2026-07-11
**Total Questions:** 142

---
## Score Overview

Scoring: 1 point per question. Correct = KB-answerable questions that returned a factually relevant answer (not a connection error).

| Metric | Score |
|---|---|
| **Overall Score** | 112/142 (78.9%) |
| **Handler Accuracy** (correct handler selected) | 134/142 (94.4%) |
| **LLM Reliability** (non-sorry) | 115/142 (81.0%) |
| **OOD Rejection** | 4/5 (80.0%) |
| **Language Consistency** | 104/142 (73.2%) |
| **Zero Errors** | ✅ Yes (0/142) |

---
## Detailed Handler Accuracy

| Handler | Total | Correct | Wrong | Accuracy |
|---|---|---|---|---|
| `structured_lookup` | 82 | 82 | 0 | 100.0% |
| `llm_tools` | 52 | 29 | 23 | 55.8% |
| `transcript_clarification` | 4 | 4 | 0 | 100.0% |
| `out_of_domain` | 3 | 3 | 0 | 100.0% |
| `llm_tools+safe_point_unknown` | 1 | 1 | 0 | 100.0% |

---
## LLM Accuracy Per Category

| Category | N | Correct | Wrong | Accuracy | Avg Latency |
|---|---|---|---|---|---|
| admission | 17 | 11 | 6 | 64.7% | 18200ms |
| ambiguous | 6 | 6 | 0 | 100.0% | 322ms |
| campus | 8 | 4 | 4 | 50.0% | 30212ms |
| contact | 2 | 1 | 1 | 50.0% | 24416ms |
| courses | 2 | 2 | 0 | 100.0% | 99ms |
| departments | 10 | 10 | 0 | 100.0% | 5946ms |
| eligibility | 2 | 2 | 0 | 100.0% | 100ms |
| facilities | 1 | 1 | 0 | 100.0% | 100ms |
| faculty | 15 | 15 | 0 | 100.0% | 1334ms |
| fees | 19 | 19 | 0 | 100.0% | 483ms |
| followup | 2 | 1 | 1 | 50.0% | 13347ms |
| hostel | 16 | 16 | 0 | 100.0% | 1087ms |
| international | 1 | 1 | 0 | 100.0% | 38072ms |
| multi_turn | 8 | 6 | 2 | 75.0% | 6740ms |
| online | 1 | 0 | 1 | 0.0% | 26464ms |
| placement | 10 | 6 | 4 | 60.0% | 21672ms |
| policies | 4 | 4 | 0 | 100.0% | 34308ms |
| refund | 2 | 2 | 0 | 100.0% | 23309ms |
| scholarship | 5 | 3 | 2 | 60.0% | 19588ms |
| unknown | 5 | 4 | 1 | 80.0% | 10261ms |
| why_bcrec | 6 | 5 | 1 | 83.3% | 7339ms |
