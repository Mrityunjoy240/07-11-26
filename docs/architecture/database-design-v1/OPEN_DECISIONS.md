# Open Decisions — BCREC Campus ERP + CIP

**Purpose:** one register for every question the design deliberately did **not** answer. Each entry states the question, why it matters, what the schema already does, the options, the impact of each option, and who must decide.

**Rule:** until an entry is marked `Decided` with an approval reference, the **default posture** in §4 applies. No implementation team may resolve an institutional question by choosing a convenient default.

**Status legend:** `Open` (no decision), `In review` (owner engaged), `Decided` (approval reference recorded), `Deferred` (explicitly out of the current release).

---

## 1. Summary

| Group | Count | Decided | Conditional | Open / in review |
|---|---:|---:|---:|---:|
| Institutional gaps `G-01`–`G-22` | 22 | 0 | 0 | 22 |
| Design decisions `OD-01`–`OD-17` | 17 | 6 | 0 | 11 |
| Technical decisions `TD-01`–`TD-12` | 12 | 9 | 1 | 2 |

**No institutional gap is closed.** This is expected: the research closed none, and the design must not invent policy.

---

## 2. Institutional gaps (`G-01`–`G-22`)

Each row follows the same shape: **Question → Why it matters → Current posture → Options → Schema impact → Decider.**

### G-01 — Attendance threshold rule

| Field | Detail |
|---|---|
| Question | Is the 75% requirement applied to aggregate attendance, or separately to theory and practical? |
| Why it matters | Determines who is detained and who sits the end-semester examination. Directly affects a student's academic career. |
| Conflict | S1 Academic Regulations §16 says 75% aggregate; S2 Prospectus 2026 p.55 says 75% separately in theory and practical; S17 (MAKAUT, August 2026) does not settle it. |
| Current posture | `attendance.eligibility_assessment.rule_variant` stores `aggregate` or `split`; both percentage sets are computed; no gate is enforced. |
| Options | (a) aggregate only; (b) split only; (c) the stricter of the two; (d) aggregate with a practical floor. |
| Schema impact | None. A new `policy.rule_version` with `status = Current`, a bundle version, and a configured gate. |
| Affects | `attendance`, `student.eligibility_determination`, `exam.exam_registration` (future). |
| Decider | Academic Council, on the Registrar's note; COE for examination application. |
| Record | OD-01 |

### G-02 — Status of the Academic Regulations

| Field | Detail |
|---|---|
| Question | Is the document marked **Draft, Edition 1.0** the operative regulation, and if not, which edition is? |
| Why it matters | Every attendance, assessment, passing, progression, and PPR rule is derived from S1. If S1 is not operative, the rules are provisional. |
| Current posture | All rules derived from S1 are stored `Draft`; the CIP must disclose the draft status; a trigger blocks `Current` without an approval reference. |
| Options | (a) ratify Edition 1.0 as-is; (b) ratify with amendments (new version); (c) replace with a later edition; (d) continue as draft for the pilot. |
| Schema impact | New `policy.rule_version` rows; old versions become `Superseded`; dispute flag on the conflict record changes. |
| Affects | `policy`, `attendance`, `assessment`, `exam`, CIP answers about rules. |
| Decider | Academic Council; Principal for institutional adoption. |
| Record | OD-01 (with G-01) |

### G-03 — MAKAUT regulation precedence

| Field | Detail |
|---|---|
| Question | Where a MAKAUT regulation and a BCREC autonomous regulation differ, which governs an autonomous batch? |
| Why it matters | The autonomy order transfers curriculum, assessment, examination, and result control, but not degree award or registration (S16). The boundary for each rule is not enumerated. |
| Current posture | `policy.rule_version.authority` records `BCREC` or `MAKAUT`; `policy.rule_scope` allows a batch or programme scope. Both can coexist as versions. |
| Options | (a) BCREC wins for autonomous batches; (b) MAKAUT wins where the degree is awarded; (c) a documented rule-by-rule matrix. |
| Schema impact | None; scope and authority rows. |
| Decider | Registrar with Academic Council; MAKAUT clarification where ambiguous. |
| Record | OD-09 (source-of-truth matrix) |

### G-04 — Autonomy batch boundary

