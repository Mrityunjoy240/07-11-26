# ERD — Integration, Policy, and Audit

**Domains:** Integration and Synchronization (`integration`), Policy (`policy`), Audit and Operations (`ops`).
**Trace:** Research §9, §11.6, §11.9, §13.1–13.6; S14, S18, S20; G-09, G-10, G-22.
**Purpose:** show the control plane that surrounds the academic domains: how external identity is mapped, which system wins per field, how a rule is versioned and scoped, and how every sensitive action is recorded without becoming mutable business state.

---

## 1. Integration and provenance

```mermaid
erDiagram
    ENTITY_TYPE {
        text entity_type_code PK
        text description
        text schema_name
        text table_name
        boolean is_active
    }
    EXTERNAL_SYSTEM {
        uuid external_system_id PK
        text code
        text name
        text system_type
        text base_url
        uuid owner_org_unit_id FK
        text status
        jsonb capabilities_json
        timestamptz last_health_at
    }
    EXTERNAL_ID_MAPPING {
        uuid external_id_mapping_id PK
        text entity_type_code FK
        uuid external_system_id FK
        uuid internal_id
        text external_id
        boolean is_primary
        date valid_from
        date valid_to
        text confidence
    }
    SOURCE_OF_TRUTH_RULE {
        uuid source_of_truth_rule_id PK
        text entity_type_code FK
        text field_name
        uuid authoritative_system_id FK
        uuid fallback_system_id FK
        text conflict_policy
        date effective_from
        date effective_to
        text status
        uuid approved_by FK
    }
    SYNC_RUN {
        uuid sync_run_id PK
        uuid external_system_id FK
        text entity_type_code FK
        text direction
        text mode
        timestamptz started_at
        timestamptz finished_at
        text status
        integer records_read
        integer records_written
        integer records_failed
        text cursor_before
        text cursor_after
        text error_summary
        text adapter_version
        uuid operator_person_id FK
    }
    SYNC_RECORD {
        uuid sync_record_id PK
        uuid sync_run_id FK
        text entity_type_code FK
        uuid internal_id
        text external_id
        text operation
        text outcome
        text error_code
        text error_detail
    }
    SYNC_CONFLICT {
        uuid sync_conflict_id PK
        uuid sync_run_id FK
        text entity_type_code FK
        uuid internal_id
        text field_name
        jsonb internal_value_json
        jsonb external_value_json
        uuid source_of_truth_rule_id FK
        text status
        text resolution
        text resolution_note
        uuid resolved_by FK
        timestamptz resolved_at
    }
    RECORD_PROVENANCE {
        uuid record_provenance_id PK
        text entity_type_code FK
        uuid internal_id
        text field_name
        uuid source_system_id FK
        uuid sync_run_id FK
        timestamptz observed_at
        text value_hash
        boolean is_human_override
    }
    OUTBOX_EVENT {
        uuid outbox_event_id PK
        text aggregate_type
        uuid aggregate_id
        text event_type
        jsonb payload_json
        timestamptz occurred_at
        timestamptz published_at
        text status
        integer retry_count
    }
    ORG_UNIT {
        uuid org_unit_id PK
        text code
    }
    PERSON {
        uuid person_id PK
    }

    EXTERNAL_SYSTEM }o--o| ORG_UNIT : owned_by
    EXTERNAL_ID_MAPPING }o--|| ENTITY_TYPE : describes
    EXTERNAL_ID_MAPPING }o--|| EXTERNAL_SYSTEM : maps_to
    SOURCE_OF_TRUTH_RULE }o--|| ENTITY_TYPE : describes
    SOURCE_OF_TRUTH_RULE }o--o| EXTERNAL_SYSTEM : authoritative
    SOURCE_OF_TRUTH_RULE }o--o| EXTERNAL_SYSTEM : fallback
    PERSON |o--o{ SOURCE_OF_TRUTH_RULE : approves
    EXTERNAL_SYSTEM ||--o{ SYNC_RUN : runs
    ENTITY_TYPE ||--o{ SYNC_RUN : scopes
    PERSON |o--o{ SYNC_RUN : operates
    SYNC_RUN ||--o{ SYNC_RECORD : records
    ENTITY_TYPE ||--o{ SYNC_RECORD : describes
    SYNC_RUN ||--o{ SYNC_CONFLICT : detects
    ENTITY_TYPE ||--o{ SYNC_CONFLICT : describes
    SOURCE_OF_TRUTH_RULE |o--o{ SYNC_CONFLICT : resolves
    PERSON |o--o{ SYNC_CONFLICT : resolves
    ENTITY_TYPE ||--o{ RECORD_PROVENANCE : describes
    EXTERNAL_SYSTEM |o--o{ RECORD_PROVENANCE : source
    SYNC_RUN |o--o{ RECORD_PROVENANCE : observes
```

