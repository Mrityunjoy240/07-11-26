# Entity Catalog — BCREC Campus ERP + CIP

**Purpose:** the authoritative logical inventory for the twelve domains. It states each entity's purpose, primary key, important attributes, foreign keys, owner, data classification, authoritative source, and release phase.

**Companion documents:** [`DOMAIN_MODEL.md`](DOMAIN_MODEL.md) for boundaries; [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md) for columns and constraints of Initial Release entities; the seven ERDs for cardinality.

**This is a logical catalogue, not DDL.** No table is created by this document.

---

## 1. Conventions

| Convention | Rule |
|---|---|
| Schema | One schema per domain; `policy` is cross-cutting. |
| Table name | Singular `snake_case` (e.g. `student.student`, `exam.result_record`). |
| Primary key | `uuid` named `<entity>_id`, default generated. UUIDv7 is preferred where the PostgreSQL version supports it; otherwise UUIDv4. |
| Business key | Separate unique constraint (e.g. `college_roll_no`), never the primary key. |
| Time | `timestamptz` in UTC; presentation in IST. `date` for calendar dates with no time. |
| Money | `numeric(12,2)` INR. Never floating point. |
| Percentages | `numeric(5,2)` with a `0–100` check. |
| Marks | `numeric(6,2)` with `>= 0`. |
| Status | `text` + `CHECK` for small stable sets; a reference table only where the set is governed. |
| History | Append-only versions for rules, marks, results, attendance corrections, documents, role assignments. |
| Deletion | Academic records are never hard-deleted; status/supersession is used. |
| External IDs | Never on domain tables; only in `integration.external_id_mapping`. |
| Classification | `P` Public, `I` Internal, `C` Confidential, `R` Restricted, `G` Regulated personal data. |
| Phase | `F` Foundation, `IE` Initial ERP, `IC` Initial CIP, `2` Future, `B` Blocked pending institutional decision. |

**Release rule:** `F`, `IE`, and `IC` entities form the Initial Release and receive a full data dictionary. Phase `2` and `B` entities are catalogued so that later implementation does not guess their relationships.

---

## 2. Domain 1 — Identity and Access (`iam`)

**Trace:** Research §7, §11.2–11.3; S6–S9; F-07, F-08. **Owner:** Registrar / ERP Administrator.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| IAM-01 | `iam.person` | One human being across all roles. | `person_id` | legal_name, preferred_name, date_of_birth, gender, blood_group, photo_uri, deceased_flag, created_at | — | Registrar / HR | C | BCREC Registrar | F |
| IAM-02 | `iam.person_contact` | Multiple typed contact points with verification. | `person_contact_id` | contact_type (email/phone/address/emergency), value, is_primary, is_verified, verified_at, valid_from, valid_to | person_id → iam.person | Registrar | C | Person / Registrar | F |
| IAM-03 | `iam.identity_account` | Login identity linked to a person and external IdP subject. | `account_id` | idp_code, subject, username, email, mfa_enabled, status, last_login_at, disabled_at | person_id → iam.person | ERP Administrator | C | BCREC IdP | F |
| IAM-04 | `iam.role` | Role definition, not a person or designation. | `role_id` | role_code, name, category (governance/executive/academic/student/system), description, default_scope_type, is_system_role | — | ERP Administrator | I | BCREC (design) | F |
| IAM-05 | `iam.permission` | Atomic action that can be granted. | `permission_id` | permission_code, resource, action, description, risk_level | — | ERP Administrator | I | BCREC (design) | F |
| IAM-06 | `iam.role_permission` | Role-to-permission grant. | `role_permission_id` | granted_at, granted_by | role_id → iam.role; permission_id → iam.permission | ERP Administrator | I | BCREC (design) | F |
| IAM-07 | `iam.role_assignment` | Time-bound authority held by a person in one scope. | `role_assignment_id` | scope_type, valid_from, valid_to, status, appointing_authority, source_document_version_id, delegated_from_assignment_id, source_membership_id, created_by, approved_by | person_id → iam.person; role_id → iam.role; institution_id → core.institution; org_unit_id → core.org_unit; programme_id → academic.programme; batch_id → academic.batch; term_id → core.term; course_offering_id → academic.course_offering; governance_body_id → core.governance_body; source_document_version_id → doc.document_version | Registrar / Principal | C | BCREC | F |
| IAM-08 | `iam.delegation` | Temporary transfer of authority with limits. | `delegation_id` | reason, valid_from, valid_to, limits_json, status, approved_by | from_assignment_id → iam.role_assignment; to_assignment_id → iam.role_assignment | Principal | C | BCREC | F |

**Invariants:** exactly one scope FK is populated per assignment; `valid_to > valid_from`; a person may hold many concurrent assignments; a designation string never grants access; closing an assignment sets `valid_to` and `status`, never deletes it.

---

## 3. Domain 2 — Institution and Governance (`core`)

**Trace:** Research §3, §6, §9.13; S3–S8, S14–S16. **Owner:** Principal / Registrar.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| GOV-01 | `core.institution` | Root legal entity. | `institution_id` | legal_name, short_name, college_code (`120`), aicte_id, address, affiliation_university, autonomy_status, autonomy_from, autonomy_to, timezone, currency | parent_institution_id → core.institution (self) | Principal / Registrar | P | BCREC | F |
| GOV-02 | `core.society` | Sponsoring body. | `society_id` | name, registration_no, registered_on, address, rules_document_version_id | institution_id → core.institution; rules_document_version_id → doc.document_version | Registrar | I | BCREC Society | F |
| GOV-03 | `core.org_unit` | Departments, offices, cells, and support units as a tree. | `org_unit_id` | code, name, unit_type (department/office/cell/committee_support), parent_id, path, head_person_id, cost_centre, is_active | parent_org_unit_id → core.org_unit (self); institution_id → core.institution; head_person_id → iam.person | Principal / HR | I | BCREC | F |
| GOV-04 | `core.governance_body` | Statutory body or committee, unified by type. | `governance_body_id` | body_code, name, body_type (BOG/AcademicCouncil/FinanceCommittee/BoardOfStudies/ExaminationCommittee/IQAC/Disciplinary/AntiRagging/ICC/Grievance/MAR/MOOCs/Library/Purchase/R&D/TP/other), is_statutory, scope_org_unit_id, term_start, term_end, constitution_order_version_id, chair_person_id, secretary_person_id, status | institution_id → core.institution; scope_org_unit_id → core.org_unit; constitution_order_version_id → doc.document_version; chair_person_id → iam.person; secretary_person_id → iam.person | Principal / Registrar | I | BCREC / UGC | F |
| GOV-05 | `core.governance_membership` | A person's seat on a body with dates and capacity. | `governance_membership_id` | role_in_body (chair/member/member_secretary/invitee/nominee), valid_from, valid_to, order_reference, status, source_role_assignment_id | governance_body_id → core.governance_body; person_id → iam.person; source_role_assignment_id → iam.role_assignment; order_document_version_id → doc.document_version | Registrar | C | BCREC | F |
| GOV-06 | `core.statutory_approval` | AICTE approval, MAKAUT affiliation, UGC autonomy, NBA/NAAC instrument. | `statutory_approval_id` | approval_type, authority, reference_no, approved_on, valid_from, valid_to, scope_type, conditions_text, status, document_version_id | institution_id → core.institution; programme_id → academic.programme (nullable); document_version_id → doc.document_version | Registrar | I | AICTE / MAKAUT / UGC / NBA / NAAC | F |
| GOV-07 | `core.affiliation_record` | Course-wise annual affiliation and approved intake. | `affiliation_record_id` | academic_year_id, programme_id, intake_approved, intake_admitted, affiliation_status, conditions_text, order_reference | programme_id → academic.programme; academic_year_id → core.academic_year; statutory_approval_id → core.statutory_approval | Registrar | I | MAKAUT | F |
| GOV-08 | `core.academic_year` | Named academic session. | `academic_year_id` | label (2026-27), start_date, end_date, status | institution_id → core.institution | Registrar | P | BCREC | F |
| GOV-09 | `core.term` | Dated academic period (odd/even/summer/supplementary). | `term_id` | term_type, term_no, start_date, end_date, instruction_start, instruction_end, exam_start, exam_end, working_days_planned, working_days_actual, status | academic_year_id → core.academic_year | COE / Registrar | I | BCREC | F |
| GOV-10 | `core.academic_calendar` | Versioned calendar for a term. | `academic_calendar_id` | version_no, status (draft/provisional/approved/superseded), approved_by, approved_at, change_note | term_id → core.term; approved_by → iam.person | COE | I | BCREC | F |
| GOV-11 | `core.calendar_milestone` | Dated activity inside a calendar (CIA, PCIA, form fill-up, exams). | `calendar_milestone_id` | milestone_code, label, planned_start, planned_end, actual_start, actual_end, applies_to_json, status | academic_calendar_id → core.academic_calendar | COE | I | BCREC | F |
| GOV-12 | `core.accreditation` | NBA/NAAC status and validity. | `accreditation_id` | body, scope_type, programme_id, grade, valid_from, valid_to, certificate_document_version_id, status | programme_id → academic.programme (nullable); certificate_document_version_id → doc.document_version | IQAC Coordinator | I | NBA / NAAC | 2 |
| GOV-13 | `core.regulatory_return` | Returns and reports submitted to MAKAUT/AICTE. | `regulatory_return_id` | return_type, period, due_date, submitted_date, status, acknowledgement_ref, document_version_id | institution_id → core.institution; document_version_id → doc.document_version | Registrar | I | MAKAUT / AICTE | 2 |