| Field | Detail |
|---|---|
| Question | Which admission batches are governed by BCREC autonomous regulations, and from which year? |
| Why it matters | Determines which rule set, curriculum, and result process apply to a cohort. A wrong boundary applies the wrong regulation to a student. |
| Current posture | `academic.batch.autonomy_status` = `autonomous` / `makaut` / `transitional`, defaulting to `transitional`. Rules are batch-scoped. |
| Options | (a) all programmes from 2024-25; (b) the 2024-25 entry batch only; (c) programme-by-programme approval; (d) a transition matrix by programme and year. |
| Schema impact | Data only (`batch.autonomy_status`), plus `policy.rule_scope` rows. |
| Decider | Registrar and COE, confirmed by the Principal; recorded in an office order. |
| Record | OD-04 |

### G-05 — New programme admission status

| Field | Detail |
|---|---|
| Question | Are MBA Hospital Management and Construction Technology and Management approved for admission in 2026-27, and with what intake? |
| Why it matters | Creates programmes, batches, fee structures, and affiliation records. |
| Current posture | `academic.programme` supports them; `core.affiliation_record.intake_approved` is per year. |
| Options | Admit / defer / not approved. |
| Schema impact | Data only. |
| Decider | Registrar with AICTE/MAKAUT approval evidence. |
| Record | — (data entry after approval) |

### G-06 — NBA accreditation validity

| Field | Detail |
|---|---|
| Question | Which programmes hold NBA accreditation, for which period, and does it affect any rule? |
| Why it matters | Accreditation status affects reporting and some eligibility claims; it does not change marks or results. |
| Current posture | `core.accreditation` is Phase 2; no rule depends on it. |
| Options | Record per programme with validity; do not gate anything. |
| Schema impact | Phase 2 table only. |
| Decider | IQAC Coordinator. |
| Record | — |

### G-07 — Board of Governors bye-laws

| Field | Detail |
|---|---|
| Question | What are the BOG's reserved powers, quorum, and term? |
| Why it matters | Determines who can approve institutional rules and appointments; the research found composition but not reserved powers. |
| Current posture | `core.governance_body` stores `quorum_min`, term, and constitution order; the powers are not modelled as rights. |
| Options | (a) publish bye-laws and encode approvals; (b) keep approvals documentary and record them as `approval_reference`. |
| Schema impact | None for (b); (a) may add an approval matrix. |
| Decider | BOG / Society. |
| Record | — |

### G-08 — Fee clearance as an examination gate

| Field | Detail |
|---|---|
| Question | Do unpaid dues bar semester registration, examination registration, or both? |
| Why it matters | A hard gate can stop a student sitting an exam; the Academic Regulations do not state the linkage, though practice suggests one. |
| Current posture | `student.eligibility_determination` records `FEE_CLEARANCE` as a fact with a policy version; the gate is not enforced. |
| Options | (a) no gate; (b) advisory flag; (c) hard gate at registration; (d) hard gate at examination; (e) hard gate at both with a hardship waiver. |
| Schema impact | Configuration + a policy bundle; no schema change. |
| Affects | `student`, `exam`, `finance` (Phase 2). |
| Decider | Finance/CFO with Registrar and Principal. |
| Record | OD-03 |

### G-09 — MAKAUT / NAD API availability

| Field | Detail |
|---|---|
| Question | Are registration numbers, degree awards, and NAD records exchangeable by API, or only by portal/file? |
| Why it matters | Determines whether the integration is automated or assisted. |
| Current posture | Manual file import path; `integration.external_system` supports `makaut_portal` and `nad`. |
| Options | (a) API; (b) scheduled file exchange; (c) manual entry with evidence. |
| Schema impact | Adapter only; `integration` tables already support all three. |
| Decider | Registrar with MAKAUT. |
| Record | — |

### G-10 — College ERP and identity provider

| Field | Detail |
|---|---|
| Question | What ERP is in use, what are its data model and APIs, and what IdP authenticates staff and students? |
| Why it matters | The whole integration and account-provisioning design depends on it. |
| Current posture | Adapter boundary, `identity_account.subject`, `external_id_mapping`, `source_of_truth_rule`; no direct DB access. |
| Options | (a) integrate via API; (b) via file; (c) replace the ERP; (d) coexist with manual reconciliation. |
| Schema impact | None; configuration and adapters. |
| Decider | Management/IT with the ERP vendor. |
| Record | OD-09 |

### G-11 — Admission officer authority and refunds