**The polymorphic exception:** `external_id_mapping.internal_id`, `record_provenance.internal_id`, `sync_record.internal_id`, `sync_conflict.internal_id`, and `audit_event.entity_id` cannot have a foreign key because they point to different tables. The design controls this with `integration.entity_type`, which is a real FK, and with application-level validation. This is the only intentional exception to referential integrity; it is documented here and in `POSTGRES_ARCHITECTURE.md`.

**Why `entity_type` is a table, not a check constraint:** the set of mapped entities grows as modules are added. A registry row is easier to audit than an ever-growing `CHECK IN (...)` list. The registry also records the schema/table, which helps the data steward and the audit tooling.

**Source-of-truth rule:** `authoritative_system_id` may be null, meaning "internal BCREC application is authoritative". A non-null value means the external system wins for that field. `conflict_policy` is `authoritative_wins`, `manual_review`, or `newest_wins`. The research's warning is enforced: two systems cannot both be authoritative for the same field at the same time.

**Provenance:** `record_provenance` records the last writer per field, the source system, the sync run, the observation time, and a hash of the value. A human override is flagged; the next sync cannot silently revert it without a conflict.

**Outbox:** `outbox_event` makes publication reliable. A transaction that changes a result or a fee demand writes an outbox row in the same transaction. A worker publishes it and marks it sent. Consumers must be idempotent.

---

## 2. Policy: rules, versions, scope, bundles, conflicts

```mermaid
erDiagram
    RULE {
        uuid rule_id PK
        text rule_code
        text title
        text domain
        text owner_role_code
    }
    RULE_VERSION {
        uuid rule_version_id PK
        uuid rule_id FK
        uuid supersedes_version_id FK
        uuid source_document_version_id FK
        integer version_no
        text statement
        jsonb parameters_json
        date effective_from
        date effective_to
        text status
        text confidence
        text confidence_reason
        text source_locator
        text approval_reference
        uuid approved_by FK
    }
    RULE_SCOPE {
        uuid rule_scope_id PK
        uuid rule_version_id FK
        uuid institution_id FK
        uuid programme_id FK
        uuid batch_id FK
        uuid term_id FK
        text scope_type
        text course_type
        text student_category
    }
    RULE_CONFLICT {
        uuid rule_conflict_id PK
        uuid rule_version_a_id FK
        uuid rule_version_b_id FK
        uuid resolution_rule_version_id FK
        text description
        text status
        text resolution_note
        uuid resolved_by FK
        timestamptz resolved_at
    }
    POLICY_BUNDLE {
        uuid policy_bundle_id PK
        text bundle_code
        text name
        text domain
        text owner_role_code
    }
    POLICY_BUNDLE_VERSION {
        uuid policy_bundle_version_id PK
        uuid policy_bundle_id FK
        integer version_no
        date effective_from
        date effective_to
        text status
        text approval_reference
        uuid approved_by FK
    }
    POLICY_BUNDLE_MEMBER {
        uuid policy_bundle_member_id PK
        uuid policy_bundle_version_id FK
        uuid rule_version_id FK
        integer sequence_no
        boolean is_required
    }
    DOCUMENT_VERSION {
        uuid document_version_id PK
        text sha256
        text classification
        text status
    }
    PERSON {
        uuid person_id PK
    }
    INSTITUTION {
        uuid institution_id PK
    }
    PROGRAMME {
        uuid programme_id PK
    }
    BATCH {
        uuid batch_id PK
    }
    TERM {
        uuid term_id PK
    }

    RULE ||--o{ RULE_VERSION : versions
    RULE_VERSION ||--o| RULE_VERSION : supersedes
    DOCUMENT_VERSION |o--o{ RULE_VERSION : evidences
    PERSON |o--o{ RULE_VERSION : approves
    RULE_VERSION ||--o{ RULE_SCOPE : applies_to
    INSTITUTION |o--o{ RULE_SCOPE : scopes
    PROGRAMME |o--o{ RULE_SCOPE : scopes
    BATCH |o--o{ RULE_SCOPE : scopes
    TERM |o--o{ RULE_SCOPE : scopes
    RULE_VERSION ||--o{ RULE_CONFLICT : side_a
    RULE_VERSION ||--o{ RULE_CONFLICT : side_b
    RULE_VERSION |o--o{ RULE_CONFLICT : resolves
    PERSON |o--o{ RULE_CONFLICT : resolves
    POLICY_BUNDLE ||--o{ POLICY_BUNDLE_VERSION : versions
    POLICY_BUNDLE_VERSION ||--o{ POLICY_BUNDLE_MEMBER : contains
    RULE_VERSION ||--o{ POLICY_BUNDLE_MEMBER : included_in
    PERSON |o--o{ POLICY_BUNDLE_VERSION : approves
```

