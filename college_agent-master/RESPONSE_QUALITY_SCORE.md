# RESPONSE_QUALITY_SCORE.md — Dimension Scores After Fixes

**Date**: 2026-07-11 13:29

**Total**: 142

## Dimension Scores
| Dimension | Pass | Rate |
|---|---|---|
| hallucination | 142/142 | 100.0% |
| handler_selection | 142/142 | 100.0% |
| content_accuracy | 116/142 | 81.7% |
| completeness | 142/142 | 100.0% |
| conciseness | 142/142 | 100.0% |
| language_mirroring | 142/142 | 100.0% |
| tone | 140/142 | 98.6% |
| latency | 98/142 | 69.0% |
| safety | 142/142 | 100.0% |

## Quality by Source Type
| Source Type | Count | Avg Lat (ms) | Pass Rate |
|---|---|---|---|
| structured | 82 | 884ms | 82/82 (100%) |
| llm | 53 | 26828ms | 9/53 (17%) |
| ood | 3 | 809ms | 3/3 (100%) |
| timeout/fallback | 26 | 36160ms | 0/26 (0%) |

## Latency Distribution
| Range (ms) | Count | % |
|---|---|---|
| 0-1000 | 48 | 33.8% |
| 1000-3000 | 44 | 31.0% |
| 3000-6000 | 4 | 2.8% |
| 6000-10000 | 2 | 1.4% |
| 10000-20000 | 7 | 4.9% |
| 20000-60000 | 37 | 26.1% |