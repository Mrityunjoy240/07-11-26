# Database Design v1 — BCREC Campus ERP + CIP

**Status:** Design complete for review. **No DDL, migration, cluster, database, or application change has been made.**
**Research basis:** [`docs/research/BCREC_MAKAUT_GOVERNANCE_AND_WORKFLOW_RESEARCH.md`](../../research/BCREC_MAKAUT_GOVERNANCE_AND_WORKFLOW_RESEARCH.md), research cut-off **6 November 2026**. This design does not repeat the institutional research; it cites it.
**Design stance:** one modular monolith on one PostgreSQL cluster, with domain-owned schemas, versioned policy, append-only academic history, and a strict separation between structured records and retrieval text.

> **A recommendation in these documents is not a BCREC policy.** Every rule that the research left unresolved is modelled as a versioned, scoped policy record with an explicit status (`Draft`, `Disputed`, `Unknown`) — never as a hidden default.

---

## 1. What this design delivers

| Deliverable | State |
|---|---|
| Bounded domain model | 12 domains, each with a schema owner and an allowed-dependency matrix |
| Entity inventory | **152** catalogued entities with purpose, PK, attributes, FKs, owner, classification, authoritative source, phase |
| Initial Release data dictionary | **108** entities with PostgreSQL-compatible columns, nullability, keys, checks, defaults, indexes, sensitivity, meaning |
| ERDs | **7** focused diagrams, **332** validated relationships, no giant diagram |
| Platform architecture | Schemas, roles, grants, FK integrity, normalization, indexing, transactions, RLS, audit, retention, backup/PITR |
| Retrieval decisions | pgvector vs ChromaDB compared against measured baselines; Redis deferred with revisit triggers |
| Release plan | Foundation / Initial ERP / Initial CIP / Future / Blocked packages with dependency graphs, delivery waves W1a–W6, and gates |
| Decision register | 22 institutional gaps, 17 design decisions, 12 technical decisions, default posture, sign-off |

---

## 2. Document map

| # | Document | What it answers | Primary audience |
|---:|---|---|---|
| 0 | `README.md` (this file) | Where to start, canonical counts, decision status | Everyone |
| 1 | [`DESIGN_REVIEW.md`](DESIGN_REVIEW.md) | What the research established vs derived vs recommended vs left open; contradictions `C-01`–`C-10`; gap map `G-01`–`G-22`; adopted design principles | Product owner, Principal, Registrar |
| 2 | [`DOMAIN_MODEL.md`](DOMAIN_MODEL.md) | The 12 bounded domains, schema ownership, dependency matrix, cross-domain invariants, rejected anti-patterns | Backend lead, architect |
| 3 | [`ENTITY_CATALOG.md`](ENTITY_CATALOG.md) | The canonical 152-entity inventory and naming resolutions | Backend lead, data steward |
| 4 | [`ERD_IDENTITY.md`](ERD_IDENTITY.md) | Person → account → role assignment → permission; governance membership vs system role | Security reviewer, backend |
| 5 | [`ERD_ACADEMIC.md`](ERD_ACADEMIC.md) | Programme → version → batch → curriculum → course → offering; student admission and registration | Backend, Registrar |
| 6 | [`ERD_STUDENT_RECORDS.md`](ERD_STUDENT_RECORDS.md) | Student identity, guardians, documents, university registration, exam roll, status history, eligibility | Registrar, backend |
| 7 | [`ERD_ATTENDANCE_ASSESSMENT.md`](ERD_ATTENDANCE_ASSESSMENT.md) | Session → record → correction → summary → eligibility; scheme → component → mark version → correction | Faculty, COE, backend |
| 8 | [`ERD_EXAMINATION_RESULTS.md`](ERD_EXAMINATION_RESULTS.md) | Import → result set → record → revision → input → grade card; future exam operations | COE, backend |
| 9 | [`ERD_KNOWLEDGE_CIP.md`](ERD_KNOWLEDGE_CIP.md) | Document version → chunk → embedding → ingestion; conversation → retrieval → citation → evaluation | CIP lead, AI engineer |
| 10 | [`ERD_INTEGRATION_AUDIT.md`](ERD_INTEGRATION_AUDIT.md) | External system → mapping → source-of-truth → sync → conflict → provenance → outbox; audit and retention | Integration lead, auditor |
| 11 | [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md) | Column-level dictionary for all 108 Initial Release entities | Database implementer |
| 12 | [`POSTGRES_ARCHITECTURE.md`](POSTGRES_ARCHITECTURE.md) | Cluster topology, roles/grants, integrity, normalization, indexes, transactions, RLS, audit, retention, backup, vectors, Redis, ERP boundary | DBA, security, platform |
| 13 | [`MVP_DEPENDENCY_MAP.md`](MVP_DEPENDENCY_MAP.md) | F/IE/IC/2/B packages, build order, parallel lanes, blocked features `B-01`–`B-14`, release gates | Delivery lead, PM |
| 14 | [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md) | `G-01`–`G-22`, `OD-01`–`OD-17`, `TD-01`–`TD-12`, default posture, impact matrix, sign-off | Principal, Registrar, COE, Finance, IT |

