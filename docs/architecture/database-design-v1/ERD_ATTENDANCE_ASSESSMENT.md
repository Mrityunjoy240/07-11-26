# ERD — Attendance and Internal Assessment

**Domains:** Attendance (`attendance`), Assessment (`assessment`).
**Trace:** Research §8.4–8.5, §9.3–9.4; S1 §§16–19; S2 p.55; S17; G-01, G-13–G-15.
**Purpose:** make the capture unit, the correction history, the computed summary, the eligibility decision, and the versioned mark chain explicit. These are the records most likely to be disputed, so no derived value is stored as if it were the original fact.

---

## 1. Attendance: capture, correction, summary, eligibility

```mermaid
erDiagram
    STUDENT {
        uuid student_id PK
        text college_roll_no
        uuid batch_id FK
    }
    COURSE_OFFERING {
        uuid course_offering_id PK
        uuid course_version_id FK
        uuid term_id FK
        uuid batch_id FK
        uuid section_id FK
    }
    TIMETABLE_SLOT {
        uuid timetable_slot_id PK
        uuid course_offering_id FK
        text day_of_week
        time start_time
        time end_time
        text slot_type
    }
    ATTENDANCE_SESSION {
        uuid session_id PK
        uuid course_offering_id FK
        uuid timetable_slot_id FK
        date session_date
        time start_time
        time end_time
        text session_type
        text status
        uuid held_by_person_id FK
    }
    ATTENDANCE_RECORD {
        uuid attendance_record_id PK
        uuid session_id FK
        uuid student_id FK
        uuid course_registration_id FK
        uuid course_offering_id FK
        text status
        text source
        timestamptz marked_at
        uuid marked_by FK
    }
    COURSE_REGISTRATION {
        uuid course_registration_id PK
        uuid student_id FK
        uuid semester_registration_id FK
        uuid course_offering_id FK
        text status
    }
    SEMESTER_REGISTRATION {
        uuid semester_registration_id PK
        uuid student_id FK
        uuid term_id FK
        text status
    }
    ATTENDANCE_CORRECTION {
        uuid correction_id PK
        uuid attendance_record_id FK
        text old_status
        text new_status
        text reason
        uuid requested_by FK
        uuid approved_by FK
        text status
        uuid evidence_document_version_id FK
    }
    ATTENDANCE_SUMMARY {
        uuid summary_id PK
        uuid student_id FK
        uuid course_offering_id FK
        integer sessions_conducted
        integer sessions_attended
        numeric attendance_pct
        timestamptz as_of
        text calculation_version
        uuid policy_rule_version_id FK
    }
    ELIGIBILITY_ASSESSMENT {
        uuid eligibility_assessment_id PK
        uuid student_id FK
        uuid term_id FK
        text rule_variant
        numeric aggregate_pct
        numeric theory_pct
        numeric practical_pct
        text outcome
        timestamptz computed_at
        jsonb inputs_json
        uuid policy_bundle_version_id FK
    }
    CONDONATION_CASE {
        uuid condonation_case_id PK
        uuid student_id FK
        uuid term_id FK
        uuid eligibility_assessment_id FK
        numeric shortfall_pct
        text grounds
        text hod_recommendation
        text ac_decision
        date decision_date
        uuid order_document_version_id FK
        text status
    }
    TERM {
        uuid term_id PK
        text term_type
    }
    PERSON {
        uuid person_id PK
        text legal_name
    }
    RULE_VERSION {
        uuid rule_version_id PK
        text status
    }
    POLICY_BUNDLE_VERSION {
        uuid policy_bundle_version_id PK
        integer version_no
        text status
    }
    DOCUMENT_VERSION {
        uuid document_version_id PK
        text sha256
        text classification
    }

    COURSE_OFFERING ||--o{ ATTENDANCE_SESSION : has
    TIMETABLE_SLOT |o--o{ ATTENDANCE_SESSION : instantiates
    PERSON ||--o{ ATTENDANCE_SESSION : conducts
    ATTENDANCE_SESSION ||--o{ ATTENDANCE_RECORD : records
    STUDENT ||--o{ ATTENDANCE_RECORD : attends
    COURSE_REGISTRATION ||--o{ ATTENDANCE_RECORD : proves_enrolment
    STUDENT ||--o{ COURSE_REGISTRATION : holds
    SEMESTER_REGISTRATION ||--o{ COURSE_REGISTRATION : contains
    COURSE_OFFERING ||--o{ COURSE_REGISTRATION : offered_to
    ATTENDANCE_RECORD ||--o{ ATTENDANCE_CORRECTION : corrected_by
    PERSON ||--o{ ATTENDANCE_CORRECTION : requests
    PERSON ||--o{ ATTENDANCE_CORRECTION : approves
    DOCUMENT_VERSION |o--o{ ATTENDANCE_CORRECTION : evidences
    STUDENT ||--o{ ATTENDANCE_SUMMARY : summarised
    COURSE_OFFERING ||--o{ ATTENDANCE_SUMMARY : summarised_for
    RULE_VERSION |o--o{ ATTENDANCE_SUMMARY : governs
    STUDENT ||--o{ ELIGIBILITY_ASSESSMENT : assessed
    TERM ||--o{ ELIGIBILITY_ASSESSMENT : scopes
    POLICY_BUNDLE_VERSION ||--o{ ELIGIBILITY_ASSESSMENT : governs
    STUDENT ||--o{ CONDONATION_CASE : seeks
    TERM ||--o{ CONDONATION_CASE : scopes
    ELIGIBILITY_ASSESSMENT ||--o| CONDONATION_CASE : challenges
    DOCUMENT_VERSION |o--o{ CONDONATION_CASE : evidences
```

