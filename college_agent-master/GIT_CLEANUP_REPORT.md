# Git Repository Cleanup Report — v1.0.0-rc1

Generated: 2026-07-11

## Repository Health Score: **45/100** (Needs cleanup before release)

---

## 1. Critical Issues

### 1.1 Large Binary in Git History — `backend/models/en_US-amy-medium.onnx`
- **Size:** 61,720 KB (61 MB)
- **Impact:** Every clone/download includes this large TTS voice model.
- **Recommendation:** Remove with `git filter-branch` or `git filter-repo`, add to `.gitignore`, and download at runtime or provide as a separate asset.

### 1.2 Duplicate / Stale Knowledge Base Files in Git
| File | Size | Issue |
|------|------|-------|
| `backend/data/knowledge_base.json` | 52 KB | Duplicate content |
| `backend/data/canonical/canonical_kb.json` | 72 KB | Duplicate content |
| `backend/data/knowledge_base/combined_kb.json` | 83 KB | Duplicate content |

**Recommendation:** Consolidate to a single canonical KB. Keep one authoritative source.

### 1.3 Benchmark Artifacts in Git
| File | Size |
|------|------|
| `backend/benchmarks/eval_reports/checkpoint.json` | 62 KB |
| `backend/benchmarks/eval_reports/demo_eval_20260630_101626.json` | 56 KB |
| `backend/benchmarks/eval_reports/demo_eval_20260630_103431.json` | 69 KB |
| `backend/benchmarks/eval_reports/demo_eval_20260630_103431.txt` | 7 KB |
| `backend/benchmarks/eval_reports/stress_test_*.txt` | 1 KB each |

**Recommendation:** Remove from git. These are generated artifacts, not source code. Add `benchmarks/eval_reports/` to `.gitignore`.

---

## 2. File Inventory & Classification

### 2.1 Root Directory (18 files, untracked — all REMOVE after review)

| File | Size | Action |
|------|------|--------|
| `BENCHMARK_DIFF.md` | 4 KB | REMOVE — generated report |
| `FAILURE_CLASSIFICATION.md` | 7 KB | REMOVE — generated report |
| `failure_diagnostics.json` | 41 KB | REMOVE — generated artifact |
| `FAILURE_PATTERNS.md` | 9 KB | REMOVE — generated report |
| `FINAL_BENCHMARK.md` | 10 KB | REMOVE — generated report |
| `FINAL_LATENCY_REPORT.md` | 3 KB | REMOVE — generated report |
| `FINAL_RESPONSE_SCORE.md` | 2 KB | REMOVE — generated report |
| `IMPROVEMENT_PLAN.md` | 4 KB | REMOVE — generated report |
| `LLM_FAILURE_AUDIT.md` | 19 KB | REMOVE — generated report |
| `RELEASE_BLOCKER_FIX.md` | 6 KB | REMOVE — generated report |
| `RELEASE_CANDIDATE_AUDIT.md` | 18 KB | REMOVE — generated report |
| `RELIABILITY_FIX_REPORT.md` | 4 KB | REMOVE — generated report |
| `RESPONSE_QUALITY_SCORE.md` | 1 KB | REMOVE — generated report |
| `ROOT_CAUSE_MATRIX.md` | 15 KB | REMOVE — generated report |
| `SECURITY_FIX_REPORT.md` | 6 KB | REMOVE — generated report |
| `TEST_REPORT.md` | 25 KB | REMOVE — generated report |
| `TOP_30_WORST_RESPONSES.md` | 3 KB | REMOVE — generated report |
| `agent_response_quality_design.md` | — | REMOVE — displaced, should be in `audit/` |

### 2.2 Root Directory (logs, untracked — all ADD TO .gitignore)

