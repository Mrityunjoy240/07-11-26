# VERIFICATION REPORT — BCREC + APC Research (2026-27)
Date: 2026-08-15 | Scope: BCREC main campus + BCRAPC (APC); polytechnic & pharmacy EXCLUDED.

## 1. Method
- Primary: official PDFs downloaded from bcrec.ac.in (16 files) + APC MAKAUT/AICTE letters.
- Independent parse: pypdf AND pdfplumber (two parsers) — token-level presence checks (250/253 PASS).
- Arithmetic: every printed/derived total recomputed from components.
- Cross-document: each key figure checked across EOA / MAKAUT letters / prospectus / fee PDFs / AICTE disclosure / NAAC cert / NIRF 2026.
- KB diff: all 38 KB JSON/MD files scanned for amounts vs verified set (49 matches, 75 unverified tokens, 102 verified values absent).

## 2. PASS / FAIL SUMMARY (per fact group)
| Fact group | Result |
|---|---|
| B.Tech fee 2026-30 (A/B/C groups, sem-by-sem, hostel variants) | PASS (incl. components: 60,500+9,075+1,600+750+500+1,500+10,000+5,000+2,200+500+1,000+6,600 = 99,225 etc.) |
| Lateral entry fees (3 groups) | PASS (97,675 / 91,350 / 59,725 1st sem; totals 4,63,300 / 4,25,350 / 2,35,600 derived) |
| M.Tech fees (CSE 66,200; others 41,200; totals 2,28,000 / 1,28,000) | PASS |
| MCA fees (2 years, 67,800 / 48,600 / 50,600 / 49,600; total 2,16,600) | PASS (duration now 2 yrs — REGISTRY corrected) |
| MBA fees sem-by-sem + one-time options | MOSTLY PASS — see PDF inconsistencies below |
| MBA-HM fees sem-by-sem + one-time options | MOSTLY PASS — see PDF inconsistencies below |
| Indents 2026-27 (CSE 240, ECE 120, IT 30, EE 60, CyS 30, ME/CE/AIML/DS 60, M.Tech ×18 + CTM 18 NEW, MBA 90, MBA-HM 60 NEW, MCA 120, WP-B.Tech 60×3 NEW, CSD intake 0) | PASS (EOA 2026-27 + MAKAUT letter + prospectus agree) |
| Mess 5,500/mo + seat rent 10,000/sem + hostel caution 2,000 (all fee PDFs) | PASS |
| Attendance rule 75% (65% never condoned) | PASS (academic regs draft) |
| Eligibility 45%/40% (reserved) | PASS (prospectus + regs agree; KB said 50% — STALE) |
| University approval letters (No.120/B.TECH etc., 29.05.2026, 18 conditions) | PASS |
| Faculty total 187 | PASS (disclosure; KB said 208+ — STALE) |
| Hostel beds 1,270 (818 boys / 452 girls), 5 hostels | PASS (disclosure; KB said 1,500 — STALE) |
| Library 100,231 vols / 7,658 titles | PASS (disclosure; KB said 80,000+ — STALE) |
| Campus 14 acres | PASS (regs preamble; KB said 17 — STALE) |
| NAAC B+ CGPA 2.72, valid to 12-Sep-2026 | PASS (certificate; KB said 2.83, no expiry — STALE) |
| NIRF 2026: placed 503 @ median 3.86L (2024-25), rank 201-250 | PASS (NIRF submission IR-E-C-6176) |
| Discipline fines 20-25K (Cat I) / 5-15K (Cat II); anti-ragging | PASS |
| Scholarships: TFW 5%, WBFS 10+10%, SWC 50+50%, MBA 10/25/35%, PG stipend 3,000/mo | PASS |
| APC: 2026-27 EOA (as-is-where-is BBA 330 + BCA 150), NOT autonomous, new program NOT approved | PASS |
| MBA/MBA-HM one-time totals (3,84,800 / 5,40,300; 3,83,200 / 5,38,700) | PASS |
| Maths check of my own figures | 250/253 token+sum checks PASS; 3 failures were script artifacts (verified against correct source — PASS) |

## 3. PDF INTERNAL INCONSISTENCIES (real, need college confirmation)
1. MBA "entire course" printed **4,22,000** vs sem-wise sum **4,27,000** (diff 5,000).
2. MBA-HM printed **4,20,000** vs sem-wise sum **4,25,000** (diff 5,000).
3. MBA 1st sem printed **1,21,400** vs itemized sum **1,22,000** (diff 600).
4. Exam fee: BCREC PDFs print 1,600 ("to be fixed by BCREC"); MAKAUT 2026 notice + APC PDFs use 1,200. CONFIRM.
5. M.Tech caution money: 5,000 WITH hostel / 7,000 WITHOUT (as printed — REVERSED vs B.Tech pattern). CONFIRM.
6. AICTE disclosure "entire programme fee" (6,02,500 / 5,51,900 / 4,41,900; M.Tech 2,23,000 / 1,23,000; MBA 4,21,800; MCA 2,11,400) = 2024-25 batch — DIFFERENT YEAR, not a conflict with 2026 figures.
7. B.Tech 2026-30 PDF header text: "Total Caution Deposit (one time) Rs. 12,000=00 WITH hostel / 10,000=00 WITHOUT" — but every semester table computes its totals with Rs. 5,000 caution (99,225 / 1,38,725 etc. verified both ways). CONFIRM actual caution amount.