| Field | Detail |
|---|---|
| Question | Who may confirm admission, cancel an offer, and approve a refund? |
| Why it matters | Determines the approval fields and whether a refund is a finance record or an admission record. |
| Current posture | `admission_offer.confirmed_by`; fee reference is a string; finance is Phase 2. |
| Options | Named role(s) and a refund workflow. |
| Schema impact | Possibly a `refund` entity in `finance` (Phase 2). |
| Decider | Registrar and Finance. |
| Record | — |

### G-12 — Result approval signatory

| Field | Detail |
|---|---|
| Question | Who approves a result set before publication: COE, Principal, Examination Committee, or a combination? |
| Why it matters | Without it, automated publication cannot be safe or auditable. |
| Current posture | `exam.result_set.approved_by/approved_at`; publication requires an approver **or** an external publication reference; initial release is read-only import. |
| Options | (a) COE; (b) COE + Principal; (c) Examination Committee resolution + COE; (d) external (MAKAUT) for non-autonomous batches. |
| Schema impact | Approval fields exist; a workflow and permission are added. |
| Decider | Principal with COE; Examination Committee for the process. |
| Record | OD-02 |

### G-13 — Attendance capture method

| Field | Detail |
|---|---|
| Question | Manual faculty marking, biometric, RFID, or a mix? |
| Why it matters | Affects source, correction volume, and device integration. |
| Current posture | `attendance.record.source` = `faculty_manual` / `import` / `biometric` / `device`; one record per student per session. |
| Options | Any of the above; the model does not change. |
| Schema impact | Possibly a device reference table; not required now. |
| Decider | Academic Council / IT. |
| Record | — |

### G-14 — Duty leave treatment

| Field | Detail |
|---|---|
| Question | Does duty leave (sports, NCC, competition, official duty) count toward the 75% requirement? |
| Why it matters | Changes a student's eligibility. |
| Current posture | `attendance.duty_leave` is Phase B with a `counts_as_attendance` parameter; not active. |
| Options | (a) counts as present; (b) excluded from denominator; (c) counted but capped; (d) not counted. |
| Schema impact | Activation of an existing table. |
| Decider | Academic Council. |
| Record | — |

### G-15 — Reassessment cap

| Field | Detail |
|---|---|
| Question | How many make-up or reassessment attempts are allowed per component? |
| Why it matters | Prevents unlimited attempts and inconsistent practice. |
| Current posture | `assessment.schedule.schedule_type` supports `makeup`/`reassessment`; no cap is enforced; a policy parameter can cap it. |
| Options | A number per component type, or uncapped with COE approval. |
| Schema impact | Policy parameter only. |
| Decider | COE / Academic Council. |
| Record | — |

### G-16 — Theory examiner appointment

| Field | Detail |
|---|---|
| Question | Who appoints external theory examiners, and how is independence ensured? |
| Why it matters | Affects answer-script custody and PPR reviewer independence. |
| Current posture | `exam.answer_script.evaluator_person_id` and `faculty.external_person` (Phase 2). |
| Options | Panel per course; MAKAUT nomination for non-autonomous batches. |
| Schema impact | Phase 2 tables exist in the catalog. |
| Decider | COE. |
| Record | — |

### G-17 — PPR refund

| Field | Detail |
|---|---|
| Question | Is the post-publication review fee refunded if the result changes? |
| Why it matters | Finance and student-relations impact. |
| Current posture | `exam.ppr_case.fee_payment_id` (Phase 2); no refund logic. |
| Options | Full, partial, none. |
| Schema impact | Finance refund entity. |
| Decider | Finance with COE. |
| Record | — |

### G-18 — Mentoring cadence and confidentiality

| Field | Detail |
|---|---|
| Question | How often must a mentor meet a mentee, and what may be recorded? |
| Why it matters | Mentoring notes can contain sensitive personal information. |
| Current posture | `faculty.mentor_assignment` is Initial; `faculty.mentoring_session` is blocked. |
| Options | Minimum meetings per term; note categories; retention. |
| Schema impact | Activation of `mentoring_session`; retention row. |
| Decider | Dean (Student Welfare) / HODs. |
| Record | — |

### G-19 — Notice approval authority

| Field | Detail |
|---|---|
| Question | Who may publish an institutional notice, and is approval required for every category? |
| Why it matters | An unapproved notice can misinform students. |
| Current posture | `doc.notice_version.approved_by`; publishing automation is off; notices can be recorded with an external approval reference. |
| Options | Per-category approver; Principal for institutional; office head for routine. |
| Schema impact | Workflow + permission; no schema change. |
| Decider | Principal / Registrar. |
| Record | — |