**Invariants:** one root institution; every org unit has a parent except the root; a governance body has a term and a constitution order; membership dates fall inside or are explicitly excepted from the body term; an approval has a validity window and a source document.

---

## 4. Domain 3 — Academic Structure (`academic`)

**Trace:** Research §3.2, §8.2–8.3, §10.4; S1, S9, S14, S15. **Owner:** Registrar / HOD / BoS.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| ACD-01 | `academic.department` | Academic department with an accountable HOD (HOD authority is a role assignment). | `department_id` | code, name, short_name, hod_person_id (derived cache), established_on, is_active | org_unit_id → core.org_unit; hod_person_id → iam.person (cache; authority is `iam.role_assignment`) | Principal | I | BCREC | F |
| ACD-02 | `academic.programme` | Degree programme and level. | `programme_id` | programme_code (MAKAUT), bcrec_code, name, level (UG/PG), degree_awarded_by, duration_years, department_id, aicte_programme_code, status | department_id → academic.department; institution_id → core.institution | Registrar / Dean | P | BCREC / MAKAUT | F |
| ACD-03 | `academic.programme_version` | Regulation/curriculum binding effective for a batch range. | `programme_version_id` | version_no, regulation_name, regulation_reference, effective_from_admission_year, effective_to_admission_year, total_credits, status, approved_by, approved_at, source_document_version_id | programme_id → academic.programme; approved_by → iam.person; source_document_version_id → doc.document_version | Academic Council / Registrar | I | BCREC | F |
| ACD-04 | `academic.batch` | Admission cohort and its regulation binding. | `batch_id` | admission_year, entry_mode (regular/lateral), autonomy_status (autonomous/makaut/transitional), programme_version_id, current_term_id, expected_graduation_year, status | programme_id → academic.programme; programme_version_id → academic.programme_version; current_term_id → core.term | Registrar | I | BCREC | IE |
| ACD-05 | `academic.section` | Class group within a batch. | `section_id` | section_code, name, strength, status | batch_id → academic.batch | HOD | I | BCREC | IE |
| ACD-06 | `academic.curriculum` | Approved set of courses for a programme version and term. | `curriculum_id` | term_no, version_no, total_credits, status, approved_by, approved_at, effective_from_term_id | programme_version_id → academic.programme_version; approved_by → iam.person; effective_from_term_id → core.term | HOD / BoS | I | BCREC Academic Council | F |
| ACD-07 | `academic.curriculum_course` | Ordered membership of a course version in a curriculum. | `curriculum_course_id` | term_no, sequence_no, category (core/elective/lab/sessional/project/MOOC/mandatory_non_credit), credits, is_mandatory, contact_hours | curriculum_id → academic.curriculum; course_version_id → academic.course_version | HOD / BoS | I | BCREC | F |
| ACD-08 | `academic.course` | Stable course catalogue identity (subject/paper). | `course_id` | course_code, title, course_type (theory/practical/sessional/project/MOOC/non_credit), department_id, is_active | department_id → academic.department | HOD / BoS | I | BCREC | F |
| ACD-09 | `academic.course_version` | Immutable content and assessment version of a course. | `course_version_id` | version_no, title, syllabus_text, credits, contact_hours, course_outcomes_json, effective_from_admission_year, effective_to_admission_year, status, approved_by, source_document_version_id | course_id → academic.course; approved_by → iam.person; source_document_version_id → doc.document_version | HOD / BoS | I | BCREC | F |
| ACD-10 | `academic.course_offering` | Delivery of a course version to a batch/section in a term; coordinator is an `offering_faculty` role. | `course_offering_id` | offering_code, term_id, batch_id, section_id, capacity, delivery_mode, status | course_version_id → academic.course_version; term_id → core.term; batch_id → academic.batch; section_id → academic.section | HOD | I | BCREC | IE |
| ACD-11 | `academic.offering_faculty` | Teaching allocation and assessment responsibility for an offering; the coordinator is one role here. | `offering_faculty_id` | role_in_offering (coordinator/instructor/lab_instructor/guest/moderator), is_assessor, valid_from, valid_to, allocated_hours | course_offering_id → academic.course_offering; person_id → iam.person | HOD | I | BCREC | IE |
| ACD-12 | `academic.timetable_slot` | Scheduled class/lab session pattern; venue is free text until Phase 2. | `timetable_slot_id` | day_of_week, start_time, end_time, slot_type (theory/practical/tutorial), venue_text, valid_from, valid_to, status | course_offering_id → academic.course_offering | HOD / Timetable Committee | I | BCREC | IE |
| ACD-13 | `academic.room` | Classroom/lab venue. | `room_id` | code, room_type, capacity, building, is_active | org_unit_id → core.org_unit | Campus Administrator | I | BCREC | 2 |
| ACD-14 | `academic.section_teacher_assignment` | Time-bound class/co-class teacher assignment with authority provenance. | `section_teacher_assignment_id` | role_in_section (class_teacher/co_class_teacher/substitute), valid_from, valid_to, status, assigned_at, assigned_by, authority_role_assignment_id, source_document_version_id, change_reason | section_id → academic.section; person_id → iam.person; authority_role_assignment_id → iam.role_assignment; source_document_version_id → doc.document_version | HOD | I | BCREC (HOD appointment) | IE |

**Invariants:** a batch has exactly one programme version; a programme version is effective for an admission-year range; a course version is immutable after first offering; a curriculum references course versions, not course identities; an offering belongs to one term and one batch; a section belongs to one batch; one active class teacher per section is held in `section_teacher_assignment`, not on `section`; a course coordinator is an `offering_faculty.role_in_offering = 'coordinator'` row and never a duplicate pointer on `course_offering`; the section-teacher assignment records the `role_assignment` that authorised the HOD's act.

---

## 5. Domain 4 — Student Lifecycle (`student`)

