# Design Review — BCREC CIP Database Architecture v1

**Status:** Design input. No DDL, migration, application change, or database was created.
**Input:** [`docs/research/BCREC_MAKAUT_GOVERNANCE_AND_WORKFLOW_RESEARCH.md`](../../research/BCREC_MAKAUT_GOVERNANCE_AND_WORKFLOW_RESEARCH.md) (research cut-off 6 November 2026).
**Scope of this document:** classify what the research established, what it derived, what it recommends, what remains unverified, and which entity problems must be fixed before a schema is written.

**Evidence labels used here follow the research:** `[BCREC]`, `[MAKAUT]`, `[UGC]`, `[AICTE]`, `[Inference]`, `[Recommendation]`, `[Unverified]`, `[Gap]`. Source IDs `S1`–`S23` and gap IDs `G-01`–`G-22` refer to the research register.

---

## 1. Review method

1. Read all sixteen research sections, including the rule repository (§9), entity inventory (§10), access requirements (§11), module classification (§12), integration strategy (§13), and gap register (§14.3).
2. Re-classified every material statement into fact, source-derived rule, recommendation, inference, assumption, contradiction, or gap.
3. Checked the §10 entity inventory for duplicate concepts, missing entities, and relationships that cannot be true as drawn.
4. Checked §12 (module release) against §10 (entity release). Where the two disagree, this review records the conflict and adopts the more conservative release boundary.
5. Converted only confirmed rules and explicit recommendations into design constraints. Unresolved rules are represented as configurable, versioned policy — never as defaults that look approved.

**Non-negotiable boundary:** a recommendation in this document is not a BCREC policy. A rule marked **Draft** or **Disputed** in the research stays Draft or Disputed in the database design.

---

## 2. Classification summary

| Class | Count in research | Design treatment |
|---|---|---|
| Confirmed institutional facts | Institutional identity, portfolio, governance, role catalogue, documented academic rules | Modelled as stable reference data or versioned records with source IDs. |
| Source-derived rules | §9 rule repository (ADM, REG, ATT, ASS, PAS, GRD, PRO, SUP, DEG, COR, PPR, MAR, DIS, PLC, SRV, CAL, EXM, AFF) | Stored as `policy.rule` + `policy.rule_version` + `policy.rule_scope`; never hard-coded. |
| Recommendations / inferences | Adapter boundary, role assignments, versioned policy, RLS, provenance, pgvector candidate, Redis deferral | Adopted as design decisions, explicitly labelled. |
| Unverified assumptions | Batch boundary, result signatory, fee gate, notice approval, IdP/ERP, retention, mentoring cadence | Carried to `OPEN_DECISIONS.md`; schema supports alternatives. |
| Contradictions | Attendance aggregate vs split; Draft vs operative regulations; discipline/result/notice authority; entity release conflicts | Both variants representable; no silent selection. |
| Gaps | G-01–G-22 | Each gap mapped to the schema feature that keeps it open. |

---

## 3. Confirmed facts that constrain the schema

These are treated as stable design inputs. Each row cites the research evidence.