---

## 3. Reading order by role

| If you are… | Read in this order |
|---|---|
| **Principal / Registrar / decision maker** | `README` → `DESIGN_REVIEW` §2–3 → `OPEN_DECISIONS` §2, §4, §7 → `DOMAIN_MODEL` §1 |
| **Database implementer** | `README` → `ENTITY_CATALOG` §1 (conventions) → `DATA_DICTIONARY` §1 → the relevant ERD → `POSTGRES_ARCHITECTURE` §3–12 |
| **Backend lead** | `DOMAIN_MODEL` → `ENTITY_CATALOG` → the relevant ERDs → `MVP_DEPENDENCY_MAP` |
| **Security / audit reviewer** | `DESIGN_REVIEW` → `POSTGRES_ARCHITECTURE` §4, §9–12 → `ERD_IDENTITY` → `ERD_INTEGRATION_AUDIT` |
| **CIP / AI engineer** | `ERD_KNOWLEDGE_CIP` → `DATA_DICTIONARY` §11–12 → `POSTGRES_ARCHITECTURE` §13–14 → `OPEN_DECISIONS` OD-06–OD-08 |
| **ERP integration lead** | `POSTGRES_ARCHITECTURE` §15 → `ERD_INTEGRATION_AUDIT` → `ENTITY_CATALOG` integration section → `OPEN_DECISIONS` G-09, G-10 |
| **Delivery / PM** | `MVP_DEPENDENCY_MAP` → `OPEN_DECISIONS` §6 (impact matrix) |

---

## 4. Canonical counts

The canonical count lives in [`ENTITY_CATALOG.md` §19](ENTITY_CATALOG.md). Every other document reconciles to it.

| Domain | Schema | Catalogued | Initial Release | Future / Blocked |
|---|---|---:|---:|---:|
| 1. Identity and Access | `iam` | 8 | 8 | 0 |
| 2. Institution and Governance | `core` | 13 | 11 | 2 |
| 3. Academic Structure | `academic` | 14 | 13 | 1 |
| 4. Student Lifecycle | `student` | 15 | 13 | 2 |
| 5. Attendance | `attendance` | 7 | 6 | 1 |
| 5. Assessment | `assessment` | 8 | 7 | 1 |
| 6. Examination and Results | `exam` | 22 | 7 | 15 |
| 7. Faculty and Mentorship | `faculty` | 6 | 3 | 3 |
| 8. Finance | `finance` | 9 | 0 | 9 |
| 8. Student Services | `services` | 9 | 0 | 9 |
| 9. Notices and Documents | `doc` | 7 | 6 | 1 |
| 10. Knowledge | `knowledge` | 3 | 3 | 0 |
| 10. CIP | `cip` | 11 | 11 | 0 |
| —. Policy (cross-cutting) | `policy` | 7 | 7 | 0 |
| 11. Integration and Synchronization | `integration` | 9 | 9 | 0 |
| 12. Audit and Operations | `ops` | 4 | 4 | 0 |
| **Total** | **16 data schemas + `api`** | **152** | **108** | **44** |