**Capture model:**

| Record | Granularity | Authoritative? | Notes |
|---|---|---|---|
| `attendance_session` | One class/lab meeting | Yes | A cancelled session is not counted in the denominator. |
| `attendance_record` | One student in one session | Yes | Unique per session and student; carries the registration and offering so the student must be enrolled in the session's offering. |
| `attendance_correction` | One change event | Audit | Does not replace the record; the record is updated and the correction preserves old/new. |
| `attendance_summary` | Student × offering | No — derived | Recomputed from records; records `as_of` and policy version. |
| `eligibility_assessment` | Student × term × rule variant | Policy decision | Stores both aggregate and split percentages so a rule change can be re-evaluated without re-capturing attendance. |
| `condonation_case` | Student × term | Institutional decision | References the assessment it challenges and the Academic Council order document. |

**Registration invariant:** `attendance_record` references the student, the `course_registration`, and the `course_offering`. Two composite foreign keys make the rule structural:

- `(course_registration_id, student_id, course_offering_id) → student.course_registration(course_registration_id, student_id, course_offering_id)` proves the registration belongs to this student and this offering.
- `(session_id, course_offering_id) → attendance.session(session_id, course_offering_id)` proves the session belongs to the same offering.

Together they make it impossible to record attendance for a student who is not registered in the exact offering being taught. The direct `student_id` FK remains for query simplicity, but it is not the authority. The service additionally rejects a record when the registration was dropped before the session date; that temporal rule is not expressible as an FK and is documented in `OPEN_DECISIONS.md` OD-14.

**Why two attendance variants:** ATT-01 (S1 §16) says 75% aggregate; ATT-05 (S2 p.55) says 75% separately in theory and practical. MAKAUT's August 2026 notification (S17) does not settle it. The assessment stores `rule_variant` and both percentage sets. The system can compute both, display both, and record which one a decision used. No default gate is enabled until G-01 is resolved.

**Attendance marks:** CIA attendance (5 marks) and PCIA attendance (10 marks) are policy parameters, not hard-coded. The mapping from percentage to marks lives in the assessment scheme/rule version. The attendance summary supplies the percentage; the assessment component records the resulting mark.

**Duty leave:** modelled as `attendance.duty_leave` (Phase B). It is not activated because the research does not define whether duty leave counts toward the 75% (G-14). The schema supports `counts_as_attendance` as a policy parameter when the institution decides.

---

## 2. Assessment: scheme, components, versioned marks