| File | Size |
|------|------|
| `agent.log` | 8 KB |
| `agent_console.log` | 244 KB |
| `agent_err.log` | 168 KB |
| `agent_log.txt` | 206 KB |
| `agent_out.log` | 96 KB |
| `agent_output.log` | 3 KB |
| `agent_status.txt` | 0 KB |
| `agent_stderr.log` | 0 KB |
| `agent_stdout.log` | 9 KB |
| `server.log` | 21 KB |
| `server_err.log` | 15 KB |
| `server_out.log` | 0 KB |
| `uvicorn.log` | 15 KB |
| `ngrok.log` | 2 KB |

### 2.3 Root Directory (test JSON, untracked — REMOVE or ADD TO .gitignore)

| File | Size |
|------|------|
| `test_addr.json` | 1 KB |
| `test_comprehensive.json` | 8 KB |
| `test_full.json` | 1 KB |
| `test_groq.json` | 0 KB |
| `test_output.json` | 0 KB |
| `test_principal.json` | 1 KB |

### 2.4 `backend/` — Temporary Validation Scripts (untracked — REMOVE)

| File | Size |
|------|------|
| `b3_evidence.py` | — |
| `b7_evidence.py` | — |
| `b8_evidence.py` | — |
| `smoke_test_security.py` | — |
| `stress_test_reliability.py` | — |
| `validate_blockers.py` | — |
| `validate_remaining.py` | — |
| `benchmarks/analyze_results.py` | — |
| `benchmarks/diagnose_failures.py` | — |
| `benchmarks/extract_failures.py` | — |

All are one-off diagnostic scripts. REMOVE after confirming no future use.

### 2.5 `backend/benchmarks/eval_reports/` — New Benchmark Artifacts (untracked — ADD TO .gitignore)

| File | Size |
|------|------|
| `demo_eval_20260711_132333.json` | — |
| `demo_eval_20260711_132333.txt` | — |
| `demo_eval_20260711_190204.json` | — |
| `demo_eval_20260711_190204.txt` | — |

### 2.6 `audit/` — (tracked, but contains generated analysis)

| File | Size | Status | Action |
|------|------|--------|--------|
| `ARCHITECTURE.md` | — | Tracked | KEEP — useful reference |
| `CALL_GRAPH.md` | — | Tracked | KEEP — useful reference |
| `CODEBASE_MAP.md` | — | Tracked | KEEP — useful reference |
| `DEAD_CODE.md` | — | Tracked | KEEP — useful reference |
| `EVIDENCE_REVIEW.md` | — | Tracked | KEEP — useful reference |
| `KNOWN_BUGS.md` | — | Tracked | KEEP — useful reference |
| `KNOWN_RUNTIME_PATHS.md` | — | Tracked | KEEP — useful reference |
| `PROJECT_STATE.md` | — | Tracked | KEEP — useful reference |

Note: `audit/` currently has 24 files totaling 475 KB. Some may be stale. Consider moving these to a separate `docs/audit/` directory that is gitignored.

### 2.7 `knowledge_audit/` — (untracked — REMOVE or ADD TO .gitignore)

14 files, 70 KB total. Generated knowledge base analysis. Not source code.

### 2.8 `reports/` — (untracked — ADD TO .gitignore)

1 file (17 KB). Generated report.

---

## 3. Large Disk Usage (untracked — all should be gitignored)