**Trace:** Research §8.1–8.2, §10.5; S1 §9, S20. **Owner:** Admission Cell / Registrar / COE.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| STU-01 | `student.admission_application` | Applicant pipeline and eligibility evidence. | `application_id` | application_no, admission_year, counselling_authority, allotment_reference, category (R/G), eligibility_status, application_status, submitted_at, verified_by, verified_at | person_id → iam.person; programme_id → academic.programme; batch_id → academic.batch (nullable until allotment) | Admission Cell | C/R/G | BCREC | IE |
| STU-02 | `student.admission_offer` | Offer, acceptance, fee reference, and admission confirmation. | `offer_id` | offer_no, offered_at, accepted_at, admission_confirmed_at, fee_receipt_reference, status, remarks | application_id → student.admission_application; confirmed_by → iam.person | Admission Cell | C | BCREC | IE |
| STU-03 | `student.student` | Academic identity of a learner. | `student_id` | college_roll_no, admission_year, batch_id, section_id (derived current-section cache), entry_mode, category (R/G), date_of_admission, expected_completion_year, current_status, photo_uri | person_id → iam.person; batch_id → academic.batch; section_id → academic.section; admission_application_id → student.admission_application | Registrar | C/R/G | BCREC | IE |
| STU-04 | `student.guardian` | Parent/guardian as a person. | `guardian_id` | occupation, education, annual_income_band (R), is_alumni | person_id → iam.person | Registrar | C/R | BCREC | IE |
| STU-05 | `student.student_guardian` | Many-to-many student–guardian relationship. | `student_guardian_id` | relation, is_primary, consent_status (R), consent_recorded_at, valid_from, valid_to | student_id → student.student; guardian_id → student.guardian | Registrar | C/R | BCREC | IE |
| STU-06 | `student.student_document` | Verified student document and provenance. | `student_document_id` | document_type, verification_status, verified_by, verified_at, expires_on, remarks | student_id → student.student; document_version_id → doc.document_version | Registrar | R/G | BCREC | IE |
| STU-07 | `student.university_registration` | MAKAUT registration number and status. | `university_registration_id` | registration_number, registration_year, status, uploaded_at, confirmed_at, proof_document_version_id | student_id → student.student; proof_document_version_id → doc.document_version | Registrar | C | MAKAUT | IE |
| STU-08 | `student.exam_roll_number` | 12-digit examination identity, versioned. | `exam_roll_number_id` | roll_number, college_code, programme_code, registration_year, course_duration_years, serial_no, issued_on, is_current, status | student_id → student.student; programme_id → academic.programme | COE | C | BCREC COE | IE |
| STU-09 | `student.semester_registration` | Student's registration for a term. | `semester_registration_id` | registration_no, submitted_at, approved_by, approved_at, status, remarks | student_id → student.student; term_id → core.term | Registrar | C | BCREC | IE |
| STU-10 | `student.course_registration` | Course-level enrolment in an offering, with a student integrity anchor. | `course_registration_id` | student_id (integrity anchor), registration_type (regular/backlog/audit/improvement), credits, status, registered_at, dropped_at, drop_reason | student_id → student.student; semester_registration_id → student.semester_registration; course_offering_id → academic.course_offering | Registrar / HOD | C | BCREC | IE |
| STU-11 | `student.status_history` | Auditable student status changes. | `status_history_id` | status (active/detained/suspended/graduated/withdrawn/year_lag), effective_from, effective_to, reason, order_document_version_id, recorded_by | student_id → student.student; order_document_version_id → doc.document_version; recorded_by → iam.person | Registrar | C/R | BCREC | IE |
| STU-12 | `student.eligibility_determination` | Configurable gate result (academic, attendance, fee, discipline). | `eligibility_determination_id` | gate_code, scope_type, scope_id, status (pass/fail/waived/unknown/not_applicable), policy_rule_version_id, source, evidence_json, determined_at, determined_by | student_id → student.student; term_id → core.term; policy_rule_version_id → policy.rule_version | Registrar / COE | C | BCREC | IE |
| STU-13 | `student.branch_change` | Programme change request and approval. | `branch_change_id` | from_programme_id, to_programme_id, from_batch_id, to_batch_id, reason, eligibility_status, approved_by, effective_term_id, status | student_id → student.student; from/to_programme_id → academic.programme; from/to_batch_id → academic.batch; effective_term_id → core.term | Registrar | C | BCREC | 2 |
| STU-14 | `student.student_migration` | Inter-college/university migration. | `migration_id` | direction, from_institution, to_institution, approval_reference, effective_term_id, document_version_id, status | student_id → student.student; effective_term_id → core.term; document_version_id → doc.document_version | Registrar | R | MAKAUT / BCREC | 2 |
| STU-15 | `student.section_assignment` | Historical student-to-section assignment with effective dates and authority provenance. | `section_assignment_id` | batch_id, effective_from, effective_to, assignment_reason (initial_allotment/transfer/section_merge/readmission/correction), status, approved_by, authority_role_assignment_id, source_document_version_id | student_id → student.student; section_id → academic.section; batch_id → academic.batch; authority_role_assignment_id → iam.role_assignment; source_document_version_id → doc.document_version | Registrar / HOD | C | BCREC | IE |

**Invariants:** one student profile per person per programme career; `college_roll_no` unique; `registration_number` unique when present; one current exam roll per student; course registration cannot exist without semester registration; `course_registration.student_id` is an integrity anchor that must match its semester registration; section transfers are historical in `section_assignment`, and `student.section_id` is a derived current-section cache updated in the same transaction; a status change writes history and updates the current status in one transaction; eligibility determinations are append-only and record the policy version.

---

## 6. Domain 5a — Attendance (`attendance`)

**Trace:** Research §8.4, §9.3; S1 §16, S2 p.55, S17; G-01, G-13, G-14. **Owner:** Faculty / HOD / Academic Council.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| ATT-01 | `attendance.session` | Unit of attendance capture. | `session_id` | session_date, start_time, end_time, session_type (theory/practical/tutorial), topic, delivery_mode, status (scheduled/held/cancelled), held_by_person_id | course_offering_id → academic.course_offering; timetable_slot_id → academic.timetable_slot (nullable); held_by_person_id → iam.person | Faculty | C | BCREC | IE |
| ATT-02 | `attendance.record` | One student's presence in one session, anchored to a course registration. | `attendance_record_id` | course_registration_id, course_offering_id, status (present/absent/late/excused), source (faculty_manual/import/biometric), marked_at, marked_by, remarks | session_id → attendance.session; student_id → student.student; course_registration_id → student.course_registration; course_offering_id → academic.course_offering | Faculty | C | BCREC | IE |
| ATT-03 | `attendance.correction` | Correction of a wrongly marked record. | `correction_id` | old_status, new_status, reason, requested_by, requested_at, approved_by, approved_at, status, evidence_document_version_id | attendance_record_id → attendance.record; evidence_document_version_id → doc.document_version; requested_by/approved_by → iam.person | Faculty / HOD | C/R | BCREC | IE |
| ATT-04 | `attendance.summary` | Computed attendance per student and offering. | `summary_id` | sessions_conducted, sessions_attended, attendance_pct, as_of, calculation_version, policy_rule_version_id | student_id → student.student; course_offering_id → academic.course_offering; policy_rule_version_id → policy.rule_version | System / HOD | C | BCREC | IE |
| ATT-05 | `attendance.eligibility_assessment` | Policy decision for a student and term under one rule variant. | `eligibility_assessment_id` | rule_variant (aggregate/split), aggregate_pct, theory_pct, practical_pct, outcome (eligible/shortage/not_condonable/pending), computed_at, inputs_json, policy_bundle_version_id | student_id → student.student; term_id → core.term; policy_bundle_version_id → policy.policy_bundle_version | Registrar / COE | C | BCREC | IE |
| ATT-06 | `attendance.condonation_case` | Academic Council decision on a shortfall. | `condonation_case_id` | shortfall_pct, grounds, evidence_summary, hod_recommendation, ac_decision, decision_date, order_document_version_id, status | student_id → student.student; term_id → core.term; eligibility_assessment_id → attendance.eligibility_assessment; order_document_version_id → doc.document_version | Registrar / Academic Council | R | BCREC Academic Council | IE |
| ATT-07 | `attendance.duty_leave` | Duty/special leave and its attendance treatment. | `duty_leave_id` | leave_type, from_date, to_date, reason, approval_status, counts_as_attendance, approving_authority, document_version_id | student_id → student.student; document_version_id → doc.document_version | HOD | R | BCREC (rule undefined, G-14) | B |