**Initial Release** = Foundation (`F`) + Initial ERP (`IE`) + Initial CIP (`IC`), including the one `F/B` entity (retention schedule). The data dictionary covers exactly these 108 entities.

---

## 5. Phase legend

| Code | Phase | Meaning | Gate |
|---|---|---|---|
| `F` | Foundation | Shared platform: identity, governance, calendar, policy, documents, integration control, audit | Platform review passes (RLS leaks, audit, restore, seed) |
| `IE` | Initial ERP | Academic operations: structure, students, attendance, internal assessment, imported results, mentoring, notices | A full term can be recorded without a spreadsheet |
| `IC` | Initial CIP | Ingestion, retrieval, citations, conversations, voice, escalation, evaluation | Golden / negative / access evaluation sets pass |
| `2` | Future | Policy and ownership not yet approved; catalogued only | Separate business case per package |
| `B` | Blocked | Schema and workflow exist; activation waits on a named decision | Decision + approval reference recorded |

---

## 6. Decision status at a glance

Full register: [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md). **No institutional gap is closed.** The design is built so that indecision blocks only the specific feature, not the build.

| Group | IDs | Status | Effect on delivery |
|---|---|---|---|
| Institutional gaps | `G-01`–`G-22` | **All open** | Each maps to one blocked feature `B-01`–`B-14` |
| Attendance rule | `G-01` / OD-01 | Open | Both variants computed; no detention gate |
| Academic Regulations | `G-02` | Open (document is “Draft, Edition 1.0”) | Rules stored `Draft`; trigger blocks `Current` without approval |
| Autonomy boundary | `G-04` / OD-04 | Open | Batches default `transitional`; rules batch-scoped |
| Fee gate | `G-08` / OD-03 | Open | Recorded as a fact; advisory only |
| Result signatory | `G-12` / OD-02 | Open | Read-only imported results; no automated publication |
| Retention | `G-22` / OD-05 | Open | No delete/anonymise/archive job |
| Embedding model / dimension | OD-06 | **Open — blocks `vector(N)` DDL** | `vector(N)` not created until decided |
| Corpus scope / languages | OD-07, OD-08 | Open | Ingestion filters and model choice |
| Source of truth | OD-09 | Open | Every field defaults to `manual_review` |
| Second student career | OD-11 | Open | Unique key is `(person_id, batch_id)` |
| Release boundary | OD-12 | Decided (design) | No Initial → Future FK; `room_id` removed |
| Section teaching / transfers | OD-13 | Decided (design) | Historical assignment tables; caches only |
| Attendance registration | OD-14 | Decided (design) | Composite FKs prove enrolment |
| Assignment authority | OD-15 | Decided (design) | Authority only from `role_assignment` |
| Sensitive student data | OD-16 | Decided (design); DPO confirmation pending | `R`/`G` fields omitted from default projections |
| Release waves | OD-17 | Decided (design) | 108 logical entities; MVT = 84 through W4 |
| Technical decisions | TD-01–TD-12 | 9 decided, 1 conditional (vector store), 2 open (hosting, vendors) | Hosting and vendor choice affect operations only |

**DDL gates:** OD-06 is the only open design decision that blocks a DDL shape (`vector(N)`). The earlier second blocker, `academic.timetable_slot.room_id`, was removed from the Initial Release rather than deferred; `venue_text` carries the venue and the column returns in Phase 2. Institutional gaps block **activation**, not table creation.

---

## 7. Key design decisions in one page

