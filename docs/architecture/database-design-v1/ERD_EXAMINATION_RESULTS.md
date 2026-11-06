# ERD — Examination and Results

**Domain:** Examination and Results (`exam`), with inputs from `assessment`, `attendance`, `student`, and `finance`.
**Trace:** Research §8.6–8.8, §9.5–9.7, §12 M10–M14; S1 §§20–24, S8, S16 §3.4; G-12, G-16, G-17.
**Purpose:** separate the **initial read-only result view** from the **future examination operation**, and separate the **per-course result** from the **per-term grade card** and the **institutional recommendation** from the **MAKAUT degree award**.

---

## 1. Initial Release — imported, published results (read-only)

```mermaid
erDiagram
    RESULT_IMPORT {
        uuid result_import_id PK
        uuid term_id FK
        uuid programme_id FK
        uuid imported_by FK
        text file_name
        text sha256
        integer row_count
        integer error_count
        text status
    }
    RESULT_SET {
        uuid result_set_id PK
        uuid term_id FK
        uuid programme_id FK
        uuid batch_id FK
        uuid import_id FK
        text exam_label
        text result_type
        text status
        uuid approved_by FK
        timestamptz approved_at
        timestamptz published_at
        text external_publication_ref
        uuid policy_bundle_version_id FK
    }
    RESULT_RECORD {
        uuid result_record_id PK
        uuid student_id FK
        uuid course_version_id FK
        uuid course_offering_id FK
        uuid result_set_id FK
        integer attempt_no
        boolean is_backlog
        integer year_of_study
        integer current_revision_no
        text status
    }
    RESULT_REVISION {
        uuid result_revision_id PK
        uuid result_record_id FK
        integer revision_no
        numeric cia_total
        numeric pcia_total
        numeric ese_total
        numeric pese_total
        numeric total_marks
        text grade
        numeric grade_point
        text result_status
        timestamptz computed_at
        uuid computed_by FK
        timestamptz published_at
        uuid policy_bundle_version_id FK
        text change_reason
    }
    RESULT_INPUT {
        uuid result_input_id PK
        uuid result_revision_id FK
        uuid mark_entry_version_id FK
        text component_code
        numeric marks_used
        numeric max_marks_snapshot
    }
    GRADE_CARD {
        uuid grade_card_id PK
        uuid student_id FK
        uuid term_id FK
        uuid result_set_id FK
        integer version_no
        numeric sgpa
        numeric ygpa
        numeric cgpa
        integer credits_registered
        integer credits_earned
        text status
        timestamptz published_at
        boolean is_current
        uuid document_version_id FK
    }
    GRADE_CARD_RESULT {
        uuid grade_card_result_id PK
        uuid grade_card_id FK
        uuid result_record_id FK
        uuid result_revision_id FK
    }
    STUDENT {
        uuid student_id PK
        text college_roll_no
    }
    TERM {
        uuid term_id PK
        text term_type
    }
    PROGRAMME {
        uuid programme_id PK
        text programme_code
    }
    BATCH {
        uuid batch_id PK
        integer admission_year
    }
    COURSE_VERSION {
        uuid course_version_id PK
        uuid course_id FK
    }
    COURSE_OFFERING {
        uuid course_offering_id PK
        uuid course_version_id FK
        uuid term_id FK
    }
    MARK_ENTRY_VERSION {
        uuid mark_entry_version_id PK
        uuid mark_entry_id FK
        numeric marks_obtained
    }
    POLICY_BUNDLE_VERSION {
        uuid policy_bundle_version_id PK
        integer version_no
    }
    DOCUMENT_VERSION {
        uuid document_version_id PK
        text sha256
        text status
    }

    TERM ||--o{ RESULT_IMPORT : imported_for
    PROGRAMME ||--o{ RESULT_IMPORT : imported_for
    RESULT_IMPORT ||--o{ RESULT_SET : produces
    TERM ||--o{ RESULT_SET : scopes
    PROGRAMME ||--o{ RESULT_SET : scopes
    BATCH |o--o{ RESULT_SET : scopes
    RESULT_SET ||--o{ RESULT_RECORD : contains
    STUDENT ||--o{ RESULT_RECORD : receives
    COURSE_VERSION ||--o{ RESULT_RECORD : assessed_as
    COURSE_OFFERING |o--o{ RESULT_RECORD : delivered_as
    RESULT_RECORD ||--o{ RESULT_REVISION : versioned_as
    RESULT_REVISION ||--o{ RESULT_INPUT : derived_from
    MARK_ENTRY_VERSION ||--o{ RESULT_INPUT : used_by
    POLICY_BUNDLE_VERSION |o--o{ RESULT_REVISION : governs
    STUDENT ||--o{ GRADE_CARD : receives
    TERM ||--o{ GRADE_CARD : scopes
    RESULT_SET |o--o{ GRADE_CARD : supports
    GRADE_CARD ||--o{ GRADE_CARD_RESULT : contains
    RESULT_RECORD ||--o{ GRADE_CARD_RESULT : included_in
    RESULT_REVISION ||--o{ GRADE_CARD_RESULT : included_as
    DOCUMENT_VERSION |o--o{ GRADE_CARD : rendered_as
```

