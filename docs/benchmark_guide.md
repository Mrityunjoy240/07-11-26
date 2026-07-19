# Benchmark Authoring Guide

**Version**: 2.0  
**Date**: 2026-07-19  
**Status**: Active

---

## 1. Purpose

This guide ensures consistent, high-quality conversation authoring for the college admission counseling benchmark. Every conversation must stress the pipeline meaningfully — not just fill slots.

**Core principle**: Gold follows intended system behavior, not today's implementation bugs. If the planner is weak, we write hard planner scenarios. We do not lower the gold standard to match current failures.

---

## 2. Directory Structure

```
data/benchmark/
├── conversations/
│   ├── admission/       # Domain subdirectories
│   ├── fees/
│   ├── hostel/
│   ├── ...
├── versions/            # Version manifests
│   ├── v1.1.json
│   └── v2.0.json
├── schema/
│   └── conversation_v2.schema.json
└── VERSION
```

Files live in domain subdirectories. Conversations never move between directories — the version manifest controls which subset belongs to each benchmark version.

---

## 3. Conversation IDs

Format: `BENCH_NNNNNN` (6 digits, globally unique, never restart)

```
BENCH_000001
BENCH_000002
...
```

IDs are independent of domain. A conversation can move between domains without changing its ID.

---

## 4. Domain × Complexity Matrix

Every domain gets examples across multiple complexity levels. This prevents "Admission = hard, Fees = easy" bias.

### 4.1 Domains

| Domain | Description |
|---|---|
| admission | Branch/college recommendation, eligibility |
| fees | Fee structure, payment plans, installments |
| hostel | Accommodation, safety, facilities |
| placement | Placements, packages, companies |
| scholarship | Scholarships, financial aid, renewal |
| management | Management quota, payment seats |
| sports | Sports quota, trials, certificates |
| nri | NRI quota, foreign students, embassy |
| lateral | Lateral entry, diploma-to-degree |
| transfer | Branch transfer, college migration |
| distance | Distance education, online programs |
| counseling | Counseling dates, process, documents |
| grievance | Complaints, escalation, feedback |
| mixed | Multi-topic conversations |
| multilingual | Hindi/Bengali/other language primary |

### 4.2 Complexity Features

| Feature | Description | Example |
|---|---|---|
| correction | Student changes a fact mid-conversation | "Actually my rank is 28k, not 18k" |
| topic_switch | Student pivots to different topic | Starts with admission, asks about hostel |
| missing_info | Key facts deliberately omitted | Student never provides rank |
| adversarial | System must recover from bad info/hostility | "Management quota doesn't exist" |
| parent_mode | Parent is primary speaker | Parent asks about daughter's admission |
| emotion | Anxiety, frustration, confusion | "I'm really worried about my future" |
| language_switch | Language changes mid-conversation | Starts in English, switches to Hindi |
| noisy_input | Typos, abbreviations, incomplete sentences | "amr rank 32k... cse hbe?" |

### 4.3 Target Distribution (Full Benchmark, 200 conversations)

```
                Single  Multi   Memory  Correct  Topic   Emotion  Parent  Contradict  Lang   Noisy  Missing  Adversarial
                Turn    Turn    +State  +State   Switch
Admission       4       8       2       2        2       2        2       2           2      2      4        2           = 34
Fees            2       4       2       0        2       0        2       0           2      2      2        0           = 16
Hostel          2       4       0       0        2       2        2       0           0      0      2        0           = 12
Placement       2       4       0       0        0       0        2       0           2      0      2        0           = 10
Scholarship     2       4       2       2        2       0        0       2           0      2      2        0           = 16
Management      2       4       0       0        0       0        0       0           0      0      2        2           = 10
Sports          2       2       0       0        0       0        0       0           0      2      0        0           = 6
NRI             2       4       0       0        0       0        0       0           2      0      2        0           = 10
Lateral         2       4       0       2        0       0        0       0           0      0      2        0           = 10
Transfer        2       2       0       0        0       0        0       0           2      0      0        0           = 6
Distance        2       2       0       0        0       0        0       0           2      0      0        0           = 6
Counseling      2       2       0       0        0       0        0       0           0      2      0        0           = 6
Grievance       2       2       0       0        0       2        0       0           0      0      0        2           = 8
Mixed           0       4       2       2        2       2        0       2           0      0      2        0           = 16
Multilingual    2       4       0       0        0       0        0       2           2      2      0        0           = 10
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Total          32      52       6       8       10       8        8       8          14     12     20        8          = 200
```

---

## 5. Annotation Workflow

```
Author writes conversation + gold annotations
    ↓
Run pipeline → auto-fill expected fields
    ↓
Author reviews/edits pipeline output
    ↓
Independent reviewer (does NOT see pipeline output first)
    ↓
Run benchmark_validate.py
    ↓
Fix issues
    ↓
Freeze (status: "frozen" in annotation metadata)
```

### 5.1 Gold Standard Rule

> Gold follows intended system behavior, not today's implementation bugs.

- If the planner currently returns wrong actions, the gold should still show the **correct** action.
- If brain currently has a bug in cutoff calculation, the gold should show **correct** eligible branches.
- Improving the pipeline should **not** require rewriting gold annotations.

### 5.2 Annotation Metadata

Every conversation must include:

```json
"annotation": {
    "author": "name",
    "reviewer": "name",
    "created": "2026-07-19T10:00:00Z",
    "reviewed": "2026-07-19T14:00:00Z",
    "status": "reviewed"
}
```

Status values: `draft` → `reviewed` → `frozen`

---

## 6. Annotation Rules

### 6.1 Understanding