## 4. KB STALENESS (resolved — KB updated 2026-08-15)
> All rows below were stale (2024-25 figures) and have been UPDATED to the verified values in §2.
> | File | Stale rows (BEFORE → AFTER) |
> |---|---|
> | college_facts.json (single source of truth for agent) | acres 17→14; NAAC 2.83→2.72 + validity; CSE intake 180→240; IT 60→30; EE 120→60; CY 60→30; group_c 4,29,100/75,650/50,350→4,57,100/79,150/53,850; MBA total 4,19,200→4,22,000; MCA 2,14,600→2,16,600; hostel capacity 1,500→1,270; faculty 208+→187; library 80,000→100,231; eligibility 50%→45%/40% |
> | canonical_kb.json | same fee/quantities above (mirrors legacy) |
> | combined_kb.json | same |
> | knowledge_base.json | same (btech group_c, mba, mca, totals) |
> | fee_structures/mca.json | 2,14,600→2,16,600 + 3rd-sem training 2,000 + 4th-sem degree 1,000 |
> | fee_structures/mba.json | full rewrite with MBA + MBA-HM per-semester components & one-time options |
> | topics/fees.md | full new tables (2026-30 verified amounts incl. derived totals 6,17,700/5,67,100/4,57,100) |
> | topics/hostel.md | 1,500→1,270 capacity (818/452), mess 5,500 |
> | topics/admissions.md | 50%→45%/40% eligibility |
> | topics/college.md | 17→14 acres |
> | fee_structures/btech.json | group_c: tuition 40,000→41,250; devt 6,000→8,250; 8th sem 41,000→42,250; computed 4,29,100/75,650/50,350/51,350→4,57,100/79,150/53,850/54,850 |
> | fee_structures/_config.json | btech_range 4,29,100→4,57,100 |
> | groq_service.py | FEE_GROUP_MAP (ME tuple, MBA 4,22,000, MCA 2,16,600), general-fee strings, library "100,000+", NAAC 2.72 |
> | CLEAN | mtech.json, hostel.json, faculty.md, placements.md (numbers absent) |

## 5. TEST STATUS AFTER KB UPDATE (2026-08-15)
| Suite | Result |
|---|---|
| tests/test_regression.py + verify_facts.py | 32/32 PASS |
| tests/test_fee_engine.py + test_fee_parity.py | 179/179 PASS (incl. parametrized ME/MBA/MCA totals, sem sums vs computed, parity old/new engines) |
| tests/multiturn_fee_audit.py | 25 conversations, 133 turns, 546 checks — 0 failures |
| tests/test_fee_fuzz.py | 500 random cases PASS |
| tests/test_groq_service.py | 208 PASS / 19 FAIL — PRE-EXISTING at HEAD (31 fail at d50ca9b), none in fee/verified-value surface |
| All 38 KB JSON files | valid JSON (dept_files.json was a corrupted traceback artifact — replaced with placeholder) |

## 6. UNVERIFIED (no official PDF; college must confirm)
- Placement percentages/avg LPA per branch (93.6% etc.) — placement policy PDF was image-only.
- WBJEE cutoffs 2024/2025 (from website, not official PDFs).
- Principal/HOD names & phones; admission helpline numbers (website only).
- Single-bed hostel rent 30,000/sem (hostel rules; disclosure only lists seat rent 10,000 + mess 60,500/yr).
- NRI seats 5% + $3,000–5,000 fee; WBJEE/JEE/management seat split 80/10/10.
- Scholarship "Swami Vivekananda ₹60,000/yr" entry.
- Faculty "student:teacher 15:1-20:1"; events; hostel timings/curfews.

## 6. UNAVAILABLE SOURCES (blocked)
- VFM & AFM (B.Sc VFX/Animation) fee PDFs + APC Academic Regs & Disciplinary PDFs — WAF-blocked on bcrec.ac.in (every URL variant returns HTML; Wayback 404).
- academic calendar 2026-27, placement policy, NBA PDF — image-only (no text layer).

## 8. FINAL COLLEGE QUESTION LIST (for Sir)
1. MBA printed 4,22,000 vs sem-sum 4,27,000 (MBA-HM 4,20,000 vs 4,25,000; 1st sem 1,21,400 vs 1,22,000) — which is correct?
2. Exam fee: 1,600 vs 1,200 — which applies 2026-27?
3. M.Tech caution: 5,000 (with hostel) / 7,000 (without) — confirmed as printed?
4. B.Tech caution: header says 12,000 (with hostel) / 10,000 (without), tables compute with 5,000 — which is correct?
5. CSD: intake 0 in 2026-27 EOA (closure applied, NOC pending) — final status?
6. WP-B.Tech (Working Professionals, CE/EE/ME 60 each, NEW) — fee structure?
7. NAAC expiry 12-Sep-2026 — re-accreditation status/cycle?
8. Faculty total 187 (AICTE disclosure) vs 208+/281+ promoted on website — correct current count?
9. Campus area: 14 acres (regs preamble) vs website 17?
10. Hostel: single-room rent 30,000/sem correct? Curfews as listed? Any 2026-27 changes?
11. VFM/AFM fee PDF + APC Academic Regs/Disciplinary — provide directly (site blocks download)?
12. Office hours & phone for admission counter 2026-27 (counselling dates too).
13. NRI seats 5% + fees $3,000-5,000; WBJEE/JEE/management split 80/10/10 — confirm.
14. Exception approval: any discretionary fee waiver/negotiation (prospectus does not list any)?
15. APC: status of new program application for 2026-27 (rejected) — any re-filing for 2027-28?