**Publication gates for the initial read-only view:**

| Gate | Meaning | Enforced by |
|---|---|---|
| Import provenance | The result file has a SHA-256, source label, row count, and error count. | `result_import` |
| Set status | Only `published` result sets are visible to students. | `result_set.status` |
| External reference | If BCREC did not compute the result, the external publication reference is recorded. | `result_set.external_publication_ref` |
| Revision | The student sees the latest published revision, not an internal draft. | `result_revision` |
| Grade card composition | A grade card references explicit result revisions, so a later correction cannot silently change an old card. | `grade_card_result` |

**Why `result_input` exists:** even when results are imported, the design must be able to answer "which marks produced this result?" If the import does not provide mark-level data, `result_input` is empty for that revision and the revision carries the external source reference. When BCREC begins computing results (Phase 2), the same table records the exact `mark_entry_version` used.

**Result status:** `X` = not eligible for promotion/degree; `XP` = eligible for promotion with backlogs; `P` = passed and promoted (S1 §22.5.1). The database does not map these to integers. The grade is separate: O/E/A/B/C/D/F/I with the policy-defined grade points.

**Why grade cards are versioned:** a result correction or PPR can change a grade. The old grade card must remain retrievable. `grade_card.version_no` and `is_current` preserve the history; the old card is marked `superseded`, never deleted.

---

## 2. Future — examination operations and result computation