**The rule model in one sentence:** a stable rule identity has immutable versions; each version has parameters, an effective window, a status, a confidence, a source document, and a scope; a named bundle selects the versions used by a calculation.

**Status values:** `Current`, `Draft`, `Historical`, `Superseded`, `Disputed`, `Unknown` (research §0.2). The database does not infer status from dates. A rule can be `Current` with an `effective_to` in the future, or `Superseded` with a past date. The status is the institutional statement.

**Conflict handling:** C-01 (attendance) is a `rule_conflict` between ATT-01 and ATT-05. Both versions remain `Disputed`. A bundle may include both, and the consuming calculation must state which variant it used. The conflict is resolved only by a new rule version with an approval reference, at which point the old versions become `Superseded` and the conflict becomes `resolved`.

**What a bundle is not:** a bundle is not a new policy. It is a reproducible selection. Two bundles may share rules. A bundle version is immutable once used by a result, eligibility assessment, or promotion decision.

---

## 3. Audit, data quality, break-glass, retention

```mermaid
erDiagram
    AUDIT_EVENT {
        uuid audit_event_id PK
        timestamptz occurred_at
        uuid actor_person_id FK
        uuid actor_account_id FK
        uuid role_assignment_id FK
        text action
        text entity_type_code FK
        uuid entity_id
        jsonb before_json
        jsonb after_json
        text reason
        text correlation_id
        text source_channel
        inet ip_address
        text user_agent
        text prev_hash
        text record_hash
    }
    DATA_QUALITY_ISSUE {
        uuid data_quality_issue_id PK
        text entity_type_code FK
        uuid record_id
        text issue_type
        text severity
        text description
        timestamptz detected_at
        text status
        uuid assigned_to_person_id FK
        text resolution
        timestamptz resolved_at
    }
    BREAK_GLASS_GRANT {
        uuid break_glass_grant_id PK
        uuid person_id FK
        uuid role_assignment_id FK
        text reason
        timestamptz starts_at
        timestamptz expires_at
        text scope_description
        text status
        uuid approved_by FK
        uuid reviewed_by FK
        timestamptz reviewed_at
    }
    RETENTION_SCHEDULE {
        uuid retention_schedule_id PK
        text entity_type_code FK
        text classification
        integer retention_period_months
        text trigger_event
        text disposition
        text legal_basis
        text status
        uuid approved_by FK
    }
    ENTITY_TYPE {
        text entity_type_code PK
        text schema_name
        text table_name
    }
    PERSON {
        uuid person_id PK
    }
    IDENTITY_ACCOUNT {
        uuid account_id PK
    }
    ROLE_ASSIGNMENT {
        uuid role_assignment_id PK
    }

    PERSON |o--o{ AUDIT_EVENT : acts
    IDENTITY_ACCOUNT |o--o{ AUDIT_EVENT : authenticates
    ROLE_ASSIGNMENT |o--o{ AUDIT_EVENT : authorises
    ENTITY_TYPE ||--o{ AUDIT_EVENT : classifies
    ENTITY_TYPE ||--o{ DATA_QUALITY_ISSUE : classifies
    PERSON |o--o{ DATA_QUALITY_ISSUE : assigned
    PERSON ||--o{ BREAK_GLASS_GRANT : receives
    ROLE_ASSIGNMENT |o--o{ BREAK_GLASS_GRANT : narrows
    PERSON |o--o{ BREAK_GLASS_GRANT : approves
    PERSON |o--o{ BREAK_GLASS_GRANT : reviews
    ENTITY_TYPE ||--o{ RETENTION_SCHEDULE : classifies
    PERSON |o--o{ RETENTION_SCHEDULE : approves
```