| Field | Rule |
|---|---|
| `intent` | ONE primary intent from the enum. First substantive question wins. |
| `facts` | Only values explicitly stated or clearly implied. Use `null` for unknown. |
| `missing` | Fields needed for the intent AND not yet stated. |
| `inference` | Lower confidence observations (anxiety, confusion, urgency, parent_mode). |

### 6.2 Reasoning

| Field | Rule |
|---|---|
| `stage` | ONE from: discovery, exploration, comparison, decision, post_admission |
| `profile_completeness` | `filled/7` across: rank, pcm_percentage, board, category, interest, budget, location |
| `current_problem` | ONE from the controlled vocabulary |
| `problems` | All active problems (can be multiple) |

### 6.3 Brain

| Field | Rule |
|---|---|
| `applicable` | `true` if student has rank AND is asking about admission eligibility |
| `eligible_branches` | Use cutoff data with 15% margin threshold |

**Cutoff reference** (rank better than 85% of cutoff = eligible):

| Category | CSE | AIML | IT | ECE | EE | ME | CE |
|---|---|---|---|---|---|---|---|
| general | 15000 | 18000 | 22000 | 28000 | 40000 | 55000 | 70000 |
| obc | 22000 | 26000 | 32000 | 40000 | 55000 | 75000 | 95000 |
| sc | 40000 | 48000 | 55000 | 65000 | 85000 | 110000 | 140000 |
| st | 50000 | 60000 | 70000 | 85000 | 110000 | 140000 | 180000 |

### 6.4 Decision

| Field | Rule |
|---|---|
| `action` | ONE from the decision action vocabulary |
| `priority` | high / normal / low |
| `why` | 1-3 reasons this action was chosen |

### 6.5 Planner

| Field | Rule |
|---|---|
| `turns[].action` | ONE from: recommend, ask, inform, reassure, encourage, listen, clarify, summarize, escalate |
| `turns[].content_contains` | Max 5 substantive keywords. No filler words. |
| `dependency_chain` | Why these actions were chosen |

---

## 7. Controlled Vocabularies

### 7.1 Decision Actions (21)

```
collect_profile, encourage_and_collect_profile, recommend_branches,
provide_admission_info, provide_fee_info, provide_placement_info,
provide_hostel_info, provide_scholarship_info, provide_career_guidance,
provide_counseling_schedule, escalate_to_human, explain_management_quota_policy,
provide_grievance_process, provide_transfer_info, provide_nri_admission_info,
provide_branch_guidance, provide_sports_info, provide_distance_ed_info,
provide_lateral_entry_info, provide_sports_quota_info, clarify
```

### 7.2 Planner Actions (9)

```
recommend, ask, inform, reassure, encourage, listen, clarify, summarize, escalate
```

### 7.3 Current Problems (11)

```
needs_admission_guidance, needs_profile_completion, needs_fee_information,
needs_placement_data, needs_hostel_info, expressing_anxiety,
comparing_options, has_management_query, has_transfer_query,
has_grievance, general_inquiry
```

### 7.4 Features (8)

```
correction, topic_switch, missing_info, adversarial,
parent_mode, emotion, language_switch, noisy_input
```

### 7.5 Filler Words (Banned from content_contains)

```
like, know, more, next, any, question, help, think, just,
also, very, really, well, okay, yes, no, right, um, uh, hmm, actually
```

---

## 8. Anti-Patterns

### DON'T

- ❌ Write 20 conversations that all start with "My rank is 12000, PCM 92"
- ❌ Use the same vocabulary across similar scenarios
- ❌ Make all fees conversations single-turn and all admission conversations multi-turn
- ❌ Put filler words in `content_contains`
- ❌ Annotate what the pipeline currently does (vs. what it should do)
- ❌ Use generic `content_contains` like ["more", "info", "details"]
- ❌ Write conversations where the student provides all info in turn 1

### DO

- ✅ Vary sentence structure, vocabulary, and information order
- ✅ Include real-world noise (typos, code-switching, incomplete sentences)
- ✅ Test edge cases (contradictions, adversarial inputs, topic switches)
- ✅ Stress weak pipeline components (planner, brain, multilingual)
- ✅ Include parent scenarios across multiple domains
- ✅ Write conversations where information arrives across 3-5 turns
- ✅ Use specific, testable `content_contains` keywords

---

## 9. Example Patterns

### 9.1 Multi-turn Profile Building (Difficulty 3-4)

```
Turn 1: "Hi, I need help with college admission"
  → Missing: rank, pcm, category, interest, board
Turn 2: "My rank is 15000 in WBJEE"
  → Missing: pcm, category, interest
Turn 3: "PCM 88%, general category"
  → Missing: interest
Turn 4: "I want CSE or IT"
  → Complete → recommend_branches
```

### 9.2 Correction Scenario (Difficulty 5)

```
Turn 1: "My rank is 18000"
Turn 2: "Wait, I checked again — it's 28000"
  → State must update, brain re-evaluates
```

### 9.3 Parent Mode (Difficulty 4)

```
Turn 1 (parent): "My son scored 92% in PCM. What are his options?"
Turn 2 (parent): "He wants CSE but I'm worried about fees"
  → parent_mode inference, fee + admission intents
```

### 9.4 Noisy Input (Difficulty 3)

```
Turn 1: "amar rank 32k... cse hbe?"
  → Bengali + English, abbreviations, incomplete
```

### 9.5 Adversarial (Difficulty 6)

```
Turn 1: "My cousin told me management quota doesn't exist"
  → System must correct misinformation and provide accurate info
```

---

## 10. Running Validation

After writing conversations, always run:

```bash
python scripts/benchmark_validate.py --all
```

Fix all issues before submitting for review. The validator checks:
- Schema compliance
- Metadata correctness
- Duplicate scenarios
- Balance across domains and features
- Annotation quality (filler words, contradictions, impossible branches)