```mermaid
erDiagram
    EXAM_EVENT {
        uuid exam_event_id PK
        uuid term_id FK
        text exam_type
        date window_start
        date window_end
        text status
        uuid notification_document_version_id FK
    }
    EXAM_REGISTRATION {
        uuid exam_registration_id PK
        uuid student_id FK
        uuid exam_event_id FK
        uuid semester_registration_id FK
        text eligibility_status
        text fee_status
        text admit_card_status
        timestamptz submitted_at
        uuid verified_by FK
    }
    EXAM_REGISTRATION_COURSE {
        uuid exam_registration_course_id PK
        uuid exam_registration_id FK
        uuid course_version_id FK
        uuid course_offering_id FK
        integer attempt_no
        boolean is_backlog
    }
    ANSWER_SCRIPT {
        uuid answer_script_id PK
        uuid exam_registration_course_id FK
        text script_barcode
        uuid evaluator_person_id FK
        text custody_location
        text status
    }
    BACKLOG_RECORD {
        uuid backlog_record_id PK
        uuid student_id FK
        uuid course_version_id FK
        uuid first_fail_term_id FK
        integer attempt_count
        text status
        uuid cleared_term_id FK
        uuid cleared_result_record_id FK
    }
    SUPPLEMENTARY_REGISTRATION {
        uuid supplementary_registration_id PK
        uuid backlog_record_id FK
        uuid exam_event_id FK
        uuid fee_demand_id FK
        text exam_type
        text fee_status
        text eligibility_status
        text status
    }
    PPR_CASE {
        uuid ppr_case_id PK
        uuid student_id FK
        uuid result_record_id FK
        uuid reviewer_person_id FK
        uuid fee_payment_id FK
        timestamptz applied_at
        text scope
        text outcome
        timestamptz decided_at
        text status
    }
    CORRECTION_CASE {
        uuid correction_case_id PK
        uuid result_record_id FK
        uuid affidavit_document_version_id FK
        uuid verified_by FK
        timestamptz received_at
        timestamptz verified_at
        text decision
        text status
    }
    STUDENT {
        uuid student_id PK
    }
    TERM {
        uuid term_id PK
    }
    COURSE_VERSION {
        uuid course_version_id PK
    }
    COURSE_OFFERING {
        uuid course_offering_id PK
    }
    SEMESTER_REGISTRATION {
        uuid semester_registration_id PK
        uuid student_id FK
        uuid term_id FK
    }
    RESULT_RECORD {
        uuid result_record_id PK
        uuid student_id FK
        uuid course_version_id FK
    }
    PERSON {
        uuid person_id PK
    }
    FEE_DEMAND {
        uuid fee_demand_id PK
        text status
    }
    FEE_PAYMENT {
        uuid payment_id PK
        numeric amount
        text status
    }
    DOCUMENT_VERSION {
        uuid document_version_id PK
        text sha256
    }

    TERM ||--o{ EXAM_EVENT : hosts
    STUDENT ||--o{ EXAM_REGISTRATION : registers
    EXAM_EVENT ||--o{ EXAM_REGISTRATION : receives
    SEMESTER_REGISTRATION |o--o{ EXAM_REGISTRATION : precedes
    EXAM_REGISTRATION ||--o{ EXAM_REGISTRATION_COURSE : includes
    COURSE_VERSION ||--o{ EXAM_REGISTRATION_COURSE : examines
    COURSE_OFFERING |o--o{ EXAM_REGISTRATION_COURSE : delivered_as
    EXAM_REGISTRATION_COURSE ||--o| ANSWER_SCRIPT : has
    PERSON |o--o{ ANSWER_SCRIPT : evaluates
    STUDENT ||--o{ BACKLOG_RECORD : carries
    COURSE_VERSION ||--o{ BACKLOG_RECORD : backlog_of
    TERM |o--o{ BACKLOG_RECORD : first_fail
    TERM |o--o{ BACKLOG_RECORD : cleared
    RESULT_RECORD |o--o{ BACKLOG_RECORD : cleared_by
    BACKLOG_RECORD ||--o{ SUPPLEMENTARY_REGISTRATION : retaken
    EXAM_EVENT ||--o{ SUPPLEMENTARY_REGISTRATION : schedules
    FEE_DEMAND |o--o{ SUPPLEMENTARY_REGISTRATION : gated_by
    STUDENT ||--o{ PPR_CASE : applies
    RESULT_RECORD ||--o{ PPR_CASE : challenges
    PERSON |o--o{ PPR_CASE : reviews
    FEE_PAYMENT |o--o{ PPR_CASE : paid_by
    RESULT_RECORD ||--o{ CORRECTION_CASE : corrected_by
    DOCUMENT_VERSION |o--o{ CORRECTION_CASE : affidavit
    PERSON |o--o{ CORRECTION_CASE : verifies
    DOCUMENT_VERSION |o--o{ EXAM_EVENT : notified_by
```

**Two different correction routes:** `ppr_case` is student-initiated, theory-only, fee-bearing, and final. `correction_case` is examiner-initiated, affidavit-based, and deadline-bound. They are deliberately not merged. They have different permissions, evidence, and audit trails (research §8.7).