| ID | Fact | Design consequence | Evidence |
|---|---|---|---|
| F-01 | BCREC is a private, self-financing college established in 2000, AICTE-approved, MAKAUT-affiliated, with college code `120`. | `core.institution` is the root scope; college code is a unique business key; programme and exam identifiers use it. | [S14][S15][S1 §9.2.2] |
| F-02 | Autonomy was granted in April 2024 for five years from 2024-25, covering B.Tech, M.Tech, MBA, and MCA. | Programmes and batches carry an autonomy/regulation binding; autonomy has a validity window. | [S1 §3][S2][S16 §3.10] |
| F-03 | The degree is awarded by MAKAUT; BCREC issues grade cards, transcripts, and provisional degree certificates. | `degree_recommendation` and `certificate_issue` are separate; BCREC never records itself as degree awarder. | [S16 §3.4][S1 §3.4] |
| F-04 | MAKAUT controls affiliation, university registration, and degree award; BCREC controls curriculum, assessment, examinations, and results for autonomous batches. | Dual-authority fields need explicit `source_of_truth_rule` per field; no single master-system assumption. | [S14][S16][S1 §3] |
| F-05 | The examination roll number is 12 digits: 3 college + 3 programme + 2 registration year + 1 duration + 3 serial. | `student.exam_roll_number` stores components and the formatted value; format is policy-driven. | [S1 §9.2.2] |
| F-06 | Governance is Society → Board of Governors → Principal, with Academic Council, Boards of Studies, Examination Committee, IQAC, and other committees. | `core` models bodies, memberships, and terms; `iam` models authority separately. | [S3][S4][S5][S6][S7][S8] |
| F-07 | One person routinely holds several roles concurrently (Principal/committee chair; Registrar/Member-Secretary; COE/Associate Professor). | `Person` is separate from `IdentityAccount`, `Student`, `FacultyProfile`, and `RoleAssignment`. No fixed user types. | [S6][S7][S8][S9] |
| F-08 | Roles have scope and validity; a new order closes the old assignment. | `role_assignment` has scope FKs, `valid_from`/`valid_to`, status, appointing authority, source document. History is retained. | [S7][S8][S9] |
| F-09 | Semester structure is 21 weeks: 18 instruction + 3 examinations, minimum 90 working days; odd from July, even from January. | `core.term` stores planned and actual dates; calendar versions are data, not constants. | [S1 §2.3.2][S9] |
| F-10 | Theory assessment is CIA-1 40 + CIA-2 40 + ESE 60; practical is PCIA 60 + PESE 40. | `assessment.scheme` and `assessment.component` store marks and weights per course version and effective term. | [S1 §19] |
| F-11 | Passing is 40% combined theory and 50% combined laboratory; grades O/E/A/B/C/D/F plus I; degree requires D in theory, C in practical/sessional, CGPA ≥ 6.0, no F/I. | Passing rules are policy parameters; `result_revision` stores the applied policy version. | [S1 §§20, 22] |
| F-12 | Result statuses are `X` (not eligible), `XP` (eligible with backlogs), `P` (passed and promoted). | Enumerated result status; no numeric substitution. | [S1 §22.5.1] |
| F-13 | PPR is theory-only, student-initiated, fee-bearing, and final; post-publication amendment is examiner-initiated, affidavit-based, within seven working days. | Two separate case types with different permissions and evidence. | [S1 §§23–24] |
| F-14 | Promotion with backlogs is allowed within `2n + 1` years; practical failure in years 1–3 causes year lag. | Progression rules are versioned and batch-scoped; practical and theory outcomes stay separate. | [S1 §§17–18] |
| F-15 | The Academic Regulations are marked **Draft, Edition 1.0**; the final approved edition was not located. | Every rule derived from S1 is stored with status `Draft`; the CIP must disclose that status. | [S1 cover][G-02] |
| F-16 | Attendance is 75% in the Academic Regulations (aggregate) and 75% separately in theory/practical in the 2026 Prospectus. | Two attendance rule variants are modelled; neither is a default gate. | [S1 §16][S2 p.55][G-01] |
| F-17 | Discipline is heard by a Central Disciplinary Committee chaired by the Principal; penalties and appeal are documented, but the appellate authority overlaps the deciding authority. | `services.disciplinary_case` and `disciplinary_action` are future; appeal body is configurable. | [S11][G-20] |
| F-18 | Placement eligibility is CGPA ≥ 6.75 or ≥ 60%, no active backlogs unless the recruiter allows, training attendance, and PPRT clearance. | Placement is future; thresholds are policy parameters. | [S10][G-21] |
| F-19 | Fees gate registration and examination in practice, but the Academic Regulations do not state the linkage. | Fee status is a separate fact; eligibility gates are configurable determinations. | [S1 §9.2.3][S20][G-08] |
| F-20 | The college ERP's data model, APIs, and identity provider are unknown. | Adapter boundary, external ID mappings, conflict queue, and no direct ERP database reads. | [G-10] |

---

## 4. Source-derived rules

The full rule set is in research §9. This design does not restate every statement. It records the rule families that require first-class storage.