**Invariants:** unique `(session_id, student_id)`; the record's `(course_registration_id, student_id, course_offering_id)` must match `course_registration`, and `(session_id, course_offering_id)` must match `session`, so the student is registered in the exact offering being taught; a correction never deletes the original record; a summary is recomputable and records its calculation time and policy version; an eligibility assessment records the rule variant; condonation never applies below the policy floor; duty leave is not activated until G-14 is decided.

---

## 7. Domain 5b — Assessment (`assessment`)

**Trace:** Research §8.5, §9.4; S1 §§17–19; G-15. **Owner:** COE / HOD / Faculty.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| ASM-01 | `assessment.scheme` | Marks pattern applied to a course version. | `scheme_id` | name, effective_from_term_id, effective_to_term_id, status, approved_by, approved_at, policy_bundle_version_id | course_version_id → academic.course_version; effective_from/to_term_id → core.term; policy_bundle_version_id → policy.policy_bundle_version | COE / Academic Council | I | BCREC | IE |
| ASM-02 | `assessment.component` | Mark-bearing component or sub-component. | `component_id` | component_code (CIA1/CIA2/PCIA/PESE/ESE), name, component_type (internal/external/practical/sessional), max_marks, weight_pct, parent_component_id, sequence_no, attendance_linked | scheme_id → assessment.scheme; parent_component_id → assessment.component (self) | COE | I | BCREC | IE |
| ASM-03 | `assessment.schedule` | When and where an assessment happens. | `schedule_id` | scheduled_start, scheduled_end, duration_min, venue_text, status, instructions | component_id → assessment.component; course_offering_id → academic.course_offering | COE | I | BCREC | IE |
| ASM-04 | `assessment.mark_entry` | Identity of a student's mark for a component; current pointer. | `mark_entry_id` | current_version_no, status (draft/submitted/verified/locked), is_absent, is_exempt | student_id → student.student; component_id → assessment.component; course_offering_id → academic.course_offering | Faculty | C | BCREC | IE |
| ASM-05 | `assessment.mark_entry_version` | Immutable version of a mark. | `mark_entry_version_id` | version_no, marks_obtained, max_marks_snapshot, is_absent, is_exempt, status, entered_by, entered_at, submitted_at, verified_by, verified_at, change_reason | mark_entry_id → assessment.mark_entry; entered_by/verified_by → iam.person | Faculty / HOD | C | BCREC | IE |
| ASM-06 | `assessment.mark_correction` | A change after submission, with evidence and approval. | `mark_correction_id` | reason, requested_by, requested_at, approved_by, approved_at, status, evidence_document_version_id | mark_entry_id → assessment.mark_entry; from_version_id/to_version_id → assessment.mark_entry_version; evidence_document_version_id → doc.document_version | COE / HOD | C/R | BCREC | IE |
| ASM-07 | `assessment.conflict_declaration` | Faculty declaration of a ward/relative in a course. | `conflict_declaration_id` | relationship_type, declared_at, action_taken (reassigned/none), reassigned_to_person_id, status, document_version_id | faculty_person_id → iam.person; course_offering_id → academic.course_offering; student_id → student.student; reassigned_to_person_id → iam.person; document_version_id → doc.document_version | HOD | R | BCREC | IE |
| ASM-08 | `assessment.moderation_record` | Moderation applied to a cohort. | `moderation_record_id` | rule_description, before_distribution_json, after_distribution_json, approved_by, approved_at, rationale | course_offering_id → academic.course_offering; approved_by → iam.person | COE / Moderation Committee | R | BCREC | 2 |

**Invariants:** a scheme belongs to one course version and an effective term range; a component's weight and max marks are immutable once marks exist; one current mark entry per student/component/offering; a mark version is immutable; a correction references the exact versions it replaces; a conflict declaration must be resolved before the faculty member assesses.

---

## 8. Domain 6 — Examination and Results (`exam`)

**Trace:** Research §8.6–8.8, §9.5–9.7, §12 M10–M14; S1 §§20–24, S8, S16 §3.4; G-12, G-16, G-17. **Owner:** COE / Registrar.

### 8.1 Initial Release (read-only imported results)

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| EXM-01 | `exam.result_import` | Provenance of an imported result file. | `result_import_id` | source_label, file_name, sha256, imported_at, imported_by, row_count, error_count, status, notes | term_id → core.term; programme_id → academic.programme; imported_by → iam.person; external_system_id → integration.external_system (nullable) | COE | C | BCREC COE / source system | IE |
| EXM-02 | `exam.result_set` | A unit of results approved/published together. | `result_set_id` | exam_label, result_type (regular/supplementary/super_supplementary), status (imported/draft/approved/published/withheld), approved_by, approved_at, published_at, external_publication_ref, policy_bundle_version_id | term_id → core.term; programme_id → academic.programme; batch_id → academic.batch; import_id → exam.result_import; approved_by → iam.person; policy_bundle_version_id → policy.policy_bundle_version | COE | C | BCREC COE | IE |
| EXM-03 | `exam.result_record` | Per-student, per-course result identity across attempts. | `result_record_id` | attempt_no, is_backlog, year_of_study, current_revision_no, status (pass/fail/absent/withheld) | student_id → student.student; course_version_id → academic.course_version; course_offering_id → academic.course_offering (nullable); result_set_id → exam.result_set | COE | C | BCREC COE | IE |
| EXM-04 | `exam.result_revision` | Immutable computed/published result version. | `result_revision_id` | revision_no, cia_total, pcia_total, ese_total, pese_total, total_marks, grade, grade_point, result_status (X/XP/P), computed_at, computed_by, published_at, policy_bundle_version_id, change_reason | result_record_id → exam.result_record; computed_by → iam.person; policy_bundle_version_id → policy.policy_bundle_version | COE | C | BCREC COE | IE |
| EXM-05 | `exam.result_input` | Traceability from a result revision to the exact mark versions used. | `result_input_id` | component_code, marks_used, max_marks_snapshot | result_revision_id → exam.result_revision; mark_entry_version_id → assessment.mark_entry_version | COE | C | BCREC COE | IE |
| EXM-06 | `exam.grade_card` | Published term grade card, versioned. | `grade_card_id` | version_no, sgpa, ygpa, cgpa, credits_registered, credits_earned, status, published_at, is_current, document_version_id | student_id → student.student; term_id → core.term; result_set_id → exam.result_set; document_version_id → doc.document_version | COE | C | BCREC COE | IE |
| EXM-07 | `exam.grade_card_result` | Explicit composition of a grade card. | `grade_card_result_id` | included | grade_card_id → exam.grade_card; result_record_id → exam.result_record; result_revision_id → exam.result_revision | COE | C | BCREC COE | IE |