**Examination eligibility:** `exam_registration.eligibility_status` is a summary. The underlying determinations are in `student.eligibility_determination` (attendance, fee, discipline, academic prerequisites). This keeps the fee gate configurable (G-08) and the attendance variant auditable (G-01).

---

## 3. Progression, degree recommendation, and award

```mermaid
erDiagram
    PROMOTION_DECISION {
        uuid promotion_decision_id PK
        uuid student_id FK
        uuid from_term_id FK
        uuid to_term_id FK
        integer backlogs_count
        numeric cgpa
        text decision
        uuid policy_bundle_version_id FK
        uuid approved_by FK
        timestamptz decided_at
    }
    DEGREE_ELIGIBILITY {
        uuid degree_eligibility_id PK
        uuid student_id FK
        integer credits_earned
        numeric cgpa
        integer active_backlogs
        integer mar_points
        text mandatory_courses_status
        text dues_status
        text decision
        uuid policy_bundle_version_id FK
        timestamptz evaluated_at
    }
    DEGREE_RECOMMENDATION {
        uuid degree_recommendation_id PK
        uuid degree_eligibility_id FK
        uuid approved_by FK
        text recommendation_no
        timestamptz recommended_at
        timestamptz submitted_at
        text makaut_reference
        text status
    }
    CERTIFICATE_ISSUE {
        uuid certificate_issue_id PK
        uuid student_id FK
        uuid issued_by FK
        text certificate_type
        text serial_no
        date issued_on
        uuid document_version_id FK
        text status
    }
    MAR_RECORD {
        uuid mar_record_id PK
        uuid student_id FK
        uuid academic_year_id FK
        text activity
        text category
        numeric points
        uuid verified_by FK
        text status
    }
    MOOC_RECORD {
        uuid mooc_record_id PK
        uuid student_id FK
        text platform
        text course_title
        numeric credits
        text usage
        uuid verified_by FK
        text status
    }
    ACHIEVEMENT {
        uuid achievement_id PK
        uuid student_id FK
        text achievement_type
        text title
        date achieved_on
        uuid verified_by FK
        text status
    }
    STUDENT {
        uuid student_id PK
    }
    TERM {
        uuid term_id PK
    }
    ACADEMIC_YEAR {
        uuid academic_year_id PK
        text label
    }
    RESULT_RECORD {
        uuid result_record_id PK
    }
    PERSON {
        uuid person_id PK
    }
    POLICY_BUNDLE_VERSION {
        uuid policy_bundle_version_id PK
    }
    DOCUMENT_VERSION {
        uuid document_version_id PK
    }

    STUDENT ||--o{ PROMOTION_DECISION : receives
    TERM |o--o{ PROMOTION_DECISION : from
    TERM |o--o{ PROMOTION_DECISION : to
    POLICY_BUNDLE_VERSION |o--o{ PROMOTION_DECISION : governs
    PERSON |o--o{ PROMOTION_DECISION : approves
    STUDENT ||--o| DEGREE_ELIGIBILITY : qualifies
    POLICY_BUNDLE_VERSION |o--o{ DEGREE_ELIGIBILITY : governs
    DEGREE_ELIGIBILITY ||--o| DEGREE_RECOMMENDATION : recommends
    PERSON |o--o{ DEGREE_RECOMMENDATION : approves
    STUDENT ||--o{ CERTIFICATE_ISSUE : receives
    PERSON |o--o{ CERTIFICATE_ISSUE : issues
    DOCUMENT_VERSION |o--o{ CERTIFICATE_ISSUE : rendered_as
    STUDENT ||--o{ MAR_RECORD : earns
    ACADEMIC_YEAR ||--o{ MAR_RECORD : scopes
    PERSON |o--o{ MAR_RECORD : verifies
    STUDENT ||--o{ MOOC_RECORD : completes
    PERSON |o--o{ MOOC_RECORD : verifies
    STUDENT ||--o{ ACHIEVEMENT : records
    PERSON |o--o{ ACHIEVEMENT : verifies
```