| Rule family | Example IDs | Storage requirement |
|---|---|---|
| Admission and registration | ADM-01–04, REG-01–05 | Versioned rules; application and registration records reference the applied rule version. |
| Attendance | ATT-01–08 | Two variants (`aggregate`, `split`); condonation band; eligibility assessment records the variant and policy version. |
| Assessment | ASS-01–13 | Scheme/component configuration; attendance-linked components; make-up and reassessment cases. |
| Passing and grading | PAS-01–04, GRD-01–05 | Grade table, pass thresholds, percentage conversion, and result status are policy parameters. |
| Progression and award | PRO-01–04, SUP-01–05, DEG-01–03 | Batch-scoped progression rules; backlog and supplementary records; degree recommendation separate from award. |
| Correction and PPR | COR-01–03, PPR-01–05 | Separate case types; evidence documents; reviewer independence. |
| MAR and Honours | MAR-01–06 | Future achievement records; points and MOOC credits are policy parameters. |
| Discipline | DIS-01–07 | Future case/action records; committee composition; appeal body configurable. |
| Placement | PLC-01–07 | Future eligibility and drive records; thresholds configurable. |
| Service and workload | SRV-01–08 | Faculty workload allocation; role duties are reference data, not permissions. |
| Calendar and examination | CAL-01–03, EXM-01–03 | Calendar versions and milestones; exam roll format; eligibility. |
| Affiliation and compliance | AFF-01–06 | Annual affiliation records, intake limits, statutory approvals, regulatory returns. |

**Storage rule:** a rule version is immutable once used. A change creates a new version with `effective_from`, an approval reference, and a source document version. Existing records keep the version they used. Retroactive application is a separate, audited operation.

---

## 5. Recommendations and inferences adopted as design decisions

These are **not** institutional policy. They are architecture choices, and each is labelled as such in the relevant document.

| ID | Decision | Basis | Status |
|---|---|---|---|
| D-01 | Person + account + profiles, not fixed user types. | Research §7.1, F-07 | Adopted design |
| D-02 | Time-bound, scoped role assignments; permissions are separate from roles. | Research §7.4, §11.3 | Adopted design |
| D-03 | Programme → ProgrammeVersion → Batch → Curriculum → CourseVersion → Offering. | Research §10.4; avoids batch/regulation drift | Adopted design |
| D-04 | Semester registration and course registration are separate records. | Research §8.2, §10.5 | Adopted design |
| D-05 | Session-level attendance with correction history and computed summaries. | Research §8.4 | Adopted design |
| D-06 | Assessment schemes are versioned; marks are versioned; result records are versioned. | Research §9.14, §10.7 | Adopted design |
| D-07 | Results and grade cards are published artefacts with explicit approval events. | Research §11.6 | Adopted design, activation blocked by G-12 |
| D-08 | Institutional rules are versioned policy records with source, authority, scope, status, confidence. | Research §9.1 | Adopted design |
| D-09 | Documents, versions, chunks, and embeddings are separate; chunks never contain restricted personal records. | Research §13.7, §11.10 | Adopted design |
| D-10 | Internal IDs are stable; external IDs live only in mapping tables. | Research §13.1 | Adopted design |
| D-11 | Modular PostgreSQL schemas with FK integrity and RLS; modular monolith, not microservices. | Research §13; database audit | Adopted design |
| D-12 | pgvector is the target vector store, conditional on measured parity; Chroma remains the pilot fallback. | Research §13.9; measured baselines | Conditional decision |
| D-13 | Redis is deferred until measured multi-replica/cache/job need. | Database audit | Deferred |
| D-14 | Initial release records and displays published results; it does not compute or publish them. | Research §12, M10 vs M12 | Adopted scope |
| D-15 | No Initial Release foreign key points at a Future/Blocked table; the release boundary is one-way. | Migration viability; FK audit | Adopted design (OD-12) |
| D-16 | Class teaching is a time-bound `section_teacher_assignment`; student section membership is historical in `section_assignment`; current values are caches. | Research §8.2–8.3; role model | Adopted design (OD-13) |
| D-17 | Attendance is anchored to `course_registration` and the session's offering by composite foreign keys. | Research §8.4; integrity review | Adopted design (OD-14) |
| D-18 | Authority comes only from `iam.role_assignment`; operational assignments scope effect and never grant permission. | Research §7.1, §11.2 | Adopted design (OD-15) |
| D-19 | The 108 Initial entities are delivered in waves; the minimum viable term is 84 entities. | Delivery risk; dependency analysis | Adopted design (OD-17) |
| D-20 | Admission category, guardian financial/consent data, identity documents, and medical evidence are `R`/`R/G`; named-role views, encryption, no corpus ingestion. | Research §11.2–11.3; DPDP Act 2023 | Adopted design (OD-16); DPO confirmation pending |

