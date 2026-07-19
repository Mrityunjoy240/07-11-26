# Inter-Rater Annotation Guidelines — Golden Conversation Benchmark

**Version**: 1.0  
**Date**: 2026-07-19

---

## 1. Purpose

These guidelines ensure consistent annotation of golden conversations by multiple raters. When two or more humans annotate the same conversations independently, inter-rater agreement (measured by Cohen's κ) validates that the benchmark is objective and reproducible.

## 2. What Gets Annotated

Each conversation turn has an `expected` object with fields across 5 stages. Annotators must fill in or verify:

### 2.1 Understanding

| Field | Annotation task | Decision rule |
|---|---|---|
| `intent.primary` | Classify the student's primary intent | Choose ONE from: `admission`, `fee`, `placement`, `hostel`, `scholarship`, `grievance`, `counseling`, `unknown` |
| `facts` | Extract factual claims from student text | Only include values explicitly stated or clearly inferable. Use `null` for unknown numeric values. |
| `missing` | List fields still needed | Include any ground_truth field not yet stated by the student AND not clearly inferable from context. |

### 2.2 Reasoning

| Field | Annotation task | Decision rule |
|---|---|---|
| `stage` | Classify student journey stage | Choose ONE: `discovery`, `exploration`, `comparison`, `decision`, `post_admission` |
| `profile_completeness` | Estimate 0.0-1.0 | Count known fields / total ground_truth fields. Round to nearest 0.1. |
| `confidence` | Your confidence in the classification | `high` (≥0.8 certainty), `medium` (0.5-0.8), `low` (<0.5) |
| `current_problem` | Primary problem to solve this turn | Choose ONE from a controlled vocabulary (see Section 4) |

### 2.3 Brain

| Field | Annotation task | Decision rule |
|---|---|---|
| `applicable` | Is brain applicable? | `true` if student has rank AND is asking about admission eligibility |
| `eligible_branches` | List branches student could get | Use cutoff data if available; otherwise mark as `[]` with note |

### 2.4 Decision

| Field | Annotation task | Decision rule |
|---|---|---|
| `action` | Choose the best action | Choose ONE from the action vocabulary (see Section 5) |

### 2.5 Planner

| Field | Annotation task | Decision rule |
|---|---|---|
| `turns[i].action` | Match decision action or choose info-gathering action | Must be a valid action from Section 5 |
| `turns[i].content_contains` | List keywords the response MUST include | Maximum 5 keywords; must be substantive (not filler words) |

## 3. Annotation Rules

### 3.1 Separation of Pipeline vs Evaluation

- **Annotate what the pipeline SHOULD do**, not what it currently does.
- If the pipeline is wrong, that's a pipeline problem, not an annotation problem.
- Gold standard reflects ideal behavior, not current behavior.

### 3.2 Conservative Extraction

- Only extract facts the student **explicitly states** or **clearly implies**.
- Do NOT infer from context that isn't present in the student text.
- Example: "I got 95%" → extract `pcm_percentage: 95`. Do NOT infer `board: cbse`.

### 3.3 Missing Information

- Mark a field as missing if:
  - It's required for the intent AND not yet stated
  - It's in ground_truth AND not yet stated
- Do NOT mark as missing:
  - Fields that are clearly inferable from context
  - Optional fields that aren't needed for this turn's decision

### 3.4 Intent Classification

- Use the primary intent only. Secondary intents go in `all_intents` (not evaluated).
- If the student asks about multiple topics, classify by the FIRST substantive question.

### 3.5 Difficulty Rating

- 1: FAQ (e.g., "What are the fees?")
- 2: Single-turn admission (e.g., "I have rank 5000, can I get CSE?")
- 3: Profile building (e.g., multiple facts needed)
- 4: Multi-turn reasoning (e.g., comparison across colleges)
- 5: Memory + contradiction (e.g., changes facts mid-conversation)
- 6: Emotion + recommendation (e.g., anxious student needs encouragement)
- 7: Everything together

## 4. Current Problem Vocabulary

Controlled vocabulary for `reasoning.current_problem`:

| Value | Description |
|---|---|
| `needs_admission_guidance` | Student needs branch/college recommendation |
| `needs_profile_completion` | Missing critical facts (rank, percentage, interest) |
| `needs_fee_information` | Asking about fees, payments, scholarships |
| `needs_placement_data` | Asking about placements, packages, companies |
| `needs_hostel_info` | Asking about accommodation, safety, facilities |
| `expressing_anxiety` | Student is worried, needs encouragement |
| `comparing_options` | Student wants to compare branches/colleges |
| `has_management_query` | Management/NRI quota question |
| `has_transfer_query` | Lateral entry or branch transfer |
| `has_grievance` | Complaint or escalation needed |
| `general_inquiry` | Doesn't fit other categories |

## 5. Decision Action Vocabulary

| Value | Description |
|---|---|
| `collect_profile` | Ask for missing profile information |
| `encourage_and_collect_profile` | Encourage anxious student + collect profile |
| `recommend_branches` | Provide branch/college recommendation |
| `provide_admission_info` | Share admission-related information |
| `provide_fee_info` | Share fee-related information |
| `provide_placement_info` | Share placement-related information |
| `provide_hostel_info` | Share hostel-related information |
| `provide_scholarship_info` | Share scholarship-related information |
| `provide_career_guidance` | Provide career guidance (non-engineering) |
| `provide_counseling_schedule` | Share counseling dates/timeline |
| `escalate_to_human` | Escalate to human counselor |

## 6. When to Disagree with Another Rater

Disagreement is expected and healthy. You SHOULD disagree when:

- The student text is ambiguous and two interpretations are equally valid
- You believe the gold standard is wrong (add a note explaining why)
- The annotation guidelines don't cover the edge case

You SHOULD NOT disagree on:

- Factual extractions (the student either said "95%" or they didn't)
- Intent classification when the intent is clear
- Missing fields that are obviously needed or obviously satisfied

## 7. Annotation Output Format

Each annotator produces a JSON file identical in structure to the benchmark conversation, but with their annotations in the `expected` fields. The difference between two annotators' files is what Cohen's κ measures.

## 8. Quality Control

- Minimum 2 annotators per conversation
- Annotators should not see each other's annotations
- Disagreements > 30% on a conversation trigger a third annotator tiebreak
- Annotators must complete at least 5 practice conversations before annotating real data
