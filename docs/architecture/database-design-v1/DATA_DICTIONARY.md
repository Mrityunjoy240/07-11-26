# Data Dictionary — Initial Release

**Scope:** the 108 entities in the Initial Release (Foundation `F`, Initial ERP `IE`, Initial CIP `IC`, and the one `F/B` retention schedule) from [`ENTITY_CATALOG.md`](ENTITY_CATALOG.md). Phase 2 and blocked entities are intentionally excluded; their columns will be specified when their policy decisions close.

**This is a logical data dictionary, not DDL.** Types are PostgreSQL-compatible; constraints and indexes are requirements for the implementation phase.

**Trace:** Research §9 (rules), §10 (entities), §11 (access), §13 (integration/CIP); source IDs and gap IDs as cited per entity.

---

## 1. How to read this dictionary

### 1.1 Entry format

Each entity has:

- **Purpose**, **owner**, **classification**, **phase**, **source trace**.
- **PK** and **FKs**.
- **Unique / checks** and **indexes** specific to the entity.
- A column table: name, PostgreSQL type, nullability, key/constraint, default, sensitivity, business meaning.

### 1.2 Standard column blocks

To avoid repeating identical audit columns 108 times, the following blocks are defined once and referenced by name. A table that says `+ AUDIT_MUTABLE` includes exactly these columns.

| Block | Columns | Types / defaults | Notes |
|---|---|---|---|
| `AUDIT_MUTABLE` | `created_at`, `created_by`, `updated_at`, `updated_by`, `row_version` | `created_at timestamptz NOT NULL DEFAULT now()`; `created_by uuid NULL`; `updated_at timestamptz NOT NULL DEFAULT now()`; `updated_by uuid NULL`; `row_version integer NOT NULL DEFAULT 1` | `created_by`/`updated_by` FK → `iam.identity_account(account_id)`. `row_version` increments on update for optimistic concurrency. |
| `AUDIT_IMMUTABLE` | `created_at`, `created_by` | `created_at timestamptz NOT NULL DEFAULT now()`; `created_by uuid NULL` | Used for append-only rows. No update columns. |
| `VALIDITY` | `valid_from`, `valid_to` | `valid_from date NOT NULL`; `valid_to date NULL` | `CHECK (valid_to IS NULL OR valid_to > valid_from)`. |
| `PROVENANCE` | `source_system_id`, `sync_run_id`, `observed_at` | `uuid NULL`, `uuid NULL`, `timestamptz NULL` | Only where a row may be imported; otherwise `integration.record_provenance` holds field provenance. |

**Every table** has an implicit primary-key index. **Every FK column** gets a btree index unless the entry says otherwise. **Every unique constraint** is listed explicitly.

### 1.3 Type conventions

| Need | Type | Rule |
|---|---|---|
| Identifier | `uuid` | PK default `gen_random_uuid()`; UUIDv7 preferred where available. |
| Human code | `text` | Case-insensitive uniqueness via `lower()` expression index. |
| Short label | `text` | `varchar(n)` only for a hard external limit. |
| Money | `numeric(12,2)` | INR; never `float`. |
| Percentage | `numeric(5,2)` | `CHECK (0 <= x AND x <= 100)`. |
| Marks | `numeric(6,2)` | `CHECK (x >= 0)`. |
| Date | `date` | Calendar date, no timezone. |
| Timestamp | `timestamptz` | UTC storage; IST presentation. |
| Duration | `integer` | Seconds or minutes; the column name states which. |
| Structured parameters | `jsonb` | Only for policy parameters, snapshots, and audit before/after; never for core relational data. |
| Vector | `vector(1024)` | pgvector; dimension fixed at deployment (OD-06). |
| Hash | `text` | Lowercase hex SHA-256 (64 chars) with `CHECK (length(sha256) = 64)`. |
| Network | `inet` | IP address for audit. |

### 1.4 Sensitivity codes

| Code | Meaning | Handling |
|---|---|---|
| `P` | Public | No restriction; still versioned and audited. |
| `I` | Internal | Authenticated staff/students; not public. |
| `C` | Confidential | Need-to-know role + scope; encrypted at rest; access logged. |
| `R` | Restricted | Named roles only; field-level encryption or masking; strict audit. |
| `G` | Regulated personal data | Statutory basis only; minimize, mask by default, record consent/legal basis. |

A column may carry **two codes** (for example `R/G`) when it is both restricted-access and regulated. Both handling rules then apply: named-role access **and** a recorded legal basis. A table-level class is the highest class of any column, not a substitute for the per-column code.

### 1.5 Common checks and indexes

- Status columns use `CHECK (status IN (...))` with the values stated in the entity.
- Effective-date columns use `CHECK (effective_to IS NULL OR effective_to > effective_from)`.
- All `*_pct` columns use `CHECK (x >= 0 AND x <= 100)`.
- All `*_amount` columns use `CHECK (x >= 0)`.
- All `*_count` columns use `CHECK (x >= 0)`.
- Partial unique indexes enforce "one current row" (e.g. `WHERE is_current`).
- `oid`/`bigint` sequences are not used for PKs; human serials use a separate `bigint GENERATED ALWAYS AS IDENTITY` where required.
- Full-text search uses `tsvector` generated columns + GIN; fuzzy names use `pg_trgm` GIN on `lower(name)`.
- No table uses `ON DELETE CASCADE` for academic records. Reference data may use `RESTRICT` or `NO ACTION`.

### 1.6 RLS and audit defaults

- RLS is enabled on every table in `student`, `attendance`, `assessment`, `exam`, `finance`, `services`, `doc`, `knowledge`, `cip`, and on `iam.person`, `iam.person_contact`, `iam.identity_account`, `iam.role_assignment`.
- RLS policies call `iam.current_person_id()` and `iam.has_permission(permission_code, scope_type, scope_id)`; they do not hard-code role names.
- Every mutable table writes an `ops.audit_event` for create/update/delete through the application service. Critical tables (`result_revision`, `mark_entry_version`, `role_assignment`, `document_version`, `policy.rule_version`, `fee_payment`) also have a database trigger that rejects update/delete after the row is sealed.

### 1.7 Special-category student data

The following fields are the highest-risk personal data in the Initial Release. The matrix is the access contract; a role name alone does not grant access, and none of these fields may enter the CIP corpus or an unmasked analytics extract.

| Data element | Table.column | Class | Who may read | Handling |
|---|---|---|---|---|
| Admission / reservation category | `student.admission_application.category`; `student.student.category` | `R/G` | Admission verification, Registrar, DPO/Legal; aggregate reporting only | Field-level encryption; named-role view; legal basis recorded; never free text; no CIP ingestion. |
| Category / income certificate | `student.student_document.document_type IN (category_certificate, income_certificate)`; linked `doc.document_version` | `R/G` | Admission verification, Registrar, Scholarship Cell, DPO; student sees own metadata | Encrypted object storage; signed short-lived URL; access logged; no preview in shared screens; no CIP ingestion. |
| Guardian contact | `iam.person_contact` for a guardian person; `student.student_guardian` | `C` | Registrar, guardian, class teacher (limited), emergency contact | Consent-gated; relationship-scoped; no bulk export. |
| Guardian income band | `student.guardian.annual_income_band` | `R` | Scholarship Cell, Finance, Registrar; not general faculty | Banded values only (never exact income); masked in default projections. |
| Identity documents | `student.student_document` and the linked `doc.document_version` | `R/G` | Registrar/verification desk, DPO; student sees own document | Encrypted, watermarked, access-logged; `id_proof` and `medical` are named-role only; no CIP ingestion. |
| Medical evidence | `student.student_document` (`medical`); `attendance.condonation_case.grounds` | `R` | Medical officer, Registrar, Academic Council case members | Need-to-know case view; never shown to general faculty; no CIP ingestion. |
| Photograph | `iam.person.photo_uri`; `student.student.photo_uri` | `C` | Self, Registrar, identity-card issuer, class teacher | Signed URL; no public bucket; no face embedding in the Initial Release. |
| Blood group | `iam.person.blood_group` | `R` | Emergency responder, medical officer, Registrar | Emergency-only view; masked elsewhere. |
| Gender | `iam.person.gender` | `G` | Registrar/HR; aggregate reporting | Legal basis; optional/prefer-not-to-say supported. |
| Date of birth | `iam.person.date_of_birth` | `C` | Self, Registrar, HR, authorised verifier | Masked in broad projections. |

**Rule:** if a field is `R` or `G`, the default projection omits it, the CIP ingestion job rejects the source document, and an access is written to `ops.audit_event` with the role assignment used. The detailed policy is in `POSTGRES_ARCHITECTURE.md` §9.3 and `ERD_STUDENT_RECORDS.md` §4.

---

## 2. Identity and Access (`iam`)

**Trace:** Research §7, §11.2–11.3; S6–S9; F-07, F-08.

### IAM-01 `iam.person`