---

## 6. Unverified assumptions

These are assumptions made to produce a concrete design. Each must be validated; none is presented as fact.

| ID | Assumption | Why it is needed | If false |
|---|---|---|---|
| A-01 | One institution row (BCREC) is sufficient for the first release. | Simplifies scoping and RLS. | Add institution scoping to every policy; multi-campus becomes a real tenancy model. |
| A-02 | College code `120` remains stable for the design horizon. | Exam roll numbers and external mappings. | Exam roll format and mappings become versioned; historical rolls remain. |
| A-03 | The first release serves one campus and the programmes listed in S14/S15. | Org and programme scope. | Add campus/branch scope to org units and offerings. |
| A-04 | The institution will use an external identity provider (OIDC/SAML) rather than building passwords. | `identity_account` stores a subject, not a password. | A local credential table is added; the person/account split remains. |
| A-05 | Initial results will be imported from the existing examination process, not computed by the new system. | M10 read-only scope. | Result computation tables activate; approval chain still required. |
| A-06 | Object storage (S3-compatible or equivalent) holds original files; PostgreSQL holds metadata and extracted text. | Document integrity and backup. | Large objects move into PostgreSQL; the metadata model is unchanged. |
| A-07 | PostgreSQL 16+ with pgvector; UTC storage, IST presentation. | Type and index choices. | pgvector version constraints change index options, not the model. |
| A-08 | The initial corpus is predominantly English with Bengali/Hindi queries and some Bengali documents. | Embedding model and language columns. | Re-evaluate embedding model and language detection. |
| A-09 | The college will accept application-level audit plus database triggers for critical tables. | Audit completeness. | Pure application audit is weaker; pure trigger audit needs context propagation. |
| A-10 | A single PostgreSQL cluster can serve ERP, CIP, and integration workloads at initial scale. | Modular monolith. | Split read replicas or services; schemas remain the boundary. |

---

## 7. Contradictions and how the design keeps them open

| ID | Contradiction | Sources | Design treatment | Blocking gap |
|---|---|---|---|---|
| C-01 | Attendance: 75% aggregate vs 75% separately in theory and practical. | S1 §16 vs S2 p.55 | `attendance.eligibility_assessment` has `rule_variant` (`aggregate`, `split`); policy versions for both; no default enforcement. | G-01 |
| C-02 | Academic Regulations marked Draft but presented as operative. | S1 cover; notices S20 | Rule status `Draft`; CIP discloses status; no rule is promoted to `Current` without an approval record. | G-02 |
| C-03 | Autonomy batch boundary: all programmes from 2024-25 vs a specific entry batch. | S1 §3 vs S20 | `batch.autonomy_status` and `batch.programme_version_id`; rules scoped by batch. | G-04 |
| C-04 | Result approval: COE administers results, but the Principal chairs the Examination Committee; no signatory is documented. | S1 §§23–24; S8 | `result_set` has approval fields; publication is a separate permission; initial mode is read-only. | G-12 |
| C-05 | Discipline appeal: the Principal decides and is also named appellate authority. | S11 | `disciplinary_action.appeal_body_type` and `appeal_decided_by` are configurable; no hard-coded Principal. | G-20 |
| C-06 | Practical ESE failure: final year gets supplementary; years 1–3 get year lag. | S1 §17.2.2 vs §17.2.3 | `result_record.year_of_study` and policy rules distinguish the cases; no merged "practical fail" rule. | G-02/G-12 |
| C-07 | Entity release conflict: `DisciplinaryCase`, `FeeHead`/`FeeStructure`/`FeeDemand`/`Payment`, `ResultApproval`, `MARRecord`, `CertificateIssue` are marked **Initial** in §10 but their modules are **Future** in §12 (M14–M16). | §10 vs §12 | This design follows §12 for activation. The entities remain in the logical catalog; only the conservative subset is in the Initial Release data dictionary. | See §9 |
| C-08 | `ResultApproval` is Initial in §10 but result processing/publication is M12 Future. | §10 vs §12 | Approval is modelled as fields on `result_set`, activated only when M12 is approved. Initial import records an external publication reference. | G-12 |
| C-09 | `CertificateIssue` is Initial in §10 but degree/certificate module is M14 Future. | §10 vs §12 | Certificate issue moves to Phase 2; the initial release does not issue certificates. | G-02 |
| C-10 | Research says "Initial release ... published-result viewing" but §10 marks `ResultRecord` Initial and M12 Future. | §12 M10 vs M12 | `result_record` is Initial for **read-only imported** results; computation tables activate in Phase 2. | A-05 |

