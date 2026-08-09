# Residual Decision Memo — v2.1 Known-Good State

Status: **Known-good baseline `e7ea428`** (2026-08-09).
Scope: the four remaining v2.1 mismatches, treated as benchmark/spec decisions — **not** classifier defects.

---

## 1. Summary

After the D1–D6 decision refinements, the residual harness reports:

| Metric | Value |
|---|---|
| Intent accuracy | 99.3% |
| Action accuracy | 97.3% |
| Mismatched turns | 4 (all frozen/deferred below) |
| New mismatches vs baseline `1351d35` | 0 |

Verified under `PYTHONHASHSEED = 0/1/42` (identical mismatch sets). Full pytest
green (1433 passed). Ruff parity on the touched files.

**Do not** modify the classifier to chase these labels. Each case below is a
competing-spec or cross-intent-state decision, not classifier instability. A fix
for any of them risks destabilizing the 99.3%/97.3% state and the flow it
protects (see "Reopen criteria" per case).

---

## 2. Case-by-Case Decisions

### 2.1 `000042` t2 — FROZEN (profile-completion policy vs answer-with-available-data)

**Conversation**: `distance/BENCH_V21_000042.json` (distance-education thread).

| | Value |
|---|---|
| Student | "Actually, what about regular admission? With 50000 rank, what are my chances for IT in regular mode?" |
| Gold | intent `admission` / action `provide_admission_info` |
| Current | intent `admission` ✓ / problem `needs_profile_completion` / action `collect_profile` |
| Root cause | Profile is missing `personal.category`; the decision engine's profile-completion gate fires `collect_profile` before any info action. Intent classification is correct; the divergence is entirely in the decision step. |

**Decision rationale**: The benchmark label expects the system to answer
"what are my chances" with the available data (rank 50000 → IT in regular mode),
while the product policy requires collecting category first. Two specs compete;
the product policy is intentional and consistent across the dataset (it is the
same gate that keeps every other conversation stable). Overriding it only for
this turn would require a per-conversation carve-out.

**Reopen criteria**: If the product decides to answer admission-chances with an
incomplete profile, change the profile-completion gate globally (with a full
dataset re-sweep), not this label.

---

### 2.2 `000048` t5 — FROZEN (career-guidance topic continuation)

**Conversation**: `career/BENCH_V21_000048.json` (engineering-vs-medical guidance).

| | Value |
|---|---|
| Student | "Thank you bhaiya. Ab clear ho gaya. CSE choose karegi. Kaunse colleges hain Delhi mein rank 20000 ke liye? Aur kya kya karna hai ab?" |
| Gold | intent `career_confusion` / action `provide_career_guidance` |
| Current | intent `admission` / problem `needs_profile_completion` / action `collect_profile` |
| Root cause | The classifier reads "Kaunse colleges ... rank 20000" as a fresh `admission` query, so the career-guidance frame is not carried forward. Gold treats the rank→colleges follow-up as a continuation of the guidance session (the daughter just resolved her confusion; "kya kya karna hai ab" = next steps). |

**Decision rationale**: This is a context-continuation semantics question: when
does a rank→colleges query stay inside an open `career_confusion` thread and when
is it a new admission intent? There is no topic-persistence rule for
`career_confusion` today (unlike hostel/safety). Adding one is a spec decision,
not a one-line classifier fix, because a broad rule could misroute genuinely new
admission queries mid-session.

**Reopen criteria**: When product defines career-guidance session persistence
(e.g., "active guidance session keeps routing follow-ups to career guidance until
the student closes it"), implement it as a state-level rule with adversarial
tests for genuine mid-session admission questions.

---

### 2.3 `000049` t1/t2 — DEFERRED (open-grievance carry-forward)

**Conversation**: `grievance/BENCH_V21_000049.json` (two-week no-response complaint).

| | t1 | t2 |
|---|---|---|
| Student | "I had WBJEE rank 15000, 78% PCM, CBSE board, general category. I want CSE. I applied two weeks ago and got no reply. What is going on? Is my application lost?" | "Fine, but I still want to know why nobody responded for two weeks. And can you confirm I will definitely get CSE? I do not want any more surprises." |
| Gold | intent `admission` / action `provide_admission_info` | intent `admission` / action `provide_admission_info` |
| Current | intent `admission` ✓ / action `recommend_branches` | intent `admission` ✓ / action `recommend_branches` |
| Root cause | The decision engine routes a complete profile + "I want CSE" through the admission-guidance → `recommend_branches` flow. The `MUST_NOT ignore_grievance_root_cause` on t1 and `MUST_NOT be_vague_about_timeline` on t2 signal the label's intent: answer the status/timeline question, not recommend branches. t0 (reassure) de-escalated the grievance, but nothing carries the open grievance thread into the t1/t2 decisions. |

**Decision rationale**: Correct handling requires cross-intent state — an open
grievance raised in a prior turn must bias subsequent decisions toward status /
timeline answers. The platform currently has no such mechanism, and building one
is a design task (state schema + decision-gate + adversarial tests), not a
classifier change. Intent classification is correct on both turns; only the
action diverges, and the fix belongs in the decision layer with a deliberate
spec. Deferred to avoid destabilizing the grievance/intent balance that t0 and
the broader grievance set depend on.

**Reopen criteria**: When the product specifies "open grievance carry-forward,"
implement a decision-layer signal (e.g., `state.metadata.open_grievance`) that
prefers status/timeline actions while the grievance is unresolved, then re-sweep
the full dataset.

---

## 3. Baseline Preservation

- `e7ea428` is the known-good baseline. Re-run and compare via the residual
  harness before any future benchmark/decision work.
- Frozen set (must stay failing-and-documented): `000042 t2`, `000048 t5`.
- Deferred set (may be reopened by design task): `000049 t1`, `000049 t2`.
- Any change to these four labels requires this memo to be updated in the same
  commit.
