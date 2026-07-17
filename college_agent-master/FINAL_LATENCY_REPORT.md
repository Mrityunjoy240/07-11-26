# Final Latency Report — v0.9.0-pre-security

**Date:** 2026-07-11
**Total Queries:** 142

---
## Overall Latency

| Metric | Value |
|---|---|
| **Average Latency** | 10193 ms |
| **Median (P50) Latency** | 123 ms |
| **P95 Latency** | 48843 ms |
| **Minimum** | 69 ms |
| **Maximum** | 49390 ms |
| **Standard Deviation** | 16822 ms |

---
## Latency by Handler

| Handler | N | Avg | P50 | P95 | Min | Max |
|---|---|---|---|---|---|---|
| `structured_lookup` | 82 | 116ms | 105ms | 149ms | 69ms | 429ms |
| `llm_tools` | 52 | 27500ms | 26477ms | 48882ms | 537ms | 49390ms |
| `transcript_clarification` | 4 | 115ms | 115ms | 123ms | 106ms | 123ms |
| `out_of_domain` | 3 | 92ms | 95ms | 99ms | 81ms | 99ms |
| `llm_tools+safe_point_unknown` | 1 | 7119ms | 7119ms | 7119ms | 7119ms | 7119ms |

---
## Latency by Category

| Category | N | Avg | P50 | P95 | Max |
|---|---|---|---|---|---|
| admission | 17 | 18200ms | 11229ms | 48881ms | 48881ms |
| ambiguous | 6 | 322ms | 150ms | 796ms | 796ms |
| campus | 8 | 30212ms | 34950ms | 49390ms | 49390ms |
| contact | 2 | 24416ms | 48742ms | 48742ms | 48742ms |
| courses | 2 | 99ms | 116ms | 116ms | 116ms |
| departments | 10 | 5946ms | 537ms | 46916ms | 46916ms |
| eligibility | 2 | 100ms | 108ms | 108ms | 108ms |
| facilities | 1 | 100ms | 100ms | 100ms | 100ms |
| faculty | 15 | 1334ms | 104ms | 18557ms | 18557ms |
| fees | 19 | 483ms | 119ms | 7119ms | 7119ms |
| followup | 2 | 13347ms | 26570ms | 26570ms | 26570ms |
| hostel | 16 | 1087ms | 108ms | 14299ms | 14299ms |
| international | 1 | 38072ms | 38072ms | 38072ms | 38072ms |
| multi_turn | 8 | 6740ms | 99ms | 26690ms | 26690ms |
| online | 1 | 26464ms | 26464ms | 26464ms | 26464ms |
| placement | 10 | 21672ms | 18200ms | 48882ms | 48882ms |
| policies | 4 | 34308ms | 44933ms | 47501ms | 47501ms |
| refund | 2 | 23309ms | 38204ms | 38204ms | 38204ms |
| scholarship | 5 | 19588ms | 111ms | 48873ms | 48873ms |
| unknown | 5 | 10261ms | 99ms | 49390ms | 49390ms |
| why_bcrec | 6 | 7339ms | 116ms | 25697ms | 25697ms |

---
## Latency by Language

| Language | N | Avg | P50 | P95 | Max |
|---|---|---|---|---|---|
| BANGLISH | 12 | 8282ms | 123ms | 48882ms | 48882ms |
| BN | 18 | 10845ms | 130ms | 48873ms | 48873ms |
| EN | 80 | 9255ms | 119ms | 47501ms | 49390ms |
| HI | 20 | 14846ms | 114ms | 48843ms | 48843ms |
| HINGLISH | 12 | 9619ms | 127ms | 46916ms | 46916ms |

---
## Latency Distribution

| Range | Count | % |
|---|---|---|
| 0-100ms | 34 | 23.9% |
| 100-500ms | 55 | 38.7% |
| 500-1000ms | 5 | 3.5% |
| 1000-3000ms | 3 | 2.1% |
| 3000-10000ms | 3 | 2.1% |
| 10000-30000ms | 21 | 14.8% |
| 30000-60000ms | 21 | 14.8% |

---
## Observations

- **Average latency** (10193ms) is high; the target for voice is <5s.
- **P95 latency** (48843ms) exceeds acceptable thresholds for interactive voice.
- **Structured lookups** are fast (<500ms for most), while **LLM calls** dominate tail latency.
- 23 queries returned connection errors with long timeouts (30-50s), inflating P95.
- Language-specific latency varies, with Hindi/BN mixed-language queries taking longer.