**Rule:** where §10 and §12 disagree, the design follows the stricter release boundary in §12 and records the conflict here. It does not silently upgrade a future module to initial.

---

## 8. Gap register mapped to design

Every gap remains open. The table shows where the design absorbs the uncertainty.

| Gap | Design location that keeps it open | Activation blocked? |
|---|---|---|
| G-01 attendance rule | `attendance.eligibility_assessment.rule_variant`; two policy versions | Yes — eligibility blocking |
| G-02 draft regulations | `policy.rule_version.status`; CIP disclosure | No for recording; yes for treating as final |
| G-03 MAKAUT regulation | `policy.rule_version` with `authority = MAKAUT`; source register | No |
| G-04 batch boundary | `academic.batch.autonomy_status`; batch-scoped rules | Yes — rule application to a cohort |
| G-05 new programme admission | `academic.programme` + `batch`; intake is per year | No |
| G-06 NBA validity | `core.accreditation` (future) | No |
| G-07 BOG bye-laws | `core.governing_body`, `governance_membership` | No |
| G-08 fee gate | `student.eligibility_determination` (configurable gate) | Yes — hard gating |
| G-09 MAKAUT/NAD API | `integration.external_system`, file exchange, adapter | No — manual path |
| G-10 ERP/IdP | `integration` schema; `identity_account.subject` | No — adapter boundary |
| G-11 admission officer/refund | `admission_application`/`admission_offer` status fields | No |
| G-12 result approval | `result_set` approval fields; read-only import | Yes — publication automation |
| G-13 attendance capture | `attendance.record.source`; capture method not fixed | No |
| G-14 duty leave | `attendance.duty_leave` (future) | No |
| G-15 reassessment cap | `assessment.scheme` parameters; `mark_correction` | No |
| G-16 theory examiner | `exam` future tables; `external_person` | No |
| G-17 PPR refund | `finance` future; `ppr_case` fee reference | No |
| G-18 mentoring cadence | `faculty.mentor_assignment`; no cadence constraint | No |
| G-19 notice approval | `doc.notice_version` status/approval; configurable | Yes — automated publishing |
| G-20 discipline appeal | `disciplinary_action.appeal_*`; configurable body | Yes — automated appeal |
| G-21 placement policy | `policy` parameters; `placement_*` future | No |
| G-22 retention | `ops.retention_schedule`; no periods assumed | No — but no automated deletion |

---

## 9. Entity review

### 9.1 Duplicate concepts and how they are resolved

