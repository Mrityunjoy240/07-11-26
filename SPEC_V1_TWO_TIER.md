# V1 SPEC — Two-Tier Grounded Voice Agent (COLD-AGENT)

Status: PULL-PLAN, no code changes yet. Supersedes nothing; companion to
RESEARCH_TELEPHONY_VOICE_AGENT.md. Validated by the same two-tier shape as
OpenAI GPT-Live (media path + async delegated work) and by our live probes
(hallucinations, latency, intent drift).

## 1. Architecture (two tiers)

```
                          ┌─ Tier 1: Deterministic router (<300ms)
Sarvam Saaras V4 STT ────►│   normalize → vocab match (typo/fuzzy) → decision table hit
                          │   → pre-rendered Bulbul audio cache → done
                          │
                          ├─ Tier 2: Evidence-gated LLM (only when Tier 1 misses)
                    ┌─────┤   context = edge only (n-1 turns), full KB row payload
                    │     │   reply strings written, numbers HTML-tagged (₹)
   barge-in / VAD / turn  │   evidence gate: no KB row → refuse/handoff
   detection (LiveKit)    └──► LLM chain: Groq → Cerebras → NIM → Gemini
                                  │
                                  ▼
                          TTS chain: Bulbul V4 → AI4Bharat OSS → Google → ElevenLabs
                          (circuit breakers on every hop)
```

Rules (from probe findings, hard):
1. Numbers (fees, seats, amounts) ONLY from KB decision-table rows; never LLM memory. Every answer embeds its KB row id for the transcript/review queue.
2. Existence answers (facility/course/rule) ONLY via decision table `present / absent`; no KB row → Tier 2 must refuse or hand off, never invent.
3. LLM runs only when Tier 1 cannot route (greetings, chat, grievances, ambivalent questions).
4. Edge context, never full history (village probe: history growth → 15–22s median; intent drift mid-call).
5. Spoken answers ≤ 2 sentences; one follow-up question per turn; pre-rendered audio for the top frequency queries.

## 2. Tier 1 design

- **Normalizer**: consume Saaras V4 *code-mixed/transliteration* output mode → canonical Banglish/Hinglish tokens. Fixes `swiming pool he kya` (Banglish word order) and typo classes the current exact-match vocabulary misses.
- **Decision tables** (TSV/JSON from Lane-1 ingest, versioned, row ids): fees-by-course, hostel (SEAT vs SINGLE rooms — resolves the ₹10K/₹30K drift), mess, scholarships (SVMCM ₹60K line fixed), seats/eligibility, facilities present+absent, contacts/timings.
- **Existence guard** stays in the backend QA path (chat_kb must be re-pointed at it — today it bypasses).
- **Fuzzy vocab matcher**: edit-distance/prefix fallback into vocabulary.py; multi-intent split (`fees kitni AND admission kaise`) routes both.
- **TTS cache**: top ~50 queries pre-rendered with Bulbul; sub-300ms answers, zero LLM.

## 3. Tier 2 design

- LLM sees: decision-table summaries (already-grounded numbers), edge context, task instruction. Everything else is black-box.
- Evidence gate as a second pass: extract claims → must trace to rows; unverifiable → rephrase refusal (`yeh baat main confirm nahi kar sakta — warden se puch lijiye`).
- `kb_conf` becomes a gating value (today it's 0.0/None and unused).
- Failover chain kept from research (Groq Llama → Cerebras → NIM → Gemini) with circuit breakers; latency budget 600–800ms E2E.

## 4. Knowledge ingest (college handover: PDF/Excel)

- **Lane 1 — tables** (xlsx/csv): Docling (OSS, local, TableFormer) → row schema → validation (types, required cols) → decision tables. Never flatten Excel to prose (current document_processor.py trap). Correct answers for fees go through this lane only.
- **Lane 2 — documents** (PDF/DOCX): Docling → **agentic retrieval** (search tool + retrieve-by-id), NOT passive chunk RAG (ACL 2026: RAG+Tools 46% vs RAG-only 6% on office docs; OCB: even frontier models fail Excel comprehension).
- **Lane 3 — scanned**: Docling OCR (or Sarvam Doc Digitisation) → re-route to 1 or 2.
- **Review gate**: diff → human approve → publish (version, source, person, date) → feeds both decision tables and review queue already in backend/admin.

## 5. Telephony & latency

- LiveKit Agents + SIP (BYO trunk), Silero VAD, semantic turn detection, full-duplex barge-in (chunk-boundary TTS cut, read-only tools cancel).
- PSTN +~500ms; landline = 1 concurrency; rent a new number (KYC 1–3 days) for launch, port later if the college insists.

## 6. Build order (pull-plan, each phase verifiable)

| Phase | Deliverable | Verify with |
|---|---|---|
| 0 | Fix KB drift (hostel ₹10K/₹30K, mess ₹5.5K/₹5K, SVMCM ₹60K) — data only | re-run probes |
| 1 | Tier-1 router + decision tables for top ~30 intents + fuzzy vocab + typo + multi-intent | messy probe (typo/banglish cases), latency <300ms/router |
| 2 | Evidence-gated Tier 2 + kb_conf gating + edge context | village probe re-run: 0 hallucinations, median cut |
| 3 | Wire brain↔voice: ws_voice → backend guard path; STT-in loop, VAD, barge-in | live call checklist, e2e latency |
| 4 | Lane-1 ingest (Docling tables) + review gate | upload sample xlsx → decision table rows exact |
| 5 | Lane-2 agentic retrieval + Lane-3 OCR | sample PDF/scanned → grounded answers |
| 6 | Dashboard polish + telephony e2e (rented number) | real PSTN call from landline/mobile |
| 7 | 50 calls/day load + failover drill (kill Sarvam → chain flips) | load test, no dead calls |

## 7. Open decisions (need user/college input)

1. Top-30 intent list — which first? (proposal: admissions, fees, hostel, hostel fees, mess, scholarship, placement, faculty dept, facility existence, timings, contacts, greetings)
2. Grounded LLM default: Groq Llama vs Gemini 3 Flash for Tier 2 (latency vs Indic quality tradeoff)
3. Do we demo on Sarvam Voice Agents platform (fast, ₹3.5/min, their dashboards) in parallel while Tier 1/2 lands? (earlier direction: yes, Sarvam+dashboard edits as interim)
4. Number: rent new (fast) vs port office line (keep number, 2–6 weeks)?