**Purpose:** one human being across all roles. **Owner:** Registrar/HR. **Class:** C. **Phase:** F.
**PK:** `person_id`. **FKs:** none.
**Unique / checks:** no unique name; `date_of_birth < current_date` enforced by trigger; `deceased_flag` does not disable history.
**Indexes:** `gin (lower(legal_name) gin_trgm_ops)` for search; `btree (date_of_birth)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| person_id | uuid | NO | PK | gen_random_uuid() | C | Stable human identifier. |
| legal_name | text | NO | length 1–200 | — | C | Name as in official records. |
| preferred_name | text | YES | length ≤ 100 | NULL | C | Display name. |
| date_of_birth | date | YES | `< current_date` (trigger) | NULL | C | Date of birth. |
| gender | text | YES | IN (female, male, other, prefer_not_to_say, unknown) | NULL | G | Gender, only where required. |
| blood_group | text | YES | IN (A+, A-, B+, B-, AB+, AB-, O+, O-, unknown) | NULL | C | Emergency medical use. |
| photo_uri | text | YES | object-storage URI | NULL | C | Portrait. |
| deceased_flag | boolean | NO | — | false | C | Prevents new logins/communications. |
| notes | text | YES | length ≤ 2000 | NULL | R | Registrar-only remarks. |
+ `AUDIT_MUTABLE`.

### IAM-02 `iam.person_contact`

**Purpose:** multiple typed contact points with verification. **Owner:** Registrar. **Class:** C. **Phase:** F.
**PK:** `person_contact_id`. **FK:** `person_id → iam.person`.
**Unique / checks:** one primary per `(person_id, contact_type)` where `valid_to IS NULL`; `valid_to > valid_from`; email/phone format validated by the application and a conservative `CHECK`.
**Indexes:** `btree (person_id, contact_type)`; `btree (lower(value))` for lookup; partial unique primary index.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| person_contact_id | uuid | NO | PK | gen_random_uuid() | C | Contact row. |
| person_id | uuid | NO | FK → iam.person | — | C | Owner. |
| contact_type | text | NO | IN (email, phone, mobile, whatsapp, address, emergency, other) | — | C | Type. |
| label | text | YES | length ≤ 50 | NULL | C | e.g. "personal", "work". |
| value | text | NO | length 1–500 | — | C | Email, phone, or address text. |
| is_primary | boolean | NO | — | false | C | Preferred for this type. |
| is_verified | boolean | NO | — | false | C | Verification status. |
| verified_at | timestamptz | YES | — | NULL | C | When verified. |
| valid_from | date | NO | — | current_date | C | Start of validity. |
| valid_to | date | YES | `> valid_from` | NULL | C | End of validity. |
+ `AUDIT_MUTABLE`.

### IAM-03 `iam.identity_account`

**Purpose:** login identity linked to a person and an external IdP subject. **Owner:** ERP Administrator. **Class:** C. **Phase:** F.
**PK:** `account_id`. **FK:** `person_id → iam.person`.
**Unique / checks:** unique `(idp_code, subject)`; unique `lower(username)` where not null; unique `(person_id, idp_code)` where `status = 'active'`; `account_type` in (interactive, service, guardian, alumni).
**Indexes:** `btree (person_id)`; `btree (status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| account_id | uuid | NO | PK | gen_random_uuid() | C | Login identity. |
| person_id | uuid | NO | FK → iam.person | — | C | Human owner. |
| idp_code | text | NO | length ≤ 50 | — | C | Identity provider code. |
| subject | text | NO | length ≤ 255 | — | C | Immutable IdP subject. |
| username | text | YES | unique lower() where not null | NULL | C | Login name. |
| email | text | YES | — | NULL | C | Login email. |
| account_type | text | NO | IN (interactive, service, guardian, alumni) | interactive | C | Account class. |
| mfa_enabled | boolean | NO | — | false | C | MFA state. |
| status | text | NO | IN (active, disabled, locked, pending) | pending | C | Account state. |
| last_login_at | timestamptz | YES | — | NULL | C | Last successful login. |
| disabled_at | timestamptz | YES | — | NULL | C | When disabled. |
| disabled_reason | text | YES | length ≤ 500 | NULL | R | Why disabled. |
+ `AUDIT_MUTABLE`.

### IAM-04 `iam.role`

**Purpose:** role definition. **Owner:** ERP Administrator. **Class:** I. **Phase:** F.
**PK:** `role_id`. **FKs:** none.
**Unique / checks:** unique `lower(role_code)`; `category` in (governance, executive, academic, student, system); `is_system_role` cannot be deleted.
**Indexes:** `btree (category, is_active)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| role_id | uuid | NO | PK | gen_random_uuid() | I | Role identity. |
| role_code | text | NO | unique lower(); length ≤ 50 | — | I | e.g. `HOD`, `COE`. |
| name | text | NO | length ≤ 100 | — | I | Display name. |
| category | text | NO | IN (governance, executive, academic, student, system) | — | I | Role family. |
| description | text | YES | length ≤ 1000 | NULL | I | Purpose. |
| default_scope_type | text | YES | IN (institution, org_unit, programme, batch, term, course_offering, governance_body) | NULL | I | Default scope. |
| is_system_role | boolean | NO | — | false | I | Protected from deletion. |
| is_active | boolean | NO | — | true | I | Available for new assignments. |
+ `AUDIT_MUTABLE`.

### IAM-05 `iam.permission`

**Purpose:** atomic action that can be granted. **Owner:** ERP Administrator. **Class:** I. **Phase:** F.
**PK:** `permission_id`. **FKs:** none.
**Unique / checks:** unique `lower(permission_code)`; `risk_level` in (low, medium, high, critical).
**Indexes:** `btree (resource, action)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| permission_id | uuid | NO | PK | gen_random_uuid() | I | Permission identity. |
| permission_code | text | NO | unique lower(); length ≤ 100 | — | I | e.g. `result.publish`. |
| resource | text | NO | length ≤ 50 | — | I | Resource name. |
| action | text | NO | length ≤ 50 | — | I | Verb. |
| description | text | YES | length ≤ 500 | NULL | I | What it allows. |
| risk_level | text | NO | IN (low, medium, high, critical) | medium | I | Review priority. |
| is_active | boolean | NO | — | true | I | Grantable. |
+ `AUDIT_MUTABLE`.

### IAM-06 `iam.role_permission`

**Purpose:** role-to-permission grant. **Owner:** ERP Administrator. **Class:** I. **Phase:** F.
**PK:** `role_permission_id`. **FKs:** `role_id → iam.role`; `permission_id → iam.permission`.
**Unique / checks:** unique `(role_id, permission_id)`.
**Indexes:** `btree (permission_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| role_permission_id | uuid | NO | PK | gen_random_uuid() | I | Grant row. |
| role_id | uuid | NO | FK → iam.role | — | I | Role. |
| permission_id | uuid | NO | FK → iam.permission | — | I | Permission. |
| granted_at | timestamptz | NO | — | now() | I | When granted. |
| granted_by | uuid | YES | FK → iam.identity_account | NULL | I | Who granted. |
+ `AUDIT_MUTABLE`.

### IAM-07 `iam.role_assignment`

**Purpose:** time-bound authority held by a person in exactly one scope. **Owner:** Registrar/Principal. **Class:** C. **Phase:** F.
**PK:** `role_assignment_id`. **FKs:** `person_id`, `role_id`, scope FKs, `source_document_version_id`, `delegated_from_assignment_id`, `source_membership_id`.
**Unique / checks:** exactly one scope FK is non-null and equals `scope_key`; `valid_to > valid_from`; status in (active, suspended, expired, revoked); partial unique `(person_id, role_id, scope_type, scope_key) WHERE status = 'active'`.
**Indexes:** `btree (person_id, status)`; `btree (role_id)`; `btree (scope_type, scope_key)`; `btree (valid_to)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| role_assignment_id | uuid | NO | PK | gen_random_uuid() | C | Assignment identity. |
| person_id | uuid | NO | FK → iam.person | — | C | Holder. |
| role_id | uuid | NO | FK → iam.role | — | C | Role. |
| scope_type | text | NO | IN (institution, org_unit, programme, batch, term, course_offering, governance_body) | — | C | Scope kind. |
| scope_key | uuid | NO | equals the populated scope FK | — | C | Normalised scope ID for uniqueness. |
| institution_id | uuid | YES | FK → core.institution | NULL | C | Institution scope. |
| org_unit_id | uuid | YES | FK → core.org_unit | NULL | C | Department/office scope. |
| programme_id | uuid | YES | FK → academic.programme | NULL | C | Programme scope. |
| batch_id | uuid | YES | FK → academic.batch | NULL | C | Batch scope. |
| term_id | uuid | YES | FK → core.term | NULL | C | Term scope. |
| course_offering_id | uuid | YES | FK → academic.course_offering | NULL | C | Offering scope. |
| governance_body_id | uuid | YES | FK → core.governance_body | NULL | C | Body scope. |
| valid_from | date | NO | — | current_date | C | Start. |
| valid_to | date | YES | `> valid_from` | NULL | C | End. |
| status | text | NO | IN (active, suspended, expired, revoked) | active | C | State. |
| appointing_authority | text | YES | length ≤ 200 | NULL | C | Who appointed. |
| source_document_version_id | uuid | YES | FK → doc.document_version | NULL | C | Order/letter. |
| delegated_from_assignment_id | uuid | YES | FK → iam.role_assignment | NULL | C | Delegation source. |
| source_membership_id | uuid | YES | FK → core.governance_membership | NULL | C | Seat that generated this. |
| approved_by | uuid | YES | FK → iam.person | NULL | C | Approver. |
| approved_at | timestamptz | YES | — | NULL | C | Approval time. |
+ `AUDIT_MUTABLE`.

### IAM-08 `iam.delegation`

**Purpose:** temporary transfer of authority with limits. **Owner:** Principal. **Class:** C. **Phase:** F.
**PK:** `delegation_id`. **FKs:** `from_assignment_id`, `to_assignment_id → iam.role_assignment`; `approved_by → iam.person`.
**Unique / checks:** `from_assignment_id <> to_assignment_id`; `valid_to > valid_from`; status in (active, expired, revoked).
**Indexes:** `btree (to_assignment_id, status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| delegation_id | uuid | NO | PK | gen_random_uuid() | C | Delegation row. |
| from_assignment_id | uuid | NO | FK → iam.role_assignment | — | C | Delegator. |
| to_assignment_id | uuid | NO | FK → iam.role_assignment | — | C | Delegate. |
| reason | text | NO | length 10–2000 | — | C | Why. |
| valid_from | timestamptz | NO | — | now() | C | Start. |
| valid_to | timestamptz | NO | `> valid_from` | — | C | End. |
| limits_json | jsonb | YES | — | '{}' | C | Value/scope limits. |
| status | text | NO | IN (active, expired, revoked) | active | C | State. |
| approved_by | uuid | YES | FK → iam.person | NULL | C | Approver. |
| approved_at | timestamptz | YES | — | NULL | C | Approval time. |
+ `AUDIT_MUTABLE`.

---

## 3. Institution and Governance (`core`)

**Trace:** Research §3, §6, §9.13; S3–S8, S14–S16.

### GOV-01 `core.institution`

**Purpose:** root legal entity. **Owner:** Principal/Registrar. **Class:** P. **Phase:** F.
**PK:** `institution_id`. **FK:** `parent_institution_id → core.institution` (self, nullable).
**Unique / checks:** unique `college_code`; autonomy dates ordered; `timezone` default `Asia/Kolkata`; `currency` default `INR`.
**Indexes:** unique `lower(college_code)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| institution_id | uuid | NO | PK | gen_random_uuid() | P | Institution identity. |
| legal_name | text | NO | length ≤ 300 | — | P | Dr. B. C. Roy Engineering College. |
| short_name | text | NO | length ≤ 50 | — | P | BCREC. |
| college_code | text | NO | unique lower(); 3 chars | — | P | `120`. |
| aicte_id | text | YES | length ≤ 50 | NULL | P | AICTE identifier. |
| address_line1 | text | YES | length ≤ 200 | NULL | P | Campus address. |
| city | text | YES | length ≤ 100 | NULL | P | Durgapur. |
| district | text | YES | length ≤ 100 | NULL | P | Paschim Bardhaman. |
| state | text | YES | length ≤ 100 | NULL | P | West Bengal. |
| postal_code | text | YES | length ≤ 10 | NULL | P | 713206. |
| country | text | YES | length ≤ 100 | 'India' | P | Country. |
| affiliation_university | text | YES | length ≤ 200 | NULL | P | MAKAUT. |
| autonomy_status | text | NO | IN (autonomous, affiliated, transitional) | affiliated | P | Current status. |
| autonomy_from | date | YES | — | NULL | P | Start. |
| autonomy_to | date | YES | `> autonomy_from` | NULL | P | End. |
| timezone | text | NO | — | 'Asia/Kolkata' | P | Presentation timezone. |
| currency | text | NO | 3 chars | 'INR' | P | Money currency. |
| parent_institution_id | uuid | YES | FK → core.institution | NULL | P | Group parent, if any. |
| status | text | NO | IN (active, inactive) | active | P | State. |
+ `AUDIT_MUTABLE`.

### GOV-02 `core.society`

**Purpose:** sponsoring body. **Owner:** Registrar. **Class:** I. **Phase:** F.
**PK:** `society_id`. **FKs:** `institution_id`, `rules_document_version_id`.
**Unique / checks:** unique `registration_no` where not null.
**Indexes:** `btree (institution_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| society_id | uuid | NO | PK | gen_random_uuid() | I | Society identity. |
| institution_id | uuid | NO | FK → core.institution | — | I | Sponsored institution. |
| name | text | NO | length ≤ 300 | — | I | Legal name. |
| registration_no | text | YES | unique where not null | NULL | I | Society registration. |
| registered_on | date | YES | — | NULL | I | Registration date. |
| address | text | YES | length ≤ 500 | NULL | I | Registered address. |
| rules_document_version_id | uuid | YES | FK → doc.document_version | NULL | I | Bye-laws/rules. |
| status | text | NO | IN (active, inactive) | active | I | State. |
+ `AUDIT_MUTABLE`.

### GOV-03 `core.org_unit`

**Purpose:** org tree. **Owner:** Principal/HR. **Class:** I. **Phase:** F.
**PK:** `org_unit_id`. **FKs:** `institution_id`, `parent_org_unit_id`, `head_person_id`.
**Unique / checks:** unique `(institution_id, code)`; `parent_org_unit_id <> org_unit_id`; `path` maintained by trigger.
**Indexes:** `btree (parent_org_unit_id)`; `btree (path text_pattern_ops)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| org_unit_id | uuid | NO | PK | gen_random_uuid() | I | Org unit. |
| institution_id | uuid | NO | FK → core.institution | — | I | Institution. |
| parent_org_unit_id | uuid | YES | FK → core.org_unit; ≠ self | NULL | I | Parent. |
| code | text | NO | unique per institution; length ≤ 30 | — | I | Short code. |
| name | text | NO | length ≤ 200 | — | I | Display name. |
| unit_type | text | NO | IN (institution, department, office, cell, support, committee_support) | — | I | Kind. |
| path | text | YES | materialized path | NULL | I | Tree path. |
| head_person_id | uuid | YES | FK → iam.person | NULL | I | Head. |
| cost_centre | text | YES | length ≤ 50 | NULL | I | Finance code. |
| sort_order | integer | NO | ≥ 0 | 0 | I | Display order. |
| is_active | boolean | NO | — | true | I | Available. |
+ `AUDIT_MUTABLE`.

### GOV-04 `core.governance_body`

**Purpose:** statutory body or committee. **Owner:** Principal/Registrar. **Class:** I. **Phase:** F.
**PK:** `governance_body_id`. **FKs:** `institution_id`, `scope_org_unit_id`, `constitution_order_version_id`, `chair_person_id`, `secretary_person_id`.
**Unique / checks:** unique `(institution_id, body_code, term_start)`; `term_end > term_start`; `quorum_min >= 1`; `body_type` in the stated list.
**Indexes:** `btree (body_type, is_statutory)`; `btree (term_end)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| governance_body_id | uuid | NO | PK | gen_random_uuid() | I | Body identity. |
| institution_id | uuid | NO | FK → core.institution | — | I | Institution. |
| body_code | text | NO | length ≤ 50 | — | I | Code. |
| name | text | NO | length ≤ 200 | — | I | Name. |
| body_type | text | NO | IN (BOG, AcademicCouncil, FinanceCommittee, BoardOfStudies, ExaminationCommittee, IQAC, Disciplinary, AntiRagging, ICC, Grievance, MAR, MOOCs, Library, Purchase, RD, TP, other) | — | I | Type. |
| is_statutory | boolean | NO | — | false | I | UGC statutory body. |
| scope_org_unit_id | uuid | YES | FK → core.org_unit | NULL | I | Department scope (BoS). |
| term_start | date | NO | — | — | I | Term start. |
| term_end | date | YES | `> term_start` | NULL | I | Term end. |
| constitution_order_version_id | uuid | YES | FK → doc.document_version | NULL | I | Order. |
| chair_person_id | uuid | YES | FK → iam.person | NULL | I | Chair. |
| secretary_person_id | uuid | YES | FK → iam.person | NULL | I | Secretary. |
| quorum_min | integer | YES | ≥ 1 | NULL | I | Quorum. |
| status | text | NO | IN (constituted, active, dissolved, superseded) | constituted | I | State. |
+ `AUDIT_MUTABLE`.

### GOV-05 `core.governance_membership`

**Purpose:** a person's seat on a body. **Owner:** Registrar. **Class:** C. **Phase:** F.
**PK:** `governance_membership_id`. **FKs:** body, person, role assignment, order document.
**Unique / checks:** unique `(governance_body_id, person_id, valid_from)`; `valid_to > valid_from`.
**Indexes:** `btree (person_id, valid_to)`; `btree (governance_body_id, status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| governance_membership_id | uuid | NO | PK | gen_random_uuid() | C | Seat. |
| governance_body_id | uuid | NO | FK → core.governance_body | — | C | Body. |
| person_id | uuid | NO | FK → iam.person | — | C | Member. |
| role_in_body | text | NO | IN (chair, member, member_secretary, invitee, nominee, co_opted) | member | C | Capacity. |
| valid_from | date | NO | — | — | C | Start. |
| valid_to | date | YES | `> valid_from` | NULL | C | End. |
| order_reference | text | YES | length ≤ 100 | NULL | C | Order number. |
| order_document_version_id | uuid | YES | FK → doc.document_version | NULL | C | Order evidence. |
| source_role_assignment_id | uuid | YES | FK → iam.role_assignment | NULL | C | Generated authority. |
| status | text | NO | IN (active, expired, revoked) | active | C | State. |
+ `AUDIT_MUTABLE`.

### GOV-06 `core.statutory_approval`

**Purpose:** AICTE/MAKAUT/UGC/NBA/NAAC instrument. **Owner:** Registrar. **Class:** I. **Phase:** F.
**PK:** `statutory_approval_id`. **FKs:** institution, programme (nullable), document version.
**Unique / checks:** unique `(approval_type, authority, reference_no)`; `valid_to > valid_from`; `scope_type` matches the populated scope.
**Indexes:** `btree (approval_type, valid_to)`; `btree (programme_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| statutory_approval_id | uuid | NO | PK | gen_random_uuid() | I | Approval. |
| institution_id | uuid | NO | FK → core.institution | — | I | Institution. |
| programme_id | uuid | YES | FK → academic.programme | NULL | I | Programme scope. |
| approval_type | text | NO | IN (aicte_eoa, makaut_affiliation, ugc_autonomy, nba, naac, state, other) | — | I | Type. |
| authority | text | NO | length ≤ 100 | — | I | Issuer. |
| reference_no | text | NO | length ≤ 100 | — | I | Number. |
| approved_on | date | NO | — | — | I | Issue date. |
| valid_from | date | NO | — | — | I | Valid from. |
| valid_to | date | YES | `> valid_from` | NULL | I | Valid to. |
| scope_type | text | NO | IN (institution, programme) | — | I | Scope. |
| conditions_text | text | YES | length ≤ 10000 | NULL | I | Conditions. |
| status | text | NO | IN (current, expired, withdrawn, draft) | current | I | State. |
| document_version_id | uuid | YES | FK → doc.document_version | NULL | I | Evidence. |
+ `AUDIT_MUTABLE`.

### GOV-07 `core.affiliation_record`

**Purpose:** annual course-wise affiliation and intake. **Owner:** Registrar. **Class:** I. **Phase:** F.
**PK:** `affiliation_record_id`. **FKs:** programme, academic year, statutory approval.
**Unique / checks:** unique `(programme_id, academic_year_id)`; `intake_approved >= 0`; `intake_admitted >= 0`; `intake_admitted <= intake_approved` unless the policy permits a transition.
**Indexes:** `btree (academic_year_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| affiliation_record_id | uuid | NO | PK | gen_random_uuid() | I | Record. |
| programme_id | uuid | NO | FK → academic.programme | — | I | Programme. |
| academic_year_id | uuid | NO | FK → core.academic_year | — | I | Year. |
| statutory_approval_id | uuid | YES | FK → core.statutory_approval | NULL | I | Order. |
| intake_approved | integer | NO | ≥ 0 | 0 | I | Approved intake. |
| intake_admitted | integer | YES | ≥ 0; ≤ approved unless policy allows | NULL | I | Actual intake. |
| affiliation_status | text | NO | IN (approved, conditional, withdrawn, pending) | pending | I | Status. |
| conditions_text | text | YES | length ≤ 10000 | NULL | I | Conditions. |
| order_reference | text | YES | length ≤ 100 | NULL | I | Reference. |
+ `AUDIT_MUTABLE`.

### GOV-08 `core.academic_year`

**Purpose:** named academic session. **Owner:** Registrar. **Class:** P. **Phase:** F.
**PK:** `academic_year_id`. **FK:** `institution_id`.
**Unique / checks:** unique `(institution_id, label)`; `end_date > start_date`.
**Indexes:** `btree (start_date, end_date)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| academic_year_id | uuid | NO | PK | gen_random_uuid() | P | Year identity. |
| institution_id | uuid | NO | FK → core.institution | — | P | Institution. |
| label | text | NO | unique per institution; `YYYY-YY` | — | P | e.g. 2026-27. |
| start_date | date | NO | — | — | P | Start. |
| end_date | date | NO | `> start_date` | — | P | End. |
| status | text | NO | IN (planned, active, closed) | planned | P | State. |
+ `AUDIT_MUTABLE`.

### GOV-09 `core.term`

**Purpose:** dated academic period. **Owner:** COE/Registrar. **Class:** I. **Phase:** F.
**PK:** `term_id`. **FK:** `academic_year_id`.
**Unique / checks:** unique `(academic_year_id, term_type, term_no)`; date order; `working_days_planned >= 0`.
**Indexes:** `btree (academic_year_id, term_type)`; `btree (start_date, end_date)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| term_id | uuid | NO | PK | gen_random_uuid() | I | Term identity. |
| academic_year_id | uuid | NO | FK → core.academic_year | — | I | Year. |
| term_type | text | NO | IN (odd, even, summer, supplementary, winter) | — | I | Type. |
| term_no | smallint | NO | 1–8 | — | I | Sequence. |
| start_date | date | NO | — | — | I | Start. |
| end_date | date | NO | `> start_date` | — | I | End. |
| instruction_start | date | YES | — | NULL | I | Teaching start. |
| instruction_end | date | YES | — | NULL | I | Teaching end. |
| exam_start | date | YES | — | NULL | I | Exams start. |
| exam_end | date | YES | — | NULL | I | Exams end. |
| working_days_planned | integer | YES | ≥ 0 | NULL | I | Planned days. |
| working_days_actual | integer | YES | ≥ 0 | NULL | I | Actual days. |
| status | text | NO | IN (planned, active, closed) | planned | I | State. |
+ `AUDIT_MUTABLE`.

### GOV-10 `core.academic_calendar`

**Purpose:** versioned calendar for a term. **Owner:** COE. **Class:** I. **Phase:** F.
**PK:** `academic_calendar_id`. **FKs:** term, approver, source document.
**Unique / checks:** unique `(term_id, version_no)`; partial unique one `approved` and active calendar per term.
**Indexes:** `btree (term_id, status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| academic_calendar_id | uuid | NO | PK | gen_random_uuid() | I | Calendar version. |
| term_id | uuid | NO | FK → core.term | — | I | Term. |
| version_no | integer | NO | ≥ 1 | 1 | I | Version. |
| status | text | NO | IN (draft, provisional, approved, superseded) | draft | I | State. |
| approved_by | uuid | YES | FK → iam.person | NULL | I | Approver. |
| approved_at | timestamptz | YES | — | NULL | I | Approval time. |
| change_note | text | YES | length ≤ 2000 | NULL | I | What changed. |
| source_document_version_id | uuid | YES | FK → doc.document_version | NULL | I | Source PDF. |
+ `AUDIT_MUTABLE`.

### GOV-11 `core.calendar_milestone`

**Purpose:** dated activity in a calendar. **Owner:** COE. **Class:** I. **Phase:** F.
**PK:** `calendar_milestone_id`. **FK:** `academic_calendar_id`.
**Unique / checks:** unique `(academic_calendar_id, milestone_code)`; `planned_end >= planned_start`; `actual_end >= actual_start` when both present.
**Indexes:** `btree (academic_calendar_id, planned_start)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| calendar_milestone_id | uuid | NO | PK | gen_random_uuid() | I | Milestone. |
| academic_calendar_id | uuid | NO | FK → core.academic_calendar | — | I | Calendar. |
| milestone_code | text | NO | length ≤ 50 | — | I | e.g. `CIA1_SUBMIT`. |
| label | text | NO | length ≤ 200 | — | I | Display label. |
| planned_start | date | YES | — | NULL | I | Planned start. |
| planned_end | date | YES | `>= planned_start` | NULL | I | Planned end. |
| actual_start | date | YES | — | NULL | I | Actual start. |
| actual_end | date | YES | `>= actual_start` | NULL | I | Actual end. |
| applies_to_json | jsonb | YES | — | '{}' | I | Programme/term scope. |
| status | text | NO | IN (planned, in_progress, completed, cancelled) | planned | I | State. |
+ `AUDIT_MUTABLE`.

---

## 4. Academic Structure (`academic`)

**Trace:** Research §3.2, §8.2–8.3, §10.4; S1, S9, S14, S15.

**Convention reminder:** `Programme` = degree; `Course` = subject/paper; `Batch` = admission cohort; `Section` = class group; `Term` = dated academic period; `Offering` = delivery of a course version to a batch/section in a term.

### ACD-01 `academic.department`

**Purpose:** academic department with an accountable HOD; HOD authority is a role assignment, not a column. **Owner:** Principal. **Class:** I. **Phase:** F.
**PK:** `department_id`. **FKs:** `org_unit_id → core.org_unit`; `hod_person_id → iam.person` (derived cache).
**Unique / checks:** unique `org_unit_id` (one department per org unit); unique `lower(code)`; `established_on <= current_date`.
**Indexes:** unique `lower(code)`; `btree (hod_person_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| department_id | uuid | NO | PK | gen_random_uuid() | I | Department identity. |
| org_unit_id | uuid | NO | FK → core.org_unit; unique | — | I | Org-tree node for this department. |
| code | text | NO | unique lower(); length ≤ 20 | — | I | e.g. `CSE`. |
| name | text | NO | length ≤ 200 | — | I | Full name. |
| short_name | text | YES | length ≤ 50 | NULL | I | Abbreviation. |
| hod_person_id | uuid | YES | FK → iam.person | NULL | I | Derived cache of the person holding the open HOD role assignment for this department's org unit; not an authority source. |
| established_on | date | YES | `<= current_date` | NULL | I | Year of establishment. |
| is_active | boolean | NO | — | true | I | Offers programmes. |
+ `AUDIT_MUTABLE`.

### ACD-02 `academic.programme`

**Purpose:** degree programme and level. **Owner:** Registrar/Dean. **Class:** P. **Phase:** F.
**PK:** `programme_id`. **FKs:** `department_id → academic.department`; `institution_id → core.institution`.
**Unique / checks:** unique `(institution_id, programme_code)`; unique `(institution_id, bcrec_code)`; `level` in (UG, PG, diploma, certificate); `duration_years` between 1 and 6; `degree_awarded_by` is the awarding university, never the college.
**Indexes:** `btree (department_id, status)`; unique `lower(programme_code)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| programme_id | uuid | NO | PK | gen_random_uuid() | P | Programme identity. |
| institution_id | uuid | NO | FK → core.institution | — | P | Offering institution. |
| department_id | uuid | NO | FK → academic.department | — | P | Owning department. |
| programme_code | text | NO | unique per institution; length ≤ 20 | — | P | MAKAUT/affiliation code. |
| bcrec_code | text | NO | unique per institution; length ≤ 20 | — | P | Internal code used in roll numbers. |
| name | text | NO | length ≤ 200 | — | P | e.g. B.Tech in Computer Science and Engineering. |
| level | text | NO | IN (UG, PG, diploma, certificate) | — | P | Academic level. |
| degree_awarded_by | text | NO | length ≤ 200 | 'MAKAUT' | P | Awarding authority (S16 §3.4). |
| duration_years | smallint | NO | 1–6 | 4 | P | Nominal duration. |
| aicte_programme_code | text | YES | length ≤ 50 | NULL | P | AICTE reference. |
| status | text | NO | IN (active, suspended, discontinued) | active | P | Lifecycle state. |
+ `AUDIT_MUTABLE`.

### ACD-03 `academic.programme_version`

**Purpose:** regulation/curriculum binding effective for an admission-year range. **Owner:** Academic Council/Registrar. **Class:** I. **Phase:** F.
**PK:** `programme_version_id`. **FKs:** `programme_id`; `approved_by → iam.person`; `source_document_version_id → doc.document_version`.
**Unique / checks:** unique `(programme_id, version_no)`; `effective_to_admission_year IS NULL OR effective_to_admission_year >= effective_from_admission_year`; `total_credits > 0`; no overlapping year ranges per programme (exclusion constraint on `int4range`).
**Indexes:** `btree (programme_id, effective_from_admission_year)`; `btree (status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| programme_version_id | uuid | NO | PK | gen_random_uuid() | I | Version identity. |
| programme_id | uuid | NO | FK → academic.programme | — | I | Programme. |
| version_no | smallint | NO | ≥ 1; unique per programme | 1 | I | Version sequence. |
| regulation_name | text | NO | length ≤ 200 | — | I | e.g. BCREC Academic Regulations. |
| regulation_reference | text | YES | length ≤ 200 | NULL | I | Edition/clause reference. |
| effective_from_admission_year | smallint | NO | 2000–2100 | — | I | First admission year bound. |
| effective_to_admission_year | smallint | YES | ≥ from; 2000–2100 | NULL | I | Last admission year bound; null = open. |
| total_credits | integer | NO | > 0 | — | I | Credits required for the award. |
| status | text | NO | IN (draft, approved, superseded, withdrawn) | draft | I | Never silently promoted to approved. |
| approved_by | uuid | YES | FK → iam.person | NULL | I | Approver. |
| approved_at | timestamptz | YES | — | NULL | I | Approval time. |
| source_document_version_id | uuid | YES | FK → doc.document_version | NULL | I | Approved regulation PDF. |
+ `AUDIT_MUTABLE`.

### ACD-04 `academic.batch`

**Purpose:** admission cohort and its regulation binding. **Owner:** Registrar. **Class:** I. **Phase:** IE.
**PK:** `batch_id`. **FKs:** `programme_id`; `programme_version_id`; `current_term_id → core.term`.
**Unique / checks:** unique `(programme_id, admission_year, entry_mode)`; `admission_year` 2000–2100; `autonomy_status` in (autonomous, makaut, transitional); `expected_graduation_year >= admission_year`.
**Indexes:** `btree (programme_id, admission_year)`; `btree (autonomy_status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| batch_id | uuid | NO | PK | gen_random_uuid() | I | Cohort identity. |
| programme_id | uuid | NO | FK → academic.programme | — | I | Programme. |
| programme_version_id | uuid | NO | FK → academic.programme_version | — | I | Regulation/curriculum binding. |
| admission_year | smallint | NO | 2000–2100 | — | I | Year of entry. |
| entry_mode | text | NO | IN (regular, lateral, transfer) | regular | I | Entry route. |
| autonomy_status | text | NO | IN (autonomous, makaut, transitional) | transitional | I | Which authority governs this cohort (G-04). |
| current_term_id | uuid | YES | FK → core.term | NULL | I | Cached current term. |
| expected_graduation_year | smallint | YES | ≥ admission_year | NULL | I | Nominal completion. |
| status | text | NO | IN (active, graduated, closed) | active | I | Cohort state. |
+ `AUDIT_MUTABLE`.

**Open decision:** the autonomy boundary (G-04) is not assumed. A batch is `transitional` until the Registrar and COE confirm its governing regulation.

### ACD-05 `academic.section`

**Purpose:** class group within a batch. **Owner:** HOD. **Class:** I. **Phase:** IE.
**PK:** `section_id`. **FK:** `batch_id → academic.batch`.
**Unique / checks:** unique `(batch_id, section_code)`; unique `(section_id, batch_id)` (composite target for `student.section_assignment`); `strength >= 0`.
**Indexes:** `btree (batch_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| section_id | uuid | NO | PK | gen_random_uuid() | I | Section identity. |
| batch_id | uuid | NO | FK → academic.batch | — | I | Parent cohort. |
| section_code | text | NO | unique per batch; length ≤ 10 | — | I | e.g. `A`. |
| name | text | YES | length ≤ 100 | NULL | I | Display name. |
| strength | integer | YES | ≥ 0 | NULL | I | Sanctioned/actual strength. |
| status | text | NO | IN (active, merged, closed) | active | I | State. |
+ `AUDIT_MUTABLE`.

**Class teacher:** the current class teacher is not stored here. It is the open `academic.section_teacher_assignment` row (ACD-14) with `role_in_section = 'class_teacher'`; one active row per section is enforced by a partial unique index.

### ACD-06 `academic.curriculum`

**Purpose:** approved set of courses for a programme version and term. **Owner:** HOD/BoS. **Class:** I. **Phase:** F.
**PK:** `curriculum_id`. **FKs:** `programme_version_id`; `approved_by`; `effective_from_term_id → core.term`.
**Unique / checks:** unique `(programme_version_id, term_no, version_no)`; `term_no` 1–12; `total_credits >= 0`.
**Indexes:** `btree (programme_version_id, term_no)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| curriculum_id | uuid | NO | PK | gen_random_uuid() | I | Curriculum identity. |
| programme_version_id | uuid | NO | FK → academic.programme_version | — | I | Regulation version. |
| term_no | smallint | NO | 1–12; unique per version/version_no | — | I | Term within the programme. |
| version_no | smallint | NO | ≥ 1 | 1 | I | Curriculum revision. |
| total_credits | integer | NO | ≥ 0 | 0 | I | Credits for this term. |
| status | text | NO | IN (draft, approved, superseded) | draft | I | State. |
| approved_by | uuid | YES | FK → iam.person | NULL | I | Approver (Academic Council). |
| approved_at | timestamptz | YES | — | NULL | I | Approval time. |
| effective_from_term_id | uuid | YES | FK → core.term | NULL | I | First term of application. |
+ `AUDIT_MUTABLE`.

### ACD-07 `academic.curriculum_course`

**Purpose:** ordered membership of a course version in a curriculum. **Owner:** HOD/BoS. **Class:** I. **Phase:** F.
**PK:** `curriculum_course_id`. **FKs:** `curriculum_id`; `course_version_id`.
**Unique / checks:** unique `(curriculum_id, course_version_id)`; unique `(curriculum_id, term_no, sequence_no)`; `credits >= 0`; `contact_hours >= 0`.
**Indexes:** `btree (course_version_id)`; `btree (curriculum_id, term_no, sequence_no)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| curriculum_course_id | uuid | NO | PK | gen_random_uuid() | I | Membership row. |
| curriculum_id | uuid | NO | FK → academic.curriculum | — | I | Curriculum. |
| course_version_id | uuid | NO | FK → academic.course_version | — | I | Course version, never a bare course. |
| term_no | smallint | NO | 1–12 | — | I | Term of study. |
| sequence_no | smallint | NO | ≥ 1 | 1 | I | Order within the term. |
| category | text | NO | IN (core, elective, lab, sessional, project, mooc, mandatory_non_credit) | core | I | Requirement class. |
| credits | numeric(4,1) | NO | ≥ 0 | 0 | I | Credits awarded. |
| is_mandatory | boolean | NO | — | true | I | Must be passed for the award. |
| contact_hours | integer | YES | ≥ 0 | NULL | I | Planned contact hours. |
+ `AUDIT_MUTABLE`.

### ACD-08 `academic.course`

**Purpose:** stable course catalogue identity. **Owner:** HOD/BoS. **Class:** I. **Phase:** F.
**PK:** `course_id`. **FK:** `department_id`.
**Unique / checks:** unique `lower(course_code)`; `course_type` in (theory, practical, sessional, project, mooc, non_credit).
**Indexes:** `gin (to_tsvector('english', title))` for catalogue search.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| course_id | uuid | NO | PK | gen_random_uuid() | I | Course identity. |
| course_code | text | NO | unique lower(); length ≤ 30 | — | I | Catalogue code. |
| title | text | NO | length ≤ 300 | — | I | Course title. |
| course_type | text | NO | IN (theory, practical, sessional, project, mooc, non_credit) | theory | I | Delivery/assessment class. |
| department_id | uuid | NO | FK → academic.department | — | I | Owning department. |
| is_active | boolean | NO | — | true | I | Offered in new curricula. |
+ `AUDIT_MUTABLE`.

### ACD-09 `academic.course_version`

**Purpose:** immutable content and assessment version of a course. **Owner:** HOD/BoS. **Class:** I. **Phase:** F.
**PK:** `course_version_id`. **FKs:** `course_id`; `approved_by`; `source_document_version_id`.
**Unique / checks:** unique `(course_id, version_no)`; `credits > 0`; `effective_to_admission_year >= effective_from_admission_year`; an update is rejected once `course_offering` exists.
**Indexes:** `btree (course_id, version_no)`; `btree (status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| course_version_id | uuid | NO | PK | gen_random_uuid() | I | Version identity. |
| course_id | uuid | NO | FK → academic.course | — | I | Stable course. |
| version_no | smallint | NO | ≥ 1; unique per course | 1 | I | Version sequence. |
| title | text | NO | length ≤ 300 | — | I | Title at this version. |
| syllabus_text | text | YES | — | NULL | I | Syllabus body or extracted text. |
| credits | numeric(4,1) | NO | > 0 | — | I | Credits. |
| contact_hours | integer | YES | ≥ 0 | NULL | I | Planned hours. |
| course_outcomes_json | jsonb | YES | array of strings | '[]' | I | CO statements. |
| effective_from_admission_year | smallint | NO | 2000–2100 | — | I | First applicable cohort. |
| effective_to_admission_year | smallint | YES | ≥ from | NULL | I | Last applicable cohort. |
| status | text | NO | IN (draft, approved, superseded, retired) | draft | I | State. |
| approved_by | uuid | YES | FK → iam.person | NULL | I | Approver. |
| source_document_version_id | uuid | YES | FK → doc.document_version | NULL | I | Approved syllabus file. |
+ `AUDIT_MUTABLE`.

### ACD-10 `academic.course_offering`

**Purpose:** delivery of a course version to a batch/section in a term; the coordinator is an `offering_faculty` role. **Owner:** HOD. **Class:** I. **Phase:** IE.
**PK:** `course_offering_id`. **FKs:** `course_version_id`; `term_id`; `batch_id`; `section_id`.
**Unique / checks:** unique `(course_version_id, term_id, section_id)`; unique `lower(offering_code)`; `section_id` must belong to `batch_id` (trigger); `capacity >= 0`.
**Indexes:** `btree (term_id, batch_id)`; `btree (course_version_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| course_offering_id | uuid | NO | PK | gen_random_uuid() | I | Offering identity. |
| offering_code | text | NO | unique lower(); length ≤ 50 | — | I | Human code. |
| course_version_id | uuid | NO | FK → academic.course_version | — | I | Delivered version. |
| term_id | uuid | NO | FK → core.term | — | I | Term. |
| batch_id | uuid | NO | FK → academic.batch | — | I | Cohort. |
| section_id | uuid | YES | FK → academic.section | NULL | I | Section, when split. |
| capacity | integer | YES | ≥ 0 | NULL | I | Maximum enrolment. |
| delivery_mode | text | NO | IN (offline, online, hybrid) | offline | I | Mode. |
| status | text | NO | IN (planned, active, completed, cancelled) | planned | I | State. |
+ `AUDIT_MUTABLE`.

**Coordinator:** there is no `coordinator_person_id` on the offering. The coordinator is the person on `academic.offering_faculty` with `role_in_offering = 'coordinator'`; a partial unique index allows one open coordinator per offering. This keeps a single source and preserves allocation history.

### ACD-11 `academic.offering_faculty`

**Purpose:** teaching allocation and assessment responsibility. **Owner:** HOD. **Class:** I. **Phase:** IE.
**PK:** `offering_faculty_id`. **FKs:** `course_offering_id`; `person_id`; `valid_from`/`valid_to` in `VALIDITY`.
**Unique / checks:** unique `(course_offering_id, person_id, role_in_offering, valid_from)`; partial unique `(course_offering_id) WHERE role_in_offering = 'coordinator' AND valid_to IS NULL` (one open coordinator); `valid_to > valid_from`; `allocated_hours >= 0`.
**Indexes:** `btree (person_id, valid_to)`; `btree (course_offering_id, role_in_offering)`; partial unique coordinator index.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| offering_faculty_id | uuid | NO | PK | gen_random_uuid() | I | Allocation identity. |
| course_offering_id | uuid | NO | FK → academic.course_offering | — | I | Offering. |
| person_id | uuid | NO | FK → iam.person | — | I | Teacher. |
| role_in_offering | text | NO | IN (coordinator, instructor, lab_instructor, guest, moderator) | instructor | I | Teaching role. |
| is_assessor | boolean | NO | — | false | I | May enter marks. |
| valid_from | date | NO | — | current_date | I | Allocation start. |
| valid_to | date | YES | `> valid_from` | NULL | I | Allocation end. |
| allocated_hours | integer | YES | ≥ 0 | NULL | I | Planned hours. |
+ `AUDIT_MUTABLE`.

**Note:** this table does not grant access by itself. Authorization requires a `Faculty` role assignment plus the allocation relationship and its validity window. `role_in_offering = 'coordinator'` is the single source of the coordinator; it scopes coordination duties but does not create a separate permission. A person may hold more than one role on the same offering only with distinct `role_in_offering` values and non-overlapping validity for the same role.

### ACD-12 `academic.timetable_slot`

**Purpose:** scheduled class/lab session pattern. **Owner:** HOD/Timetable Committee. **Class:** I. **Phase:** IE.
**PK:** `timetable_slot_id`. **FKs:** `course_offering_id → academic.course_offering`.
**Unique / checks:** `end_time > start_time`; unique `(course_offering_id, day_of_week, start_time, valid_from)`; `slot_type` in (theory, practical, tutorial).
**Indexes:** `btree (course_offering_id, day_of_week, start_time)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| timetable_slot_id | uuid | NO | PK | gen_random_uuid() | I | Slot identity. |
| course_offering_id | uuid | NO | FK → academic.course_offering | — | I | Offering. |
| day_of_week | smallint | NO | 1–7 (Mon = 1) | — | I | Weekday. |
| start_time | time | NO | — | — | I | Start. |
| end_time | time | NO | `> start_time` | — | I | End. |
| slot_type | text | NO | IN (theory, practical, tutorial) | theory | I | Activity type. |
| venue_text | text | YES | length ≤ 100 | NULL | I | Free-text venue until the room master exists. |
| valid_from | date | NO | — | current_date | I | Effective from. |
| valid_to | date | YES | `> valid_from` | NULL | I | Effective to. |
| status | text | NO | IN (planned, active, cancelled) | planned | I | State. |
+ `AUDIT_MUTABLE`.

**Phase-2 expansion:** `academic.room` (ACD-13) is not created in the Initial Release, so this table has no `room_id` column. When rooms are introduced, the expand migration adds a nullable `room_id uuid`, backfills from `venue_text` where possible, then adds `FK → academic.room` and the capacity/overlap checks. No Initial Release foreign key points at a Future entity (see `POSTGRES_ARCHITECTURE.md` §5.5).

### ACD-14 `academic.section_teacher_assignment`

**Purpose:** time-bound class/co-class teacher allocation with the authority and evidence that produced it. **Owner:** HOD. **Class:** I. **Phase:** IE.
**PK:** `section_teacher_assignment_id`. **FKs:** `section_id`; `person_id`; `authority_role_assignment_id`; `source_document_version_id`; `assigned_by`.
**Unique / checks:** unique `(section_id, person_id, role_in_section, valid_from)`; `valid_to > valid_from`; partial unique `(section_id) WHERE role_in_section = 'class_teacher' AND status = 'active' AND valid_to IS NULL`; exclusion on `(section_id WITH =, daterange(valid_from, valid_to, '[]') WITH &&) WHERE role_in_section = 'class_teacher'`; `role_in_section` in (class_teacher, co_class_teacher, substitute); `status` in (active, ended, superseded, cancelled); the person must hold an active `Faculty` role assignment; `authority_role_assignment_id` must be an open HOD/Principal assignment whose scope covers the section's department/org unit (trigger).
**Indexes:** `btree (section_id, role_in_section, valid_from DESC)`; `btree (person_id, valid_to)`; `btree (authority_role_assignment_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| section_teacher_assignment_id | uuid | NO | PK | gen_random_uuid() | I | Assignment identity. |
| section_id | uuid | NO | FK → academic.section | — | I | Section. |
| person_id | uuid | NO | FK → iam.person | — | I | Teacher. |
| role_in_section | text | NO | IN (class_teacher, co_class_teacher, substitute) | class_teacher | I | Role in the section. |
| valid_from | date | NO | — | current_date | I | Start. |
| valid_to | date | YES | `> valid_from` | NULL | I | End; null = open. |
| status | text | NO | IN (active, ended, superseded, cancelled) | active | I | State. |
| assigned_at | timestamptz | NO | — | now() | I | Allocation time. |
| assigned_by | uuid | YES | FK → iam.person | NULL | I | HOD/Principal who allocated. |
| authority_role_assignment_id | uuid | NO | FK → iam.role_assignment | — | I | The role assignment under which the allocation was made. |
| source_document_version_id | uuid | YES | FK → doc.document_version | NULL | I | Appointment/office order, when one exists. |
| change_reason | text | YES | length ≤ 1000 | NULL | I | Why the teacher changed. |
+ `AUDIT_MUTABLE`.

**Authority rule:** this table scopes access; it does not grant a permission. The teacher must also hold a `Faculty` role assignment. The `authority_role_assignment_id` proves that the allocating HOD acted under a valid HOD assignment. Closing a row is an update to `status`/`valid_to`; history is never deleted. A transfer writes a new row for the incoming teacher and closes the old row in the same transaction.

---

## 5. Student Lifecycle (`student`)

**Trace:** Research §8.1–8.2, §10.5; S1 §9, S20; G-04, G-08, G-11.

### STU-01 `student.admission_application`

**Purpose:** applicant pipeline and eligibility evidence. **Owner:** Admission Cell. **Class:** C/R/G. **Phase:** IE.
**PK:** `application_id`. **FKs:** `person_id`; `programme_id`; `batch_id` (nullable until allotment); `verified_by`.
**Unique / checks:** unique `(admission_year, application_no)`; `application_status` in (draft, submitted, under_verification, eligible, ineligible, waitlisted, offered, admitted, withdrawn); `category` from the controlled category set.
**Indexes:** `btree (programme_id, admission_year, application_status)`; `btree (person_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| application_id | uuid | NO | PK | gen_random_uuid() | C | Application identity. |
| person_id | uuid | NO | FK → iam.person | — | C | Applicant. |
| programme_id | uuid | NO | FK → academic.programme | — | C | Applied programme. |
| batch_id | uuid | YES | FK → academic.batch | NULL | C | Target cohort once allotted. |
| application_no | text | NO | unique per admission year | — | C | Form number. |
| admission_year | smallint | NO | 2000–2100 | — | C | Admission cycle. |
| counselling_authority | text | YES | IN (WBJEE, JEE, JELET, JECA, JEMAT, PGET, institute) | NULL | C | Allotment route (S2). |
| allotment_reference | text | YES | length ≤ 100 | NULL | C | Counselling allotment ID. |
| category | text | YES | IN (general, obc_a, obc_b, sc, st, ews, tfw, pwd, other) | NULL | R/G | Reservation category; restricted access and statutory basis. |
| eligibility_status | text | NO | IN (pending, eligible, ineligible, conditional) | pending | C | Eligibility check outcome. |
| application_status | text | NO | IN (draft, submitted, under_verification, eligible, ineligible, waitlisted, offered, admitted, withdrawn) | draft | C | Pipeline state. |
| submitted_at | timestamptz | YES | — | NULL | C | Submission time. |
| verified_by | uuid | YES | FK → iam.person | NULL | C | Verifying officer. |
| verified_at | timestamptz | YES | — | NULL | C | Verification time. |
+ `AUDIT_MUTABLE`.

### STU-02 `student.admission_offer`

**Purpose:** offer, acceptance, fee reference, admission confirmation. **Owner:** Admission Cell. **Class:** C. **Phase:** IE.
**PK:** `offer_id`. **FKs:** `application_id`; `confirmed_by → iam.person`.
**Unique / checks:** unique `application_id` (one live offer per application); unique `offer_no`; `accepted_at >= offered_at` when both present.
**Indexes:** `btree (status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| offer_id | uuid | NO | PK | gen_random_uuid() | C | Offer identity. |
| application_id | uuid | NO | FK → student.admission_application; unique | — | C | Source application. |
| offer_no | text | NO | unique; length ≤ 50 | — | C | Offer number. |
| offered_at | timestamptz | NO | — | now() | C | Offer time. |
| accepted_at | timestamptz | YES | `>= offered_at` | NULL | C | Acceptance time. |
| admission_confirmed_at | timestamptz | YES | — | NULL | C | Confirmation time. |
| fee_receipt_reference | text | YES | length ≤ 100 | NULL | C | Receipt reference; not a payment table. |
| confirmed_by | uuid | YES | FK → iam.person | NULL | C | Confirming officer. |
| status | text | NO | IN (offered, accepted, confirmed, declined, expired, cancelled) | offered | C | State. |
| remarks | text | YES | length ≤ 2000 | NULL | C | Notes. |
+ `AUDIT_MUTABLE`.

### STU-03 `student.student`

**Purpose:** academic identity of a learner. **Owner:** Registrar. **Class:** C/R/G. **Phase:** IE.
**PK:** `student_id`. **FKs:** `person_id`; `batch_id`; `section_id`; `admission_application_id`.
**Unique / checks:** unique `college_roll_no`; unique `(person_id, batch_id)`; unique `(student_id, batch_id)` (composite target for `section_assignment` and `attendance.record`); `admission_year` 2000–2100; `current_status` in (active, detained, suspended, year_lag, graduated, withdrawn, migrated).
**Indexes:** `btree (batch_id, section_id)`; `btree (current_status)`; `btree (person_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| student_id | uuid | NO | PK | gen_random_uuid() | C | Student identity. |
| person_id | uuid | NO | FK → iam.person | — | C | The human. |
| batch_id | uuid | NO | FK → academic.batch | — | C | Admission cohort. |
| section_id | uuid | YES | FK → academic.section | NULL | C | Current section cache; the history is `student.section_assignment`. |
| admission_application_id | uuid | YES | FK → student.admission_application | NULL | C | Origin application. |
| college_roll_no | text | NO | unique; length ≤ 30 | — | C | College roll number. |
| admission_year | smallint | NO | 2000–2100 | — | C | Year of entry. |
| entry_mode | text | NO | IN (regular, lateral, transfer) | regular | C | Entry route. |
| category | text | YES | IN (general, obc_a, obc_b, sc, st, ews, tfw, pwd, other) | NULL | R/G | Admission category; restricted access and statutory basis. |
| date_of_admission | date | NO | — | — | C | Date of admission. |
| expected_completion_year | smallint | YES | ≥ admission_year | NULL | C | Nominal completion. |
| current_status | text | NO | IN (active, detained, suspended, year_lag, graduated, withdrawn, migrated) | active | C | Cached current status. |
| photo_uri | text | YES | object-storage URI | NULL | C | Portrait. |
+ `AUDIT_MUTABLE`.

**Deferred decision:** whether a person may hold two concurrent student records (second programme) is OD-11. The unique key is `(person_id, batch_id)` so the model does not forbid it silently.

### STU-04 `student.guardian`

**Purpose:** parent/guardian as a person. **Owner:** Registrar. **Class:** C/R. **Phase:** IE.
**PK:** `guardian_id`. **FK:** `person_id`.
**Unique / checks:** unique `person_id` (one guardian profile per person); `annual_income_band` from a controlled band set, never a precise income.
**Indexes:** `btree (person_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| guardian_id | uuid | NO | PK | gen_random_uuid() | C | Guardian profile. |
| person_id | uuid | NO | FK → iam.person; unique | — | C | The human. |
| occupation | text | YES | length ≤ 100 | NULL | C | Occupation. |
| education | text | YES | length ≤ 100 | NULL | C | Qualification. |
| annual_income_band | text | YES | IN (below_1l, 1l_3l, 3l_5l, 5l_10l, above_10l, not_disclosed) | NULL | R | Banded income, not exact; scholarship/finance access only. |
| is_alumni | boolean | NO | — | false | C | BCREC alumnus flag. |
+ `AUDIT_MUTABLE`.

### STU-05 `student.student_guardian`

**Purpose:** many-to-many student–guardian relationship with consent. **Owner:** Registrar. **Class:** C/R. **Phase:** IE.
**PK:** `student_guardian_id`. **FKs:** `student_id`; `guardian_id`.
**Unique / checks:** unique `(student_id, guardian_id)`; partial unique `(student_id) WHERE is_primary AND valid_to IS NULL`; `valid_to > valid_from`; `consent_status` in (pending, granted, denied, withdrawn).
**Indexes:** `btree (guardian_id)`; `btree (student_id, is_primary)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| student_guardian_id | uuid | NO | PK | gen_random_uuid() | C | Link identity. |
| student_id | uuid | NO | FK → student.student | — | C | Student. |
| guardian_id | uuid | NO | FK → student.guardian | — | C | Guardian. |
| relation | text | NO | IN (father, mother, guardian, sibling, other) | guardian | C | Relationship. |
| is_primary | boolean | NO | — | false | C | Primary contact. |
| consent_status | text | NO | IN (pending, granted, denied, withdrawn) | pending | R | Consent for data sharing/access; restricted because it is the legal basis record. |
| consent_recorded_at | timestamptz | YES | — | NULL | R | When consent was captured. |
| valid_from | date | NO | — | current_date | C | Link start. |
| valid_to | date | YES | `> valid_from` | NULL | C | Link end. |
+ `AUDIT_MUTABLE`.

### STU-06 `student.student_document`

**Purpose:** verified student document and provenance. **Owner:** Registrar. **Class:** R/G. **Phase:** IE.
**PK:** `student_document_id`. **FKs:** `student_id`; `document_version_id`; `verified_by`.
**Unique / checks:** unique `(student_id, document_type, document_version_id)`; `verification_status` in (pending, verified, rejected, expired).
**Indexes:** `btree (student_id, document_type)`; `btree (verification_status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| student_document_id | uuid | NO | PK | gen_random_uuid() | R | Link identity. |
| student_id | uuid | NO | FK → student.student | — | R | Student. |
| document_version_id | uuid | NO | FK → doc.document_version | — | R | Immutable file version. |
| document_type | text | NO | IN (photo, signature, marksheet_10, marksheet_12, diploma, category_certificate, income_certificate, migration, transfer, medical, id_proof, other) | — | R | Kind. |
| verification_status | text | NO | IN (pending, verified, rejected, expired) | pending | R | Check state. |
| verified_by | uuid | YES | FK → iam.person | NULL | R | Verifier. |
| verified_at | timestamptz | YES | — | NULL | R | Verification time. |
| expires_on | date | YES | — | NULL | R | Expiry, where applicable. |
| remarks | text | YES | length ≤ 1000 | NULL | R | Officer notes. |
+ `AUDIT_MUTABLE`.

**Access rule:** identity, category, income, and medical documents are `R/G`. The metadata row is restricted; the linked `doc.document_version` inherits the classification and is never ingested into `knowledge`. The student sees their own document metadata and file; a verifier sees only the assigned case; the CIP corpus excludes the document entirely.

### STU-07 `student.university_registration`

**Purpose:** MAKAUT registration number and status. **Owner:** Registrar. **Class:** C. **Phase:** IE.
**PK:** `university_registration_id`. **FKs:** `student_id`; `proof_document_version_id`.
**Unique / checks:** unique `student_id` (one active university registration per student); unique `registration_number` where not null; `registration_year` 2000–2100.
**Indexes:** unique `lower(registration_number)`; `btree (status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| university_registration_id | uuid | NO | PK | gen_random_uuid() | C | Record identity. |
| student_id | uuid | NO | FK → student.student; unique | — | C | Student. |
| registration_number | text | YES | unique where not null; length ≤ 50 | NULL | C | MAKAUT number. |
| registration_year | smallint | NO | 2000–2100 | — | C | Registration year. |
| status | text | NO | IN (pending, uploaded, confirmed, rejected) | pending | C | State. |
| uploaded_at | timestamptz | YES | — | NULL | C | Upload time. |
| confirmed_at | timestamptz | YES | — | NULL | C | University confirmation. |
| proof_document_version_id | uuid | YES | FK → doc.document_version | NULL | C | Proof file. |
+ `AUDIT_MUTABLE`.

### STU-08 `student.exam_roll_number`

**Purpose:** 12-digit examination identity, versioned with one current row. **Owner:** COE. **Class:** C. **Phase:** IE.
**PK:** `exam_roll_number_id`. **FKs:** `student_id`; `programme_id`.
**Unique / checks:** unique `roll_number`; partial unique `(student_id) WHERE is_current`; `length(roll_number) = 12`; `college_code` 3 chars, `programme_code` 3 chars, `registration_year` 2 digits, `course_duration_years` 1 digit, `serial_no` 3 digits; concatenation must equal `roll_number` (trigger).
**Indexes:** `btree (student_id, is_current)`; `btree (registration_year, serial_no)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| exam_roll_number_id | uuid | NO | PK | gen_random_uuid() | C | Record identity. |
| student_id | uuid | NO | FK → student.student | — | C | Student. |
| programme_id | uuid | NO | FK → academic.programme | — | C | Programme encoded in the roll. |
| roll_number | text | NO | unique; length = 12 | — | C | Formatted 12-digit roll. |
| college_code | text | NO | length = 3 | — | C | `120`. |
| programme_code | text | NO | length = 3 | — | C | Programme segment. |
| registration_year | smallint | NO | 0–99 (2-digit) | — | C | Year segment. |
| course_duration_years | smallint | NO | 1–9 | — | C | Duration segment. |
| serial_no | smallint | NO | 1–999 | — | C | Serial segment. |
| issued_on | date | NO | — | current_date | C | Issue date. |
| is_current | boolean | NO | — | true | C | Only one current per student. |
| status | text | NO | IN (active, superseded, cancelled) | active | C | State. |
+ `AUDIT_MUTABLE`.

**Trace:** format from S1 §9.2.2. The format is stored as components so a policy change does not require parsing old strings.

### STU-09 `student.semester_registration`

**Purpose:** student's registration for a term. **Owner:** Registrar. **Class:** C. **Phase:** IE.
**PK:** `semester_registration_id`. **FKs:** `student_id`; `term_id`; `approved_by`.
**Unique / checks:** unique `(student_id, term_id)`; unique `(semester_registration_id, student_id)` (composite target for `course_registration`); unique `registration_no`; `approved_at >= submitted_at` when both present; `status` in (draft, submitted, approved, rejected, cancelled).
**Indexes:** `btree (term_id, status)`; `btree (student_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| semester_registration_id | uuid | NO | PK | gen_random_uuid() | C | Registration identity. |
| student_id | uuid | NO | FK → student.student | — | C | Student. |
| term_id | uuid | NO | FK → core.term | — | C | Term. |
| registration_no | text | YES | unique where not null; length ≤ 50 | NULL | C | Registration number. |
| submitted_at | timestamptz | YES | — | NULL | C | Submission time. |
| approved_by | uuid | YES | FK → iam.person | NULL | C | Approver. |
| approved_at | timestamptz | YES | `>= submitted_at` | NULL | C | Approval time. |
| status | text | NO | IN (draft, submitted, approved, rejected, cancelled) | draft | C | State. |
| remarks | text | YES | length ≤ 1000 | NULL | C | Notes. |
+ `AUDIT_MUTABLE`.

### STU-10 `student.course_registration`

**Purpose:** course-level enrolment in an offering, with a student integrity anchor for attendance. **Owner:** Registrar/HOD. **Class:** C. **Phase:** IE.
**PK:** `course_registration_id`. **FKs:** `student_id`; `semester_registration_id`; `course_offering_id`.
**Unique / checks:** unique `(semester_registration_id, course_offering_id)`; unique `(course_registration_id, student_id, course_offering_id)` (composite target for `attendance.record`); `student_id` must match the parent semester registration (composite FK `(semester_registration_id, student_id)`); `credits >= 0`; `registration_type` in (regular, backlog, audit, improvement); `status` in (registered, dropped, completed, failed, withdrawn).
**Indexes:** `btree (course_offering_id, status)`; `btree (semester_registration_id)`; `btree (student_id, course_offering_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| course_registration_id | uuid | NO | PK | gen_random_uuid() | C | Enrolment identity. |
| student_id | uuid | NO | FK → student.student; composite with semester_registration_id | — | C | Student integrity anchor; must match the parent semester registration. |
| semester_registration_id | uuid | NO | FK → student.semester_registration | — | C | Parent term registration. |
| course_offering_id | uuid | NO | FK → academic.course_offering | — | C | Offering. |
| registration_type | text | NO | IN (regular, backlog, audit, improvement) | regular | C | Enrolment reason. |
| credits | numeric(4,1) | NO | ≥ 0 | 0 | C | Credits for this enrolment. |
| status | text | NO | IN (registered, dropped, completed, failed, withdrawn) | registered | C | State. |
| registered_at | timestamptz | NO | — | now() | C | Registration time. |
| dropped_at | timestamptz | YES | `>= registered_at` | NULL | C | Drop time. |
| drop_reason | text | YES | length ≤ 500 | NULL | C | Reason. |
+ `AUDIT_MUTABLE`.

### STU-11 `student.status_history`

**Purpose:** auditable student status timeline. **Owner:** Registrar. **Class:** C/R. **Phase:** IE.
**PK:** `status_history_id`. **FKs:** `student_id`; `order_document_version_id`; `recorded_by`.
**Unique / checks:** `valid_to > effective_from`; no overlapping ranges per student (exclusion constraint on `daterange(effective_from, effective_to)`); `status` in the same set as `student.current_status`.
**Indexes:** `btree (student_id, effective_from)`; GiST exclusion index on the daterange.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| status_history_id | uuid | NO | PK | gen_random_uuid() | C | Row identity. |
| student_id | uuid | NO | FK → student.student | — | C | Student. |
| status | text | NO | IN (active, detained, suspended, year_lag, graduated, withdrawn, migrated) | — | C | Status during the period. |
| effective_from | date | NO | — | — | C | Start. |
| effective_to | date | YES | `> effective_from` | NULL | C | End; null = current. |
| reason | text | YES | length ≤ 2000 | NULL | R | Reason; masked by default. |
| order_document_version_id | uuid | YES | FK → doc.document_version | NULL | C | Order/evidence. |
| recorded_by | uuid | YES | FK → iam.person | NULL | C | Recording officer. |
+ `AUDIT_MUTABLE`.

**Rule:** the history row is authoritative; `student.current_status` is updated in the same transaction and must match the open history row.

### STU-12 `student.eligibility_determination`

**Purpose:** configurable gate result (academic, attendance, fee, discipline, documents). **Owner:** Registrar/COE. **Class:** C. **Phase:** IE.
**PK:** `eligibility_determination_id`. **FKs:** `student_id`; `term_id`; `policy_rule_version_id`; `determined_by`.
**Unique / checks:** `status` in (pass, fail, waived, unknown, not_applicable); `gate_code` length ≤ 50; `scope_type` in (institution, programme, batch, term, course_offering) and exactly one scope is populated when `scope_type` is not `institution`.
**Indexes:** `btree (student_id, gate_code, term_id)`; `btree (status, determined_at)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| eligibility_determination_id | uuid | NO | PK | gen_random_uuid() | C | Determination identity. |
| student_id | uuid | NO | FK → student.student | — | C | Student. |
| term_id | uuid | NO | FK → core.term | — | C | Term. |
| gate_code | text | NO | length ≤ 50; e.g. `ATTENDANCE`, `FEE_CLEARANCE` | — | C | Which gate. |
| scope_type | text | NO | IN (institution, programme, batch, term, course_offering) | term | C | Scope kind. |
| scope_id | uuid | YES | validated against the entity registry | NULL | C | Scope identifier. |
| status | text | NO | IN (pass, fail, waived, unknown, not_applicable) | unknown | C | Outcome. |
| policy_rule_version_id | uuid | YES | FK → policy.rule_version | NULL | C | Rule applied. |
| source | text | NO | IN (computed, imported, manual, external_api) | computed | C | Where the fact came from. |
| evidence_json | jsonb | YES | — | '{}' | C | Inputs used. |
| determined_at | timestamptz | NO | — | now() | C | When computed. |
| determined_by | uuid | YES | FK → iam.person | NULL | C | Who determined; null = system. |
+ `AUDIT_IMMUTABLE`.

**Why append-only:** an eligibility decision is evidence. A re-evaluation writes a new row; it does not overwrite the prior outcome or its policy version. This is the schema's answer to G-01 and G-08.

**Scope exception:** `scope_id` is polymorphic within a controlled set; it is validated by the application and `integration.entity_type`, not by a foreign key. Documented in `POSTGRES_ARCHITECTURE.md`.

### STU-15 `student.section_assignment`

**Purpose:** historical student-to-section assignment, including transfers, with the authority and evidence that produced it. **Owner:** Registrar/HOD. **Class:** C. **Phase:** IE.
**PK:** `section_assignment_id`. **FKs:** `student_id`; `section_id`; `batch_id`; `approved_by`; `authority_role_assignment_id`; `source_document_version_id`.
**Unique / checks:** unique `(student_id, effective_from)`; `effective_to > effective_from`; exclusion on `(student_id WITH =, daterange(effective_from, effective_to, '[]') WITH &&)`; partial unique `(student_id) WHERE effective_to IS NULL AND status = 'active'`; `assignment_reason` in (initial_allotment, transfer, section_merge, readmission, correction); `status` in (active, ended, cancelled); composite FK `(student_id, batch_id) → student.student(student_id, batch_id)`; composite FK `(section_id, batch_id) → academic.section(section_id, batch_id)`.
**Indexes:** `btree (student_id, effective_from DESC)`; `btree (section_id, effective_from DESC)`; GiST exclusion index on the daterange.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| section_assignment_id | uuid | NO | PK | gen_random_uuid() | C | Assignment identity. |
| student_id | uuid | NO | FK → student.student | — | C | Student. |
| section_id | uuid | NO | FK → academic.section | — | C | Section. |
| batch_id | uuid | NO | FK → academic.batch; must match student and section | — | C | Batch anchor for the composite FKs. |
| effective_from | date | NO | — | current_date | C | Start of assignment. |
| effective_to | date | YES | `> effective_from` | NULL | C | End; null = current. |
| assignment_reason | text | NO | IN (initial_allotment, transfer, section_merge, readmission, correction) | initial_allotment | C | Why the assignment changed. |
| status | text | NO | IN (active, ended, cancelled) | active | C | State. |
| approved_by | uuid | YES | FK → iam.person | NULL | C | Approving officer. |
| authority_role_assignment_id | uuid | YES | FK → iam.role_assignment | NULL | C | Role assignment under which the transfer was approved. |
| source_document_version_id | uuid | YES | FK → doc.document_version | NULL | C | Transfer/approval order, when one exists. |
+ `AUDIT_MUTABLE`.

**Cache rule:** `student.section_id` is a derived current-section cache. Every open/close of a `section_assignment` updates it in the same transaction; a nightly reconciliation reports any student whose cached section differs from the open assignment. History is never deleted; a transfer closes the old row and opens the new one atomically. The composite FKs guarantee that a student is never assigned to a section in another batch.

---

## 6. Attendance (`attendance`)

**Trace:** Research §8.4, §9.3; S1 §16, S2 p.55, S17; G-01, G-13, G-14.

**Design rule:** the session and the record are the facts; the summary and the eligibility assessment are derived. A record is structurally tied to a course registration, not merely to a student, so attendance cannot be captured for a student who is not enrolled in the session's offering. A derived row always records the policy version and the calculation time, so a rule change can be re-run without re-capturing attendance.

### ATT-01 `attendance.session`

**Purpose:** unit of attendance capture. **Owner:** Faculty. **Class:** C. **Phase:** IE.
**PK:** `session_id`. **FKs:** `course_offering_id`; `timetable_slot_id` (nullable); `held_by_person_id`.
**Unique / checks:** unique `(course_offering_id, session_date, start_time)`; unique `(session_id, course_offering_id)` (composite target for `attendance.record`); `end_time > start_time`; `session_type` in (theory, practical, tutorial); `status` in (scheduled, held, cancelled).
**Indexes:** `btree (course_offering_id, session_date)`; `btree (session_date, status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| session_id | uuid | NO | PK | gen_random_uuid() | C | Session identity. |
| course_offering_id | uuid | NO | FK → academic.course_offering | — | C | Offering. |
| timetable_slot_id | uuid | YES | FK → academic.timetable_slot | NULL | C | Slot instantiated. |
| session_date | date | NO | — | — | C | Date held. |
| start_time | time | NO | — | — | C | Start. |
| end_time | time | NO | `> start_time` | — | C | End. |
| session_type | text | NO | IN (theory, practical, tutorial) | theory | C | Activity. |
| topic | text | YES | length ≤ 500 | NULL | C | Topic covered. |
| delivery_mode | text | NO | IN (offline, online, hybrid) | offline | C | Mode. |
| status | text | NO | IN (scheduled, held, cancelled) | scheduled | C | State; only `held` counts. |
| held_by_person_id | uuid | YES | FK → iam.person | NULL | C | Teacher who conducted it. |
+ `AUDIT_MUTABLE`.

**Denominator rule:** only sessions with `status = 'held'` count toward `sessions_conducted`. A cancelled session is retained for audit but excluded from the percentage.

### ATT-02 `attendance.record`

**Purpose:** one student's presence in one session, anchored to a course registration. **Owner:** Faculty. **Class:** C. **Phase:** IE.
**PK:** `attendance_record_id`. **FKs:** `session_id`; `student_id`; `course_registration_id`; `course_offering_id`; `marked_by`.
**Unique / checks:** unique `(session_id, student_id)`; composite FK `(course_registration_id, student_id, course_offering_id) → student.course_registration(course_registration_id, student_id, course_offering_id)`; composite FK `(session_id, course_offering_id) → attendance.session(session_id, course_offering_id)`; `status` in (present, absent, late, excused); `source` in (faculty_manual, import, biometric, device).
**Indexes:** `btree (student_id, session_id)`; `btree (session_id, status)`; `btree (course_registration_id)`; `btree (course_offering_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| attendance_record_id | uuid | NO | PK | gen_random_uuid() | C | Record identity. |
| session_id | uuid | NO | FK → attendance.session; composite with course_offering_id | — | C | Session. |
| student_id | uuid | NO | FK → student.student; composite with course_registration_id | — | C | Student. |
| course_registration_id | uuid | NO | FK → student.course_registration; composite | — | C | Registration that proves enrolment in the taught offering. |
| course_offering_id | uuid | NO | FK → academic.course_offering; composite with session_id | — | C | Offering of the session; must match the registration and the session. |
| status | text | NO | IN (present, absent, late, excused) | absent | C | Presence. |
| source | text | NO | IN (faculty_manual, import, biometric, device) | faculty_manual | C | Capture source. |
| marked_at | timestamptz | NO | — | now() | C | Marking time. |
| marked_by | uuid | YES | FK → iam.person | NULL | C | Marker; null for device import. |
| remarks | text | YES | length ≤ 500 | NULL | C | Reason for `excused`/`late`. |
+ `AUDIT_MUTABLE`.

**Registration invariant:** the two composite foreign keys are the database-enforced proof that the student is registered in the exact offering associated with the session. The service additionally rejects a new record when the registration was dropped before `session_date`; that temporal rule cannot be expressed as an FK. A direct `student_id` FK remains for query simplicity, but the composite key is authoritative.

### ATT-03 `attendance.correction`

**Purpose:** correction of a wrongly marked record. **Owner:** Faculty/HOD. **Class:** C/R. **Phase:** IE.
**PK:** `correction_id`. **FKs:** `attendance_record_id`; `requested_by`; `approved_by`; `evidence_document_version_id`.
**Unique / checks:** `old_status <> new_status`; `approved_at >= requested_at` when both present; `status` in (requested, approved, rejected, withdrawn).
**Indexes:** `btree (attendance_record_id)`; `btree (status, requested_at)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| correction_id | uuid | NO | PK | gen_random_uuid() | C | Correction identity. |
| attendance_record_id | uuid | NO | FK → attendance.record | — | C | Corrected record. |
| old_status | text | NO | IN (present, absent, late, excused) | — | C | Value before. |
| new_status | text | NO | IN (present, absent, late, excused); `<> old_status` | — | C | Value after. |
| reason | text | NO | length 5–2000 | — | R | Justification. |
| requested_by | uuid | NO | FK → iam.person | — | C | Requester. |
| requested_at | timestamptz | NO | — | now() | C | Request time. |
| approved_by | uuid | YES | FK → iam.person | NULL | C | Approver. |
| approved_at | timestamptz | YES | `>= requested_at` | NULL | C | Approval time. |
| status | text | NO | IN (requested, approved, rejected, withdrawn) | requested | C | State. |
| evidence_document_version_id | uuid | YES | FK → doc.document_version | NULL | R | Supporting file. |
+ `AUDIT_MUTABLE`.

**Integrity:** on approval, the service updates `attendance.record.status` and writes the correction in one transaction. The original value is never deleted; the correction is the audit trail.

### ATT-04 `attendance.summary`

**Purpose:** computed attendance per student and offering. **Owner:** System/HOD. **Class:** C. **Phase:** IE.
**PK:** `summary_id`. **FKs:** `student_id`; `course_offering_id`; `policy_rule_version_id`.
**Unique / checks:** unique `(student_id, course_offering_id, as_of)`; `sessions_attended <= sessions_conducted`; `attendance_pct` 0–100.
**Indexes:** `btree (student_id, course_offering_id, as_of DESC)`; `btree (course_offering_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| summary_id | uuid | NO | PK | gen_random_uuid() | C | Summary identity. |
| student_id | uuid | NO | FK → student.student | — | C | Student. |
| course_offering_id | uuid | NO | FK → academic.course_offering | — | C | Offering. |
| sessions_conducted | integer | NO | ≥ 0 | 0 | C | Held sessions counted. |
| sessions_attended | integer | NO | ≥ 0; ≤ conducted | 0 | C | Attended sessions. |
| attendance_pct | numeric(5,2) | NO | 0–100 | 0 | C | Percentage. |
| as_of | timestamptz | NO | — | now() | C | Calculation time. |
| calculation_version | text | NO | length ≤ 20 | 'v1' | C | Algorithm version. |
| policy_rule_version_id | uuid | YES | FK → policy.rule_version | NULL | C | Counting rule applied. |
+ `AUDIT_IMMUTABLE`.

### ATT-05 `attendance.eligibility_assessment`

**Purpose:** policy decision for a student and term under one rule variant. **Owner:** Registrar/COE. **Class:** C. **Phase:** IE.
**PK:** `eligibility_assessment_id`. **FKs:** `student_id`; `term_id`; `policy_bundle_version_id`.
**Unique / checks:** unique `(student_id, term_id, rule_variant, computed_at)`; `rule_variant` in (aggregate, split); all percentages 0–100; `outcome` in (eligible, shortage, not_condonable, pending).
**Indexes:** `btree (student_id, term_id, computed_at DESC)`; `btree (outcome)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| eligibility_assessment_id | uuid | NO | PK | gen_random_uuid() | C | Assessment identity. |
| student_id | uuid | NO | FK → student.student | — | C | Student. |
| term_id | uuid | NO | FK → core.term | — | C | Term. |
| rule_variant | text | NO | IN (aggregate, split) | — | C | Which attendance rule was applied (G-01). |
| aggregate_pct | numeric(5,2) | YES | 0–100 | NULL | C | Overall percentage. |
| theory_pct | numeric(5,2) | YES | 0–100 | NULL | C | Theory percentage. |
| practical_pct | numeric(5,2) | YES | 0–100 | NULL | C | Practical percentage. |
| outcome | text | NO | IN (eligible, shortage, not_condonable, pending) | pending | C | Decision. |
| computed_at | timestamptz | NO | — | now() | C | Calculation time. |
| inputs_json | jsonb | YES | — | '{}' | C | Offerings and sessions used. |
| policy_bundle_version_id | uuid | YES | FK → policy.policy_bundle_version | NULL | C | Rule set applied. |
+ `AUDIT_IMMUTABLE`.

**Conflict handling (C-01):** the row stores `rule_variant` explicitly. Both variants can be computed for the same student/term. No row is created with a default variant chosen by the system. The outcome is advisory until the Academic Council resolves G-01 and the gate is configured.

### ATT-06 `attendance.condonation_case`

**Purpose:** Academic Council decision on a shortfall. **Owner:** Registrar/Academic Council. **Class:** R. **Phase:** IE.
**PK:** `condonation_case_id`. **FKs:** `student_id`; `term_id`; `eligibility_assessment_id`; `order_document_version_id`.
**Unique / checks:** unique `(student_id, term_id)`; `shortfall_pct` 0–100; `status` in (opened, hod_recommended, ac_review, approved, rejected, closed).
**Indexes:** `btree (term_id, status)`; `btree (student_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| condonation_case_id | uuid | NO | PK | gen_random_uuid() | R | Case identity. |
| student_id | uuid | NO | FK → student.student | — | R | Student. |
| term_id | uuid | NO | FK → core.term | — | R | Term. |
| eligibility_assessment_id | uuid | NO | FK → attendance.eligibility_assessment | — | R | Assessment challenged. |
| shortfall_pct | numeric(5,2) | NO | 0–100 | — | R | How far below the threshold. |
| grounds | text | YES | length ≤ 2000 | NULL | R | Medical/other grounds. |
| evidence_summary | text | YES | length ≤ 2000 | NULL | R | Evidence description. |
| hod_recommendation | text | YES | length ≤ 2000 | NULL | R | HOD view. |
| ac_decision | text | YES | IN (condoned, not_condoned, deferred) | NULL | R | Academic Council outcome. |
| decision_date | date | YES | — | NULL | R | Decision date. |
| order_document_version_id | uuid | YES | FK → doc.document_version | NULL | R | Order file. |
| status | text | NO | IN (opened, hod_recommended, ac_review, approved, rejected, closed) | opened | R | State. |
+ `AUDIT_MUTABLE`.

**Privacy:** grounds and evidence may contain medical information. They are Restricted, never embedded, and never shown to general faculty.

---

## 7. Assessment (`assessment`)

**Trace:** Research §8.5, §9.4; S1 §§17–19; G-15.

### ASM-01 `assessment.scheme`

**Purpose:** marks pattern applied to a course version. **Owner:** COE/Academic Council. **Class:** I. **Phase:** IE.
**PK:** `scheme_id`. **FKs:** `course_version_id`; `effective_from_term_id`; `effective_to_term_id`; `approved_by`; `policy_bundle_version_id`.
**Unique / checks:** unique `(course_version_id, name, effective_from_term_id)`; `effective_to_term_id IS NULL OR effective_to_term_id <> effective_from_term_id`; `status` in (draft, approved, active, superseded).
**Indexes:** `btree (course_version_id, status)`; `btree (effective_from_term_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| scheme_id | uuid | NO | PK | gen_random_uuid() | I | Scheme identity. |
| course_version_id | uuid | NO | FK → academic.course_version | — | I | Course version. |
| name | text | NO | length ≤ 100 | — | I | e.g. `Theory 40+40+60`. |
| effective_from_term_id | uuid | NO | FK → core.term | — | I | First term. |
| effective_to_term_id | uuid | YES | FK → core.term | NULL | I | Last term; null = open. |
| status | text | NO | IN (draft, approved, active, superseded) | draft | I | State. |
| approved_by | uuid | YES | FK → iam.person | NULL | I | Approver. |
| approved_at | timestamptz | YES | — | NULL | I | Approval time. |
| policy_bundle_version_id | uuid | YES | FK → policy.policy_bundle_version | NULL | I | Weighting/pass rules. |
+ `AUDIT_MUTABLE`.

### ASM-02 `assessment.component`

**Purpose:** mark-bearing component or sub-component. **Owner:** COE. **Class:** I. **Phase:** IE.
**PK:** `component_id`. **FKs:** `scheme_id`; `parent_component_id` (self).
**Unique / checks:** unique `(scheme_id, component_code)`; `max_marks > 0`; `weight_pct` 0–100; sum of sibling `weight_pct` = 100 per scheme (trigger or deferred check); `parent_component_id <> component_id`.
**Indexes:** `btree (scheme_id, sequence_no)`; `btree (parent_component_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| component_id | uuid | NO | PK | gen_random_uuid() | I | Component identity. |
| scheme_id | uuid | NO | FK → assessment.scheme | — | I | Scheme. |
| component_code | text | NO | IN (CIA1, CIA2, PCIA, PESE, ESE, ATTENDANCE, ASSIGNMENT, CLASS_TEST, VIVA, PROJECT) | — | I | Code. |
| name | text | NO | length ≤ 150 | — | I | Display name. |
| component_type | text | NO | IN (internal, external, practical, sessional) | internal | I | Class. |
| max_marks | numeric(6,2) | NO | > 0 | — | I | Maximum. |
| weight_pct | numeric(5,2) | NO | 0–100 | — | I | Contribution. |
| parent_component_id | uuid | YES | FK → assessment.component; ≠ self | NULL | I | Parent, for sub-components. |
| sequence_no | smallint | NO | ≥ 1 | 1 | I | Order. |
| attendance_linked | boolean | NO | — | false | I | Mark derived from attendance. |
+ `AUDIT_MUTABLE`.

**Immutability:** once any `mark_entry` exists for the scheme, `max_marks`, `weight_pct`, and `component_code` cannot be updated. A change creates a new scheme version.

### ASM-03 `assessment.schedule`

**Purpose:** when and where an assessment happens. **Owner:** COE. **Class:** I. **Phase:** IE.
**PK:** `schedule_id`. **FKs:** `component_id`; `course_offering_id`.
**Unique / checks:** unique `(component_id, course_offering_id, schedule_type)`; `scheduled_end > scheduled_start`; `duration_min > 0`.
**Indexes:** `btree (course_offering_id, scheduled_start)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| schedule_id | uuid | NO | PK | gen_random_uuid() | I | Schedule identity. |
| component_id | uuid | NO | FK → assessment.component | — | I | Component. |
| course_offering_id | uuid | NO | FK → academic.course_offering | — | I | Offering. |
| schedule_type | text | NO | IN (regular, makeup, reassessment) | regular | I | Why scheduled. |
| scheduled_start | timestamptz | NO | — | — | I | Start. |
| scheduled_end | timestamptz | NO | `> scheduled_start` | — | I | End. |
| duration_min | integer | NO | > 0 | — | I | Duration. |
| venue_text | text | YES | length ≤ 100 | NULL | I | Venue. |
| instructions | text | YES | length ≤ 2000 | NULL | I | Instructions. |
| status | text | NO | IN (planned, held, cancelled, rescheduled) | planned | I | State. |
+ `AUDIT_MUTABLE`.

### ASM-04 `assessment.mark_entry`

**Purpose:** identity of a student's mark for a component; current pointer. **Owner:** Faculty. **Class:** C. **Phase:** IE.
**PK:** `mark_entry_id`. **FKs:** `student_id`; `component_id`; `course_offering_id`.
**Unique / checks:** unique `(student_id, component_id, course_offering_id)`; `current_version_no >= 1`; `status` in (draft, submitted, verified, locked).
**Indexes:** `btree (course_offering_id, component_id)`; `btree (student_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| mark_entry_id | uuid | NO | PK | gen_random_uuid() | C | Mark identity. |
| student_id | uuid | NO | FK → student.student | — | C | Student. |
| component_id | uuid | NO | FK → assessment.component | — | C | Component. |
| course_offering_id | uuid | NO | FK → academic.course_offering | — | C | Offering. |
| current_version_no | integer | NO | ≥ 1 | 1 | C | Latest version. |
| status | text | NO | IN (draft, submitted, verified, locked) | draft | C | Aggregate state. |
| is_absent | boolean | NO | — | false | C | Absent flag. |
| is_exempt | boolean | NO | — | false | C | Exemption flag. |
+ `AUDIT_MUTABLE`.

### ASM-05 `assessment.mark_entry_version`

**Purpose:** immutable version of a mark. **Owner:** Faculty/HOD. **Class:** C. **Phase:** IE.
**PK:** `mark_entry_version_id`. **FKs:** `mark_entry_id`; `entered_by`; `verified_by`.
**Unique / checks:** unique `(mark_entry_id, version_no)`; `marks_obtained >= 0`; `marks_obtained <= max_marks_snapshot`; `status` in (draft, submitted, verified, locked); update/delete rejected after `status = 'verified'`.
**Indexes:** `btree (mark_entry_id, version_no DESC)`; `btree (entered_by)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| mark_entry_version_id | uuid | NO | PK | gen_random_uuid() | C | Version identity. |
| mark_entry_id | uuid | NO | FK → assessment.mark_entry | — | C | Parent mark. |
| version_no | integer | NO | ≥ 1; unique per mark | — | C | Version. |
| marks_obtained | numeric(6,2) | YES | ≥ 0; ≤ snapshot | NULL | C | Score; null if absent. |
| max_marks_snapshot | numeric(6,2) | NO | > 0 | — | C | Maximum at entry time. |
| is_absent | boolean | NO | — | false | C | Absent. |
| is_exempt | boolean | NO | — | false | C | Exempt. |
| status | text | NO | IN (draft, submitted, verified, locked) | draft | C | State. |
| entered_by | uuid | NO | FK → iam.person | — | C | Enterer. |
| entered_at | timestamptz | NO | — | now() | C | Entry time. |
| submitted_at | timestamptz | YES | `>= entered_at` | NULL | C | Submission. |
| verified_by | uuid | YES | FK → iam.person | NULL | C | Verifier. |
| verified_at | timestamptz | YES | `>= submitted_at` | NULL | C | Verification. |
| change_reason | text | YES | length ≤ 1000 | NULL | C | Why this version exists. |
+ `AUDIT_IMMUTABLE`.

**Separation of duties:** `verified_by` must differ from `entered_by` where the policy requires independent verification. This is enforced in the authorization service against `iam.permission`, not by a hard-coded trigger, because small departments may need an exception recorded as a policy parameter.

### ASM-06 `assessment.mark_correction`

**Purpose:** a change after submission, with evidence and approval. **Owner:** COE/HOD. **Class:** C/R. **Phase:** IE.
**PK:** `mark_correction_id`. **FKs:** `mark_entry_id`; `from_version_id`; `to_version_id`; `requested_by`; `approved_by`; `evidence_document_version_id`.
**Unique / checks:** `from_version_id <> to_version_id`; both versions belong to the same `mark_entry_id` (trigger); `status` in (requested, approved, rejected, withdrawn).
**Indexes:** `btree (mark_entry_id, requested_at DESC)`; `btree (status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| mark_correction_id | uuid | NO | PK | gen_random_uuid() | C | Correction identity. |
| mark_entry_id | uuid | NO | FK → assessment.mark_entry | — | C | Mark. |
| from_version_id | uuid | NO | FK → assessment.mark_entry_version | — | C | Replaced version. |
| to_version_id | uuid | NO | FK → assessment.mark_entry_version; `<> from_version_id` | — | C | Replacement version. |
| reason | text | NO | length 5–2000 | — | R | Justification. |
| requested_by | uuid | NO | FK → iam.person | — | C | Requester. |
| requested_at | timestamptz | NO | — | now() | C | Request time. |
| approved_by | uuid | YES | FK → iam.person | NULL | C | Approver. |
| approved_at | timestamptz | YES | `>= requested_at` | NULL | C | Approval time. |
| status | text | NO | IN (requested, approved, rejected, withdrawn) | requested | C | State. |
| evidence_document_version_id | uuid | YES | FK → doc.document_version | NULL | R | Evidence. |
+ `AUDIT_MUTABLE`.

### ASM-07 `assessment.conflict_declaration`

**Purpose:** faculty declaration of a ward/relative in a course. **Owner:** HOD. **Class:** R. **Phase:** IE.
**PK:** `conflict_declaration_id`. **FKs:** `faculty_person_id`; `course_offering_id`; `student_id`; `reassigned_to_person_id`; `document_version_id`.
**Unique / checks:** unique `(faculty_person_id, course_offering_id, student_id)`; `faculty_person_id <> reassigned_to_person_id`; `action_taken` in (none, reassigned, recused); `status` in (declared, under_review, resolved, rejected).
**Indexes:** `btree (course_offering_id, status)`; `btree (faculty_person_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| conflict_declaration_id | uuid | NO | PK | gen_random_uuid() | R | Declaration identity. |
| faculty_person_id | uuid | NO | FK → iam.person | — | R | Declaring teacher. |
| course_offering_id | uuid | NO | FK → academic.course_offering | — | R | Affected offering. |
| student_id | uuid | NO | FK → student.student | — | R | Student concerned. |
| relationship_type | text | NO | IN (child, sibling, spouse, relative, other) | — | R | Relationship. |
| declared_at | timestamptz | NO | — | now() | R | When declared. |
| action_taken | text | NO | IN (none, reassigned, recused) | none | R | Mitigation. |
| reassigned_to_person_id | uuid | YES | FK → iam.person; `<> faculty_person_id` | NULL | R | Replacement assessor. |
| status | text | NO | IN (declared, under_review, resolved, rejected) | declared | R | State. |
| document_version_id | uuid | YES | FK → doc.document_version | NULL | R | Signed declaration. |
+ `AUDIT_MUTABLE`.

**Enforcement:** the authorization service checks for an unresolved declaration before allowing `mark_entry` or `attendance.record` writes by that faculty member for that student. It is a system rule derived from ASS-09, not a new institutional policy.

---

## 8. Examination and Results (`exam`)

**Trace:** Research §8.6–8.8, §9.5–9.7, §12 M10–M14; S1 §§20–24, S8, S16 §3.4; G-12, G-16, G-17.

**Initial-release scope:** read-only imported results and grade cards. No result computation and no automated publication. The tables below are the seven Initial entities; the fifteen future entities are catalogued in `ENTITY_CATALOG.md` §8.2 and are not column-dicted here.

### EXM-01 `exam.result_import`

**Purpose:** provenance of an imported result file. **Owner:** COE. **Class:** C. **Phase:** IE.
**PK:** `result_import_id`. **FKs:** `term_id`; `programme_id`; `imported_by`; `external_system_id` (nullable).
**Unique / checks:** unique `(term_id, programme_id, sha256)`; `length(sha256) = 64`; `row_count >= 0`; `error_count >= 0`; `status` in (received, parsed, validated, imported, failed, quarantined).
**Indexes:** `btree (term_id, programme_id)`; `btree (status, imported_at)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| result_import_id | uuid | NO | PK | gen_random_uuid() | C | Import identity. |
| term_id | uuid | NO | FK → core.term | — | C | Term. |
| programme_id | uuid | NO | FK → academic.programme | — | C | Programme. |
| external_system_id | uuid | YES | FK → integration.external_system | NULL | C | Source system, if any. |
| source_label | text | NO | length ≤ 100 | — | C | Human source name. |
| file_name | text | NO | length ≤ 300 | — | C | Original file. |
| sha256 | text | NO | length = 64; unique per term/programme | — | C | File hash. |
| imported_at | timestamptz | NO | — | now() | C | Import time. |
| imported_by | uuid | NO | FK → iam.person | — | C | Operator. |
| row_count | integer | NO | ≥ 0 | 0 | C | Rows read. |
| error_count | integer | NO | ≥ 0 | 0 | C | Rows rejected. |
| status | text | NO | IN (received, parsed, validated, imported, failed, quarantined) | received | C | State. |
| notes | text | YES | length ≤ 2000 | NULL | C | Notes. |
+ `AUDIT_IMMUTABLE`.

### EXM-02 `exam.result_set`

**Purpose:** a unit of results approved/published together. **Owner:** COE. **Class:** C. **Phase:** IE.
**PK:** `result_set_id`. **FKs:** `term_id`; `programme_id`; `batch_id`; `import_id`; `approved_by`; `policy_bundle_version_id`.
**Unique / checks:** unique `(term_id, programme_id, batch_id, exam_label, result_type)`; `status` in (imported, draft, approved, published, withheld); `approved_at >= published_at` is not allowed (publication cannot precede approval).
**Indexes:** `btree (term_id, programme_id, status)`; `btree (published_at)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| result_set_id | uuid | NO | PK | gen_random_uuid() | C | Set identity. |
| term_id | uuid | NO | FK → core.term | — | C | Term. |
| programme_id | uuid | NO | FK → academic.programme | — | C | Programme. |
| batch_id | uuid | YES | FK → academic.batch | NULL | C | Cohort; null for cross-batch sets. |
| import_id | uuid | YES | FK → exam.result_import | NULL | C | Import provenance. |
| exam_label | text | NO | length ≤ 100 | — | C | e.g. `Even 2025-26`. |
| result_type | text | NO | IN (regular, supplementary, super_supplementary) | regular | C | Attempt class. |
| status | text | NO | IN (imported, draft, approved, published, withheld) | imported | C | State. |
| approved_by | uuid | YES | FK → iam.person | NULL | C | Approver; null until G-12 resolved. |
| approved_at | timestamptz | YES | — | NULL | C | Approval time. |
| published_at | timestamptz | YES | `>= approved_at` | NULL | C | Publication time. |
| external_publication_ref | text | YES | length ≤ 200 | NULL | C | Reference when published outside this system. |
| policy_bundle_version_id | uuid | YES | FK → policy.policy_bundle_version | NULL | C | Rules applied. |
+ `AUDIT_MUTABLE`.

**Publication gate:** a set with `status = 'published'` must have either a non-null `approved_by`/`approved_at` or a non-null `external_publication_ref`. This is a `CHECK`, so the database cannot hold an unattributed publication.

### EXM-03 `exam.result_record`

**Purpose:** per-student, per-course result identity across attempts. **Owner:** COE. **Class:** C. **Phase:** IE.
**PK:** `result_record_id`. **FKs:** `student_id`; `course_version_id`; `course_offering_id` (nullable); `result_set_id`.
**Unique / checks:** unique `(student_id, course_version_id, result_set_id)`; `attempt_no >= 1`; `year_of_study` 1–5; `status` in (pass, fail, absent, withheld).
**Indexes:** `btree (student_id, course_version_id)`; `btree (result_set_id)`; `btree (status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| result_record_id | uuid | NO | PK | gen_random_uuid() | C | Result identity. |
| student_id | uuid | NO | FK → student.student | — | C | Student. |
| course_version_id | uuid | NO | FK → academic.course_version | — | C | Course version. |
| course_offering_id | uuid | YES | FK → academic.course_offering | NULL | C | Offering, when known. |
| result_set_id | uuid | NO | FK → exam.result_set | — | C | Owning set. |
| attempt_no | smallint | NO | ≥ 1 | 1 | C | Attempt. |
| is_backlog | boolean | NO | — | false | C | Backlog attempt. |
| year_of_study | smallint | NO | 1–5 | — | C | Year, for the practical-failure rule. |
| current_revision_no | integer | NO | ≥ 1 | 1 | C | Latest revision pointer. |
| status | text | NO | IN (pass, fail, absent, withheld) | fail | C | Course outcome. |
+ `AUDIT_MUTABLE`.

**Why `year_of_study`:** the practical-ESE rule differs for years 1–3 (year lag) and the final year (supplementary) — C-06. Storing the year makes the distinction auditable instead of inferring it from a term sequence.

### EXM-04 `exam.result_revision`

**Purpose:** immutable computed/published result version. **Owner:** COE. **Class:** C. **Phase:** IE.
**PK:** `result_revision_id`. **FKs:** `result_record_id`; `computed_by`; `policy_bundle_version_id`.
**Unique / checks:** unique `(result_record_id, revision_no)`; `grade` in (O, E, A, B, C, D, F, I); `result_status` in (X, XP, P); `grade_point` 0–10; all totals ≥ 0; update/delete rejected once `published_at` is set.
**Indexes:** `btree (result_record_id, revision_no DESC)`; `btree (result_status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| result_revision_id | uuid | NO | PK | gen_random_uuid() | C | Revision identity. |
| result_record_id | uuid | NO | FK → exam.result_record | — | C | Parent result. |
| revision_no | integer | NO | ≥ 1; unique per result | 1 | C | Revision. |
| cia_total | numeric(6,2) | YES | ≥ 0 | NULL | C | CIA total. |
| pcia_total | numeric(6,2) | YES | ≥ 0 | NULL | C | PCIA total. |
| ese_total | numeric(6,2) | YES | ≥ 0 | NULL | C | ESE total. |
| pese_total | numeric(6,2) | YES | ≥ 0 | NULL | C | PESE total. |
| total_marks | numeric(6,2) | YES | ≥ 0 | NULL | C | Combined total. |
| grade | text | YES | IN (O, E, A, B, C, D, F, I) | NULL | C | Letter grade. |
| grade_point | numeric(4,2) | YES | 0–10 | NULL | C | Grade point. |
| result_status | text | YES | IN (X, XP, P) | NULL | C | Promotion status. |
| computed_at | timestamptz | NO | — | now() | C | Computation time. |
| computed_by | uuid | YES | FK → iam.person | NULL | C | Actor; null for import. |
| published_at | timestamptz | YES | — | NULL | C | Publication time. |
| policy_bundle_version_id | uuid | YES | FK → policy.policy_bundle_version | NULL | C | Rules applied. |
| change_reason | text | YES | length ≤ 1000 | NULL | C | Why a new revision exists. |
+ `AUDIT_IMMUTABLE`.

**Status semantics:** `X` = not eligible to proceed; `XP` = eligible with backlogs; `P` = passed and promoted (S1 §22.5.1). The database never stores these as `0/1/2`.

### EXM-05 `exam.result_input`

**Purpose:** traceability from a result revision to the exact mark versions used. **Owner:** COE. **Class:** C. **Phase:** IE.
**PK:** `result_input_id`. **FKs:** `result_revision_id`; `mark_entry_version_id`.
**Unique / checks:** unique `(result_revision_id, component_code)`; `marks_used >= 0`; `max_marks_snapshot > 0`.
**Indexes:** `btree (mark_entry_version_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| result_input_id | uuid | NO | PK | gen_random_uuid() | C | Input identity. |
| result_revision_id | uuid | NO | FK → exam.result_revision | — | C | Revision. |
| mark_entry_version_id | uuid | YES | FK → assessment.mark_entry_version | NULL | C | Mark version used; null for imported totals. |
| component_code | text | NO | length ≤ 30 | — | C | Component. |
| marks_used | numeric(6,2) | NO | ≥ 0 | — | C | Value used. |
| max_marks_snapshot | numeric(6,2) | NO | > 0 | — | C | Maximum at use time. |
+ `AUDIT_IMMUTABLE`.

**Rule:** if the revision was computed by BCREC, every component must have a `mark_entry_version_id`. If it was imported as a total, the row records the external component label and the set's `external_publication_ref` carries provenance. The design never pretends a computed mark exists when it does not.

### EXM-06 `exam.grade_card`

**Purpose:** published term grade card, versioned. **Owner:** COE. **Class:** C. **Phase:** IE.
**PK:** `grade_card_id`. **FKs:** `student_id`; `term_id`; `result_set_id`; `document_version_id`.
**Unique / checks:** unique `(student_id, term_id, version_no)`; partial unique `(student_id, term_id) WHERE is_current`; `sgpa`, `ygpa`, `cgpa` 0–10; `credits_earned <= credits_registered`; `status` in (draft, published, superseded, withheld).
**Indexes:** `btree (student_id, term_id, version_no DESC)`; `btree (result_set_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| grade_card_id | uuid | NO | PK | gen_random_uuid() | C | Card identity. |
| student_id | uuid | NO | FK → student.student | — | C | Student. |
| term_id | uuid | NO | FK → core.term | — | C | Term. |
| result_set_id | uuid | YES | FK → exam.result_set | NULL | C | Source set. |
| version_no | integer | NO | ≥ 1; unique per student/term | 1 | C | Version. |
| sgpa | numeric(4,2) | YES | 0–10 | NULL | C | Semester GPA. |
| ygpa | numeric(4,2) | YES | 0–10 | NULL | C | Year GPA. |
| cgpa | numeric(4,2) | YES | 0–10 | NULL | C | Cumulative GPA. |
| credits_registered | numeric(5,1) | YES | ≥ 0 | NULL | C | Credits attempted. |
| credits_earned | numeric(5,1) | YES | ≥ 0; ≤ registered | NULL | C | Credits earned. |
| status | text | NO | IN (draft, published, superseded, withheld) | draft | C | State. |
| published_at | timestamptz | YES | — | NULL | C | Publication time. |
| is_current | boolean | NO | — | true | C | Current card. |
| document_version_id | uuid | YES | FK → doc.document_version | NULL | C | Rendered PDF. |
+ `AUDIT_MUTABLE`.

### EXM-07 `exam.grade_card_result`

**Purpose:** explicit composition of a grade card. **Owner:** COE. **Class:** C. **Phase:** IE.
**PK:** `grade_card_result_id`. **FKs:** `grade_card_id`; `result_record_id`; `result_revision_id`.
**Unique / checks:** unique `(grade_card_id, result_record_id)`; the revision must belong to the record (trigger).
**Indexes:** `btree (result_record_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| grade_card_result_id | uuid | NO | PK | gen_random_uuid() | C | Link identity. |
| grade_card_id | uuid | NO | FK → exam.grade_card | — | C | Card. |
| result_record_id | uuid | NO | FK → exam.result_record | — | C | Result. |
| result_revision_id | uuid | NO | FK → exam.result_revision | — | C | Exact revision included. |
| included | boolean | NO | — | true | C | Included in SGPA. |
+ `AUDIT_IMMUTABLE`.

**Why this table exists:** a grade card is not derivable later from "all results in the term" because a correction changes which revision was current. The explicit link preserves the published composition.

---

## 9. Faculty and Mentorship (`faculty`)

**Trace:** Research §8.9–8.10, §9.11; S3, S12; G-18.

### FAC-01 `faculty.faculty_profile`

**Purpose:** academic staff employment and academic attributes. **Owner:** HR/HOD. **Class:** C. **Phase:** IE.
**PK:** `faculty_profile_id`. **FKs:** `person_id`; `department_id`.
**Unique / checks:** unique `person_id`; unique `lower(employee_id)`; `relieving_date IS NULL OR relieving_date >= joining_date`; `employment_type` in (permanent, contractual, visiting, guest, part_time); `status` in (active, on_leave, relieved, retired).
**Indexes:** `btree (department_id, status)`; `btree (designation)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| faculty_profile_id | uuid | NO | PK | gen_random_uuid() | C | Profile identity. |
| person_id | uuid | NO | FK → iam.person; unique | — | C | The human. |
| employee_id | text | NO | unique lower(); length ≤ 30 | — | C | HR employee number. |
| designation | text | NO | length ≤ 100 | — | C | e.g. Professor, Associate Professor. |
| department_id | uuid | NO | FK → academic.department | — | C | Home department. |
| joining_date | date | NO | — | — | C | Date joined. |
| employment_type | text | NO | IN (permanent, contractual, visiting, guest, part_time) | permanent | C | Engagement type. |
| highest_qualification | text | YES | length ≤ 200 | NULL | C | Highest degree. |
| specialization | text | YES | length ≤ 300 | NULL | C | Teaching/research area. |
| workload_category | text | YES | IN (principal, professor, associate_professor, assistant_professor, other) | NULL | I | Used for workload rules (SRV). |
| status | text | NO | IN (active, on_leave, relieved, retired) | active | C | State. |
| relieving_date | date | YES | `>= joining_date` | NULL | C | When employment ended. |
+ `AUDIT_MUTABLE`.

**Note:** `designation` is an employment attribute, not a system role. The authority to enter marks or approve results comes from `iam.role_assignment`.

### FAC-02 `faculty.staff_profile`

**Purpose:** non-teaching staff attributes. **Owner:** HR. **Class:** C. **Phase:** IE.
**PK:** `staff_profile_id`. **FKs:** `person_id`; `org_unit_id`; `reporting_to_person_id`.
**Unique / checks:** unique `person_id`; unique `lower(employee_id)`; `reporting_to_person_id <> person_id`; `relieving_date >= joining_date` when present.
**Indexes:** `btree (org_unit_id, status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| staff_profile_id | uuid | NO | PK | gen_random_uuid() | C | Profile identity. |
| person_id | uuid | NO | FK → iam.person; unique | — | C | The human. |
| employee_id | text | NO | unique lower() | — | C | HR number. |
| designation | text | NO | length ≤ 100 | — | C | Job title. |
| org_unit_id | uuid | NO | FK → core.org_unit | — | C | Office/cell. |
| reporting_to_person_id | uuid | YES | FK → iam.person; ≠ person_id | NULL | C | Supervisor. |
| joining_date | date | NO | — | — | C | Date joined. |
| employment_type | text | NO | IN (permanent, contractual, outsourced) | permanent | C | Engagement. |
| status | text | NO | IN (active, on_leave, relieved, retired) | active | C | State. |
| relieving_date | date | YES | `>= joining_date` | NULL | C | End date. |
+ `AUDIT_MUTABLE`.

### FAC-03 `faculty.mentor_assignment`

**Purpose:** term-bound mentor–mentee relationship. **Owner:** HOD. **Class:** C/R. **Phase:** IE.
**PK:** `mentor_assignment_id`. **FKs:** `mentor_person_id`; `student_id`; `term_id`; `assigned_by`.
**Unique / checks:** partial unique `(student_id, term_id) WHERE status = 'active'`; `valid_to > valid_from`; `mentor_person_id` must hold an active faculty profile (trigger); `notes_visibility` in (mentor_only, hod_and_mentor).
**Indexes:** `btree (mentor_person_id, term_id)`; `btree (student_id, term_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| mentor_assignment_id | uuid | NO | PK | gen_random_uuid() | C | Assignment identity. |
| mentor_person_id | uuid | NO | FK → iam.person | — | C | Mentor. |
| student_id | uuid | NO | FK → student.student | — | C | Mentee. |
| term_id | uuid | NO | FK → core.term | — | C | Term. |
| assigned_at | timestamptz | NO | — | now() | C | Allocation time. |
| valid_from | date | NO | — | current_date | C | Start. |
| valid_to | date | YES | `> valid_from` | NULL | C | End. |
| status | text | NO | IN (active, ended, revoked) | active | C | State. |
| assigned_by | uuid | YES | FK → iam.person | NULL | C | Allocating HOD. |
| notes_visibility | text | NO | IN (mentor_only, hod_and_mentor) | mentor_only | R | Who may read mentoring notes. |
+ `AUDIT_MUTABLE`.

**Access rule:** a mentor assignment grants read access to the mentee's attendance and published results for the assigned term only. It never grants marks-entry or result-publication rights.

---

## 10. Notices and Documents (`doc`)

**Trace:** Research §8.11, §10.10, §11.10, §13.7; S1, S20; G-19, G-22.

### DOC-01 `doc.document`

**Purpose:** logical source document (regulation, order, policy, circular, prospectus). **Owner:** Registrar/CIP Curator. **Class:** P/I/C/R/G. **Phase:** F.
**PK:** `document_id`. **FKs:** `issuer_org_unit_id`; `owner_org_unit_id`; `retention_schedule_id`.
**Unique / checks:** unique `(issuer_org_unit_id, reference_no)` where `reference_no` is not null; `document_type` from the controlled list; `effective_date >= document_date` when both present; `classification` in (P, I, C, R, G).
**Indexes:** `btree (document_type, document_date)`; `btree (classification)`; `gin (to_tsvector('simple', title))`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| document_id | uuid | NO | PK | gen_random_uuid() | Inherits | Document identity. |
| title | text | NO | length ≤ 500 | — | Inherits | Title. |
| document_type | text | NO | IN (regulation, policy, order, notification, circular, prospectus, syllabus, minutes, report, form, other) | — | Inherits | Kind. |
| issuer_name | text | NO | length ≤ 200 | — | Inherits | Who issued it. |
| issuer_org_unit_id | uuid | YES | FK → core.org_unit | NULL | Inherits | Issuing unit. |
| reference_no | text | YES | unique per issuer where not null | NULL | Inherits | Order/reference number. |
| document_date | date | NO | — | — | Inherits | Date on the document. |
| effective_date | date | YES | `>= document_date` | NULL | Inherits | When it takes effect. |
| classification | text | NO | IN (P, I, C, R, G) | I | Inherits | Highest classification of content. |
| owner_org_unit_id | uuid | YES | FK → core.org_unit | NULL | Inherits | Custodian. |
| status | text | NO | IN (draft, active, superseded, withdrawn, archived) | active | Inherits | State of the logical document. |
| source_url | text | YES | length ≤ 2000 | NULL | Inherits | Public source, when applicable. |
| retention_schedule_id | uuid | YES | FK → ops.retention_schedule | NULL | Inherits | Retention rule; null until G-22. |
+ `AUDIT_MUTABLE`.

### DOC-02 `doc.document_version`

**Purpose:** immutable file version. **Owner:** CIP Curator. **Class:** P/I/C/R/G. **Phase:** F.
**PK:** `document_version_id`. **FKs:** `document_id`; `supersedes_version_id` (self); `approved_by`.
**Unique / checks:** unique `(document_id, version_no)`; unique `sha256` (identical bytes are the same version); `length(sha256) = 64`; `file_size >= 0`; `page_count >= 0`; update/delete rejected after `status` in (active, superseded).
**Indexes:** `btree (document_id, version_no DESC)`; `btree (sha256)`; `btree (status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| document_version_id | uuid | NO | PK | gen_random_uuid() | Inherits | Version identity. |
| document_id | uuid | NO | FK → doc.document | — | Inherits | Logical document. |
| version_no | integer | NO | ≥ 1; unique per document | 1 | Inherits | Version. |
| version_label | text | YES | length ≤ 50 | NULL | Inherits | e.g. `Edition 1.0`. |
| file_uri | text | NO | object-storage URI | — | Inherits | Immutable original. |
| mime_type | text | NO | length ≤ 100 | — | Inherits | File type. |
| file_size | bigint | YES | ≥ 0 | NULL | Inherits | Bytes. |
| sha256 | text | NO | unique; length = 64 | — | Inherits | Content hash. |
| page_count | integer | YES | ≥ 0 | NULL | Inherits | Pages. |
| ocr_used | boolean | NO | — | false | Inherits | Text is OCR-derived. |
| language | text | YES | IN (en, bn, hi, multilingual, other) | NULL | Inherits | Content language. |
| change_note | text | YES | length ≤ 2000 | NULL | Inherits | What changed. |
| supersedes_version_id | uuid | YES | FK → doc.document_version; ≠ self | NULL | Inherits | Prior version. |
| effective_from | date | YES | — | NULL | Inherits | Effective start. |
| effective_to | date | YES | `> effective_from` | NULL | Inherits | Effective end. |
| status | text | NO | IN (draft, active, superseded, withdrawn, archived) | draft | Inherits | State. |
| ingested_at | timestamptz | YES | — | NULL | Inherits | When added to the corpus. |
| approved_by | uuid | YES | FK → iam.person | NULL | Inherits | Approver. |
| approved_at | timestamptz | YES | — | NULL | Inherits | Approval time. |
+ `AUDIT_IMMUTABLE`.

**Classification inheritance:** a version cannot be less restricted than its `document.classification`. A trigger rejects a downgrade unless an explicit, audited declassification record exists (future feature).

### DOC-03 `doc.document_relation`

**Purpose:** non-linear relations between versions. **Owner:** CIP Curator. **Class:** I. **Phase:** F.
**PK:** `document_relation_id`. **FKs:** `from_version_id`; `to_version_id`.
**Unique / checks:** unique `(from_version_id, to_version_id, relation_type)`; `from_version_id <> to_version_id`; `relation_type` in (supersedes, corrigendum, attachment, translation, duplicate, references).
**Indexes:** `btree (to_version_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| document_relation_id | uuid | NO | PK | gen_random_uuid() | I | Relation identity. |
| from_version_id | uuid | NO | FK → doc.document_version | — | I | Source version. |
| to_version_id | uuid | NO | FK → doc.document_version; ≠ from | — | I | Target version. |
| relation_type | text | NO | IN (supersedes, corrigendum, attachment, translation, duplicate, references) | — | I | Kind. |
| note | text | YES | length ≤ 1000 | NULL | I | Explanation. |
+ `AUDIT_MUTABLE`.

### DOC-04 `doc.notice`

**Purpose:** logical notice identity. **Owner:** Issuing office. **Class:** P/I. **Phase:** IE.
**PK:** `notice_id`. **FKs:** `issuing_org_unit_id`; `owner_person_id`.
**Unique / checks:** unique `lower(notice_no)`; `category` in (academic, examination, admission, fee, event, placement, general, urgent).
**Indexes:** `btree (category, status)`; `btree (issuing_org_unit_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| notice_id | uuid | NO | PK | gen_random_uuid() | I | Notice identity. |
| notice_no | text | NO | unique lower(); length ≤ 50 | — | I | Notice number. |
| category | text | NO | IN (academic, examination, admission, fee, event, placement, general, urgent) | general | I | Kind. |
| issuing_org_unit_id | uuid | YES | FK → core.org_unit | NULL | I | Issuer. |
| owner_person_id | uuid | YES | FK → iam.person | NULL | I | Responsible officer. |
| status | text | NO | IN (draft, active, withdrawn, archived) | draft | I | Logical state. |
+ `AUDIT_MUTABLE`.

### DOC-05 `doc.notice_version`

**Purpose:** published/corrected notice content. **Owner:** Issuing office. **Class:** P/I. **Phase:** IE.
**PK:** `notice_version_id`. **FKs:** `notice_id`; `supersedes_version_id`; `document_version_id`; `approved_by`.
**Unique / checks:** unique `(notice_id, version_no)`; `effective_to > effective_from` when present; `status` in (draft, scheduled, published, superseded, withdrawn); `publish_at` required when `status = 'scheduled'`.
**Indexes:** `btree (notice_id, version_no DESC)`; `btree (publish_at, status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| notice_version_id | uuid | NO | PK | gen_random_uuid() | I | Version identity. |
| notice_id | uuid | NO | FK → doc.notice | — | I | Logical notice. |
| version_no | integer | NO | ≥ 1; unique per notice | 1 | I | Version. |
| title | text | NO | length ≤ 300 | — | I | Title. |
| body_markdown | text | NO | length ≤ 20000 | — | I | Content. |
| publish_at | timestamptz | YES | — | NULL | I | Scheduled publication. |
| effective_from | timestamptz | YES | — | NULL | I | Effective start. |
| effective_to | timestamptz | YES | `> effective_from` | NULL | I | Effective end. |
| status | text | NO | IN (draft, scheduled, published, superseded, withdrawn) | draft | I | State. |
| supersedes_version_id | uuid | YES | FK → doc.notice_version; ≠ self | NULL | I | Prior version. |
| document_version_id | uuid | YES | FK → doc.document_version | NULL | I | Attached PDF/file. |
| approved_by | uuid | YES | FK → iam.person | NULL | I | Approver. |
| approved_at | timestamptz | YES | — | NULL | I | Approval time. |
+ `AUDIT_MUTABLE`.

**G-19:** the approver is recorded but the approval workflow is not automated until the notice-approval authority is confirmed. A notice may be `published` with an external approval reference recorded in `ops.audit_event` rather than `approved_by`.

### DOC-06 `doc.notice_audience`

**Purpose:** who a notice version applies to. **Owner:** Issuing office. **Class:** I. **Phase:** IE.
**PK:** `notice_audience_id`. **FKs:** `notice_version_id`; `programme_id`; `batch_id`; `term_id`; `role_id`; `org_unit_id`.
**Unique / checks:** unique `(notice_version_id, audience_type, programme_id, batch_id, term_id, role_id, org_unit_id)`; `audience_type` in (all, programme, batch, term, role, org_unit, person); at least one target must be present unless `audience_type = 'all'`.
**Indexes:** `btree (notice_version_id)`; `btree (programme_id, batch_id)`; `btree (role_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| notice_audience_id | uuid | NO | PK | gen_random_uuid() | I | Audience row. |
| notice_version_id | uuid | NO | FK → doc.notice_version | — | I | Notice version. |
| audience_type | text | NO | IN (all, programme, batch, term, role, org_unit, person) | all | I | Targeting mode. |
| programme_id | uuid | YES | FK → academic.programme | NULL | I | Programme target. |
| batch_id | uuid | YES | FK → academic.batch | NULL | I | Batch target. |
| term_id | uuid | YES | FK → core.term | NULL | I | Term target. |
| role_id | uuid | YES | FK → iam.role | NULL | I | Role target. |
| org_unit_id | uuid | YES | FK → core.org_unit | NULL | I | Unit target. |
+ `AUDIT_MUTABLE`.

**Version-bound:** audience attaches to the version, so a correction can change the audience without rewriting history.

---

## 11. Knowledge (`knowledge`)

**Trace:** Research §13.7–13.9, §11.10; database audit (28 embeddings in Chroma, MiniLM 384 dimensions, CPU-only).

### KNW-01 `knowledge.document_chunk`

**Purpose:** retrieval unit derived from a document version. **Owner:** CIP Curator. **Class:** inherits document. **Phase:** IC.
**PK:** `chunk_id`. **FKs:** `document_version_id`; `ingestion_run_id`.
**Unique / checks:** unique `(document_version_id, chunking_profile, sequence_no)`; `page_to >= page_from` when both present; `token_count > 0`; `length(text_hash) = 64`; a trigger rejects a chunk whose source document is classified `R` or `G`.
**Indexes:** `gin (to_tsvector('simple', chunk_text))` for lexical retrieval; `btree (document_version_id, sequence_no)`; `btree (language)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| chunk_id | uuid | NO | PK | gen_random_uuid() | Inherits | Chunk identity. |
| document_version_id | uuid | NO | FK → doc.document_version | — | Inherits | Source version. |
| ingestion_run_id | uuid | YES | FK → knowledge.ingestion_run | NULL | I | Producing run. |
| sequence_no | integer | NO | ≥ 0; unique per version/profile | — | Inherits | Order in the document. |
| chunk_text | text | NO | length 1–20000 | — | Inherits | Retrieval text. |
| section_path | text | YES | length ≤ 1000 | NULL | Inherits | Heading path. |
| page_from | integer | YES | ≥ 1 | NULL | Inherits | First page. |
| page_to | integer | YES | ≥ page_from | NULL | Inherits | Last page. |
| token_count | integer | NO | > 0 | — | Inherits | Token count. |
| language | text | YES | IN (en, bn, hi, multilingual, other) | NULL | Inherits | Detected language. |
| chunking_profile | text | NO | length ≤ 50 | 'default' | Inherits | Chunker configuration. |
| text_hash | text | NO | length = 64 | — | Inherits | Normalised-text hash. |
| created_at | timestamptz | NO | — | now() | Inherits | Creation time. |
+ `AUDIT_IMMUTABLE`.

**Exclusion rule:** restricted personal data, answer scripts, medical records, fee ledgers, disciplinary files, and identity documents are never chunked. The classification check is a database trigger plus an ingestion-service filter.

### KNW-02 `knowledge.embedding`

**Purpose:** vector representation of a chunk. **Owner:** AI Platform. **Class:** I. **Phase:** IC.
**PK:** `embedding_id`. **FKs:** `chunk_id`.
**Unique / checks:** unique `(chunk_id, model_name, model_version)`; `dimensions > 0`; `dimensions` must equal the vector length (trigger); `is_active` partial unique `(chunk_id) WHERE is_active` if only one active model is desired — the design instead allows one active per model name.
**Indexes:** HNSW or IVFFlat on `embedding` with the chosen distance operator (OD-06); `btree (chunk_id, model_name)`; partial index `WHERE is_active`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| embedding_id | uuid | NO | PK | gen_random_uuid() | I | Embedding identity. |
| chunk_id | uuid | NO | FK → knowledge.document_chunk | — | I | Chunk. |
| model_name | text | NO | length ≤ 100 | — | I | e.g. `all-MiniLM-L6-v2`. |
| model_version | text | NO | length ≤ 50 | — | I | Model revision. |
| dimensions | integer | NO | > 0 | — | I | Vector length. |
| embedding | vector(1024) | NO | dimension fixed at deployment | — | I | Vector. |
| created_at | timestamptz | NO | — | now() | I | Creation time. |
| is_active | boolean | NO | — | true | I | Used for retrieval. |
+ `AUDIT_IMMUTABLE`.

**Dimension decision:** the baseline MiniLM model produces 384 dimensions; the illustrated type is `vector(1024)` for a multilingual model. The choice is OD-06 and must be fixed before DDL. The column is shown at 1024 because a multilingual model is the likely target; changing it is a deployment decision, not a data-model change.

### KNW-03 `knowledge.ingestion_run`

**Purpose:** provenance of parsing, chunking, and embedding. **Owner:** CIP Curator. **Class:** I. **Phase:** IC.
**PK:** `ingestion_run_id`. **FK:** `triggered_by` (nullable).
**Unique / checks:** `finished_at >= started_at` when both present; all counts ≥ 0; `status` in (running, completed, completed_with_errors, failed).
**Indexes:** `btree (started_at DESC)`; `btree (status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| ingestion_run_id | uuid | NO | PK | gen_random_uuid() | I | Run identity. |
| triggered_by | uuid | YES | FK → iam.person | NULL | I | Operator; null = scheduled. |
| source_type | text | NO | IN (file_upload, url, folder_scan, api) | — | I | Input mode. |
| source_uri | text | YES | length ≤ 2000 | NULL | I | Source location. |
| started_at | timestamptz | NO | — | now() | I | Start. |
| finished_at | timestamptz | YES | `>= started_at` | NULL | I | Finish. |
| status | text | NO | IN (running, completed, completed_with_errors, failed) | running | I | State. |
| documents_seen | integer | NO | ≥ 0 | 0 | I | Documents examined. |
| versions_created | integer | NO | ≥ 0 | 0 | I | New versions. |
| chunks_created | integer | NO | ≥ 0 | 0 | I | Chunks written. |
| embeddings_created | integer | NO | ≥ 0 | 0 | I | Embeddings written. |
| error_count | integer | NO | ≥ 0 | 0 | I | Failures. |
| error_summary | text | YES | length ≤ 5000 | NULL | I | Failure summary. |
| parser_version | text | YES | length ≤ 50 | NULL | I | Parser build. |
| ocr_engine | text | YES | length ≤ 50 | NULL | I | OCR engine. |
| chunker_version | text | YES | length ≤ 50 | NULL | I | Chunker build. |
| embedding_model | text | YES | length ≤ 100 | NULL | I | Model used. |
+ `AUDIT_IMMUTABLE`.

---

## 12. CIP Runtime (`cip`)

**Trace:** Research §13.8–13.10, §11.10.

### CIP-01 `cip.conversation`

**Purpose:** a CIP session across text or voice. **Owner:** CIP Operator. **Class:** C. **Phase:** IC.
**PK:** `conversation_id`. **FK:** `person_id` (nullable for anonymous).
**Unique / checks:** `ended_at >= started_at` when both present; `channel` in (web, voice, whatsapp, api, kiosk); `outcome` in (resolved, escalated, abandoned, open).
**Indexes:** `btree (person_id, started_at DESC)`; `btree (channel, started_at)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| conversation_id | uuid | NO | PK | gen_random_uuid() | C | Conversation identity. |
| person_id | uuid | YES | FK → iam.person | NULL | C | Known person; null = anonymous. |
| channel | text | NO | IN (web, voice, whatsapp, api, kiosk) | web | C | Channel. |
| language | text | YES | IN (en, bn, hi, mixed) | NULL | C | Dominant language. |
| started_at | timestamptz | NO | — | now() | C | Start. |
| ended_at | timestamptz | YES | `>= started_at` | NULL | C | End. |
| outcome | text | NO | IN (resolved, escalated, abandoned, open) | open | C | Result. |
| escalation_flag | boolean | NO | — | false | C | Handoff occurred. |
| consent_recording | boolean | YES | — | NULL | R | Recording consent. |
+ `AUDIT_MUTABLE`.

### CIP-02 `cip.call_session`

**Purpose:** voice-call specific metadata. **Owner:** CIP Operator. **Class:** R. **Phase:** IC.
**PK:** `call_session_id`. **FK:** `conversation_id`.
**Unique / checks:** unique `(provider, provider_call_id)`; `duration_sec >= 0`; `direction` in (inbound, outbound); `status` in (ringing, in_progress, completed, failed, no_answer).
**Indexes:** `btree (conversation_id)`; `btree (started_at DESC)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| call_session_id | uuid | NO | PK | gen_random_uuid() | R | Call identity. |
| conversation_id | uuid | NO | FK → cip.conversation | — | R | Conversation. |
| provider | text | NO | length ≤ 50 | — | R | Telephony provider. |
| provider_call_id | text | YES | unique per provider | NULL | R | Provider ID. |
| direction | text | NO | IN (inbound, outbound) | inbound | R | Direction. |
| from_number_masked | text | YES | length ≤ 20 | NULL | R | Masked origin. |
| to_number_masked | text | YES | length ≤ 20 | NULL | R | Masked destination. |
| started_at | timestamptz | NO | — | now() | R | Start. |
| ended_at | timestamptz | YES | `>= started_at` | NULL | R | End. |
| duration_sec | integer | YES | ≥ 0 | NULL | R | Duration. |
| recording_uri | text | YES | object-storage URI | NULL | R | Recording. |
| recording_consent | boolean | NO | — | false | R | Consent captured. |
| status | text | NO | IN (ringing, in_progress, completed, failed, no_answer) | ringing | R | State. |
+ `AUDIT_MUTABLE`.

### CIP-03 `cip.message`

**Purpose:** a turn in a conversation. **Owner:** CIP Operator. **Class:** C/R. **Phase:** IC.
**PK:** `message_id`. **FK:** `conversation_id`.
**Unique / checks:** unique `(conversation_id, sequence_no)`; `role` in (user, assistant, system, tool); `confidence` 0–1; `latency_ms >= 0`.
**Indexes:** `btree (conversation_id, sequence_no)`; `btree (intent_code)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| message_id | uuid | NO | PK | gen_random_uuid() | C | Message identity. |
| conversation_id | uuid | NO | FK → cip.conversation | — | C | Conversation. |
| sequence_no | integer | NO | ≥ 1 | — | C | Turn order. |
| role | text | NO | IN (user, assistant, system, tool) | — | C | Speaker. |
| content_text | text | YES | — | NULL | R | Working text. |
| content_redacted | text | YES | — | NULL | C | Safe retained text. |
| language | text | YES | IN (en, bn, hi, mixed) | NULL | C | Detected language. |
| intent_code | text | YES | length ≤ 50 | NULL | C | Classified intent. |
| confidence | numeric(4,3) | YES | 0–1 | NULL | C | Confidence. |
| model_name | text | YES | length ≤ 100 | NULL | C | LLM used. |
| model_version | text | YES | length ≤ 50 | NULL | C | Model revision. |
| latency_ms | integer | YES | ≥ 0 | NULL | C | End-to-end latency. |
| token_count | integer | YES | ≥ 0 | NULL | C | Tokens. |
| created_at | timestamptz | NO | — | now() | C | Time. |
+ `AUDIT_IMMUTABLE`.

### CIP-04 `cip.retrieval_log`

**Purpose:** what was retrieved and why. **Owner:** CIP Operator. **Class:** C. **Phase:** IC.
**PK:** `retrieval_log_id`. **FK:** `message_id`.
**Unique / checks:** `top_k > 0`; `result_count >= 0`; `latency_ms >= 0`; `strategy` in (vector, lexical, hybrid, structured_api, none).
**Indexes:** `btree (message_id)`; `btree (created_at DESC)`; `btree (strategy)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| retrieval_log_id | uuid | NO | PK | gen_random_uuid() | C | Log identity. |
| message_id | uuid | NO | FK → cip.message | — | C | Triggering message. |
| query_text | text | NO | length ≤ 2000 | — | C | User query. |
| normalized_query | text | YES | length ≤ 2000 | NULL | C | Normalised query. |
| strategy | text | NO | IN (vector, lexical, hybrid, structured_api, none) | hybrid | C | Method. |
| filters_json | jsonb | YES | — | '{}' | C | Access/corpus filters. |
| top_k | integer | NO | > 0 | 5 | C | Requested depth. |
| latency_ms | integer | YES | ≥ 0 | NULL | C | Retrieval latency. |
| result_count | integer | NO | ≥ 0 | 0 | C | Hits returned. |
| fallback_used | boolean | NO | — | false | C | Fallback path used. |
| created_at | timestamptz | NO | — | now() | C | Time. |
+ `AUDIT_IMMUTABLE`.

### CIP-05 `cip.retrieval_hit`

**Purpose:** ranked chunk considered for an answer. **Owner:** CIP Operator. **Class:** C. **Phase:** IC.
**PK:** `retrieval_hit_id`. **FKs:** `retrieval_log_id`; `chunk_id`.
**Unique / checks:** unique `(retrieval_log_id, rank)`; `rank >= 1`.
**Indexes:** `btree (retrieval_log_id, rank)`; `btree (chunk_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| retrieval_hit_id | uuid | NO | PK | gen_random_uuid() | C | Hit identity. |
| retrieval_log_id | uuid | NO | FK → cip.retrieval_log | — | C | Log. |
| chunk_id | uuid | NO | FK → knowledge.document_chunk | — | C | Chunk. |
| rank | integer | NO | ≥ 1; unique per log | — | C | Rank. |
| vector_score | numeric(8,6) | YES | — | NULL | C | Similarity. |
| lexical_score | numeric(8,6) | YES | — | NULL | C | FTS score. |
| rerank_score | numeric(8,6) | YES | — | NULL | C | Reranker score. |
+ `AUDIT_IMMUTABLE`.

### CIP-06 `cip.citation`

**Purpose:** source actually shown to the user. **Owner:** CIP Operator. **Class:** C. **Phase:** IC.
**PK:** `citation_id`. **FKs:** `message_id`; `chunk_id`; `document_version_id`.
**Unique / checks:** unique `(message_id, chunk_id, page_from, page_to)`; `page_to >= page_from`; `confidence` 0–1.
**Indexes:** `btree (message_id)`; `btree (document_version_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| citation_id | uuid | NO | PK | gen_random_uuid() | C | Citation identity. |
| message_id | uuid | NO | FK → cip.message | — | C | Answer. |
| chunk_id | uuid | YES | FK → knowledge.document_chunk | NULL | C | Chunk cited. |
| document_version_id | uuid | YES | FK → doc.document_version | NULL | C | Source version. |
| page_from | integer | YES | ≥ 1 | NULL | C | First page. |
| page_to | integer | YES | ≥ page_from | NULL | C | Last page. |
| quote | text | YES | length ≤ 2000 | NULL | C | Displayed excerpt. |
| confidence | numeric(4,3) | YES | 0–1 | NULL | C | Confidence. |
| displayed | boolean | NO | — | true | C | Shown to user. |
+ `AUDIT_IMMUTABLE`.

### CIP-07 `cip.feedback`

**Purpose:** user rating and reason. **Owner:** CIP Operator. **Class:** I. **Phase:** IC.
**PK:** `feedback_id`. **FKs:** `message_id`; `person_id` (nullable).
**Unique / checks:** unique `(message_id, person_id)` where person is not null (one rating per user per message); `rating` in (up, down, 1, 2, 3, 4, 5).
**Indexes:** `btree (message_id)`; `btree (rating, created_at)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| feedback_id | uuid | NO | PK | gen_random_uuid() | I | Feedback identity. |
| message_id | uuid | NO | FK → cip.message | — | I | Rated answer. |
| person_id | uuid | YES | FK → iam.person | NULL | I | Rater. |
| rating | text | NO | IN (up, down, 1, 2, 3, 4, 5) | — | I | Rating. |
| reason_code | text | YES | length ≤ 50 | NULL | I | Reason. |
| comment | text | YES | length ≤ 2000 | NULL | I | Comment. |
| created_at | timestamptz | NO | — | now() | I | Time. |
+ `AUDIT_IMMUTABLE`.

### CIP-08 `cip.escalation`

**Purpose:** no-answer or human handoff case. **Owner:** CIP Operator. **Class:** C. **Phase:** IC.
**PK:** `escalation_id`. **FKs:** `conversation_id`; `message_id`; `assigned_org_unit_id`.
**Unique / checks:** `resolved_at >= created_at` when present; `status` in (open, assigned, in_progress, resolved, closed, rejected).
**Indexes:** `btree (status, created_at)`; `btree (assigned_org_unit_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| escalation_id | uuid | NO | PK | gen_random_uuid() | C | Case identity. |
| conversation_id | uuid | NO | FK → cip.conversation | — | C | Conversation. |
| message_id | uuid | YES | FK → cip.message | NULL | C | Triggering message. |
| assigned_org_unit_id | uuid | YES | FK → core.org_unit | NULL | C | Owning office. |
| reason_code | text | NO | length ≤ 50 | — | C | Why escalated. |
| status | text | NO | IN (open, assigned, in_progress, resolved, closed, rejected) | open | C | State. |
| created_at | timestamptz | NO | — | now() | C | Created. |
| resolved_at | timestamptz | YES | `>= created_at` | NULL | C | Resolved. |
| resolution_note | text | YES | length ≤ 2000 | NULL | C | Outcome. |
+ `AUDIT_MUTABLE`.

### CIP-09 `cip.eval_case`

**Purpose:** evaluation question and expected answer/citation. **Owner:** AI Platform. **Class:** I. **Phase:** IC.
**PK:** `eval_case_id`. **Unique / checks:** unique `lower(case_code)`; `category` in (golden, negative, conflict, version, personal, language, access, latency); `language` in (en, bn, hi, mixed); `question` not empty.
**Indexes:** `btree (category, is_active)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| eval_case_id | uuid | NO | PK | gen_random_uuid() | I | Case identity. |
| case_code | text | NO | unique lower(); length ≤ 50 | — | I | Stable code. |
| category | text | NO | IN (golden, negative, conflict, version, personal, language, access, latency) | golden | I | Test class. |
| question | text | NO | length ≤ 2000 | — | I | Input. |
| expected_answer | text | YES | — | NULL | I | Expected content. |
| expected_citation | text | YES | length ≤ 500 | NULL | I | Expected source. |
| language | text | NO | IN (en, bn, hi, mixed) | en | I | Language. |
| is_active | boolean | NO | — | true | I | In the suite. |
+ `AUDIT_MUTABLE`.

### CIP-10 `cip.eval_run`

**Purpose:** a run of the evaluation set against a corpus/model version. **Owner:** AI Platform. **Class:** I. **Phase:** IC.
**PK:** `eval_run_id`. **FK:** `created_by`.
**Unique / checks:** `finished_at >= started_at` when present; `status` in (running, completed, failed, aborted).
**Indexes:** `btree (started_at DESC)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| eval_run_id | uuid | NO | PK | gen_random_uuid() | I | Run identity. |
| created_by | uuid | YES | FK → iam.person | NULL | I | Operator. |
| started_at | timestamptz | NO | — | now() | I | Start. |
| finished_at | timestamptz | YES | `>= started_at` | NULL | I | Finish. |
| corpus_version | text | YES | length ≤ 50 | NULL | I | Corpus snapshot. |
| model_name | text | YES | length ≤ 100 | NULL | I | Model. |
| status | text | NO | IN (running, completed, failed, aborted) | running | I | State. |
+ `AUDIT_IMMUTABLE`.

### CIP-11 `cip.eval_result`

**Purpose:** result per case in a run. **Owner:** AI Platform. **Class:** I. **Phase:** IC.
**PK:** `eval_result_id`. **FKs:** `eval_run_id`; `eval_case_id`.
**Unique / checks:** unique `(eval_run_id, eval_case_id)`; `latency_ms >= 0`.
**Indexes:** `btree (eval_run_id, pass)`; `btree (eval_case_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| eval_result_id | uuid | NO | PK | gen_random_uuid() | I | Result identity. |
| eval_run_id | uuid | NO | FK → cip.eval_run | — | I | Run. |
| eval_case_id | uuid | NO | FK → cip.eval_case | — | I | Case. |
| actual_answer | text | YES | — | NULL | I | Model output. |
| citation_correct | boolean | YES | — | NULL | I | Citation matched. |
| answer_correct | boolean | YES | — | NULL | I | Answer matched. |
| latency_ms | integer | YES | ≥ 0 | NULL | I | Latency. |
| pass | boolean | NO | — | false | I | Overall. |
| notes | text | YES | length ≤ 2000 | NULL | I | Reviewer note. |
+ `AUDIT_IMMUTABLE`.

---

## 13. Policy (`policy`)

**Trace:** Research §9.1, §9.14–9.15; G-01, G-02.

**Design rule:** a rule is an identity; a rule version is an immutable statement with parameters and an effective window; a scope says where it applies; a bundle is a reproducible selection used by a calculation.

### POL-01 `policy.rule`

**Purpose:** stable rule identity. **Owner:** Academic Council/Registrar. **Class:** I. **Phase:** F.
**PK:** `rule_id`. **FKs:** none.
**Unique / checks:** unique `lower(rule_code)`; `domain` in (admission, registration, attendance, assessment, passing, progression, supplementary, degree, correction, ppr, mar, discipline, placement, service, calendar, examination, affiliation, other); `owner_role_code` references a role code, not a person.
**Indexes:** unique `lower(rule_code)`; `btree (domain)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| rule_id | uuid | NO | PK | gen_random_uuid() | I | Rule identity. |
| rule_code | text | NO | unique lower(); length ≤ 30 | — | I | e.g. `ATT-01`. |
| title | text | NO | length ≤ 200 | — | I | Short name. |
| domain | text | NO | controlled list | — | I | Subject area. |
| description | text | YES | length ≤ 2000 | NULL | I | Purpose. |
| owner_role_code | text | YES | length ≤ 50 | NULL | I | Accountable role code. |
+ `AUDIT_MUTABLE`.

### POL-02 `policy.rule_version`

**Purpose:** immutable version of a rule. **Owner:** Academic Council/Registrar. **Class:** I. **Phase:** F.
**PK:** `rule_version_id`. **FKs:** `rule_id`; `source_document_version_id`; `supersedes_version_id`; `approved_by`.
**Unique / checks:** unique `(rule_id, version_no)`; `effective_to IS NULL OR effective_to >= effective_from`; `status` in (Current, Draft, Historical, Superseded, Disputed, Unknown); `confidence` in (High, Medium, Low); update/delete rejected once referenced by a bundle or a calculation.
**Indexes:** `btree (rule_id, version_no DESC)`; `btree (status)`; `btree (effective_from)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| rule_version_id | uuid | NO | PK | gen_random_uuid() | I | Version identity. |
| rule_id | uuid | NO | FK → policy.rule | — | I | Rule. |
| version_no | integer | NO | ≥ 1; unique per rule | 1 | I | Version. |
| statement | text | NO | length ≤ 5000 | — | I | Plain-language rule. |
| authority | text | NO | IN (BCREC, MAKAUT, AICTE, other) | BCREC | I | Which authority issued this rule version (G-03). |
| parameters_json | jsonb | NO | — | '{}' | I | Thresholds, marks, windows. |
| effective_from | date | NO | — | — | I | Start. |
| effective_to | date | YES | `>= effective_from` | NULL | I | End. |
| status | text | NO | IN (Current, Draft, Historical, Superseded, Disputed, Unknown) | Draft | I | Institutional status. |
| confidence | text | NO | IN (High, Medium, Low) | Medium | I | Evidence confidence. |
| confidence_reason | text | YES | length ≤ 1000 | NULL | I | Why. |
| source_document_version_id | uuid | YES | FK → doc.document_version | NULL | I | Evidence. |
| source_locator | text | YES | length ≤ 300 | NULL | I | Section/page/clause. |
| approval_reference | text | YES | length ≤ 200 | NULL | I | Order/meeting reference. |
| supersedes_version_id | uuid | YES | FK → policy.rule_version; ≠ self | NULL | I | Prior version. |
| approved_by | uuid | YES | FK → iam.person | NULL | I | Approver. |
+ `AUDIT_IMMUTABLE`.

**The Draft rule:** S1 (Academic Regulations) is marked `Draft, Edition 1.0`. Every rule derived from it must be inserted with `status = 'Draft'`. A trigger rejects `status = 'Current'` when `approval_reference` is null. This is the schema's defence of C-02.

### POL-03 `policy.rule_scope`

**Purpose:** where a rule version applies. **Owner:** Registrar. **Class:** I. **Phase:** F.
**PK:** `rule_scope_id`. **FKs:** `rule_version_id`; `institution_id`; `programme_id`; `batch_id`; `term_id`.
**Unique / checks:** unique `(rule_version_id, scope_type, institution_id, programme_id, batch_id, term_id, course_type, student_category)`; `scope_type` in (institution, programme, batch, term, course_type, student_category); exactly one of institution/programme/batch/term is set when the scope is a scope entity.
**Indexes:** `btree (rule_version_id)`; `btree (batch_id)`; `btree (programme_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| rule_scope_id | uuid | NO | PK | gen_random_uuid() | I | Scope identity. |
| rule_version_id | uuid | NO | FK → policy.rule_version | — | I | Rule version. |
| scope_type | text | NO | IN (institution, programme, batch, term, course_type, student_category) | institution | I | Scope kind. |
| institution_id | uuid | YES | FK → core.institution | NULL | I | Institution scope. |
| programme_id | uuid | YES | FK → academic.programme | NULL | I | Programme scope. |
| batch_id | uuid | YES | FK → academic.batch | NULL | I | Batch scope. |
| term_id | uuid | YES | FK → core.term | NULL | I | Term scope. |
| course_type | text | YES | IN (theory, practical, sessional, project, mooc, non_credit) | NULL | I | Course-type scope. |
| student_category | text | YES | length ≤ 50 | NULL | I | Category scope. |
+ `AUDIT_MUTABLE`.

**Batch scoping is the G-04 answer:** a rule can apply only to an autonomy batch, a MAKAUT batch, or a transitional one. The scope row makes the boundary explicit rather than global.

### POL-04 `policy.rule_conflict`

**Purpose:** two current rules that disagree. **Owner:** Registrar. **Class:** I. **Phase:** F.
**PK:** `rule_conflict_id`. **FKs:** `rule_version_a_id`; `rule_version_b_id`; `resolution_rule_version_id`; `resolved_by`.
**Unique / checks:** unique `(rule_version_a_id, rule_version_b_id)` with `a < b` ordering enforced; `rule_version_a_id <> rule_version_b_id`; `status` in (open, resolved, accepted_risk); `resolved_at >= created_at`.
**Indexes:** `btree (status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| rule_conflict_id | uuid | NO | PK | gen_random_uuid() | I | Conflict identity. |
| rule_version_a_id | uuid | NO | FK → policy.rule_version | — | I | First rule. |
| rule_version_b_id | uuid | NO | FK → policy.rule_version; `> a` | — | I | Second rule. |
| resolution_rule_version_id | uuid | YES | FK → policy.rule_version | NULL | I | Rule that resolves it. |
| description | text | NO | length ≤ 2000 | — | I | What disagrees. |
| status | text | NO | IN (open, resolved, accepted_risk) | open | I | State. |
| resolution_note | text | YES | length ≤ 2000 | NULL | I | How resolved. |
| resolved_by | uuid | YES | FK → iam.person | NULL | I | Resolver. |
| resolved_at | timestamptz | YES | `>= created_at` | NULL | I | Resolution time. |
+ `AUDIT_MUTABLE`.

**Seeded conflicts:** C-01 (attendance aggregate vs split) is the first row. It stays `open` until the Academic Council issues an order.

### POL-05 `policy.policy_bundle`

**Purpose:** stable identity for a named set of rules used by one calculation. **Owner:** Academic Council/Registrar. **Class:** I. **Phase:** F.
**PK:** `policy_bundle_id`.
**Unique / checks:** unique `lower(bundle_code)`; `domain` from the rule domain list.
**Indexes:** unique `lower(bundle_code)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| policy_bundle_id | uuid | NO | PK | gen_random_uuid() | I | Bundle identity. |
| bundle_code | text | NO | unique lower(); length ≤ 50 | — | I | e.g. `ATT_ELIGIBILITY`. |
| name | text | NO | length ≤ 200 | — | I | Display name. |
| domain | text | NO | controlled list | — | I | Subject area. |
| description | text | YES | length ≤ 2000 | NULL | I | Purpose. |
| owner_role_code | text | YES | length ≤ 50 | NULL | I | Accountable role. |
+ `AUDIT_MUTABLE`.

### POL-06 `policy.policy_bundle_version`

**Purpose:** immutable version of a policy bundle. **Owner:** Academic Council/Registrar. **Class:** I. **Phase:** F.
**PK:** `policy_bundle_version_id`. **FKs:** `policy_bundle_id`; `approved_by`.
**Unique / checks:** unique `(policy_bundle_id, version_no)`; `effective_to IS NULL OR effective_to >= effective_from`; `status` in (draft, approved, active, superseded).
**Indexes:** `btree (policy_bundle_id, version_no DESC)`; `btree (status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| policy_bundle_version_id | uuid | NO | PK | gen_random_uuid() | I | Version identity. |
| policy_bundle_id | uuid | NO | FK → policy.policy_bundle | — | I | Bundle. |
| version_no | integer | NO | ≥ 1; unique per bundle | 1 | I | Version. |
| effective_from | date | NO | — | — | I | Start. |
| effective_to | date | YES | `>= effective_from` | NULL | I | End. |
| status | text | NO | IN (draft, approved, active, superseded) | draft | I | State. |
| approval_reference | text | YES | length ≤ 200 | NULL | I | Approval evidence. |
| approved_by | uuid | YES | FK → iam.person | NULL | I | Approver. |
| created_at | timestamptz | NO | — | now() | I | Creation time. |
+ `AUDIT_IMMUTABLE`.

### POL-07 `policy.policy_bundle_member`

**Purpose:** rule version included in a bundle version. **Owner:** Registrar. **Class:** I. **Phase:** F.
**PK:** `policy_bundle_member_id`. **FKs:** `policy_bundle_version_id`; `rule_version_id`.
**Unique / checks:** unique `(policy_bundle_version_id, rule_version_id)`; `sequence_no >= 1`.
**Indexes:** `btree (rule_version_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| policy_bundle_member_id | uuid | NO | PK | gen_random_uuid() | I | Membership identity. |
| policy_bundle_version_id | uuid | NO | FK → policy.policy_bundle_version | — | I | Bundle version. |
| rule_version_id | uuid | NO | FK → policy.rule_version | — | I | Rule version. |
| sequence_no | smallint | NO | ≥ 1 | 1 | I | Evaluation order. |
| is_required | boolean | NO | — | true | I | Required for the calculation. |
+ `AUDIT_IMMUTABLE`.

**Reproducibility:** `attendance.eligibility_assessment`, `exam.result_revision`, `exam.promotion_decision`, and `exam.degree_eligibility` reference a `policy_bundle_version_id`. A later rule change creates a new bundle version; historical calculations keep the old one.

---

## 14. Integration and Synchronization (`integration`)

**Trace:** Research §13.1–13.6; S14, S18, S20; G-09, G-10.

**The one documented integrity exception:** `internal_id`, `record_id`, and `entity_id` in this schema and in `ops` are polymorphic. They are validated by `integration.entity_type`, not by a foreign key. Every other reference in this dictionary is a real FK.

### INT-01 `integration.entity_type`

**Purpose:** controlled registry for polymorphic references. **Owner:** Data Steward. **Class:** I. **Phase:** F.
**PK:** `entity_type_code` (text).
**Unique / checks:** PK is the code; `is_active` default true; the pair `(schema_name, table_name)` should be unique.
**Indexes:** unique `(schema_name, table_name)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| entity_type_code | text | NO | PK; length ≤ 60 | — | I | e.g. `student.student`. |
| description | text | YES | length ≤ 500 | NULL | I | What it is. |
| schema_name | text | NO | length ≤ 60 | — | I | PostgreSQL schema. |
| table_name | text | NO | length ≤ 60 | — | I | Table. |
| is_active | boolean | NO | — | true | I | Still mapped. |
+ `AUDIT_IMMUTABLE`.

**Why not a `CHECK IN (...)`:** the set grows with each module. A registry row is auditable and lets the data steward record the physical table.

### INT-02 `integration.external_system`

**Purpose:** a system exchanged with. **Owner:** ERP Administrator. **Class:** I. **Phase:** F.
**PK:** `external_system_id`. **FK:** `owner_org_unit_id`.
**Unique / checks:** unique `lower(code)`; `system_type` in (college_erp, makaut_portal, payment_gateway, email, sms, lms, idp, nad, other); `base_url` empty or a valid URL (application check).
**Indexes:** `btree (system_type, status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| external_system_id | uuid | NO | PK | gen_random_uuid() | I | System identity. |
| code | text | NO | unique lower(); length ≤ 50 | — | I | e.g. `COLLEGE_ERP`. |
| name | text | NO | length ≤ 200 | — | I | Display name. |
| system_type | text | NO | controlled list | — | I | Class. |
| base_url | text | YES | length ≤ 500 | NULL | I | Endpoint root. |
| owner_org_unit_id | uuid | YES | FK → core.org_unit | NULL | I | Business owner. |
| status | text | NO | IN (active, inactive, planned, retired) | planned | I | State. |
| capabilities_json | jsonb | YES | — | '{}' | I | Declared capabilities. |
| last_health_at | timestamptz | YES | — | NULL | I | Last health check. |
+ `AUDIT_MUTABLE`.

### INT-03 `integration.external_id_mapping`

**Purpose:** stable internal ID to external ID. **Owner:** Data Steward. **Class:** C. **Phase:** F.
**PK:** `external_id_mapping_id`. **FKs:** `entity_type_code`; `external_system_id`.
**Unique / checks:** unique `(entity_type_code, internal_id, external_system_id, valid_from)`; partial unique `(entity_type_code, external_id, external_system_id) WHERE valid_to IS NULL`; `valid_to > valid_from`; `confidence` in (high, medium, low).
**Indexes:** `btree (entity_type_code, internal_id)`; `btree (external_system_id, external_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| external_id_mapping_id | uuid | NO | PK | gen_random_uuid() | C | Mapping identity. |
| entity_type_code | text | NO | FK → integration.entity_type | — | C | Entity kind. |
| external_system_id | uuid | NO | FK → integration.external_system | — | C | External system. |
| internal_id | uuid | NO | polymorphic; validated by registry | — | C | Internal record. |
| external_id | text | NO | length ≤ 200 | — | C | External identifier. |
| is_primary | boolean | NO | — | true | C | Canonical mapping. |
| valid_from | date | NO | — | current_date | C | Start. |
| valid_to | date | YES | `> valid_from` | NULL | C | End. |
| confidence | text | NO | IN (high, medium, low) | high | C | Match confidence. |
+ `AUDIT_MUTABLE`.

### INT-04 `integration.source_of_truth_rule`

**Purpose:** which system wins for which field. **Owner:** Data Steward. **Class:** I. **Phase:** F.
**PK:** `source_of_truth_rule_id`. **FKs:** `entity_type_code`; `authoritative_system_id`; `fallback_system_id`; `approved_by`.
**Unique / checks:** unique `(entity_type_code, field_name, effective_from)` — only one rule per field per effective date; `authoritative_system_id <> fallback_system_id`; `conflict_policy` in (authoritative_wins, manual_review, newest_wins); `effective_to >= effective_from`.
**Indexes:** `btree (entity_type_code, field_name)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| source_of_truth_rule_id | uuid | NO | PK | gen_random_uuid() | I | Rule identity. |
| entity_type_code | text | NO | FK → integration.entity_type | — | I | Entity. |
| field_name | text | NO | length ≤ 100 | — | I | Field. |
| authoritative_system_id | uuid | YES | FK → integration.external_system | NULL | I | Winner; null = internal is authoritative. |
| fallback_system_id | uuid | YES | FK → integration.external_system | NULL | I | Fallback. |
| conflict_policy | text | NO | IN (authoritative_wins, manual_review, newest_wins) | manual_review | I | Resolution mode. |
| effective_from | date | NO | — | — | I | Start. |
| effective_to | date | YES | `>= effective_from` | NULL | I | End. |
| status | text | NO | IN (draft, active, superseded) | draft | I | State. |
| approved_by | uuid | YES | FK → iam.person | NULL | I | Approver. |
+ `AUDIT_MUTABLE`.

**Rule:** `manual_review` is the default for every field until BCREC approves a winner. The design does not assume the ERP wins or the new system wins.

### INT-05 `integration.sync_run`

**Purpose:** one import/export attempt. **Owner:** Integration Service. **Class:** I. **Phase:** F.
**PK:** `sync_run_id`. **FKs:** `external_system_id`; `entity_type_code`; `operator_person_id`.
**Unique / checks:** `finished_at >= started_at` when present; counts ≥ 0; `direction` in (pull, push, bidirectional); `mode` in (full, incremental, event, manual_file); `status` in (running, completed, completed_with_errors, failed, aborted).
**Indexes:** `btree (external_system_id, started_at DESC)`; `btree (status)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| sync_run_id | uuid | NO | PK | gen_random_uuid() | I | Run identity. |
| external_system_id | uuid | NO | FK → integration.external_system | — | I | System. |
| entity_type_code | text | NO | FK → integration.entity_type | — | I | Entity. |
| direction | text | NO | IN (pull, push, bidirectional) | pull | I | Flow. |
| mode | text | NO | IN (full, incremental, event, manual_file) | incremental | I | Mode. |
| started_at | timestamptz | NO | — | now() | I | Start. |
| finished_at | timestamptz | YES | `>= started_at` | NULL | I | Finish. |
| status | text | NO | IN (running, completed, completed_with_errors, failed, aborted) | running | I | State. |
| records_read | integer | NO | ≥ 0 | 0 | I | Read. |
| records_written | integer | NO | ≥ 0 | 0 | I | Written. |
| records_failed | integer | NO | ≥ 0 | 0 | I | Failed. |
| cursor_before | text | YES | length ≤ 500 | NULL | I | Checkpoint before. |
| cursor_after | text | YES | length ≤ 500 | NULL | I | Checkpoint after. |
| error_summary | text | YES | length ≤ 5000 | NULL | I | Errors. |
| adapter_version | text | YES | length ≤ 50 | NULL | I | Adapter build. |
| operator_person_id | uuid | YES | FK → iam.person | NULL | I | Operator; null = scheduled. |
+ `AUDIT_IMMUTABLE`.

### INT-06 `integration.sync_record`

**Purpose:** per-record outcome of a sync. **Owner:** Integration Service. **Class:** I. **Phase:** F.
**PK:** `sync_record_id`. **FKs:** `sync_run_id`; `entity_type_code`.
**Unique / checks:** unique `(sync_run_id, entity_type_code, internal_id, operation, external_id)`; `operation` in (insert, update, skip, delete, conflict); `outcome` in (success, failed).
**Indexes:** `btree (sync_run_id, outcome)`; `btree (entity_type_code, internal_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| sync_record_id | uuid | NO | PK | gen_random_uuid() | I | Outcome identity. |
| sync_run_id | uuid | NO | FK → integration.sync_run | — | I | Run. |
| entity_type_code | text | NO | FK → integration.entity_type | — | I | Entity. |
| internal_id | uuid | YES | polymorphic | NULL | I | Internal record. |
| external_id | text | YES | length ≤ 200 | NULL | I | External record. |
| operation | text | NO | IN (insert, update, skip, delete, conflict) | — | I | Action. |
| outcome | text | NO | IN (success, failed) | — | I | Result. |
| error_code | text | YES | length ≤ 50 | NULL | I | Code. |
| error_detail | text | YES | length ≤ 2000 | NULL | I | Detail. |
+ `AUDIT_IMMUTABLE`.

### INT-07 `integration.sync_conflict`

**Purpose:** detected disagreement and its resolution. **Owner:** Data Steward. **Class:** C. **Phase:** F.
**PK:** `sync_conflict_id`. **FKs:** `sync_run_id`; `entity_type_code`; `source_of_truth_rule_id`; `resolved_by`.
**Unique / checks:** `status` in (open, resolved, deferred); `resolution` in (use_internal, use_external, manual, none); `resolved_at >= created_at` when present; a resolved conflict must have `resolved_by`.
**Indexes:** `btree (status, created_at)`; `btree (entity_type_code, internal_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| sync_conflict_id | uuid | NO | PK | gen_random_uuid() | C | Conflict identity. |
| sync_run_id | uuid | NO | FK → integration.sync_run | — | C | Run. |
| entity_type_code | text | NO | FK → integration.entity_type | — | C | Entity. |
| internal_id | uuid | YES | polymorphic | NULL | C | Internal record. |
| field_name | text | NO | length ≤ 100 | — | C | Field. |
| internal_value_json | jsonb | YES | — | NULL | C | Internal value. |
| external_value_json | jsonb | YES | — | NULL | C | External value. |
| source_of_truth_rule_id | uuid | YES | FK → integration.source_of_truth_rule | NULL | C | Rule. |
| status | text | NO | IN (open, resolved, deferred) | open | C | State. |
| resolution | text | NO | IN (use_internal, use_external, manual, none) | none | C | Decision. |
| resolution_note | text | YES | length ≤ 2000 | NULL | C | Why. |
| resolved_by | uuid | YES | FK → iam.person | NULL | C | Resolver. |
| resolved_at | timestamptz | YES | — | NULL | C | Time. |
+ `AUDIT_MUTABLE`.

**Rule:** the service never overwrites silently. It records the conflict and leaves the internal value untouched until a steward decides.

### INT-08 `integration.record_provenance`

**Purpose:** per-field source, timestamp, and override state. **Owner:** Integration Service. **Class:** I. **Phase:** F.
**PK:** `record_provenance_id`. **FKs:** `entity_type_code`; `source_system_id`; `sync_run_id`.
**Unique / checks:** unique `(entity_type_code, internal_id, field_name)` — latest observation per field; `length(value_hash) = 64`.
**Indexes:** `btree (entity_type_code, internal_id)`; `btree (observed_at)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| record_provenance_id | uuid | NO | PK | gen_random_uuid() | I | Provenance identity. |
| entity_type_code | text | NO | FK → integration.entity_type | — | I | Entity. |
| internal_id | uuid | NO | polymorphic | — | I | Record. |
| field_name | text | NO | length ≤ 100 | — | I | Field. |
| source_system_id | uuid | YES | FK → integration.external_system | NULL | I | Source; null = internal. |
| sync_run_id | uuid | YES | FK → integration.sync_run | NULL | I | Observing run. |
| observed_at | timestamptz | NO | — | now() | I | When seen. |
| value_hash | text | NO | length = 64 | — | I | Hash of the value. |
| is_human_override | boolean | NO | — | false | I | Manual edit. |
+ `AUDIT_MUTABLE`.

### INT-09 `integration.outbox_event`

**Purpose:** transactional outbox for reliable publishing. **Owner:** Integration Service. **Class:** I. **Phase:** F.
**PK:** `outbox_event_id`. **Unique / checks:** `retry_count >= 0`; `status` in (pending, published, failed, dead_letter); `published_at >= occurred_at` when present.
**Indexes:** partial `btree (occurred_at) WHERE status = 'pending'`; `btree (aggregate_type, aggregate_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| outbox_event_id | uuid | NO | PK | gen_random_uuid() | I | Event identity. |
| aggregate_type | text | NO | length ≤ 60 | — | I | Aggregate. |
| aggregate_id | uuid | NO | — | — | I | Record. |
| event_type | text | NO | length ≤ 100 | — | I | Event name. |
| payload_json | jsonb | NO | — | '{}' | I | Body. |
| occurred_at | timestamptz | NO | — | now() | I | Domain time. |
| published_at | timestamptz | YES | `>= occurred_at` | NULL | I | Publish time. |
| status | text | NO | IN (pending, published, failed, dead_letter) | pending | I | State. |
| retry_count | integer | NO | ≥ 0 | 0 | I | Retries. |
+ `AUDIT_IMMUTABLE`.

**Delivery:** at-least-once. Consumers must be idempotent on `(aggregate_type, aggregate_id, event_type)` or an explicit idempotency key in the payload.

---

## 15. Audit and Operations (`ops`)

**Trace:** Research §11.6, §11.9; S16 §11.1; G-22.

### OPS-01 `ops.audit_event`

**Purpose:** immutable record of a state-changing action. **Owner:** Audit/Security. **Class:** C/R. **Phase:** F.
**PK:** `audit_event_id`. **FKs:** `actor_person_id`; `actor_account_id`; `role_assignment_id`; `entity_type_code`.
**Unique / checks:** `entity_type_code` + `entity_id` identify the target; `correlation_id` not null for state changes; `length(prev_hash) IN (0, 64)` and `length(record_hash) = 64`.
**Indexes:** `btree (occurred_at DESC)`; `btree (entity_type_code, entity_id)`; `btree (actor_person_id, occurred_at DESC)`; `btree (correlation_id)`.
**Partitioning:** range-partition by `occurred_at` (monthly). Partition pruning keeps the hot table small and makes retention a partition detach, not a mass delete.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| audit_event_id | uuid | NO | PK | gen_random_uuid() | C | Event identity. |
| occurred_at | timestamptz | NO | — | now() | C | When. |
| actor_person_id | uuid | YES | FK → iam.person | NULL | C | Human actor. |
| actor_account_id | uuid | YES | FK → iam.identity_account | NULL | C | Authenticated account. |
| role_assignment_id | uuid | YES | FK → iam.role_assignment | NULL | C | Authority exercised. |
| action | text | NO | length ≤ 100 | — | C | e.g. `result.publish`. |
| entity_type_code | text | YES | FK → integration.entity_type | NULL | C | Target kind. |
| entity_id | uuid | YES | polymorphic | NULL | C | Target record. |
| before_json | jsonb | YES | changed fields only | NULL | R | Prior values. |
| after_json | jsonb | YES | changed fields only | NULL | R | New values. |
| reason | text | YES | length ≤ 2000 | NULL | R | Justification. |
| correlation_id | text | YES | length ≤ 100 | NULL | C | Request/job link. |
| source_channel | text | YES | IN (web, api, batch, integration, system) | NULL | C | Origin. |
| ip_address | inet | YES | — | NULL | C | Client IP. |
| user_agent | text | YES | length ≤ 500 | NULL | C | Client. |
| prev_hash | text | YES | length 0 or 64 | NULL | C | Chain link. |
| record_hash | text | NO | length = 64 | — | C | Chain value. |
+ `AUDIT_IMMUTABLE`.

**Immutability:** application roles have `INSERT` only. `UPDATE` and `DELETE` are revoked. The hash chain is a tamper-evidence control, not a substitute for backups and WAL archiving.

### OPS-02 `ops.data_quality_issue`

**Purpose:** known data defect and resolution. **Owner:** Data Steward. **Class:** I. **Phase:** F.
**PK:** `data_quality_issue_id`. **FKs:** `entity_type_code`; `assigned_to_person_id`.
**Unique / checks:** `severity` in (low, medium, high, critical); `status` in (open, investigating, resolved, accepted, deferred); `resolved_at >= detected_at` when present.
**Indexes:** `btree (status, severity)`; `btree (entity_type_code, record_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| data_quality_issue_id | uuid | NO | PK | gen_random_uuid() | I | Issue identity. |
| entity_type_code | text | NO | FK → integration.entity_type | — | I | Entity. |
| record_id | uuid | YES | polymorphic | NULL | I | Record. |
| issue_type | text | NO | length ≤ 50 | — | I | e.g. `orphan_fk`, `duplicate`. |
| severity | text | NO | IN (low, medium, high, critical) | medium | I | Priority. |
| description | text | NO | length ≤ 2000 | — | I | What is wrong. |
| detected_at | timestamptz | NO | — | now() | I | When found. |
| status | text | NO | IN (open, investigating, resolved, accepted, deferred) | open | I | State. |
| assigned_to_person_id | uuid | YES | FK → iam.person | NULL | I | Owner. |
| resolution | text | YES | length ≤ 2000 | NULL | I | Fix. |
| resolved_at | timestamptz | YES | `>= detected_at` | NULL | I | Closed. |
+ `AUDIT_MUTABLE`.

### OPS-03 `ops.break_glass_grant`

**Purpose:** temporary emergency access. **Owner:** Principal/Audit (recommendation). **Class:** R. **Phase:** F.
**PK:** `break_glass_grant_id`. **FKs:** `person_id`; `role_assignment_id`; `approved_by`; `reviewed_by`.
**Unique / checks:** `expires_at > starts_at`; `status` in (requested, active, expired, revoked, reviewed); a grant cannot exceed the policy maximum duration.
**Indexes:** `btree (status, expires_at)`; `btree (person_id)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| break_glass_grant_id | uuid | NO | PK | gen_random_uuid() | R | Grant identity. |
| person_id | uuid | NO | FK → iam.person | — | R | Grantee. |
| role_assignment_id | uuid | YES | FK → iam.role_assignment | NULL | R | Narrowed authority. |
| reason | text | NO | length 10–2000 | — | R | Emergency reason. |
| starts_at | timestamptz | NO | — | now() | R | Start. |
| expires_at | timestamptz | NO | `> starts_at` | — | R | End. |
| scope_description | text | YES | length ≤ 1000 | NULL | R | What is opened. |
| status | text | NO | IN (requested, active, expired, revoked, reviewed) | requested | R | State. |
| approved_by | uuid | YES | FK → iam.person | NULL | R | Approver. |
| reviewed_by | uuid | YES | FK → iam.person | NULL | R | Post-hoc reviewer. |
| reviewed_at | timestamptz | YES | — | NULL | R | Review time. |
+ `AUDIT_MUTABLE`.

**Label:** the research marks break-glass as a recommendation, not an observed BCREC practice. The table exists so emergency access is not invented ad hoc; its policy must be approved before activation.

### OPS-04 `ops.retention_schedule`

**Purpose:** retention and disposition rule per entity/class. **Owner:** Registrar/Legal. **Class:** I. **Phase:** F/B.
**PK:** `retention_schedule_id`. **FK:** `entity_type_code`; `approved_by`.
**Unique / checks:** unique `(entity_type_code, classification)`; `retention_period_months > 0`; `disposition` in (destroy, anonymize, archive); `status` in (draft, approved, superseded); an approved schedule must have `approved_by`.
**Indexes:** `btree (entity_type_code)`.

| Column | Type | Null | Key / check | Default | Sens | Meaning |
|---|---|---|---|---|---|---|
| retention_schedule_id | uuid | NO | PK | gen_random_uuid() | I | Schedule identity. |
| entity_type_code | text | NO | FK → integration.entity_type | — | I | Entity. |
| classification | text | NO | IN (P, I, C, R, G) | — | I | Data class. |
| retention_period_months | integer | NO | > 0 | — | I | Period. |
| trigger_event | text | YES | length ≤ 200 | NULL | I | e.g. `graduation`. |
| disposition | text | NO | IN (destroy, anonymize, archive) | archive | I | Action at expiry. |
| legal_basis | text | YES | length ≤ 1000 | NULL | I | Why this period. |
| status | text | NO | IN (draft, approved, superseded) | draft | I | State. |
| approved_by | uuid | YES | FK → iam.person | NULL | I | Approver. |
+ `AUDIT_MUTABLE`.

**G-22 posture:** the table is empty of approved rows until BCREC legal/Registrar decides. No automated deletion job may run against an entity without an `approved` schedule. This is the safest possible default and is visible to auditors.

---

## 16. Coverage reconciliation

| Section | Schema | Entities in this dictionary | IDs |
|---|---|---:|---|
| 2 | `iam` | 8 | IAM-01–IAM-08 |
| 3 | `core` | 11 | GOV-01–GOV-11 |
| 4 | `academic` | 13 | ACD-01–ACD-12, ACD-14 |
| 5 | `student` | 13 | STU-01–STU-12, STU-15 |
| 6 | `attendance` | 6 | ATT-01–ATT-06 |
| 7 | `assessment` | 7 | ASM-01–ASM-07 |
| 8 | `exam` | 7 | EXM-01–EXM-07 |
| 9 | `faculty` | 3 | FAC-01–FAC-03 |
| 10 | `doc` | 6 | DOC-01–DOC-06 |
| 11 | `knowledge` | 3 | KNW-01–KNW-03 |
| 12 | `cip` | 11 | CIP-01–CIP-11 |
| 13 | `policy` | 7 | POL-01–POL-07 |
| 14 | `integration` | 9 | INT-01–INT-09 |
| 15 | `ops` | 4 | OPS-01–OPS-04 |
| **Total** | | **108** | |

This matches `ENTITY_CATALOG.md` §19: **152 catalogued, 108 Initial Release, 44 Future/Blocked**.

---

## 17. Implementation notes that apply to every table

| Concern | Requirement |
|---|---|
| Naming | `snake_case`, singular table names, `<entity>_id` primary keys. |
| Time | Store `timestamptz` in UTC; the application renders `Asia/Kolkata`. Never store local time. |
| Money | `numeric(12,2)`, INR, never `float`. |
| Concurrency | `row_version` on mutable tables; update uses `WHERE row_version = :expected`. |
| Soft delete | Not used for academic facts. `status`/`superseded`/`valid_to` carry lifecycle. |
| Hard delete | Only unreferenced draft rows, and only through an audited administrative function. |
| FK actions | `RESTRICT`/`NO ACTION` by default. No `CASCADE` on academic, assessment, attendance, result, document, or audit tables. |
| Partial unique | Used for "one current row" (`is_current`, `status = 'active'`). |
| Exclusion | Used for non-overlapping validity ranges (`status_history`, `programme_version` year ranges). |
| Text search | `tsvector` generated columns + GIN for document/chunk/notice search; `pg_trgm` for names. |
| Vectors | pgvector `vector(N)` with HNSW (cosine) once OD-06 fixes N; exact scan acceptable below ~50k chunks. |
| Partitioning | `ops.audit_event` monthly; optionally `attendance.record` and `cip.message` by term/date at scale. |
| RLS | Enabled on all student/attendance/assessment/exam/finance/services/doc/knowledge/cip tables and on `iam.person`, `iam.person_contact`, `iam.identity_account`, `iam.role_assignment`. |
| Audit | Application writes `ops.audit_event`; triggers seal append-only tables. The audit writer is a dedicated role. |
| Secrets | Never in the database. IdP tokens, provider keys, and storage credentials live in the secret manager. |
| Personal data | `R`/`G` columns are excluded from the retrieval corpus and masked in default projections. |

---

## 18. What this dictionary deliberately leaves open

| Item | Why | Where tracked |
|---|---|---|
| Vector dimension (384 vs 1024) | Depends on the multilingual embedding decision and a measured benchmark. | `OPEN_DECISIONS.md` OD-06 |
| Attendance variant enforcement | C-01 / G-01 unresolved. | `OPEN_DECISIONS.md` OD-01 |
| Result approval signatory | G-12 unresolved. | `OPEN_DECISIONS.md` OD-02 |
| Fee gate | G-08 unresolved. | `OPEN_DECISIONS.md` OD-03 |
| Autonomy batch boundary | G-04 unresolved. | `OPEN_DECISIONS.md` OD-04 |
| Retention periods | G-22 unresolved; table exists but is not populated. | `OPEN_DECISIONS.md` OD-05 |
| Second student career | OD-11; unique key is per batch, not per person. | `OPEN_DECISIONS.md` OD-11 |
| Section teaching history | Decided design: `academic.section_teacher_assignment`; authority is a role assignment. | `OPEN_DECISIONS.md` OD-13 |
| Student section transfers | Decided design: `student.section_assignment`; `student.section_id` is a cache. | `OPEN_DECISIONS.md` OD-13 |
| Sensitive student data | Decided design: `R/G` classification matrix; legal basis and named-role access still require DPO confirmation. | `OPEN_DECISIONS.md` OD-16 |
| Finance and services columns | Phase 2; catalogued relationships, no column dictionary yet. | `ENTITY_CATALOG.md` §§10–11 |
| Future exam operations | Phase 2; catalogued, not column-dicted. | `ENTITY_CATALOG.md` §8.2 |

**End of data dictionary.**