### 8.2 Future examination operations

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| EXM-08 | `exam.exam_event` | Examination session (regular/supplementary). | `exam_event_id` | exam_type, window_start, window_end, status, notification_document_version_id | term_id → core.term; notification_document_version_id → doc.document_version | COE | I | BCREC COE | 2 |
| EXM-09 | `exam.exam_registration` | Student form fill-up for an exam event. | `exam_registration_id` | eligibility_status, fee_status, admit_card_status, submitted_at, verified_by | student_id → student.student; exam_event_id → exam.exam_event; semester_registration_id → student.semester_registration | COE | C | BCREC COE | 2/B (G-08) |
| EXM-10 | `exam.exam_registration_course` | Course/paper entered for an exam. | `exam_registration_course_id` | attempt_no, is_backlog, course_type | exam_registration_id → exam.exam_registration; course_version_id → academic.course_version; course_offering_id → academic.course_offering (nullable) | COE | C | BCREC COE | 2 |
| EXM-11 | `exam.backlog_record` | Active and cleared backlog. | `backlog_record_id` | first_fail_term_id, attempt_count, status, cleared_term_id, cleared_result_record_id | student_id → student.student; course_version_id → academic.course_version; first_fail_term_id/cleared_term_id → core.term; cleared_result_record_id → exam.result_record | COE | C | BCREC COE | 2 |
| EXM-12 | `exam.supplementary_registration` | Entry to supplementary/super-supplementary exam. | `supplementary_registration_id` | exam_type, fee_status, eligibility_status, status | backlog_record_id → exam.backlog_record; exam_event_id → exam.exam_event; fee_demand_id → finance.fee_demand (nullable) | COE | C | BCREC COE | 2 |
| EXM-13 | `exam.ppr_case` | Student-initiated post-publication review. | `ppr_case_id` | scope (theory only), application_at, fee_payment_id, reviewer_person_id, outcome, decided_at, status, reason | student_id → student.student; result_record_id → exam.result_record; fee_payment_id → finance.payment; reviewer_person_id → iam.person | COE | R | BCREC COE | 2 |
| EXM-14 | `exam.correction_case` | Examiner-initiated correction with affidavit. | `correction_case_id` | trigger_description, affidavit_document_version_id, received_at, verified_by, verified_at, decision, status | result_record_id → exam.result_record; affidavit_document_version_id → doc.document_version; verified_by → iam.person | COE | R | BCREC COE | 2 |
| EXM-15 | `exam.promotion_decision` | Promotion/year-lag decision. | `promotion_decision_id` | from_term_id, to_term_id, backlogs_count, cgpa, decision (promoted/withheld/year_lag), policy_bundle_version_id, approved_by, decided_at | student_id → student.student; from/to_term_id → core.term; approved_by → iam.person; policy_bundle_version_id → policy.policy_bundle_version | Registrar / COE | C | BCREC | 2 |
| EXM-16 | `exam.degree_eligibility` | Whether a student may be recommended. | `degree_eligibility_id` | credits_earned, cgpa, active_backlogs, mar_points, mandatory_courses_status, dues_status, decision, policy_bundle_version_id, evaluated_at | student_id → student.student; policy_bundle_version_id → policy.policy_bundle_version | Registrar / COE | C | BCREC | 2 |
| EXM-17 | `exam.degree_recommendation` | Recommendation to MAKAUT. | `degree_recommendation_id` | recommendation_no, recommended_at, approved_by, status, submitted_at, makaut_reference | degree_eligibility_id → exam.degree_eligibility; approved_by → iam.person | Registrar | C | BCREC → MAKAUT | 2 |
| EXM-18 | `exam.certificate_issue` | Provisional degree, transcript, bonafide, character certificate. | `certificate_issue_id` | certificate_type, serial_no, issued_on, issued_by, status, document_version_id | student_id → student.student; issued_by → iam.person; document_version_id → doc.document_version | Registrar | C | BCREC | 2 |
| EXM-19 | `exam.answer_script` | Evaluated script and custody/re-evaluation link. | `answer_script_id` | script_barcode, evaluator_person_id, custody_location, scanned_uri, status | exam_registration_course_id → exam.exam_registration_course; evaluator_person_id → iam.person | COE | R | BCREC COE | 2 |
| EXM-20 | `exam.mar_record` | Mandatory Additional Requirements points. | `mar_record_id` | activity, category, points, academic_year_id, evidence_document_version_id, verified_by, status | student_id → student.student; academic_year_id → core.academic_year; verified_by → iam.person; evidence_document_version_id → doc.document_version | MAR Committee | C | BCREC | 2 |
| EXM-21 | `exam.mooc_record` | MOOC credits for Honours/MAR. | `mooc_record_id` | platform, course_title, credits, certificate_document_version_id, usage (honours/mar), verified_by, status | student_id → student.student; verified_by → iam.person; certificate_document_version_id → doc.document_version | MOOCs Committee | C | BCREC | 2 |
| EXM-22 | `exam.achievement` | Awards, publications, patents, sports, cultural. | `achievement_id` | achievement_type, title, achieved_on, description, evidence_document_version_id, verified_by, status | student_id → student.student; verified_by → iam.person; evidence_document_version_id → doc.document_version | Dean (SW&A) / IQAC | I | BCREC | 2 |

**Invariants:** a result record belongs to one result set; a result revision is immutable; a grade card references explicit result revisions; publication has an approval event or an external publication reference; BCREC never records itself as degree awarder; result status uses `X`/`XP`/`P`, not numeric codes.

---

## 9. Domain 7 — Faculty and Mentorship (`faculty`)

**Trace:** Research §8.9–8.10, §9.11; S3, S12; G-18. **Owner:** HR / HOD.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| FAC-01 | `faculty.faculty_profile` | Academic staff employment and academic attributes. | `faculty_profile_id` | employee_id, designation, department_id, joining_date, employment_type, highest_qualification, specialization, workload_category, status, relieving_date | person_id → iam.person; department_id → academic.department | HR / HOD | C | BCREC Society | IE |
| FAC-02 | `faculty.staff_profile` | Non-teaching staff attributes. | `staff_profile_id` | employee_id, designation, org_unit_id, reporting_to_person_id, joining_date, employment_type, status | person_id → iam.person; org_unit_id → core.org_unit; reporting_to_person_id → iam.person | HR | C | BCREC Society | IE |
| FAC-03 | `faculty.mentor_assignment` | Term-bound mentor–mentee relationship. | `mentor_assignment_id` | assigned_at, valid_from, valid_to, status, notes_visibility | mentor_person_id → iam.person; student_id → student.student; term_id → core.term; assigned_by → iam.person | HOD | C/R | BCREC | IE |
| FAC-04 | `faculty.mentoring_session` | Record of a mentoring contact. | `mentoring_session_id` | session_at, mode, summary, concerns, referral_type, referral_to, confidentiality_level | mentor_assignment_id → faculty.mentor_assignment | Mentor | R | BCREC | 2/B (G-18) |
| FAC-05 | `faculty.workload_allocation` | Teaching/R&D/administrative workload per term. | `workload_allocation_id` | teaching_hours, rnd_hours, administrative_hours, total_hours, policy_rule_version_id, approved_by | faculty_profile_id → faculty.faculty_profile; term_id → core.term; policy_rule_version_id → policy.rule_version | HOD | I | BCREC | 2 |
| FAC-06 | `faculty.external_person` | External examiner, nominee, industry expert, vendor contact. | `external_person_id` | organisation, designation, contact_json, valid_from, valid_to, status | person_id → iam.person (nullable) | COE / Registrar | C | BCREC | 2 |

**Invariants:** one faculty profile per person; employee ID unique; a mentor assignment is term-bound; a mentor sees only assigned mentees; mentoring notes are restricted and never used as automatic academic evidence.

---

## 10. Domain 8a — Finance (`finance`)

**Trace:** Research §8.14, §12 M15; S20, S22, S23; G-08, G-17. **Owner:** Finance/CFO. **All Phase 2.**

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| FIN-01 | `finance.fee_head` | Named charge. | `fee_head_id` | code, name, is_refundable, frequency, is_statutory, status | — | Finance | I | BCREC | 2 |
| FIN-02 | `finance.fee_structure` | Programme/batch/term fee schedule version. | `fee_structure_id` | version_no, effective_from, effective_to, status, approved_by, approved_at | programme_id → academic.programme; batch_id → academic.batch; academic_year_id → core.academic_year; term_id → core.term; approved_by → iam.person | Finance | C | BCREC | 2 |
| FIN-03 | `finance.fee_structure_item` | Amount per head in a structure. | `fee_structure_item_id` | amount, is_optional, due_offset_days | fee_structure_id → finance.fee_structure; fee_head_id → finance.fee_head | Finance | C | BCREC | 2 |
| FIN-04 | `finance.fee_demand` | Amount due from a student. | `fee_demand_id` | demand_no, total_amount, concession_amount, payable_amount, due_date, status, policy_rule_version_id | student_id → student.student; term_id → core.term; fee_structure_id → finance.fee_structure; policy_rule_version_id → policy.rule_version | Finance | R | BCREC | 2 |
| FIN-05 | `finance.fee_demand_item` | Itemised demand snapshot. | `fee_demand_item_id` | amount, description | fee_demand_id → finance.fee_demand; fee_head_id → finance.fee_head | Finance | R | BCREC | 2 |
| FIN-06 | `finance.payment` | Money received. | `payment_id` | amount, mode, external_reference, paid_at, status, idempotency_key, received_by | fee_demand_id → finance.fee_demand; received_by → iam.person | Finance | R | BCREC / gateway | 2 |
| FIN-07 | `finance.receipt` | Immutable proof of payment. | `receipt_id` | receipt_no, issued_at, issued_by, document_version_id | payment_id → finance.payment; issued_by → iam.person; document_version_id → doc.document_version | Finance | R | BCREC | 2 |
| FIN-08 | `finance.scholarship` | Scheme definition. | `scholarship_id` | name, sponsor, scheme_type, eligibility_text, benefit_text, valid_from, valid_to, status | — | Registrar / Scholarship Cell | I | Government / BCREC | 2 |
| FIN-09 | `finance.scholarship_award` | A student's award and disbursement. | `scholarship_award_id` | academic_year_id, amount_awarded, amount_disbursed, status, disbursement_reference | student_id → student.student; scholarship_id → finance.scholarship; academic_year_id → core.academic_year; payment_id → finance.payment (nullable) | Registrar | R | Government / BCREC | 2 |