| Question | Decision | Where |
|---|---|---|
| Person vs account vs profiles | One `iam.person`; zero-or-one `identity_account`; role-specific profiles (`student`, `faculty`, `staff`, `guardian`) reference the person | `ERD_IDENTITY`, `DATA_DICTIONARY` §2 |
| Fixed user types? | No. `Person` + time-bound `role_assignment` + exactly one scope | `ERD_IDENTITY`, DD IAM-07 |
| Programme versions and batches | `programme` → `programme_version` (admission-year range) → `batch` (one version) | `ERD_ACADEMIC`, DD ACD-02–04 |
| Course vs course version vs offering | Stable `course`; immutable `course_version`; `course_offering` delivers a version to a batch/section in a term | DD ACD-08–10 |
| Semester vs course registration | `semester_registration` per student/term; `course_registration` per offering | DD STU-09–10 |
| Attendance | Session + record are facts; correction preserves old/new; summary and eligibility are derived and versioned; the record is anchored to `course_registration` so an unregistered student cannot be marked | `ERD_ATTENDANCE_ASSESSMENT`, DD §6 |
| Section teaching and transfers | Time-bound `section_teacher_assignment` and `section_assignment`; `student.section_id` is a cache; authority is proven by `authority_role_assignment_id` | DD ACD-14, STU-15; ERD identity §3 |
| Assignment authority | Only `iam.role_assignment` grants permission; offering faculty, section teacher, mentor, and section assignment scope effect | `ERD_IDENTITY` §3.1–3.2; OD-15 |
| Release boundary | No Initial Release FK to a Future table; the timetable room column is Phase 2 only | `POSTGRES_ARCHITECTURE` §5.5; OD-12 |
| Sensitive student data | Category, guardian income, consent, identity documents, and medical evidence are `R`/`R/G`; named-role views, encryption, no CIP ingestion | DD §1.7; `POSTGRES_ARCHITECTURE` §9.3 |
| Implementation waves | 108 logical entities delivered in W1a/W1b/W2–W6; MVT = 84 entities through W4 | `MVP_DEPENDENCY_MAP` §8.1 |
| Assessment | Scheme → component → `mark_entry` (identity) → `mark_entry_version` (immutable); correction references versions | DD §7 |
| Results | `result_record` (identity) → `result_revision` (immutable) → `result_input` (exact marks used); publication is gated | `ERD_EXAMINATION_RESULTS`, DD §8 |
| Institutional rules | `rule` → `rule_version` (immutable) → `rule_scope`; `policy_bundle_version` makes a calculation reproducible | DD §13 |
| Documents | `document` (logical) → `document_version` (immutable, SHA-256) → relation; classification cannot be downgraded silently | DD §10 |
| Retrieval | Chunks and embeddings in PostgreSQL; structured records never mixed with document text | `ERD_KNOWLEDGE_CIP`, DD §11–12 |
| Internal vs external IDs | Internal UUIDs only; every ERP/MAKAUT identifier lives in `integration.external_id_mapping` | DD §14 |
| Polymorphic references | One documented exception, validated by `integration.entity_type` + orphan checks | `POSTGRES_ARCHITECTURE` §5.2 |
| Vector store | pgvector target, conditional on a benchmark gate; Chroma pilot fallback | `POSTGRES_ARCHITECTURE` §13 |
| Redis | Rejected at initial scale; explicit revisit triggers | `POSTGRES_ARCHITECTURE` §14 |
| Multi-application access | Separate DB roles + RLS + `api` views; no runtime role owns a table | `POSTGRES_ARCHITECTURE` §4, §9 |

---

## 8. Evidence boundary

Measured and cited:

| Measurement | Value |
|---|---|
| Embedding model in use | `all-MiniLM-L6-v2`, 384 dimensions, CPU, normalised |
| Embedding latency | p50 12.6 ms, p95 14.4 ms, p99 15.2 ms |
| Cold model load | 2.03 s |
| Exact 384-dim cosine scan | 0.09 ms @ 1k; 0.64 ms @ 10k; 10.78 ms @ 100k chunks (NumPy, not pgvector) |
| Populated Chroma store | 28 embeddings |

**Not measured, and therefore not claimed:**

