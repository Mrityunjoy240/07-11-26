# Final Benchmark Report — v0.9.0-pre-security

**Date:** 2026-07-11
**Engine:** Groq Llama 3.3 (real API key from `.env`)
**Total Questions:** 142

---
## Overall Results

| Metric | Value |
|---|---|
| **Overall Pass Rate** | 112/142 = **78.9%** |
| **LLM/Connection Failures** | 27/142 = 19.0% |
| **OOD Correctness** | 4/5 = 80.0% |
| **Language Match** | 104/142 = 73.2% |
| **Handler Accuracy** | See by-handler table below |
| **Eval Hallucination Flag** | 142/142 (100.0%) — methodology artifact (see note) |
| **Zero Errors** | 0/142 (0%) |

> **Note on hallucination metric:** The evaluation's `check_hallucination()` compares numbers in the
> answer vs numbers in the RAG context. Since structured_lookup handlers answer from the KB directly
> without RAG context, the context is always empty, causing a false-positive 100% hallucination flag.
> The actual answer quality is assessed via KB data presence and handler classification below.

---
## Handler Distribution

| Handler | Count | % | Failures | Failure Rate |
|---|---|---|---|---|
| `structured_lookup` | 82 | 57.7% | 0 | 0.0% |
| `llm_tools` | 52 | 36.6% | 23 | 44.2% |
| `transcript_clarification` | 4 | 2.8% | 0 | 0.0% |
| `out_of_domain` | 3 | 2.1% | 0 | 0.0% |
| `llm_tools+safe_point_unknown` | 1 | 0.7% | 0 | 0.0% |

---
## Classification Breakdown

| Classification | Count | % of Total |
|---|---|---|
| kb_correct | 95 | 66.9% |
| llm_failure | 27 | 19.0% |
| handled_ok | 13 | 9.2% |
| ood_correct | 4 | 2.8% |
| empty_answer | 2 | 1.4% |
| ood_incorrect | 1 | 0.7% |

---
## By Category

| Category | N | Avg Latency | Failures |
|---|---|---|---|
| admission | 17 | 18200ms | 6 |
| ambiguous | 6 | 322ms | 0 |
| campus | 8 | 30212ms | 4 |
| contact | 2 | 24416ms | 1 |
| courses | 2 | 99ms | 0 |
| departments | 10 | 5946ms | 0 |
| eligibility | 2 | 100ms | 0 |
| facilities | 1 | 100ms | 0 |
| faculty | 15 | 1334ms | 0 |
| fees | 19 | 483ms | 0 |
| followup | 2 | 13347ms | 1 |
| hostel | 16 | 1087ms | 0 |
| international | 1 | 38072ms | 0 |
| multi_turn | 8 | 6740ms | 2 |
| online | 1 | 26464ms | 1 |
| placement | 10 | 21672ms | 4 |
| policies | 4 | 34308ms | 0 |
| refund | 2 | 23309ms | 0 |
| scholarship | 5 | 19588ms | 2 |
| unknown | 5 | 10261ms | 1 |
| why_bcrec | 6 | 7339ms | 1 |

---
## By Language

| Language | N | Avg Latency | Failures | Language Match |
|---|---|---|---|---|
| BANGLISH | 12 | 8282ms | 2 | 3/12 = 25% |
| BN | 18 | 10845ms | 4 | 7/18 = 39% |
| EN | 80 | 9255ms | 8 | 80/80 = 100% |
| HI | 20 | 14846ms | 7 | 4/20 = 20% |
| HINGLISH | 12 | 9619ms | 2 | 10/12 = 83% |

---
## Remaining Failures