### G-20 — Disciplinary appellate authority

| Field | Detail |
|---|---|
| Question | Who hears an appeal against a disciplinary penalty, given that the Principal chairs the deciding committee? |
| Why it matters | Natural justice; the research found the roles overlap. |
| Current posture | `services.disciplinary_action.appeal_body_type` and `appeal_decided_by` are configurable; no default. |
| Options | (a) BOG sub-committee; (b) an independent senior professor; (c) the university; (d) an external ombudsman. |
| Schema impact | Configuration only. |
| Decider | Principal with BOG. |
| Record | — |

### G-21 — Placement eligibility policy

| Field | Detail |
|---|---|
| Question | Are the CGPA 6.75 / 60% and no-active-backlog thresholds universal, or recruiter-specific? |
| Why it matters | Determines who can apply to a drive. |
| Current posture | Policy parameters; `services.placement_registration` is Phase 2/B. |
| Options | Universal, per-drive, or both with an override. |
| Schema impact | Policy parameters. |
| Decider | T&P with Principal. |
| Record | — |

### G-22 — Retention periods

| Field | Detail |
|---|---|
| Question | How long is each class of record kept, and what happens at expiry? |
| Why it matters | Legal compliance, storage cost, and the right to erasure for personal data. |
| Current posture | `ops.retention_schedule` exists but is empty of approved rows; no deletion job. |
| Options | Per classification and entity; legal minimums; archive vs destroy. |
| Schema impact | Data only; a retention job is written but disabled. |
| Decider | Registrar/Legal with Principal. |
| Record | OD-05 |

---

## 3. Design decisions (`OD-01`–`OD-17`)

These are project decisions, not institutional policy. `OD-01`–`OD-05` are the decision records that close `G-01`, `G-12`, `G-08`, `G-04`, `G-22`. `OD-06`–`OD-11` are architecture choices that remain open. `OD-12`–`OD-17` are design decisions made in this revision and recorded so the implementation phase does not re-litigate them.

### OD-01 — Attendance variant activation (closes G-01/G-02)

| Field | Detail |
|---|---|
| Decision needed | Which `rule_variant` becomes `Current`, and when may the gate be enforced? |
| Default posture | Both variants computed; neither enforced. |
| Options | Aggregate / split / stricter / aggregate with practical floor. |
| Impact | One policy version promoted; one gate configured; UI copy updated. |
| Owner | Academic Council. |
| Status | Open |

### OD-02 — Result publication workflow (closes G-12)

| Field | Detail |
|---|---|
| Decision needed | The approval chain and the permission that publishes a result set. |
| Default posture | Read-only import; publication is external; no internal approval. |
| Options | COE / COE+Principal / Committee+COE / external. |
| Impact | `result_set` approval fields, a permission, a workflow, an audit event. |
| Owner | Principal + COE. |
| Status | Open |

### OD-03 — Fee gate configuration (closes G-08)

| Field | Detail |
|---|---|
| Decision needed | Whether `FEE_CLEARANCE` blocks registration, examination, or nothing, and who may waive it. |
| Default posture | Recorded as a fact; advisory only. |
| Options | None / advisory / registration / examination / both. |
| Impact | A gate configuration and a waiver permission; no schema change. |
| Owner | Finance/CFO + Registrar. |
| Status | Open |

### OD-04 — Batch autonomy binding (closes G-04)

| Field | Detail |
|---|---|
| Decision needed | The autonomy status per programme and admission year. |
| Default posture | `transitional`; rules are batch-scoped and not auto-applied. |
| Options | Per §2 G-04. |
| Impact | Data rows; a policy bundle per batch; possibly a different curriculum. |
| Owner | Registrar + COE. |
| Status | Open |

### OD-05 — Retention and disposition (closes G-22)

| Field | Detail |
|---|---|
| Decision needed | Periods per entity/classification and the disposition action. |
| Default posture | Nothing deleted, archived, or anonymised. |
| Options | Per legal advice. |
| Impact | `ops.retention_schedule` rows; a disabled job becomes enabled; partitioning affects delete cost. |
| Owner | Registrar/Legal. |
| Status | Open |

### OD-06 — Embedding model and dimension