**Invariants:** a demand snapshots amounts; a payment is never edited; a receipt is immutable; a scholarship award is separate from a fee waiver; fee status is a fact, not an eligibility decision (see `student.eligibility_determination`).

---

## 11. Domain 8b — Student Services (`services`)

**Trace:** Research §8.12–8.13, §9.9–9.10, §12 M16–M19; S10, S11; G-20, G-21. **Owner:** Principal / Dean / T&P / Hostel / Library. **All Phase 2 or blocked.**

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| SRV-01 | `services.disciplinary_case` | Incident to decision. | `case_id` | case_no, category, complaint_summary, reported_at, show_cause_at, response_at, inquiry_at, recommendation, decision, status | student_id → student.student; reported_by → iam.person; committee_body_id → core.governance_body | Principal / CDC | R | BCREC | 2/B (G-20) |
| SRV-02 | `services.disciplinary_action` | Penalty and its execution. | `action_id` | penalty_type, amount, effective_from, effective_to, affects_exam, affects_promotion, appeal_body_type, appeal_decided_by, appeal_decision, status | case_id → services.disciplinary_case; appeal_decided_by → iam.person | Principal | R | BCREC | 2/B (G-20) |
| SRV-03 | `services.grievance` | Student complaint outside discipline. | `grievance_id` | category, description, submitted_at, assigned_to, status, resolution, resolved_at | student_id → student.student; assigned_to → iam.person | Dean (SW&A) | R | BCREC | 2 |
| SRV-04 | `services.placement_registration` | Annual opt-in and eligibility. | `placement_registration_id` | academic_year_id, eligibility_status, cgpa_snapshot, active_backlogs, consent_status, pprt_status | student_id → student.student; academic_year_id → core.academic_year | T&P | R | BCREC T&P | 2/B (G-21) |
| SRV-05 | `services.placement_drive` | Recruiter event. | `drive_id` | company_name, drive_date, roles, ctc, eligibility_text, rounds, status | academic_year_id → core.academic_year | T&P | I | BCREC T&P | 2 |
| SRV-06 | `services.placement_application` | Student participation and outcome. | `application_id` | applied_at, current_round, status, outcome | drive_id → services.placement_drive; placement_registration_id → services.placement_registration | T&P | C | BCREC T&P | 2 |
| SRV-07 | `services.placement_offer` | Offer terms and acceptance. | `offer_id` | company_name, ctc, role, location, offered_at, accepted_at, dream_offer_flag, document_version_id | application_id → services.placement_application; document_version_id → doc.document_version | T&P | C | BCREC T&P | 2 |
| SRV-08 | `services.hostel_allocation` | Room and mess allocation. | `hostel_allocation_id` | hostel_name, room_no, bed_no, valid_from, valid_to, status | student_id → student.student | Hostel Superintendent | C | BCREC | 2 |
| SRV-09 | `services.library_loan` | Book bank and library transactions. | `library_loan_id` | item_ref, issued_at, due_at, returned_at, fine_amount, status | student_id → student.student | Librarian | C | BCREC | 2 |

**Invariants:** a disciplinary case has a decision and an appeal record; the appellate body is configurable and must not be hard-coded to the Principal; a grievance is not a disciplinary case; placement registration is annual and application is per drive; hostel and library records are term-bound.

---

## 12. Domain 9 — Notices and Document Management (`doc`)

**Trace:** Research §8.11, §10.10, §11.10; S1, S20; G-19. **Owner:** Issuing office / Registrar / CIP Curator.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| DOC-01 | `doc.document` | Logical source document (regulation, order, policy, circular). | `document_id` | title, document_type, issuer_name, issuer_org_unit_id, reference_no, document_date, effective_date, classification, owner_org_unit_id, status, source_url, retention_schedule_id | issuer_org_unit_id/owner_org_unit_id → core.org_unit; retention_schedule_id → ops.retention_schedule | Registrar / CIP Curator | P/I/C/R/G | Issuing authority | F |
| DOC-02 | `doc.document_version` | Immutable file version. | `document_version_id` | version_no, version_label, file_uri, mime_type, file_size, sha256, page_count, ocr_used, language, change_note, supersedes_version_id, effective_from, effective_to, status, ingested_at, approved_by, approved_at | document_id → doc.document; supersedes_version_id → doc.document_version (self); approved_by → iam.person | CIP Curator | P/I/C/R/G | Issuing authority | F |
| DOC-03 | `doc.document_relation` | Non-linear relations between versions. | `document_relation_id` | relation_type (supersedes/corrigendum/attachment/translation/duplicate), note | from_version_id/to_version_id → doc.document_version | CIP Curator | I | BCREC | F |
| DOC-04 | `doc.notice` | Logical notice identity. | `notice_id` | notice_no, category, issuing_org_unit_id, owner_person_id, status | issuing_org_unit_id → core.org_unit; owner_person_id → iam.person | Issuing office | P/I | BCREC | IE |
| DOC-05 | `doc.notice_version` | Published/corrected notice content. | `notice_version_id` | version_no, title, body_markdown, publish_at, effective_from, effective_to, status, supersedes_version_id, document_version_id, approved_by, approved_at | notice_id → doc.notice; supersedes_version_id → doc.notice_version (self); document_version_id → doc.document_version; approved_by → iam.person | Issuing office | P/I | BCREC | IE |
| DOC-06 | `doc.notice_audience` | Who a notice version applies to. | `notice_audience_id` | audience_type (all/programme/batch/term/role/org_unit), programme_id, batch_id, term_id, role_id, org_unit_id | notice_version_id → doc.notice_version; programme_id → academic.programme; batch_id → academic.batch; term_id → core.term; role_id → iam.role; org_unit_id → core.org_unit | Issuing office | I | BCREC | IE |
| DOC-07 | `doc.notice_acknowledgement` | Proof a person saw a notice. | `notice_acknowledgement_id` | read_at, channel | notice_version_id → doc.notice_version; person_id → iam.person | Issuing office | I | BCREC | 2 |

**Invariants:** every version has a SHA-256 and an immutable original; supersession is explicit; audience attaches to a version; a superseded version is never treated as current; a notice version may reference a document version but does not duplicate the file.

---

## 13. Domain 10a — Knowledge (`knowledge`)

**Trace:** Research §13.7–13.9, §11.10; database audit. **Owner:** CIP Curator / AI Platform.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| KNW-01 | `knowledge.document_chunk` | Retrieval unit derived from a document version. | `chunk_id` | sequence_no, chunk_text, section_path, page_from, page_to, token_count, language, chunking_profile, text_hash, created_at | document_version_id → doc.document_version; ingestion_run_id → knowledge.ingestion_run | CIP Curator | Inherits document | Derived | IC |
| KNW-02 | `knowledge.embedding` | Vector representation of a chunk. | `embedding_id` | model_name, model_version, dimensions, embedding vector(1024), created_at, is_active | chunk_id → knowledge.document_chunk | AI Platform | Internal | Derived | IC |
| KNW-03 | `knowledge.ingestion_run` | Provenance of parsing, chunking, and embedding. | `ingestion_run_id` | source_type, source_uri, started_at, finished_at, status, documents_seen, versions_created, chunks_created, embeddings_created, error_count, error_summary, parser_version, ocr_engine, chunker_version, embedding_model | triggered_by → iam.person (nullable) | CIP Curator | Internal | BCREC | IC |