- pgvector HNSW build time, query latency, or recall.
- Chroma query latency (blocked by an OpenTelemetry version conflict in the audit environment).
- BGE-M3 or any multilingual model inference.
- The college ERP data model, APIs, or identity provider.

The architecture treats these as benchmark gates, not assumptions. `POSTGRES_ARCHITECTURE.md` §13 defines the pass conditions before cutover.

---

## 9. What this design is not

- **Not DDL.** No `CREATE TABLE`, migration, extension install, or database change exists.
- **Not approved policy.** Thresholds (`75`, `40`, `50`, `6.0`, `6.75`, `120`) are stored as policy parameters, never hard-coded.
- **Not a vendor decision.** Hosting, object storage, telephony, and LLM providers remain open (`TD-11`, `TD-12`).
- **Not a rewrite of the research.** The research document is unchanged.
- **Not a commitment to a schedule.** Week ranges in `MVP_DEPENDENCY_MAP` show sequencing, not dates.

---

## 10. Consistency checks performed

| Check | Result |
|---|---|
| Domain count | 12 numbered domains + cross-cutting `policy`; matches the requirement |
| Entity count | 152 catalogued = 108 Initial + 44 Future/Blocked; all rows reconciled |
| Dictionary coverage | Exactly the 108 Initial entities; no Future entity has a column dictionary |
| Phase labels | Catalog and dictionary agree on every one of the 108 entities |
| Release-boundary FK audit | 0 Initial Release foreign keys to Future/Blocked tables; `ops.retention_schedule` (`F/B`) is Initial and a valid target |
| ERD self-containment | 7 diagrams, 332 relationships; every endpoint is defined in its own diagram |
| Mermaid syntax | Cardinality tokens valid on both sides; all code fences balanced |
| Decision references | `OD-01`–`OD-17` and `G-01`–`G-22` all resolve; no dangling IDs |
| Cross-referenced columns | Referenced columns exist in the dictionary (`student_id` on `course_registration`, uniqueness targets for composite FKs) |
| Naming consistency | `RULE_VERSION` used uniformly across ERDs; `POLICY_RULE_VERSION` removed |
| Assignment authority | No table stores a second pointer to HOD, class teacher, coordinator, or mentor |
| Sensitive fields | Every `R`/`G` field has a named-role rule and a CIP exclusion |
| Encoding | All documents are valid UTF-8 |

---

## 11. How to change this design

1. **A decision closes.** Record it in `OPEN_DECISIONS.md` with the approval reference, promote the relevant `policy.rule_version` to `Current`, configure the gate, and re-run the Gate B checklist in `MVP_DEPENDENCY_MAP.md` §9.
2. **An entity changes phase.** Update `ENTITY_CATALOG.md` §19 and the phase label in the dictionary entry; do not silently move a Future entity into the Initial Release.
3. **A new entity is needed.** Add it to the catalog with owner, classification, authority, and phase before adding columns; then add the ERD edge and the dictionary entry.
4. **A new polymorphic reference is proposed.** It requires an architecture review and an entry in `POSTGRES_ARCHITECTURE.md` §5.2. The default is a real foreign key.
5. **A threshold changes.** It changes in `policy.rule_version.parameters_json`, not in code or DDL.
6. **The design set is versioned.** This is v1. A material change produces v2; prior documents remain for traceability.

---

## 12. Traceability

Every design document cites research sections and source IDs. The top-level mapping is:

| Design area | Research basis |
|---|---|
| Governance, autonomy, dual authority | §3, §6, §7; S1, S14, S16, S20 |
| Entity inventory and domains | §10; S1–S23 |
| Rules and versioning | §9.1, §9.14–9.15; S1, S17 |
| Student lifecycle and assessment | §8.1–8.8; S1, S2 |
| Notices, documents, corpus | §8.11, §10.10, §11.10, §13.7 |
| Integration and retrieval | §13.1–13.10; G-09, G-10; database audit |
| Security, audit, retention | §11.2–11.9; G-22 |

Per-document trace tables appear at the end of each document.

---

**End of index.**