**Degree authority:** `degree_recommendation` records BCREC's recommendation. It has no column that says BCREC awarded the degree. The award is MAKAUT's act (S16 §3.4). If a MAKAUT reference is later recorded, it is an external reference, not a local degree record.

**Progression and year lag:** `promotion_decision.decision` distinguishes promoted, withheld, and year lag. The policy bundle carries the `2n + 1` limit and the practical-failure rule. The decision references the result records through the policy evaluation; it does not duplicate grades.

**MAR and Honours:** `mar_record` and `mooc_record` are Phase 2 because the entity inventory and the module table disagree on release (C-07). The composite rules (100/75 points, 25/year, 20/16 MOOC credits) are policy parameters, not columns with defaults.

---

## 4. Eligibility and fee linkage (kept configurable)

```mermaid
flowchart LR
    A["student.semester_registration"] --> B["student.eligibility_determination"]
    C["attendance.eligibility_assessment"] --> B
    D["finance.fee_demand<br/>(Phase 2)"] --> B
    E["services.disciplinary_case<br/>(Phase 2)"] --> B
    B --> F{"Gate configuration<br/>(policy)"}
    F -->|hard gate| G["exam_registration denied"]
    F -->|advisory| H["exam_registration allowed<br/>with flag"]
    F -->|not used| I["exam_registration allowed"]
```

**Why this is a flow, not an FK:** the institution has not decided whether unpaid dues bar examination (G-08). The `eligibility_determination` table records the fact and the policy version; the gate behaviour is a configuration decision. The schema does not contain a `fee_cleared boolean NOT NULL` that would silently invent a hard gate.

---

## 5. Publication and approval controls

| Control | Implementation |
|---|---|
| Marks entry vs publication | Different permissions; `result_revision.computed_by` and `result_set.approved_by` must be different people where the policy requires. |
| Result set approval | `result_set.approved_by` + `approved_at`; null until approved. |
| External publication | `external_publication_ref` allows read-only import without pretending BCREC approved it. |
| Correction after publication | New `result_revision`; old revision retained; `grade_card` superseded. |
| PPR reviewer independence | `ppr_case.reviewer_person_id` must differ from the original evaluator recorded on the answer script/result input. |
| Audit | `ops.audit_event` records the actor, role assignment, before/after, and reason for every publication, correction, and recommendation. |

**Blocked activation:** automated result publication waits for G-12 (signatory) and M12. The Initial Release can display an imported published result because the publication happened outside the new system and carries an external reference.

---

## 6. RLS implications

| Table | Policy intent |
|---|---|
| `exam.result_record` | Student sees own published results; faculty sees own course results after publication; HOD sees department; COE sees institution; Registrar reads; Auditor reads. |
| `exam.result_revision` | Same as result record; draft revisions are COE-only. |
| `exam.grade_card` | Student sees own current card and historical cards; Registrar/COE see institution; Auditor reads. |
| `exam.result_import` | COE and Auditor only. |
| Future `exam.ppr_case` | Student sees own; reviewer sees assigned; COE sees all; others denied. |
| Future `exam.correction_case` | COE, examiner, Auditor; restricted. |

---

## 7. Open decisions that affect this ERD

| Decision | Effect |
|---|---|
| G-12 result approval signatory | Enables `result_set` approval workflow and automated publication. |
| G-08 fee gate | Determines whether `eligibility_determination` with `gate_code = FEE_CLEARANCE` can block exam registration. |
| G-06 NBA validity | Does not affect results; affects accreditation reporting. |
| G-16 theory examiner appointment | Adds examiner assignment to `answer_script`/`exam_registration_course`. |
| G-17 PPR refund | Adds a refund link on the payment; does not change the case model. |
| G-04 batch boundary | Determines which policy bundle applies to a batch's results. |