**Invariants:** a chunk belongs to one document version; chunks never contain restricted personal records; an embedding is unique per chunk/model/model-version; a model change creates new embeddings, not overwrites; the embedding column dimension is fixed at deployment (see `OPEN_DECISIONS.md` OD-06).

---

## 14. Domain 10b — CIP Runtime (`cip`)

**Trace:** Research §13.8–13.10, §11.10. **Owner:** CIP Operator / AI Platform.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| CIP-01 | `cip.conversation` | A CIP session across text or voice. | `conversation_id` | channel (web/voice/whatsapp/api), language, started_at, ended_at, outcome (resolved/escalated/abandoned), escalation_flag, consent_recording | person_id → iam.person (nullable) | CIP Operator | C | BCREC | IC |
| CIP-02 | `cip.call_session` | Voice-call specific metadata. | `call_session_id` | provider, provider_call_id, direction, from_number_masked, to_number_masked, started_at, ended_at, duration_sec, recording_uri, recording_consent, status | conversation_id → cip.conversation | CIP Operator | R | BCREC | IC |
| CIP-03 | `cip.message` | A turn in a conversation. | `message_id` | sequence_no, role (user/assistant/system/tool), content_text, content_redacted, language, intent_code, confidence, model_name, model_version, latency_ms, token_count, created_at | conversation_id → cip.conversation | CIP Operator | C/R | BCREC | IC |
| CIP-04 | `cip.retrieval_log` | What was retrieved and why. | `retrieval_log_id` | query_text, normalized_query, strategy (vector/lexical/hybrid), filters_json, top_k, latency_ms, result_count, fallback_used, created_at | message_id → cip.message | CIP Operator | C | BCREC | IC |
| CIP-05 | `cip.retrieval_hit` | Ranked chunk considered for an answer. | `retrieval_hit_id` | rank, vector_score, lexical_score, rerank_score | retrieval_log_id → cip.retrieval_log; chunk_id → knowledge.document_chunk | CIP Operator | C | BCREC | IC |
| CIP-06 | `cip.citation` | Source actually shown to the user. | `citation_id` | page_from, page_to, quote, confidence, displayed | message_id → cip.message; chunk_id → knowledge.document_chunk; document_version_id → doc.document_version | CIP Operator | C | BCREC | IC |
| CIP-07 | `cip.feedback` | User rating and reason. | `feedback_id` | rating (up/down/1-5), reason_code, comment, created_at | message_id → cip.message; person_id → iam.person (nullable) | CIP Operator | I | BCREC | IC |
| CIP-08 | `cip.escalation` | No-answer or human handoff case. | `escalation_id` | reason_code, assigned_org_unit_id, status, created_at, resolved_at, resolution_note | conversation_id → cip.conversation; message_id → cip.message; assigned_org_unit_id → core.org_unit | CIP Operator | C | BCREC | IC |
| CIP-09 | `cip.eval_case` | Evaluation question and expected answer/citation. | `eval_case_id` | case_code, category (golden/negative/conflict/version/personal/language/access/latency), question, expected_answer, expected_citation, language, is_active | — | AI Platform | I | BCREC | IC |
| CIP-10 | `cip.eval_run` | A run of the evaluation set against a corpus/model version. | `eval_run_id` | started_at, finished_at, corpus_version, model_name, status, created_by | created_by → iam.person | AI Platform | I | BCREC | IC |
| CIP-11 | `cip.eval_result` | Result per case in a run. | `eval_result_id` | actual_answer, citation_correct, answer_correct, latency_ms, pass, notes | eval_run_id → cip.eval_run; eval_case_id → cip.eval_case | AI Platform | I | BCREC | IC |

**Invariants:** every factual answer has at least one citation or an explicit structured-source marker; retrieval logs are immutable; restricted personal data is never embedded or retrieved; call recordings require consent; a no-answer escalation is available; evaluation results gate release.

---

## 15. Cross-cutting — Policy (`policy`)

**Trace:** Research §9.1, §9.14–9.15; G-01, G-02. **Owner:** Academic Council / BOG / Registrar.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| POL-01 | `policy.rule` | Stable rule identity. | `rule_id` | rule_code (e.g. ATT-01), title, domain, description, owner_role_code, created_at | — | Academic Council / Registrar | I | Named authority | F |
| POL-02 | `policy.rule_version` | Immutable version of a rule. | `rule_version_id` | version_no, statement, authority (BCREC/MAKAUT/AICTE/other), parameters_json, effective_from, effective_to, status (Current/Draft/Historical/Superseded/Disputed/Unknown), confidence, confidence_reason, source_document_version_id, source_locator, approval_reference, supersedes_version_id, approved_by | rule_id → policy.rule; source_document_version_id → doc.document_version; supersedes_version_id → policy.rule_version (self); approved_by → iam.person | Academic Council / Registrar | I | Named authority | F |
| POL-03 | `policy.rule_scope` | Where a rule version applies. | `rule_scope_id` | scope_type (institution/programme/batch/term/course_type/student_category), course_type, student_category | rule_version_id → policy.rule_version; institution_id → core.institution; programme_id → academic.programme; batch_id → academic.batch; term_id → core.term | Registrar | I | BCREC | F |
| POL-04 | `policy.rule_conflict` | Two current rules that disagree. | `rule_conflict_id` | description, status (open/resolved), resolution_note, resolved_by, resolved_at | rule_version_a_id/rule_version_b_id → policy.rule_version; resolution_rule_version_id → policy.rule_version; resolved_by → iam.person | Registrar | I | BCREC | F |
| POL-05 | `policy.policy_bundle` | Stable identity for a named set of rules used by one calculation. | `policy_bundle_id` | bundle_code, name, domain, description, owner_role_code | — | Academic Council / Registrar | I | BCREC | F |
| POL-06 | `policy.policy_bundle_version` | Immutable version of a policy bundle. | `policy_bundle_version_id` | version_no, effective_from, effective_to, status, approval_reference, approved_by, created_at | policy_bundle_id → policy.policy_bundle; approved_by → iam.person | Academic Council / Registrar | I | BCREC | F |
| POL-07 | `policy.policy_bundle_member` | Rule version included in a bundle version. | `policy_bundle_member_id` | sequence_no, is_required | policy_bundle_version_id → policy.policy_bundle_version; rule_version_id → policy.rule_version | Registrar | I | BCREC | F |

**Bundle purpose:** a bundle makes a calculation reproducible. Attendance eligibility, result computation, and promotion decisions reference one `policy_bundle_version_id` rather than a loose set of rule IDs. A bundle is a technical composition; it does not create a new institutional rule.

**Invariants:** a rule version is immutable once used; status and confidence are explicit; a conflict is a first-class record; no rule is silently promoted from Draft to Current; retroactive application is a separate audited operation.

---

## 16. Domain 11 — Integration and Synchronization (`integration`)

