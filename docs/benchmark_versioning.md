# Benchmark Versioning & Stability Rules

Status: **Frozen** as of v2.0.
Any change requires a new version manifest.

---

## 1. Checksum Algorithm

Every manifest includes a `checksum` field. It must match exactly:

```
checksum = SHA256(
    json.dumps(
        sorted(conversation_ids),
        sort_keys=True,
        ensure_ascii=False
    )
)[:16]
```

Rules:
- Input: the `conversations` array from the manifest, sorted alphabetically.
- Encoding: UTF-8.
- Output: first 16 hex characters of the SHA-256 digest.
- Never hash file contents. Always hash the sorted ID list.
- Enforced by: `tests/test_manifest_checksum.py` (regression test, mandatory).

---

## 2. Manifest Format

Location: `data/benchmark/versions/{version}.json`

```json
{
  "version": "2.0",
  "status": "draft|frozen",
  "schema": "v2",
  "created": "2026-07-19T00:00:00Z",
  "conversation_count": 5,
  "checksum": "8102a3e1d323bf80",
  "conversations": [
    "BENCH_000001",
    "BENCH_000002"
  ]
}
```

Required fields: `version`, `status`, `schema`, `conversation_count`, `checksum`, `conversations`.
Status transitions: `draft` → `frozen`. Never back to `draft`.

---

## 3. Conversation ID Convention

Format: `BENCH_NNNNNN` (prefix + 6 digits, zero-padded).

Rules:
- Globally unique across all versions.
- Never reused. If a conversation is removed, its ID is retired.
- The 6-digit range supports up to 999,999 conversations.
- IDs are assigned sequentially at authoring time, not at validation time.

---

## 4. Naming Conventions (Frozen)

| Element | Convention | Example |
|---------|-----------|---------|
| Conversation ID | `BENCH_NNNNNN` | `BENCH_000001` |
| Domain directory | lowercase singular | `admission/`, `fees/`, `hostel/` |
| Schema file | `conversation_{version}.schema.json` | `conversation_v2.schema.json` |
| Manifest file | `versions/{version}.json` | `versions/v2.0.json` |
| Baseline file | `evaluation/baseline.json` | `evaluation/baseline.json` |
| Annotation status | `draft` \| `reviewed` \| `frozen` | `reviewed` |
| Features array | controlled vocabulary | `["missing_info", "topic_switch"]` |
| Difficulty | integer 1-5 | `4` (label derived, not stored) |
| Languages | array of ISO 639-1 codes | `["en", "hi"]` |

---

## 5. Validator CLI (Frozen)

Script: `scripts/benchmark_validate.py`

### Public flags (frozen — no renames, no removals)

| Flag | Description |
|------|-------------|
| `--version VERSION` | Validate a single version (e.g., `v2.0`) |
| `--all-versions` | Validate all manifests + cross-version compatibility |
| `--schema` | Run schema validation |
| `--metadata` | Run metadata validation (domain, ID, features, languages) |
| `--quality` | Run quality checks (duplicates, filler words, similar endings) |
| `--coverage` | Run coverage checks |
| `--regression` | Run regression checks |
| `--run` | Run pipeline and compare against baseline |

### Output format (frozen)

- Section headers: `══════════` dividers
- Per-conversation errors: `  CONV_ID: error message`
- Summary: `TOTAL ISSUES: N`
- Exit code: 0 if no issues, 1 if issues found

### Stability rules after freeze

- No renamed flags.
- No changed output format.
- Only additive features (new checks, new flags).
- Breaking changes require a new major version of the validator.

---

## 6. Schema Version (Frozen)

Current: `v2` (file: `data/benchmark/schema/conversation_v2.schema.json`).

Changes require:
1. New schema file: `conversation_v{N}.schema.json`
2. New manifest: `versions/v{X}.0.json` pointing to the new schema
3. Validator updated to load the new schema
4. All conversations in the new version validated against the new schema

Never modify `conversation_v2.schema.json` in place. Create `v3` instead.

---

## 7. Annotation Guidelines (Frozen)

Current: `docs/annotation_guidelines.md`

Changes require:
1. Version bump in the guidelines header
2. Re-annotation of affected conversations
3. Reviewer sign-off

Key rules (frozen):
- Gold follows **intended behavior**, not current pipeline bugs.
- Annotation provenance: author, reviewer, created, reviewed, status.
- Required fields: understanding, reasoning, brain, decision, planner.
- `must_not` array: at least 1 item per turn.
- `ideal_counselor_notes`: always present.

---

## 8. Baseline Format (Frozen)

Location: `data/benchmark/evaluation/baseline.json`

```json
{
  "version": "v2.0",
  "pipeline": "main",
  "date": "2026-07-19",
  "pipeline_commit": "abc1234",
  "benchmark_checksum": "8102a3e1d323bf80",
  "conversation_count": 5,
  "turn_count": 10,
  "turn_accuracy": 0.75,
  "conversation_accuracy": 0.40,
  "intent_accuracy": 0.75,
  "action_accuracy": 0.75,
  "retrieval_accuracy": null,
  "hallucination_rate": null,
  "avg_latency_ms": null,
  "failed_conversations": ["BENCH_000003"],
  "per_conversation": {}
}
```

`null` fields are measured when the corresponding check is implemented.
Baseline is overwritten on each pipeline version bump.
Regression threshold: no more than 1% drop from previous baseline.