| Apparent duplicate | Resolution | Reason |
|---|---|---|
| `Person` vs `IdentityAccount` vs `Student` vs `FacultyProfile` | Separate. Person = human; account = credential subject; student/faculty = role-specific profiles. | One human can be student, then employee, then alumni; a shared account would leak data. |
| `RoleAssignment` vs `GovernanceMembership` | Membership records the constitutional seat and body composition; the role assignment records the authority used by the system. A membership may generate a role assignment, linked by `source_membership_id`. | Composition is an institutional fact; authorization is a system fact. |
| `Role` vs `Designation` | Role is an authority definition; designation is an employment attribute on `faculty_profile`. | Designations change without changing system permissions. |
| `Department` vs `OrgUnit` | `academic.department` references `core.org_unit`; it does not duplicate the org tree. | Departments are academic units with HODs; org units include offices and cells. |
| `Programme` vs `Batch` vs `ProgrammeVersion` | Programme is the degree; version is the regulation/curriculum binding; batch is the admitted cohort. | A programme can have several concurrent versions. |
| `Course` vs `CourseVersion` vs `CourseOffering` | Catalogue identity vs content/assessment version vs delivery in a term/section. | Prevents syllabus edits from rewriting historical results. |
| `Curriculum` vs `CourseVersion` | Curriculum is an ordered set for a programme version and term; course versions are members via `curriculum_course`. | A course version can appear in several curricula. |
| `AssessmentScheme` vs `AssessmentComponent` | Scheme is the pattern; component is a mark-bearing part. | Components change independently within a scheme version. |
| `MarkEntry` vs `ResultRecord` | Mark is an input; result is a computed, approved outcome. | Never merge; a result has many mark inputs. |
| `ResultRecord` vs `GradeCard` | Result is per student per course; grade card is per student per term. | Different publication and correction units. |
| `AttendanceSummary` vs `AttendanceEligibility` | Summary is measured attendance; eligibility is a policy decision. | A summary can be correct while eligibility is disputed. |
| `AttendanceCorrection` vs `AttendanceCondonationCase` | Correction fixes a record; condonation decides eligibility despite a shortfall. | Different actors and evidence. |
| `Notice` vs `Document` | Notice is a time-bound communication; document is the evidence file. A notice version may reference a document version. | Prevents two competing copies of the same PDF. |
| `DocumentChunk` vs `Embedding` | Chunk is text with anchors; embedding is a model output. | Multiple embedding models can coexist. |
| `Citation` vs `RetrievalLog` | Retrieval log records what was considered; citation records what was shown. | Audit and evaluation need both. |
| `PolicyVersion` (research) vs `Rule`/`RuleVersion` | Split into stable rule identity, immutable rule version, scope, and conflict. | A "policy" is a bundle of rules, not one row. |
| `StatutoryApproval` vs `AffiliationRecord` vs `Accreditation` | Approval is the instrument; affiliation is the annual programme-scope record; accreditation is a body's status. | Different validity and scope. |
| `FeeDemand` vs `Payment` | Demand is an obligation; payment is money received. One demand can have many payments. | Partial payments are normal. |
| `Scholarship` vs `ScholarshipAward` | Scheme definition vs a student's award. | One scheme, many awards. |
| `PlacementRegistration` vs `PlacementApplication` | Registration is annual opt-in; application is per drive. | Eligibility is checked once, participation many times. |
| Class teacher: `section.class_teacher_person_id` vs `iam.role_assignment` | Removed the column; `academic.section_teacher_assignment` is the time-bound operational record, and the teacher's `Faculty` role assignment supplies authority. | One source of truth; history and validity are preserved. |
| Course coordinator: `course_offering.coordinator_person_id` vs `offering_faculty` | Removed the column; `offering_faculty.role_in_offering = 'coordinator'` is the only record, with a partial unique index. | Avoids two pointers to the same appointment. |
| Mentor: a `Mentor` role vs `faculty.mentor_assignment` | No separate role; a `Faculty` assignment plus a term-bound `mentor_assignment` scopes access. | Mentoring is a duty, not a distinct authority. |
| Student section: `student.section_id` vs history | `student.section_assignment` is the history; `student.section_id` is a derived current cache. | Transfers are answerable; no lost history. |

### 9.2 Missing entities added by this design

The research inventory is strong but omits structures needed for integrity. These are added, not invented policy.

| Added entity | Why it is necessary |
|---|---|
| `iam.permission`, `iam.role_permission` | Roles alone cannot express least privilege; permissions must be assignable and auditable. |
| `student.eligibility_determination` | G-08 requires a configurable gate record rather than a hard-coded fee/attendance boolean. |
| `attendance.eligibility_assessment` | C-01 requires recording which attendance variant was applied and the computed outcome. |
| `assessment.mark_entry_version` | Mark corrections need immutable history, not only a current value. |
| `exam.result_set` | Results are approved/published as a set; per-row approval is not auditable. |
| `exam.result_revision` | Result versioning and publication require immutable revisions. |
| `exam.result_input` | A result must be traceable to the exact mark versions used. |
| `exam.grade_card_result` | A grade card is a composition of specific result revisions, not an inferred join. |
| `exam.result_import` | Initial result viewing is imported; the import needs provenance and row counts. |
| `doc.document_relation` | Supersession, corrigendum, attachment, and translation are not all expressible as "previous version". |
| `knowledge.ingestion_run` (in inventory) + `knowledge.embedding` model versioning | Provenance and re-embedding. |
| `cip.call_session` | The AI Calling Agent has voice-specific provider, consent, and recording metadata. |
| `cip.retrieval_hit`, `cip.escalation`, `cip.eval_*` | Retrieval audit, no-answer escalation, and the release-gate evaluation set. |
| `integration.entity_type` | Polymorphic mappings and audit need a controlled entity registry. |
| `integration.record_provenance` | Research §13.1 requires per-field source and timestamp. |
| `integration.outbox_event` | Reliable integration and asynchronous publication without dual writes. |
| `ops.break_glass_grant`, `ops.retention_schedule` | Research §11.9 and G-22 require controlled emergency access and retention. |
| `academic.section_teacher_assignment` | A class-teacher column cannot hold history or a validity window and bypasses the role model. |
| `student.section_assignment` | A single `student.section_id` cannot answer "which section was the student in last term" after a transfer. |