- **#45** [EN/unknown] `llm_tools` — What is the stock price of Apple?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#46** [EN/campus] `llm_tools` — Does BCREC have a library?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#49** [EN/placement] `llm_tools` — Top recruiters at BCREC
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#56** [EN/contact] `llm_tools` — What is the college portal?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#66** [EN/online] `llm_tools` — Does BCREC have online classes?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#73** [HI/placement] `llm_tools` — बीसीआरईसी में प्लेसमेंट कितना है?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#74** [HI/admission] `llm_tools` — मुझे एडमिशन लेना है। क्या प्रक्रिया है?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#75** [HI/admission] `llm_tools` — बी.टेक में एडमिशन के लिए क्या योग्यता है?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#79** [HI/campus] `llm_tools` — कैंपस में वाई-फाई उपलब्ध है?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#80** [HI/scholarship] `llm_tools` — क्या छात्रवृत्ति मिलती है?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#81** [HI/why_bcrec] `llm_tools` — बीसीआरईसी एनबीए मान्यता प्राप्त है?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#82** [HI/admission] `llm_tools` — क्या लेटरल एंट्री मिलती है?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#91** [BN/placement] `llm_tools` — বিসিআরইসি এর প্লেসমেন্ট রেট কত?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#97** [BN/campus] `llm_tools` — ক্যাম্পাসে ওয়াই-ফাই আছে?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#98** [BN/scholarship] `llm_tools` — স্কলারশিপ কী কী পাওয়া যায়?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#99** [BN/admission] `llm_tools` — ল্যাটারাল এন্ট্রি কি পাওয়া যায়?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#108** [HINGLISH/admission] `llm_tools` — Admission ke liye kya karna padta hai?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#111** [HINGLISH/campus] `llm_tools` — WiFi available hai campus mein?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#119** [BANGLISH/placement] `llm_tools` — Placement rate koto BCREC te?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#120** [BANGLISH/admission] `llm_tools` — Vorti process ta ki?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#128** [EN/followup] `llm_tools` — What about placements?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#134** [EN/multi_turn] `llm_tools` — What about AIML?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools
- **#136** [EN/multi_turn] `llm_tools` — Where can I track my application?
  - Answer: I'm sorry, I'm having trouble connecting. Please call 0343-2501353.
  - Classification: llm_tools

---
## Issue Classification for Remaining Failures

| # | Query | Category | Issue Type | Rationale |
|---|---|---|---|---|
| #45 | What is the stock price of Apple? | unknown | Product Issue | LLM returned connection error |
| #46 | Does BCREC have a library? | campus | LLM Failure | LLM returned connection error |
| #49 | Top recruiters at BCREC | placement | LLM Failure | LLM returned connection error |
| #56 | What is the college portal? | contact | LLM Failure | LLM returned connection error |
| #66 | Does BCREC have online classes? | online | LLM Failure | LLM returned connection error |
| #73 | बीसीआरईसी में प्लेसमेंट कितना है? | placement | LLM Failure | LLM returned connection error |
| #74 | मुझे एडमिशन लेना है। क्या प्रक्रिया है? | admission | LLM Failure | LLM returned connection error |
| #75 | बी.टेक में एडमिशन के लिए क्या योग्यता है | admission | LLM Failure | LLM returned connection error |
| #79 | कैंपस में वाई-फाई उपलब्ध है? | campus | LLM Failure | LLM returned connection error |
| #80 | क्या छात्रवृत्ति मिलती है? | scholarship | LLM Failure | LLM returned connection error |
| #81 | बीसीआरईसी एनबीए मान्यता प्राप्त है? | why_bcrec | LLM Failure | LLM returned connection error |
| #82 | क्या लेटरल एंट्री मिलती है? | admission | LLM Failure | LLM returned connection error |
| #91 | বিসিআরইসি এর প্লেসমেন্ট রেট কত? | placement | LLM Failure | LLM returned connection error |
| #97 | ক্যাম্পাসে ওয়াই-ফাই আছে? | campus | LLM Failure | LLM returned connection error |
| #98 | স্কলারশিপ কী কী পাওয়া যায়? | scholarship | LLM Failure | LLM returned connection error |
| #99 | ল্যাটারাল এন্ট্রি কি পাওয়া যায়? | admission | LLM Failure | LLM returned connection error |
| #108 | Admission ke liye kya karna padta hai? | admission | LLM Failure | LLM returned connection error |
| #111 | WiFi available hai campus mein? | campus | LLM Failure | LLM returned connection error |
| #119 | Placement rate koto BCREC te? | placement | LLM Failure | LLM returned connection error |
| #120 | Vorti process ta ki? | admission | LLM Failure | LLM returned connection error |
| #128 | What about placements? | followup | LLM Failure | LLM returned connection error |
| #134 | What about AIML? | multi_turn | LLM Failure | LLM returned connection error |
| #136 | Where can I track my application? | multi_turn | LLM Failure | LLM returned connection error |