**Trace:** Research §13.1–13.6; S14, S18, S20; G-09, G-10. **Owner:** ERP Administrator / Data Steward.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| INT-01 | `integration.entity_type` | Controlled registry for polymorphic references. | `entity_type_code` (text PK) | description, schema_name, table_name, is_active | — | Data Steward | I | BCREC | F |
| INT-02 | `integration.external_system` | A system exchanged with. | `external_system_id` | code, name, system_type (college_erp/makaut_portal/payment_gateway/email/sms/lms/idp), base_url, owner_org_unit_id, status, capabilities_json, last_health_at | owner_org_unit_id → core.org_unit | ERP Administrator | I | BCREC | F |
| INT-03 | `integration.external_id_mapping` | Stable internal ID to external ID. | `external_id_mapping_id` | entity_type_code, internal_id, external_id, is_primary, valid_from, valid_to, confidence | entity_type_code → integration.entity_type; external_system_id → integration.external_system | Data Steward | C | BCREC | F |
| INT-04 | `integration.source_of_truth_rule` | Which system wins for which field. | `source_of_truth_rule_id` | entity_type_code, field_name, authoritative_system_id, fallback_system_id, conflict_policy (authoritative_wins/manual_review/newest_wins), effective_from, effective_to, status, approved_by | entity_type_code → integration.entity_type; authoritative/fallback_system_id → integration.external_system; approved_by → iam.person | Data Steward | I | BCREC | F |
| INT-05 | `integration.sync_run` | One import/export attempt. | `sync_run_id` | direction (pull/push/bidirectional), entity_type_code, mode (full/incremental/event/manual_file), started_at, finished_at, status, records_read, records_written, records_failed, cursor_before, cursor_after, error_summary, adapter_version, operator_person_id | external_system_id → integration.external_system; entity_type_code → integration.entity_type; operator_person_id → iam.person | Integration Service | I | BCREC | F |
| INT-06 | `integration.sync_record` | Per-record outcome of a sync. | `sync_record_id` | internal_id, external_id, operation (insert/update/skip/delete/conflict), outcome (success/failed), error_code, error_detail | sync_run_id → integration.sync_run; entity_type_code → integration.entity_type | Integration Service | I | BCREC | F |
| INT-07 | `integration.sync_conflict` | Detected disagreement and its resolution. | `sync_conflict_id` | internal_id, field_name, internal_value_json, external_value_json, status (open/resolved/deferred), resolution (use_internal/use_external/manual), resolution_note, resolved_by, resolved_at | sync_run_id → integration.sync_run; entity_type_code → integration.entity_type; source_of_truth_rule_id → integration.source_of_truth_rule; resolved_by → iam.person | Data Steward | C | BCREC | F |
| INT-08 | `integration.record_provenance` | Per-field source, timestamp, and override state. | `record_provenance_id` | entity_type_code, internal_id, field_name, observed_at, value_hash, is_human_override | entity_type_code → integration.entity_type; source_system_id → integration.external_system (nullable); sync_run_id → integration.sync_run (nullable) | Integration Service | I | BCREC | F |
| INT-09 | `integration.outbox_event` | Transactional outbox for reliable publishing. | `outbox_event_id` | aggregate_type, aggregate_id, event_type, payload_json, occurred_at, published_at, status, retry_count | — | Integration Service | I | BCREC | F |

**Invariants:** no external ID on a domain table; every mapping has a validity window; every conflict is queued; a rerun is idempotent; `internal_id` is polymorphic and validated by the entity registry, not by a foreign key (documented exception); outbox events are published at least once and consumers are idempotent.

---

## 17. Domain 12 — Audit and Operations (`ops`)

**Trace:** Research §11.6, §11.9; S16 §11.1; G-22. **Owner:** Audit / Security / Data Steward.

| ID | Entity | Purpose | Primary key | Important attributes | Foreign keys | Owner | Cls | Authority | Phase |
|---|---|---|---|---|---|---|---|---|---|
| OPS-01 | `ops.audit_event` | Immutable record of a state-changing action. | `audit_event_id` | occurred_at, action, entity_type_code, entity_id, before_json, after_json, reason, correlation_id, source_channel, ip_address, user_agent, prev_hash, record_hash | actor_person_id → iam.person; actor_account_id → iam.identity_account; role_assignment_id → iam.role_assignment; entity_type_code → integration.entity_type | Audit / Security | C/R | BCREC | F |
| OPS-02 | `ops.data_quality_issue` | Known data defect and resolution. | `data_quality_issue_id` | entity_type_code, record_id, issue_type, severity, description, detected_at, status, assigned_to_person_id, resolution, resolved_at | entity_type_code → integration.entity_type; assigned_to_person_id → iam.person | Data Steward | I | BCREC | F |
| OPS-03 | `ops.break_glass_grant` | Temporary emergency access. | `break_glass_grant_id` | reason, starts_at, expires_at, scope_description, status, approved_by, reviewed_by, reviewed_at | person_id → iam.person; role_assignment_id → iam.role_assignment; approved_by/reviewed_by → iam.person | Principal / Audit | R | BCREC (recommendation) | F |
| OPS-04 | `ops.retention_schedule` | Retention and disposition rule per entity/class. | `retention_schedule_id` | classification, retention_period_months, trigger_event, disposition (destroy/anonymize/archive), legal_basis, status, approved_by | entity_type_code → integration.entity_type; approved_by → iam.person | Registrar / Legal | I | BCREC / law (G-22) | F/B |

**Invariants:** `audit_event` is append-only; every state change has an actor or system marker and a correlation ID; before/after values are captured for sensitive fields; break-glass expires and is reviewed; retention periods are not invented — the table exists but is not populated until G-22 is decided.

---

## 18. Duplicate and naming resolutions (summary)

| Issue | Resolution |
|---|---|
| `Person` vs `User` vs `Student` vs `Faculty` | Person is the human; account is the login; student/faculty are optional profiles. |
| `GoverningBody` + `Committee` | One `core.governance_body` with `body_type` and `is_statutory`; one membership table. |
| `Department` vs `OrgUnit` | Department references one org unit; no duplicate tree. |
| `Programme` vs `Course` | Programme = degree; course = subject/paper. |
| `Batch` vs `Section` | Batch = admission cohort; section = class group. |
| `Semester` vs `Term` | Term is the period; semester is an odd/even term type. |
| `Registration` | Qualified as university/semester/course/exam registration. |
| `PolicyVersion` | Split into rule, rule version, scope, conflict, and optional bundle. |
| `Notice` vs `Document` | Notice is communication; document is evidence; a notice version may cite a document version. |
| `Mark` vs `Result` vs `GradeCard` | Input vs per-course outcome vs per-term aggregate. |
| `AttendanceSummary` vs `Eligibility` | Measurement vs policy decision. |
| `ResultApproval` | Fields on `result_set`, not a separate per-row approval. |
| `ExternalIdMapping` | Polymorphic `internal_id` validated by `entity_type`; documented exception to FK integrity. |
| Class teacher, HOD, mentor, faculty allocation | Authority comes only from `iam.role_assignment`. Operational assignments scope effect and never grant permission. `department.hod_person_id` and `student.section_id` are derived caches. |
| Course coordinator | `offering_faculty.role_in_offering = 'coordinator'` with one active row per offering; no duplicate pointer on `course_offering`. |
| Student section transfer | `student.section_assignment` is the history; `student.section_id` is a current cache. |
| Attendance registration | `attendance.record` carries the registration and offering; composite FKs prove the student is registered in the session's offering. |

---

## 19. Entity count reconciliation

| Domain | Catalogued | Foundation / Initial | Future / Blocked |
|---|---:|---:|---:|
| Identity and Access | 8 | 8 | 0 |
| Institution and Governance | 13 | 11 | 2 |
| Academic Structure | 14 | 13 | 1 |
| Student Lifecycle | 15 | 13 | 2 |
| Attendance | 7 | 6 | 1 |
| Assessment | 8 | 7 | 1 |
| Examination and Results | 22 | 7 | 15 |
| Faculty and Mentorship | 6 | 3 | 3 |
| Finance | 9 | 0 | 9 |
| Student Services | 9 | 0 | 9 |
| Notices and Documents | 7 | 6 | 1 |
| Knowledge | 3 | 3 | 0 |
| CIP | 11 | 11 | 0 |
| Policy | 7 | 7 | 0 |
| Integration | 9 | 9 | 0 |
| Audit and Operations | 4 | 4 | 0 |
| **Total** | **152** | **108** | **44** |

The data dictionary covers the 108 Foundation/Initial entities (including the one `F/B` retention schedule). The earlier domain table in `DOMAIN_MODEL.md` groups policy bundles under the cross-cutting policy row; the canonical count is this table.