| Field | Detail |
|---|---|
| Decision needed | The multilingual embedding model and its output dimension. |
| Why it matters | Fixes `vector(N)`, the HNSW index, storage, and re-embedding cost. |
| Evidence | Current model `all-MiniLM-L6-v2`, 384 dims, English-centric; p50 12.6 ms on CPU. No multilingual benchmark was possible in the audit environment. |
| Options | (a) MiniLM 384 (cheap, weak Bengali/Hindi); (b) a multilingual sentence-transformer (768/1024); (c) BGE-M3 (1024, strong multilingual, heavier). |
| Default posture | Schema illustrated at `vector(1024)`; **do not create the column until this is decided**. |
| Impact | DDL dimension, index type, memory, inference latency, re-embedding of the corpus. |
| Owner | AI/Platform lead with the CIP content owner. |
| Status | Open — requires a measured multilingual benchmark |

### OD-07 — Corpus scope

| Field | Detail |
|---|---|
| Decision needed | Which document types are ingested into the retrieval corpus. |
| Default posture | Institutional documents only; restricted personal data excluded. |
| Proposed inclusion | Regulations, prospectus, notices, fee circulars, syllabi, committee composition, placement policy, academic calendar. |
| Proposed exclusion | Student records, marks, answer scripts, medical, disciplinary, identity documents, fee ledgers. |
| Impact | Ingestion filters, evaluation set, disclosure text. |
| Owner | CIP Content Curator + Registrar. |
| Status | Open (initial exclusion list is a design recommendation, not an approved policy) |

### OD-08 — Language set and detection

| Field | Detail |
|---|---|
| Decision needed | Which languages must the CIP answer in, and at what quality. |
| Default posture | English corpus, English answers with Bengali/Hindi query understanding; answers cite English sources. |
| Options | English only; English + Bengali; English + Bengali + Hindi; full multilingual answers. |
| Impact | Model choice, tokenizer, evaluation set, UI, fallback copy. |
| Owner | CIP product owner. |
| Status | Open |

### OD-09 — Source-of-truth matrix

| Field | Detail |
|---|---|
| Decision needed | For each field, which system wins: the new platform, the college ERP, or MAKAUT. |
| Default posture | `manual_review` for every field; no automatic overwrite. |
| Impact | `integration.source_of_truth_rule` rows; sync behaviour; conflict volume. |
| Owner | Data Steward with Registrar and IT. |
| Status | Open |

### OD-10 — Audit retention and partitioning

| Field | Detail |
|---|---|
| Decision needed | How long audit is kept, and whether it is partitioned monthly from day one. |
| Default posture | Append-only, monthly partitions, no deletion. |
| Impact | Storage, restore time, hash-chain verification, retention job. |
| Owner | Audit/Security with DBA. |
| Status | Open |

### OD-11 — Second student career

| Field | Detail |
|---|---|
| Decision needed | May one person hold two concurrent student records (e.g. a second programme)? |
| Default posture | Unique key is `(person_id, batch_id)`, so it is possible but not automatic. |
| Options | One career per person; one per programme; one per level. |
| Impact | Unique constraint, portal behaviour, fee and result ownership. |
| Owner | Registrar. |
| Status | Open |

### OD-12 — Release-boundary foreign-key containment

| Field | Detail |
|---|---|
| Decision needed | May an Initial Release table reference a Future/Blocked table? |
| Decision | No. The boundary is one-way: Initial → Initial only; Future tables may reference Initial tables. |
| Why it matters | An Initial migration that references a non-existent table cannot run; the alternative is a placeholder table, which corrupts the model. |
| Resolution applied | `academic.timetable_slot.room_id` was removed; `venue_text` remains, and `room_id` is added by a Phase-2 expand migration. `ops.retention_schedule` is `F/B` but part of the Initial Release, so `doc.document.retention_schedule_id` is valid. |
| Evidence | Programmatic FK audit over `ENTITY_CATALOG.md` and `DATA_DICTIONARY.md`: zero Initial → Future foreign keys after the fix. |
| Impact | Schema migration ordering; staged-FK list in `MVP_DEPENDENCY_MAP.md` §8.2. |
| Owner | ERP Architect / Data Steward. |
| Status | Decided (design) |

### OD-13 — Section teaching and student section history