### 9.3 Relationships that were wrong or ambiguous in the overview

| Research ER statement | Problem | Corrected design |
|---|---|---|
| `ROLE_ASSIGNMENT }o--|| ORG_UNIT` | Not every assignment is department-scoped. | Scope is one of institution, org unit, programme, batch, term, course offering, governance body. Exactly one scope is populated. |
| `CURRICULUM ||--o{ COURSE_VERSION` | A course version can belong to several curricula; curriculum membership is ordered. | `academic.curriculum_course` join with `term_no`, `sequence`, `credits`, `is_mandatory`. |
| `COURSE_OFFERING ||--o{ ASSESSMENT_COMPONENT` | Components belong to a scheme, not an offering. | `assessment.scheme` → `component`; offering uses the scheme through its course version. |
| `MARK_ENTRY ||--o| RESULT_RECORD` | One result aggregates many mark entries. | `result_revision` → `result_input` → `mark_entry_version` (many-to-one). |
| `RESULT_RECORD ||--o{ GRADE_CARD` | A grade card aggregates many results. | `grade_card` → `grade_card_result` → `result_record`. |
| `DOCUMENT_CHUNK ||--o| EMBEDDING` | A chunk may have several embeddings (models/versions). | One-to-many, unique per model and model version. |
| `NOTICE ||--o{ NOTICE_AUDIENCE` | Audience belongs to a notice **version**, not the logical notice. | `notice_audience` references `notice_version`. |
| `POLICY_VERSION ||--o{ PROMOTION_DECISION` | Policy is a rule set; decisions may use several rules. | Decisions store `policy_bundle_version_id` or rule-version references; no single policy FK. |
| `PERSON ||--o| STUDENT` and `PERSON ||--o| FACULTY_PROFILE` | Optionality is correct, but a person may hold both. | Two independent optional profiles; access is by role/scope, never by profile existence. |
| `ATTENDANCE_RECORD` references student and session independently | A student could be marked for an offering they never registered in. | `attendance.record` carries `course_registration_id` and `course_offering_id`; composite FKs tie it to the student's registration and the session's offering. |
| `TIMETABLE_SLOT → ROOM` | Room is Phase 2, so an Initial Release FK would point at a non-existent table. | `venue_text` only in the Initial Release; `room_id` is added in a Phase-2 expand migration. |

### 9.4 Naming resolutions

| Ambiguous term | Canonical name | Definition |
|---|---|---|
| Course (Indian usage can mean degree) | `Programme` for the degree; `Course` for a subject/paper. | Every document states this convention. |
| Batch / section | `Batch` = admission cohort; `Section` = class group within a batch. | A batch may have several sections. |
| Semester / term | `Term` = a dated academic period; `term_type` = odd, even, summer, supplementary. | "Semester" is a term type, not a separate table. |
| Registration | Qualified: `university_registration`, `semester_registration`, `course_registration`, `exam_registration`. | No unqualified `registration` table. |
| Marks / grade | `mark` = raw score; `grade` = derived letter and grade point. | Different tables and permissions. |
| Result / grade card | `result` = per course; `grade_card` = per term. | Never used interchangeably. |
| User | `identity_account` (login) and `person` (human). | No `user` table. |
| Role | `role` (definition) and `role_assignment` (instance). | A designation is not a role. |
| Policy | `rule` + `rule_version`; a bundle is a named set. | A policy is not a single mutable row. |
| Document / notice | `document` = file/evidence; `notice` = communication. | A notice may cite a document. |
| Condonation | `attendance.condonation_case`; PPR is not condonation. | Different processes. |