```mermaid
erDiagram
    COURSE_VERSION {
        uuid course_version_id PK
        uuid course_id FK
        integer version_no
        text title
    }
    ASSESSMENT_SCHEME {
        uuid scheme_id PK
        uuid course_version_id FK
        uuid effective_from_term_id FK
        uuid effective_to_term_id FK
        text name
        text status
        uuid policy_bundle_version_id FK
    }
    ASSESSMENT_COMPONENT {
        uuid component_id PK
        uuid scheme_id FK
        uuid parent_component_id FK
        text component_code
        text name
        text component_type
        numeric max_marks
        numeric weight_pct
        integer sequence_no
        boolean attendance_linked
    }
    ASSESSMENT_SCHEDULE {
        uuid schedule_id PK
        uuid component_id FK
        uuid course_offering_id FK
        timestamptz scheduled_start
        integer duration_min
        text venue_text
        text status
    }
    MARK_ENTRY {
        uuid mark_entry_id PK
        uuid student_id FK
        uuid component_id FK
        uuid course_offering_id FK
        integer current_version_no
        text status
        boolean is_absent
        boolean is_exempt
    }
    MARK_ENTRY_VERSION {
        uuid mark_entry_version_id PK
        uuid mark_entry_id FK
        integer version_no
        numeric marks_obtained
        numeric max_marks_snapshot
        boolean is_absent
        boolean is_exempt
        text status
        uuid entered_by FK
        timestamptz entered_at
        uuid verified_by FK
        timestamptz verified_at
        text change_reason
    }
    MARK_CORRECTION {
        uuid mark_correction_id PK
        uuid mark_entry_id FK
        uuid from_version_id FK
        uuid to_version_id FK
        text reason
        uuid requested_by FK
        uuid approved_by FK
        text status
        uuid evidence_document_version_id FK
    }
    CONFLICT_DECLARATION {
        uuid conflict_declaration_id PK
        uuid faculty_person_id FK
        uuid course_offering_id FK
        uuid student_id FK
        text relationship_type
        timestamptz declared_at
        text action_taken
        uuid reassigned_to_person_id FK
        text status
        uuid document_version_id FK
    }
    COURSE_OFFERING {
        uuid course_offering_id PK
        uuid course_version_id FK
        uuid term_id FK
    }
    STUDENT {
        uuid student_id PK
        text college_roll_no
    }
    PERSON {
        uuid person_id PK
        text legal_name
    }
    TERM {
        uuid term_id PK
        text term_type
    }
    POLICY_BUNDLE_VERSION {
        uuid policy_bundle_version_id PK
        integer version_no
        text status
    }
    DOCUMENT_VERSION {
        uuid document_version_id PK
        text sha256
    }

    COURSE_VERSION ||--o{ ASSESSMENT_SCHEME : assessed_by
    TERM |o--o{ ASSESSMENT_SCHEME : effective_from
    TERM |o--o{ ASSESSMENT_SCHEME : effective_to
    ASSESSMENT_SCHEME ||--o{ ASSESSMENT_COMPONENT : contains
    ASSESSMENT_COMPONENT ||--o{ ASSESSMENT_COMPONENT : sub_component_of
    ASSESSMENT_COMPONENT ||--o{ ASSESSMENT_SCHEDULE : scheduled_as
    COURSE_OFFERING ||--o{ ASSESSMENT_SCHEDULE : hosts
    STUDENT ||--o{ MARK_ENTRY : receives
    ASSESSMENT_COMPONENT ||--o{ MARK_ENTRY : captured_in
    COURSE_OFFERING ||--o{ MARK_ENTRY : scopes
    MARK_ENTRY ||--o{ MARK_ENTRY_VERSION : versioned_as
    PERSON ||--o{ MARK_ENTRY_VERSION : enters
    PERSON ||--o{ MARK_ENTRY_VERSION : verifies
    MARK_ENTRY ||--o{ MARK_CORRECTION : corrected_by
    MARK_ENTRY_VERSION ||--o{ MARK_CORRECTION : from_version
    MARK_ENTRY_VERSION ||--o{ MARK_CORRECTION : to_version
    PERSON ||--o{ MARK_CORRECTION : requests
    PERSON ||--o{ MARK_CORRECTION : approves
    DOCUMENT_VERSION |o--o{ MARK_CORRECTION : evidences
    PERSON ||--o{ CONFLICT_DECLARATION : declares
    COURSE_OFFERING ||--o{ CONFLICT_DECLARATION : relates_to
    STUDENT |o--o{ CONFLICT_DECLARATION : is_ward
    PERSON |o--o{ CONFLICT_DECLARATION : reassigned_to
    DOCUMENT_VERSION |o--o{ CONFLICT_DECLARATION : evidences
    POLICY_BUNDLE_VERSION |o--o{ ASSESSMENT_SCHEME : governs
```

**Mark lifecycle:**