| Field | Detail |
|---|---|
| Decision needed | How are class teachers and student section membership represented over time? |
| Decision | `academic.section_teacher_assignment` is the time-bound teaching record; `student.section_assignment` is the historical membership record. `section.class_teacher_person_id` is removed. `student.section_id` remains only as a derived current-section cache. |
| Why it matters | A column cannot answer "who was the class teacher last term" or "which section was the student in before the transfer", and it bypasses the role-assignment model. |
| Authority | The allocating HOD/Registrar records `authority_role_assignment_id`; the assignment scopes effect and does not grant a permission. |
| Invariants | One open class teacher per section (partial unique + daterange exclusion); one open section assignment per student; composite FKs keep student/section within the same batch. |
| Impact | ERD academic and student records, data dictionary ACD-14 and STU-15, RLS helpers. |
| Owner | Registrar + HOD. |
| Status | Decided (design) |

### OD-14 — Attendance registration invariant

| Field | Detail |
|---|---|
| Decision needed | How does the database prevent attendance for a student who is not registered in the session's offering? |
| Decision | `attendance.record` carries `course_registration_id` and `course_offering_id`, with two composite FKs: `(course_registration_id, student_id, course_offering_id) → student.course_registration`, and `(session_id, course_offering_id) → attendance.session(session_id, course_offering_id)`. |
| Why it matters | Two independent references (`student_id`, `session_id`) allow a record for an unregistered or dropped student. |
| Limit | "Dropped before the session date" is temporal and cannot be an FK; the service checks it and records the reason. |
| Impact | `course_registration` gets `student_id` and unique `(course_registration_id, student_id, course_offering_id)`; `attendance.session` gets unique `(session_id, course_offering_id)`; `attendance.record` gets the columns, FKs, and indexes. |
| Owner | COE + Registrar. |
| Status | Decided (design) |

### OD-15 — Assignment authority reconciliation

| Field | Detail |
|---|---|
| Decision needed | Which record grants authority for HOD, class teacher, offering faculty, mentor, and coordinator? |
| Decision | Only `iam.role_assignment` grants a permission. `academic.section_teacher_assignment`, `academic.offering_faculty`, `faculty.mentor_assignment`, and `student.section_assignment` scope effect and never grant a permission. |
| Duplicates removed | `academic.section.class_teacher_person_id`, `academic.course_offering.coordinator_person_id`, and any `Mentor`/`Course Coordinator` role. The coordinator is `offering_faculty.role_in_offering = 'coordinator'`. |
| Derived caches | `academic.department.hod_person_id` and `student.section_id` are caches, updated in the same transaction and reconciled nightly. |
| Why it matters | Duplicate pointers create two truths and bypass revocation. |
| Impact | ACD-01, ACD-05, ACD-10, ACD-11, ACD-14; ERD identity §3; RLS helper functions. |
| Owner | Registrar + Principal. |
| Status | Decided (design) |

### OD-16 — Sensitive student data classification

| Field | Detail |
|---|---|
| Decision needed | Which student fields are special-category, and how are they accessed? |
| Decision | Admission/reservation category, category/income certificates, guardian income band, guardian consent records, identity documents, and medical evidence are `R` or `R/G`. Default projections omit them; access is via named-role `SECURITY DEFINER` views; category and document numbers are field-encrypted; every read is audited; none enters the CIP corpus or an unmasked analytics extract. |
| Why it matters | RLS filters rows, not columns. A faculty member who can see a student must not see the student's category or income. |
| Evidence | `DATA_DICTIONARY.md` §1.7 special-category matrix; `POSTGRES_ARCHITECTURE.md` §9.3; DPDP Act 2023 minimisation principle. |
| Open part | The DPO/Legal office must confirm the named-role list and the legal basis before production. The design and default posture are decided. |
| Impact | Column grants, views, KMS key management, audit volume, analytics exclusion. |
| Owner | DPO/Legal + Registrar. |
| Status | Decided (design); DPO confirmation pending |

### OD-17 — Implementation release waves

| Field | Detail |
|---|---|
| Decision needed | Must all 108 Initial Release entities ship at once? |
| Decision | No. The complete logical catalog is retained, but delivery is staged in waves W1a, W1b, W2, W3, W4, W5, W6. The minimum viable term is 84 entities through W4. |
| Why it matters | A single 108-table release delays the first usable term and couples every module to every other. |
| Constraint | A wave may reference only earlier waves. A forward reference uses the staged-FK mechanism, never a placeholder table. |
| Impact | Implementation sequencing only; no entity is removed from the catalogue. |
| Owner | ERP Architect + Programme Manager. |
| Status | Decided (design) |