---

## 10. Design principles adopted

1. **Stable identity, multiple authorities.** Internal UUIDs never change; external IDs live in `integration.external_id_mapping`.
2. **History is append-only for academic facts.** Marks, results, attendance corrections, role assignments, and policy versions are never overwritten in place.
3. **Policy is data, not code.** Thresholds, bands, marks, windows, and formats are versioned parameters.
4. **Derived data is labelled.** Summaries, percentages, SGPA/CGPA, and eligibility outcomes record their inputs and policy version.
5. **Structured data and document text never mix.** A personal-data question routes to an API; a rule question retrieves a cited document.
6. **Scope is mandatory.** A role assignment without a scope is invalid; a query without a scope is denied by RLS.
7. **Unresolved rules remain visibly unresolved.** The schema supports both variants; the UI/API must disclose the status.
8. **No cascading deletes on academic records.** Deactivation and supersession replace deletion.
9. **Integration is a boundary, not a dependency.** No foreign key points into an external ERP; mappings and provenance do.
10. **Conservative release.** A module activates only when its rule, owner, and data capture are documented.

---

## 11. What this review does not decide

- It does not choose the attendance rule (G-01).
- It does not declare the Draft Academic Regulations final (G-02).
- It does not set the autonomy batch boundary (G-04).
- It does not name the result approval signatory (G-12).
- It does not make fees a hard gate (G-08).
- It does not define notice approval or disciplinary appeal authority (G-19, G-20).
- It does not set retention periods (G-22).
- It does not assert that pgvector meets production latency; that requires a benchmark.
- It does not assert that the existing college ERP can be integrated; that requires discovery.

Those decisions are tracked in [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md), with the default design posture and the exact schema impact of each outcome.

---

## 12. Confidence statement

| Area | Confidence | Reason |
|---|---|---|
| Identity and role model | High | Multiple official orders show concurrent roles and changing incumbents. |
| Academic structure | High | Programme, course, assessment, and semester rules are documented. |
| Attendance model | Medium | Capture granularity is inferable; the threshold rule is disputed. |
| Assessment and marks | High | Component marks and weights are explicit; moderation is not. |
| Results and publication | Medium | Result statuses and PPR are explicit; approval authority is not. |
| Governance | Medium–High | Composition is documented; reserved powers and quorum are missing. |
| Finance and services | Low–Medium | Policy documents exist; data model and ERP ownership are unknown. |
| Documents and CIP | High for separation; Medium for retrieval | Requirements are clear; pgvector performance is unmeasured. |
| Integration | Low | The college ERP and IdP are undocumented. |

**Bottom line:** the design is detailed enough to implement identity, academic structure, student records, attendance, internal assessment, notices, documents, policy, audit, and result viewing without inventing relationships. It deliberately stops short of automating attendance eligibility, result publication, fee gating, discipline appeals, and ERP synchronization until the institution decides.

---

## 13. Traceability index

| Design area | Research sections | Source IDs |
|---|---|---|
| Institution and governance | §3, §6 | S3–S8, S14–S16 |
| Roles and access | §7, §11 | S6–S9, S16 |
| Academic structure | §8.2–8.3, §10.4 | S1, S9, S14 |
| Student lifecycle | §8.1–8.2, §10.5 | S1, S20 |
| Attendance | §8.4, §9.3 | S1, S2, S17 |
| Assessment | §8.5, §9.4 | S1 |
| Examination and results | §8.6–8.8, §9.5–9.7 | S1, S8, S16 |
| Faculty and mentoring | §8.9–8.10, §9.11 | S3, S12 |
| Finance and services | §8.12–8.14, §9.9–9.10 | S10–S11, S20, S22–S23 |
| Documents and notices | §8.11, §10.10 | S20, S1 |
| CIP and retrieval | §13.7–13.10, §11.10 | S1, S20, database audit |
| Integration | §13.1–13.6 | S14, S18, S20; G-09, G-10 |
| Audit and operations | §11.6, §11.9 | S16, research recommendation |