| State | Meaning | Who may act |
|---|---|---|
| `draft` | Faculty is entering; not visible to the student | Assigned faculty |
| `submitted` | Faculty has submitted for verification | Assigned faculty |
| `verified` | HOD/COE has checked | HOD/COE |
| `locked` | Used by result processing; immutable | COE |

A correction does not edit a locked version. It creates a new `mark_entry_version` and a `mark_correction` that references the old and new versions. The `mark_entry.current_version_no` points to the latest. The result processor records which version it used in `exam.result_input`.

**Why a separate `mark_entry` and `mark_entry_version`:** the identity (student, component, offering) is stable; the value is versioned. This allows the student to see the current mark while an audit trail preserves every correction, the reason, the evidence, and the approver.

**Conflict of interest:** `assessment.conflict_declaration` is checked before a faculty member is allowed to enter marks or attendance. If a declaration exists and the action is not reassigned, the authorization service denies the write. This implements ASS-09 as an access rule, not just a policy statement.

**Make-up and reassessment:** a make-up assessment is a new `assessment.schedule` for the same component with a `schedule_type` (regular/makeup/reassessment). The resulting mark is a new `mark_entry_version`. The regulations do not cap reassessments (G-15), so the schema does not impose a cap; the policy version may.

---

## 3. Cross-domain links to results

```mermaid
flowchart LR
    A["attendance.record"] --> B["attendance.summary"]
    B --> C["attendance.eligibility_assessment"]
    C --> D["student.eligibility_determination<br/>(gate = ATTENDANCE)"]
    E["assessment.mark_entry_version"] --> F["exam.result_input"]
    F --> G["exam.result_revision"]
    B --> H["assessment.component<br/>(attendance-linked mark)"]
    H --> E
```

**Rule:** attendance never flows directly into a result grade. It flows into an assessment component mark (CIA/PCIA attendance marks) and, separately, into an eligibility determination. The result processor uses the component mark and records the eligibility gate outcome; it does not recompute attendance.

---

## 4. Versioning summary

| Entity | Versioned? | History mechanism | Immutable after |
|---|---|---|---|
| `attendance.session` | No | Correction of status is audited | Session is held |
| `attendance.record` | No, current value | `attendance.correction` old/new | Never deleted |
| `attendance.summary` | Yes, by `as_of` | New row per calculation | No — recomputable |
| `attendance.eligibility_assessment` | Yes, by `computed_at` | New row per run/variant | No — recomputable |
| `attendance.condonation_case` | Case state | Decision + order document | Decision recorded |
| `assessment.scheme` | Yes, by effective term | New scheme row | Marks exist |
| `assessment.component` | No, within scheme | New scheme version | Marks exist |
| `assessment.mark_entry` | Current pointer | `mark_entry_version` | Never deleted |
| `assessment.mark_entry_version` | Yes | Immutable rows | Created |
| `assessment.mark_correction` | Event | References old/new | Created |

---

## 5. RLS implications

| Table | Policy intent |
|---|---|
| `attendance.record` | Student sees own; faculty sees own offerings; HOD sees department; Registrar/COE see institution; Guardian sees linked student if consent allows. The registration column tightens row scope to the enrolled offering. |
| `attendance.correction` | Faculty sees own requests; HOD approves within department; Auditor reads. |
| `attendance.condonation_case` | Student sees own case status; HOD sees department; Academic Council members see cases for decision; Auditor reads. |
| `assessment.mark_entry` / `_version` | Student sees own **published** marks only; faculty sees own offerings; HOD sees department; COE sees institution. |
| `assessment.conflict_declaration` | HOD, COE, Auditor; the declaring faculty sees own; the student's identity is restricted. |

**Sensitive-data rule:** condonation evidence and conflict declarations may contain family or medical information. They are Restricted and never enter the document retrieval corpus.

---

## 6. Open decisions that affect this ERD

| Decision | Effect if resolved |
|---|---|
| G-01 attendance variant | One variant becomes `Current`; the other remains `Historical`; eligibility enforcement can be enabled. |
| G-13 capture method | May add a device/source reference; the record model does not change. |
| G-14 duty leave | `attendance.duty_leave` activates; the calculation includes or excludes it. |
| G-15 reassessment cap | A policy parameter; no schema change. |
| G-12 result approval | Does not change marks; changes whether `locked` marks may feed an automated result. |
| OD-14 attendance registration invariant | Composite FKs from `attendance.record` to `course_registration` and `attendance.session` are mandatory in every implementation wave. |