| Path | Size | Category |
|------|------|----------|
| `backend/logs/app.log.1` | 10,240 KB | Logs |
| `backend/logs/app.log` | 6,963 KB | Logs |
| `backend/logs/error.log` | 674 KB | Logs |
| `backend/server_err.log` | 1,594 KB | Logs |
| `backend/backend.log` | 466 KB | Logs |
| `agent_console.log` | 244 KB | Logs |
| `agent_log.txt` | 206 KB | Logs |
| `agent_err.log` | 168 KB | Logs |
| `agent_log.txt` (root) | 206 KB | Logs |
| `logs/app.log` | 606 KB | Logs |
| `scripts/agent.log` | 238 KB | Logs |
| `scripts/logs/agent.log` | 295 KB | Logs |
| `scripts/agent_err.txt` | 148 KB | Logs |
| `scripts/agent_out.txt` | 196 KB | Logs |
| `data/logs/conversations/` | 529 files, 6,606 KB | Conversation history |
| `data/logs/reports/` | 12 files, 109 KB | Generated reports |
| `chroma_db/chroma_db_v2/chroma.sqlite3` | 5,792 KB | ChromaDB data |
| `chroma_db/chroma_db_v2.backup/chroma.sqlite3` | 5,792 KB | ChromaDB backup |
| `temp_audio/tts_cache/` | 50 files, 24,160 KB | TTS audio cache |
| `downloads/` | 10 files, 952 KB | Downloaded PDFs |
| `uploads/` | 6 files, 772 KB | Uploaded PDFs |
| `data/models/lid.176.ftz` | 916 KB | Language detection model |
| `venv/` | ~7 MB | Python virtual environment |
| `frontend/node_modules/` | ~Varies | JS dependencies |
| `.ruff_cache/` | ~5 KB | Linter cache |
| `.pytest_cache/` | ~31 KB | Test cache |

---

## 4. `.gitignore` — Missing Entries

Current `.gitignore`:
```
venv/
__pycache__/
*.pyc
node_modules/
.env
backend/.env
backend/logs/
backend/models/
chroma_db/
temp_audio/
downloads/
uploads/
data/logs/
data/models/
```

**Suggested additions:**
```gitignore
# Caches
.pytest_cache/
.ruff_cache/

# Logs at root
*.log
agent_*.txt
agent_*.log
server*.log
server*.txt
uvicorn.log
ngrok.log

# Generated reports
*.md
failure_diagnostics.json

# Test artifacts
test_*.json

# Benchmark artifacts
backend/benchmarks/eval_reports/

# Generated analysis
knowledge_audit/
reports/

# Root temporary scripts
backend/validate_blockers.py
backend/validate_remaining.py
backend/b3_evidence.py
backend/b7_evidence.py
backend/b8_evidence.py
backend/smoke_test_security.py
backend/stress_test_reliability.py
backend/benchmarks/analyze_results.py
backend/benchmarks/diagnose_failures.py
backend/benchmarks/extract_failures.py
```

Note: Do NOT blanket-gitignore `*.md` (README.md and future docs would be lost).

---

## 5. Risk Assessment

| Risk | Severity | Description |
|------|----------|-------------|
| Binary bloat (61 MB ONNX) | **HIGH** | Every clone pays this cost. Need `git filter-repo` to expunge. |
| Secrets in history | **MEDIUM** | Must audit full git history for accidental `.env` or `secret_key` commits. |
| KB data duplication | **LOW** | Stale data could cause confusion. Deduplicate before release. |
| Benchmark artifacts in git | **LOW** | Unnecessary history bloat (200+ KB). Add to `.gitignore` and `git rm`. |
| No README/CHANGELOG at root | **LOW** | Missing release documentation. Create before tagging. |

---

## 6. Recommended Cleanup Sequence

### Phase 1 — Quick wins (no history rewrite)
1. Update `.gitignore` with all missing entries
2. `git rm --cached` for `backend/benchmarks/eval_reports/*` (keep files locally)
3. `git rm --cached` for `audit/*.md` (already tracked — might want to keep)
4. Clean up root directory (delete logs, test JSONs, generated reports)
5. Delete temporary scripts from `backend/`

### Phase 2 — Data deduplication
6. Consolidate KB JSON files into single source
7. Remove duplicate ChromaDB backup directory

### Phase 3 — History rewrite (requires coordination)
8. Use `git filter-repo` to remove `en_US-amy-medium.onnx` from history
9. Audit full history for secrets with `git log -p -S secret_key`
10. Tag v1.0.0-rc1 after cleanup

### Phase 4 — Release documentation
11. Create/update `README.md` (root level exists, verify it is current)
12. Create `CHANGELOG.md` with release notes
13. Verify `LICENSE` exists