**Audit event:** append-only. `before_json` and `after_json` hold only the changed fields for sensitive entities, not full row copies. `prev_hash` and `record_hash` form a hash chain per partition; a nightly checkpoint can be signed and stored separately. The chain detects tampering but does not prevent a privileged administrator from deleting rows; database privileges and WAL archiving are the real controls.

**Actor model:** `actor_person_id` and `actor_account_id` are both stored. A service account has a null person and a non-null account. `role_assignment_id` is the authority actually exercised; a person with several roles must act under one assignment, never an amorphous "user".

**Correlation:** `correlation_id` links an HTTP request, a background job, and an outbox event. It is mandatory for state changes.

**Data quality:** `data_quality_issue` is a first-class work item. It links to the entity type and record, records severity and assignment, and closes with a resolution. It is not a comment field on a business table.

**Break-glass:** a grant is time-bound and scoped. It must be approved and later reviewed. It does not bypass audit; it creates additional audit events. The research labels break-glass a recommendation, not an observed BCREC practice.

**Retention:** the table exists, but no period is populated until G-22 is decided. `disposition` is `destroy`, `anonymize`, or `archive`. A retention job cannot run against a table with no approved schedule.

---

## 4. Integrity and service-boundary notes

| Concern | Design |
|---|---|
| External IDs | Only in `integration.external_id_mapping`; never on `student`, `exam`, or `finance` tables. |
| Polymorphic IDs | Validated by `integration.entity_type`; no FK. Documented exception. |
| Audit immutability | `ops.audit_event` has no update/delete grant for application roles; only the audit writer may insert. |
| Policy immutability | `policy.rule_version` and `policy.policy_bundle_version` are insert-only after use; updates are blocked by trigger. |
| Integration writes | The integration service calls domain APIs; it has no direct `INSERT/UPDATE` on academic tables. |
| Conflict resolution | A human steward resolves; the service never silently overwrites. |
| Outbox delivery | At-least-once; consumers use an idempotency key. |
| Service accounts | No interactive login; `iam.identity_account` has `account_type = service`; scoped permissions only. |

---

## 5. RLS implications

| Table | Policy intent |
|---|---|
| `integration.external_id_mapping` | Data Steward, Integration Service, Auditor. |
| `integration.sync_conflict` | Data Steward and Auditor; integration service writes but cannot resolve. |
| `integration.record_provenance` | Data Steward, Auditor; read-only to domain owners. |
| `policy.rule_version` | Read by all authenticated roles (rules are internal); write by Academic Council/Registrar. Draft status visible. |
| `policy.rule_conflict` | Read by Academic Council, Registrar, Auditor; write by Registrar. |
| `ops.audit_event` | Auditor and Principal read; no one updates; writes via a security-definer function. |
| `ops.break_glass_grant` | Principal, Auditor; the grantee sees own grant. |
| `ops.retention_schedule` | Registrar, Legal, Auditor; empty until approved. |

---

## 6. Open decisions that affect this ERD

| Decision | Effect |
|---|---|
| G-09 MAKAUT/NAD integration | Determines whether a portal adapter or manual file exchange is built first. |
| G-10 college ERP/IdP | Determines `external_system` rows, adapter capabilities, and the account subject format. |
| G-22 retention | Populates `retention_schedule`; enables disposition jobs. |
| OD-09 source-of-truth approval | Confirms the per-field authority matrix before any sync writes. |
| OD-10 audit retention | Determines partition retention and hash-checkpoint storage. |
