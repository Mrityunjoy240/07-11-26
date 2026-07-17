# Current Rollback Plan

---

## Prerequisite: Git Snapshot

Today's state (2026-07-13) represents the last stable pre-migration baseline. **Before any Phase 1 work begins, ensure this commit exists and is tagged:**

```bash
git tag -a pre-phase-1 -m "Baseline before Phase 1: channel adapters + pipeline"
git push origin pre-phase-1
```

---

## Complete Rollback (Restore Today's State)

### If working directory is clean (no uncommitted changes):
```bash
git checkout -- .
git checkout pre-phase-1
```

### If working directory has changes:
```bash
# Stash all uncommitted work
git stash -u

# Checkout the pre-migration baseline
git checkout pre-phase-1

# To restore stashed work later:
git stash pop
```

### If using feature branches:
```bash
# Create a branch from current state for your experiments
git checkout -b phase-1-experiment

# To roll back Phase 1:
git checkout main  # or master
git merge --abort  # if in merge conflict
```

---

## Partial Rollback (Undo Specific Changes)

### Rollback Phase 0 architecture additions:
```bash
# Remove all new files created in Phase 0
rm -rf backend/app/core/
rm -rf backend/app/channel/
rm -rf backend/app/pipeline/
rm -rf backend/app/pipeline/
```

### Restore original main.py:
```bash
# If you have the original in git:
git checkout pre-phase-1 -- backend/app/main.py

# Or manually remove the Phase 0 initialization block (lines 43-89)
# and restore the original vector store pre-warm section
```

### Rollback feature flags:
```bash
# Simply keep all flags at their default (False)
# Or set environment variables:
set FF_USE_PIPELINE=0
set FF_USE_CHANNEL_ADAPTERS=0
set FF_USE_EVENT_BUS=0
```

---

## Recovery Options

| Scenario | Recovery Action | Downtime |
|---|---|---|
| Phase 1 breaks web chat | Set `FF_USE_CHANNEL_ADAPTERS=0`, restart | ~30s |
| Phase 2 breaks fee queries | Set `FF_USE_PIPELINE=0`, restart | ~30s |
| Phase 3 breaks logging | Set `FF_USE_EVENT_BUS=0`, restart | ~30s |
| Database migration fails | Restore from `data/conversations.db` backup | ~2min |
| ChromaDB corruption | Re-run `POST /admin/reindex` | ~5min |
| Full system failure | `git checkout pre-phase-1 && pip install -r requirements.txt` | ~10min |

---

## Database Rollback

The SQLite database is at `backend/data/conversations.db`. To back it up before any migration:

```bash
copy backend\data\conversations.db backend\data\conversations.db.bak
```

To restore:
```bash
copy backend\data\conversations.db.bak backend\data\conversations.db
```

The ChromaDB vector store is at `backend/chroma_db/chroma_db_v2/`. Full re-index via `POST /admin/reindex` is the fastest recovery path.

---

## Key Files That Must NOT Change During Rollback

These files are the stable baseline. If they are modified during Phase 1+ and need rollback:

- `backend/app/services/llm/groq_service.py` (5046 lines, core logic)
- `backend/app/services/llm/fee_engine.py` (874 lines, fee computation)
- `backend/app/services/llm/intent_classifier.py` (intent routing)
- `backend/app/services/llm/safe_point.py` (hallucination guard)
- `backend/app/services/vector_store.py` (151 lines, RAG)
- `backend/app/services/sarvam_service.py` (304 lines, TTS/STT)
- `backend/app/database.py` (54 lines, SQLite schema)
- `backend/app/api/qa.py` (145 lines, main Q&A endpoint)
- `backend/app/api/conversations.py` (273 lines, conversation CRUD)

---

## Verification After Rollback

```bash
# 1. Verify all imports work
cd backend
python -c "from app import main; print('main imports OK')"

# 2. Verify feature flags are at defaults
python -c "from app.core.feature_flags import feature_flags; print(f'pipeline={feature_flags.use_pipeline}')"

# 3. Verify all tests pass
python -m pytest tests/ -x -q

# 4. Verify API responds
python -c "
import requests
# Start server in background first
r = requests.get('http://localhost:8000/qa/health')
print(f'Health: {r.json()}')
"

# 5. Verify frontend builds
cd frontend
npm run build --if-present
```
