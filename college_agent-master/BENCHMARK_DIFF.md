# BENCHMARK_DIFF.md — Before vs After (Sprint 1 Fixes)

**Date**: 2026-07-11 13:29

## 1. Overall Score
| Metric | Before (129 q) | After (142 q) | Δ |
|---|---|---|---|
| Pass rate | 29.5% (38/129) | 69.0% (98/142) | +39.5pp |
| Failures | 91/129 | 44/142 | -47 |

## 2. Per-Dimension Comparison
| Dimension | Before Pass | After Pass | Δ |
|---|---|---|---|
| hallucination | 129/129 (100%) | 142/142 (100%) | +13 |
| handler_selection | 75/129 (58%) | 142/142 (100%) | +67 |
| content_accuracy | 76/129 (59%) | 116/142 (82%) | +40 |
| completeness | 104/129 (81%) | 142/142 (100%) | +38 |
| conciseness | 116/129 (90%) | 142/142 (100%) | +26 |
| language_mirroring | 129/129 (100%) | 142/142 (100%) | +13 |
| tone | 129/129 (100%) | 140/142 (99%) | +11 |
| latency | 82/129 (64%) | 98/142 (69%) | +16 |
| safety | 120/129 (93%) | 142/142 (100%) | +22 |

## 3. Source Distribution (After)
| structured_lookup | 82 | 58% |
| llm_tools | 52 | 37% |
| transcript_clarification | 4 | 3% |
| out_of_domain | 3 | 2% |
| llm_tools+safe_point_unknown | 1 | 1% |

## 5. Specific Fix Verification

| Fix Query | Status | Source | Latency (ms) | Notes |
|---|---|---|---|---|
| namaste | ✅ PASS | greeting_deterministic | 486 | Correctly recognized as greeting |
| नमस्ते | ✅ PASS | greeting_deterministic | 344 | Devanagari greeting now works |
| নমস্কার | ✅ PASS | greeting_deterministic | 330 | Bengali greeting now works |
| tell me a joke | ✅ PASS | out_of_domain | 324 | Blocked by OOD pattern |
| how to make biryani | ✅ PASS | out_of_domain | 308 | Blocked by OOD regex |
| translate to bengali | ✅ PASS | out_of_domain | 334 | Blocked by OOD regex |
| how to build a website | ✅ PASS | out_of_domain | 306 | Blocked by OOD regex |
| college address | ✅ PASS | structured_lookup | 312 | New handler works |
| college website | ✅ PASS | structured_lookup | 328 | New handler works |
| college canteen | ✅ PASS | structured_lookup | 352 | New handler works |
| how to reach BCREC | ✅ PASS | structured_lookup | 312 | New handler works |
| dean of BCREC | ✅ PASS | structured_lookup | 339 | New handler works |
| chairman of BCREC | ✅ PASS | structured_lookup | 372 | New handler works |
| yes (standalone) | ✅ PASS | yes_no_continuation | 314 | Standalone yes now works |
| no (standalone) | ✅ PASS | yes_no_continuation | 351 | Standalone no now works |
| konsa department lu | ✅ PASS | structured_lookup | 333 | Branch recommendation works |
| play cricket with me | ✅ PASS | out_of_domain | 333 | Blocked by OOD regex |
| latest bollywood movie | ✅ PASS | out_of_domain | 320 | Blocked by OOD regex |
| CSE er fees koto | ✅ PASS | structured_lookup | 322 | SafePoint no longer blocks |
| CSE er fee koto | ✅ PASS | structured_lookup | 319 | SafePoint no longer blocks |
| canteen (single word) | ❌ FAIL | transcript_clarification | 321 | Single word blocked by validation |
| sports facilities | ❌ FAIL | llm_tools | 1941 | Regex `\bsport\b` doesn't match "sports" (needs `s?`) |
| faculty list | ❌ FAIL | llm_tools | 881 | Pre-empted by general faculty handler before new handler |
| departments (single word) | ❌ FAIL | llm_tools | 15682 | Regex `\bdepartment\b` doesn't match "departments" + handler order |
| laboratory facilities | ❌ FAIL | llm_tools | 15322 | Regex `laborator` matches but handler falls through |
| how many faculty members | ❌ FAIL | llm_tools | 15025 | Pre-empted by general faculty handler |
| how many students | ❌ FAIL | llm_tools | 15811 | Top-level handler not matching |
| BCREC er placement kemon | ✅ PASS | llm_tools | 3886 | Now passes SafePoint → LLM handles |

## 6. Average Latency by Source Type
| Type | Count | Avg Latency (ms) |
|---|---|---|
| Structured handlers | 82 | 884ms
| LLM responses | 53 | 26828ms
| OOD blocked | 3 | 809ms
| Timeout/fallback | 26 | 36160ms