---

## 4. Default design posture

If no decision arrives, the system behaves as follows. This is the **safe** posture, not a neutral one.

| Area | Default |
|---|---|
| Attendance | Measure and display both variants; do not detain or block. |
| Academic Regulations | Treated as `Draft`; CIP discloses the draft status. |
| Autonomy | Batch is `transitional`; rules are not auto-applied. |
| Fee | Recorded as a fact; not a gate. |
| Results | Read-only imported results with an external publication reference; no internal approval, no computation, no automated publication. |
| Notices | Recorded with an external approval reference; no scheduled auto-publish. |
| Discipline | No automated appeal routing; the appellate body is unset. |
| Mentoring | Assignment only; no session notes. |
| Duty leave | Not counted. |
| Retention | Nothing deleted, anonymised, or archived. |
| Integration | `manual_review`; no automatic overwrite; no direct ERP writes. |
| Corpus | Institutional documents only; restricted data excluded. |
| Vectors | Not created until the model/dimension is chosen. |
| Redis | Not deployed. |
| Section membership | Historical assignment; `student.section_id` is a nullable current cache until an assignment exists. |
| Authority | Only `iam.role_assignment`; operational assignments scope effect. |
| Sensitive fields | `R`/`G` fields omitted from default projections and never ingested. |
| Phase 2 modules | Not activated. |

**Why this posture:** every default is reversible, none silently creates an obligation for a student, and none presents an unapproved rule as policy. The cost is that some conveniences (automatic detention, automatic publication) wait. That cost is acceptable; the opposite error is not.

---

## 5. Technical decisions (`TD`)

| ID | Decision | Status | Choice | Rationale |
|---|---|---|---|---|
| TD-01 | PostgreSQL version | Decided (design) | 16 or 17 | `gen_random_uuid`, `MERGE`, `jsonb` features, `NULLS NOT DISTINCT` |
| TD-02 | Schema layout | Decided | One schema per domain + `api` | Ownership, grants, clarity |
| TD-03 | Primary key type | Decided | `uuid` (UUIDv7 preferred) | Stable, non-guessable, merge-safe; v7 improves index locality |
| TD-04 | Access control | Decided | RLS + scoped role assignments + permissions | Least privilege; research §11 |
| TD-05 | Vector store | Conditional | pgvector; Chroma fallback | §13 of the architecture doc; benchmark gate |
| TD-06 | Cache/queue | Decided | No Redis; Postgres + outbox + `SKIP LOCKED` | Audit evidence: Redis unused; adds a failure domain |
| TD-07 | Integration pattern | Decided | Outbox + adapter + ID mapping + provenance | Reliable, idempotent, no dual writes |
| TD-08 | Polymorphic references | Decided | Registry table + orphan checks; single documented exception | Avoids a generic super-table |
| TD-09 | Audit | Decided | App audit + seal triggers + hash chain + `pgaudit` | Tamper evidence and attribution |
| TD-10 | Connection pooling | Decided | PgBouncer, transaction mode | Many app roles, one primary |
| TD-11 | Hosting | Open | Cloud vs on-prem vs managed | Affects backup, DR, cost, and who operates it |
| TD-12 | Object storage and telephony/LLM providers | Open | Vendor selection | Affects only adapters, not the data model |

---

## 6. Decision impact matrix

| Decision | Blocks schema? | Blocks build? | Blocks go-live? | Reversible? |
|---|---|---|---|---|
| G-01 / OD-01 attendance | No | No | Only detention feature | Yes (policy version) |
| G-02 regulations | No | No | CIP rule answers need disclosure | Yes (status change) |
| G-04 / OD-04 batch | No | No | Rule application to a cohort | Yes (data) |
| G-08 / OD-03 fee gate | No | No | Fee-gated registration | Yes (config) |
| G-12 / OD-02 results | No | No | Automated publication | Yes (workflow off) |
| G-19 notice approval | No | No | Auto-publish | Yes |
| G-20 discipline appeal | No | No | Automated appeal | Yes |
| G-22 / OD-05 retention | No | No | Deletion jobs | Yes |
| G-10 ERP/IdP | No | Adapter only | Automated sync | Yes |
| OD-06 embedding | **Yes** — `vector(N)` DDL | Yes | CIP retrieval | Re-embed, not schema |
| OD-07 corpus scope | No | Ingestion filters | CIP answers | Yes |
| OD-08 languages | No | Model/eval | Multilingual answers | Re-index |
| OD-09 source of truth | No | Sync writes | ERP sync | Yes |
| OD-11 second career | No (unique key chosen) | No | Edge case | Yes |
| OD-12 release boundary | No — decided; prevents a future blocker | No | No | Yes (migration order) |
| OD-13 section history | No — decided | No | No | Yes (additive) |
| OD-14 attendance invariant | No — decided | No | No | Yes (additive) |
| OD-15 authority reconciliation | No — decided | No | No | Yes (additive) |
| OD-16 sensitive data | No (columns exist) | Named-role views + encryption | Production access | Yes |
| OD-17 release waves | No | Sequencing only | No | Yes |

**DDL blocking status:**

- **OD-06 is the only open design decision that blocks a DDL shape.** No `vector(N)` column or HNSW index is created until the embedding model and dimension are chosen. A provisional `vector(1024)` is an illustration, not a migration.
- The former second DDL blocker, `academic.timetable_slot.room_id → academic.room`, is **resolved by removal**, not by a decision: the column is not in the Initial Release and is added in Phase 2. This is a phase-sequencing issue (OD-12), not an open question.
- Institutional gaps (G-01, G-02, G-04, G-08, G-12, G-19, G-20, G-22) block **activation**, not table creation. They are configuration, data, or workflow gates.
- OD-16 does not block table creation; it blocks production access to `R`/`G` fields until the DPO confirms the named-role list and legal basis.

---

## 7. Sign-off

| Role | Name | Scope | Signature | Date |
|---|---|---|---|---|
| Principal | | Institutional policy, result publication, discipline appeal | | |
| Registrar | | Student records, affiliation, retention, batch boundary | | |
| Controller of Examinations | | Assessment, results, examination operations | | |
| Finance Officer / CFO | | Fee gate, refunds, scholarships | | |
| Dean (Student Welfare) | | Mentoring, grievance | | |
| IQAC Coordinator | | Accreditation and returns | | |
| ERP Administrator / IT | | Integration, identity provider, hosting | | |
| CIP Product Owner | | Corpus scope, languages, escalation | | |
| Data Protection / Legal | | Retention, consent, personal-data handling | | |
| Audit / Security | | Break-glass, audit retention, access review | | |

**Sign-off rule:** a decision is not `Decided` until the row above is signed **and** the approval reference is stored in the relevant `policy.rule_version.approval_reference` or `integration.source_of_truth_rule` record. A verbal decision is not a database state.

---

## 8. Review cadence

| Cadence | Purpose |
|---|---|
| Weekly (project) | Unblock build dependencies; review `sync_conflict` and `data_quality_issue` counts. |
| Monthly (academic) | Close `G-01`, `G-02`, `G-04`, `G-19` with the Registrar/COE. |
| Per release | Re-run the Gate B checklist in `MVP_DEPENDENCY_MAP.md` §9. |
| Quarterly | Restore drill, access review, retention review, audit-chain verification. |

---

## 9. Traceability

| Decision group | Research basis |
|---|---|
| G-01 attendance | S1 §16; S2 p.55; S17 |
| G-02 regulations | S1 cover; S20 |
| G-04 autonomy | S1 §3; S20 |
| G-08 fee gate | S1 §9.2.3; S20 |
| G-12 result approval | S1 §§23–24; S8 |
| G-19 notice approval | S20; research §11 |
| G-20 discipline appeal | S11 |
| G-22 retention | Research §11.9 |
| OD-06–OD-08 retrieval | Research §13.9–13.10; database audit; baseline JSON |
| OD-09–OD-11 integration/identity | Research §13.1–13.6; G-09, G-10 |
| OD-12 release boundary | Entity catalog phase column; FK audit |
| OD-13 section history | Research §8.2–8.3; S1 §9; G-04 |
| OD-14 attendance invariant | Research §8.4, §9.3; S1 §16 |
| OD-15 authority reconciliation | Research §7.1, §7.4, §11.2 |
| OD-16 sensitive data | Research §11.2–11.3; DPDP Act 2023 |
| OD-17 release waves | Entity catalog §19; MVP dependency map §8 |

**End of open decisions.**
