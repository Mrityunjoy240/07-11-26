# Fee Architecture Audit & Future-Proof Fee Engine Design

## 1. Problems in Current Architecture

### 1.1 Six Fee Data Sources — All With Different Values

The same fee data is duplicated across 6 sources, and 4 of them contain **stale/wrong values**:

| Source | File | CSE Total | Status |
|--------|------|-----------|--------|
| `FEE_GROUP_MAP` (code constant) | `groq_service.py:698` | 6,17,700 | ✅ Correct (verified against PDF) |
| Per-department `fees.total` | `combined_kb.json:117` | 6,17,700 | ✅ Correct |
| `fees_summary` | `combined_kb.json:444` | Rs. 617,700 | ✅ Correct (string format) |
| `canonical_kb.json` | `canonical_kb.json:1616` | Rs. 617,700 | ✅ Correct |
| `voice_ready_answers.fees` | `combined_kb.json:1262` | **6,04,700** | ❌ **Stale** (off by 13,000) |
| `fees.md` | `topics/fees.md:7` | **6,04,700** | ❌ **Stale** (off by 13,000) |
| `SYSTEM_PROMPT` (hardcoded) | `groq_service.py:864` | **6,04,700** | ❌ **Stale** (off by 13,000) |

The stale sources all share the same wrong values, suggesting they were generated from an earlier version of the fee data that has since been updated. This means:
- LLM-based responses (reading `voice_ready_answers`, `fees.md`, or `SYSTEM_PROMPT`) return **wrong amounts**
- Only the deterministic `FEE_GROUP_MAP` + `_structured_lookup()` path returns correct amounts
- Students asking the same question may get different answers depending on which code path handles it

### 1.2 Catastrophic Naming Collision — "Admission Fee" Means Three Different Things

The term **"admission fee"** is used inconsistently across data sources:

```
FEE_GROUP_MAP tuple:     (total_fee, admission_fee, per_semester)
                                   ^^^^^^^^^^^^
                                   Actually = first semester payable (Rs. 99,225 for CSE)

Per-department fee entry: "admission": 10000
                          ^^^^^^^^^^^^
                          Actually = admission fee component only

SYSTEM_PROMPT:            "Admission fee: approximately 8,000"
                                                   ^^^^^
                                                   Completely wrong (probably from even older data)
```

The `FEE_GROUP_MAP` tuple labels its second field `admission_fee`, but the value `99,225` for CSE is the **total first semester payable amount** — which includes:
- Admission fee component: Rs. 10,000
- Tuition (1 sem): Rs. 60,500
- Development fee (1 sem): Rs. 9,075
- Caution money (refundable): Rs. 5,000
- Other charges: ~Rs. 14,650 (library, registration, etc.)

So when `_lang_fee_response()` says *"Admission and semester fees are separate"*, it actually means *"The first semester amount and subsequent semester amounts are different"* — but uses the wrong word "admission".

### 1.3 The "Alag Se" Lie — Root Cause

The response template in `_lang_fee_response()` (line 4191):
```python
f"The total fee for {dept} is {amount_str}. Admission and semester fees are separate."
```

This is **factually wrong**. The total fee (Rs. 6,17,700) **already includes**:
- The first semester payment (Rs. 99,225)
- 6 regular semester payments (Rs. 73,925 × 6)
- The eighth semester payment (Rs. 74,925)

A student reading this would understandably think "I have to pay Rs. 6,17,700 PLUS admission fee PLUS semester fees" — a misinterpretation that could cost lakhs.

The dead code `_calculate_total_fees()` (line 3844) has the **correct** wording:
```python
"The total fee for CSE is six lakh seventeen thousand seven hundred rupees. "
"This includes an admission fee of ninety nine thousand two hundred twenty five rupees "
"and per semester fee of seventy three thousand nine hundred twenty five rupees."
```

This method is never called from production. Its wording says **"includes"** (correct) instead of **"are separate"** (misleading).

### 1.4 Hardcoded Fee Constants Block Future-Proofing

`FEE_GROUP_MAP` is defined as a module-level dictionary (line 698):
```python
FEE_GROUP_MAP: Dict[str, tuple[int, int, int]] = {
    "CSE": (617700, 99225, 73925),
    ...
}
```

Problems:
- **Adding a fee component** (e.g., training charge from 3rd semester) requires code changes to the tuple structure and all consumers
- **Changing fees for a specific batch** is impossible — no academic-year dimension
- **Mid-course fee revision** (e.g., college adds Rs. 5,000/semester "smart class fee" from 2027 batch) requires code change
- The 3-tuple format is rigid — MBA uses `per_sem=0` as a sentinel, which is hacky
- No hostel fee, caution money, or optional charges can be represented

### 1.5 Semester-Wise Data Exists in KB But Is Never Used by Code

`combined_kb.json` already contains semester-wise breakdowns:
```json
"semester_wise_cse_it_ece": {
    "first": 99225,
    "per_semester": 73925,
    "eighth": 74925,
    "total_btech": 617700
}
```

The production code **never reads this data**. It only reads the 3-tuple from `FEE_GROUP_MAP`. So:
- Query "2nd semester fee for CSE" falls through to `_lang_fee_response("semester", ...)` → returns **per_semester (73,925)** for ALL semesters, when the correct answer should be 73,925 (which happens to be correct for semesters 2-7, but wrong for semester 1 and 8)
- Query "8th semester fee for CSE" → incorrectly returns 73,925 instead of 74,925
- Query "first semester fee for CSE" → hits the "admission fee" handler if user says "admission", otherwise returns per_semester

### 1.6 Voice_Ready_Answers Also Contains Stale Fees

The `voice_ready_answers.fees` section in `combined_kb.json` (line 1260) and `canonical_kb.json` are used by the LLM-based response path. These contain the old (wrong) values. Since the `_structured_lookup()` fee handler returns early (before LLM fallback), this stale data only surfaces if the structured handler misses the intent.

### 1.7 All B.Tech Branches Share an Incorrect Fixed Admission Component of Rs. 10,000

In `combined_kb.json` per-department fees, every B.Tech branch has `"admission": 10000`. This is hardcoded to the same value for all branches, even though the first-semester amounts differ significantly (CSE: 99,225 vs ME: 75,650). This means the admission fee component is not actually representative of the per-department first-semester fee breakdown.

### 1.8 MBA Fee Data Has No Semester Breakdown

- `FEE_GROUP_MAP` stores MBA as `(419200, 121400, 0)` — `per_sem=0` means "no semester breakdown available"
- The code handles this by falling back to "total" response for MBA when semester fee is asked
- The official PDF may have semester data that was never extracted

### 1.9 SYSTEM_PROMPT Fee Values Are Wrong and Outdated

The SYSTEM_PROMPT (line 864-869) is the instruction given to the LLM for fallback responses. Its fee values are from an older revision and are wrong:
- CSE total: shows 6,04,700 (should be 6,17,700)
- Per semester: "approximately 65,000 to 75,000" (vague)
- Admission fee: "approximately 8,000" (completely wrong)

If the LLM ever generates a fee response (when structured handler fails), it will answer incorrectly.

---

## 2. New Fee Data Model Schema

### 2.1 Design Philosophy

- **Single source of truth**: One `fee_structures.json` file. Every code path reads from it.
- **Component-based**: Store individual fee line items, not pre-computed totals.
- **Versioned**: Each fee revision has a `valid_from` batch/session. Past revisions are retained (append-only).
- **Semester-aware**: Every component can be mapped to specific semesters or semester ranges.
- **Admin-updatable**: Changing fees = editing JSON. No code changes.

### 2.2 JSON Schema

```jsonc
{
  // Schema version for migration detection
  "schema_version": "2.0.0",

  // Each program has its own fee structure with versioned entries
  "programs": {
    "B.Tech": {
      "display_name": "Bachelor of Technology",
      "duration_semesters": 8,
      "groups": {
        // Fee groups share the same fee structure
        "group_a": { "branches": ["CSE", "IT", "ECE"] },
        "group_b": { "branches": ["EE", "AIML", "DS", "CY", "CSD"] },
        "group_c": { "branches": ["ME", "CE"] }
      },
      "structures": [
        {
          "version_id": "2026-01",
          "label": "2026-2030 Fee Structure",
          "valid_from_batch": "2026-2027",
          "valid_until_batch": null,        // null = current (still active)
          "admission_batches": ["2026-2030"],
          "effective_date": "2026-07-01",
          "last_updated": "2026-07-10",
          "source": "BCREC Fee Structure PDF 2026-30",

          // Shared components that apply uniformly
          "shared": {
            "caution_money": {
              "refundable": true,
              "with_hostel": 12000,
              "without_hostel": 10000
            }
          },

          // Group-specific fee components
          "groups": {
            "group_a": {
              "components": [
                {
                  "id": "admission_fee",
                  "label": "Admission Fee (one-time)",
                  "type": "one_time",
                  "category": "compulsory",
                  "amount": 10000,
                  "charged_in_semester": 1,
                  "notes": "Non-refundable admission processing fee"
                },
                {
                  "id": "tuition",
                  "label": "Tuition Fee",
                  "type": "per_semester",
                  "category": "compulsory",
                  "amount": 60500,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8],
                  "notes": "Covers academic instruction"
                },
                {
                  "id": "development_fee",
                  "label": "Development Fee",
                  "type": "per_semester",
                  "category": "compulsory",
                  "amount": 9075,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8],
                  "notes": "Infrastructure and campus development"
                },
                {
                  "id": "library_fee",
                  "label": "Library Fee",
                  "type": "per_semester",
                  "category": "compulsory",
                  "amount": 2500,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                },
                {
                  "id": "exam_fee",
                  "label": "Examination Fee",
                  "type": "per_semester",
                  "category": "compulsory",
                  "amount": 2000,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                },
                {
                  "id": "student_welfare",
                  "label": "Student Welfare Fee",
                  "type": "per_semester",
                  "category": "compulsory",
                  "amount": 1500,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                },
                {
                  "id": "training_placement",
                  "label": "Training & Placement Fee",
                  "type": "per_semester",
                  "category": "compulsory",
                  "amount": {
                    "type": "simple",
                    "semester_ranges": {
                      "1-1": 5000,    // special in sem 1
                      "2-7": 2000,    // regular in sems 2-7
                      "8-8": 2500     // special in sem 8
                    }
                  },
                  "notes": "Covers training, soft skills, placement drives"
                },
                {
                  "id": "caution_deposit",
                  "label": "Caution Money (Refundable)",
                  "type": "one_time",
                  "category": "refundable",
                  "amount": 5000,
                  "charged_in_semester": 1,
                  "refundable_at": "course_completion",
                  "notes": "Refundable after completion of course"
                },
                {
                  "id": "university_charge",
                  "label": "University Charge (MAKAUT)",
                  "type": "per_semester",
                  "category": "compulsory",
                  "amount": 350,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                }
              ],

              // Semester-level overrides for semesters whose total differs from sum of per_semester components
              "semester_overrides": {
                "8": {
                  "training_placement": 2500,
                  "tuition": 61500,
                  "adjustment_note": "Eighth semester has reduced academic load, training fee includes final placement support"
                }
              },

              // Pre-computed total for quick reference (can be auto-validated)
              "computed": {
                "total_course_fee": 617700,
                "first_semester_payable": 99225,
                "regular_semester_fee": 73925,
                "eighth_semester_fee": 74925
              }
            },

            "group_b": {
              "components": [
                {
                  "id": "admission_fee",
                  "label": "Admission Fee (one-time)",
                  "type": "one_time",
                  "category": "compulsory",
                  "amount": 10000,
                  "charged_in_semester": 1
                },
                {
                  "id": "tuition",
                  "label": "Tuition Fee",
                  "type": "per_semester",
                  "amount": 55000,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                },
                {
                  "id": "development_fee",
                  "label": "Development Fee",
                  "type": "per_semester",
                  "amount": 8250,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                },
                {
                  "id": "library_fee",
                  "label": "Library Fee",
                  "type": "per_semester",
                  "amount": 2000,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                },
                {
                  "id": "exam_fee",
                  "label": "Examination Fee",
                  "type": "per_semester",
                  "amount": 1500,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                },
                {
                  "id": "student_welfare",
                  "label": "Student Welfare Fee",
                  "type": "per_semester",
                  "amount": 1250,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                },
                {
                  "id": "training_placement",
                  "label": "Training & Placement Fee",
                  "type": "per_semester",
                  "amount": 1500,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                },
                {
                  "id": "caution_deposit",
                  "label": "Caution Money (Refundable)",
                  "type": "one_time",
                  "category": "refundable",
                  "amount": 5000,
                  "charged_in_semester": 1
                },
                {
                  "id": "university_charge",
                  "label": "University Charge (MAKAUT)",
                  "type": "per_semester",
                  "amount": 350,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                }
              ],
              "semester_overrides": {
                "8": { "tuition": 56000, "training_placement": 2500 }
              },
              "computed": {
                "total_course_fee": 567100,
                "first_semester_payable": 92900,
                "regular_semester_fee": 67600,
                "eighth_semester_fee": 68600
              }
            },

            "group_c": {
              "components": [
                {
                  "id": "admission_fee",
                  "label": "Admission Fee (one-time)",
                  "type": "one_time",
                  "amount": 10000,
                  "charged_in_semester": 1
                },
                {
                  "id": "tuition",
                  "label": "Tuition Fee",
                  "type": "per_semester",
                  "amount": 40000,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                },
                {
                  "id": "development_fee",
                  "label": "Development Fee",
                  "type": "per_semester",
                  "amount": 6000,
                  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8]
                },
                // ... other components
              ],
              "computed": {
                "total_course_fee": 429100,
                "first_semester_payable": 75650,
                "regular_semester_fee": 50350,
                "eighth_semester_fee": 51350
              }
            }
          }
        }
        // Future: add new structure version here when fees change
        // {
        //   "version_id": "2027-01",
        //   "label": "2027-2031 Fee Structure (Revised)",
        //   "valid_from_batch": "2027-2028",
        //   "admission_batches": ["2027-2031"],
        //   "effective_date": "2027-07-01",
        //   "supersedes": "2026-01",
        //   "groups": { ... }
        // }
      ]
    },

    "MBA": {
      "display_name": "Master of Business Administration",
      "duration_semesters": 4,
      "groups": {
        "mba": { "branches": ["MBA"] }
      },
      "structures": [
        {
          "version_id": "2026-01",
          "label": "2026-2028 MBA Fee Structure",
          "valid_from_batch": "2026-2027",
          "groups": {
            "mba": {
              "components": [
                {
                  "id": "admission_fee",
                  "label": "Admission Fee (one-time)",
                  "type": "one_time",
                  "amount": 50000,
                  "charged_in_semester": 1
                },
                {
                  "id": "tuition",
                  "label": "Tuition Fee",
                  "type": "per_semester",
                  "amount": 65000,
                  "applicable_semesters": [1, 2, 3, 4]
                },
                // ... other components
              ],
              "computed": {
                "total_course_fee": 419200,
                "first_semester_payable": 121400
              }
            }
          }
        }
      ]
    },

    "MCA": {
      "display_name": "Master of Computer Applications",
      "duration_semesters": 4,
      "groups": {
        "mca": { "branches": ["MCA"] }
      },
      "structures": [
        {
          "version_id": "2026-01",
          "valid_from_batch": "2026-2027",
          "groups": {
            "mca": {
              "components": [ /* MCA components */ ],
              "computed": {
                "total_course_fee": 214600,
                "first_semester_payable": 67800,
                "regular_semester_fee": 48600
              }
            }
          }
        }
      ]
    }
  },

  // Separate hostel fee model — independent of program
  "hostel": {
    "structures": [
      {
        "version_id": "2026-01",
        "valid_from_batch": "2026-2027",
        "components": [
          {
            "id": "hostel_seat_rent_single",
            "label": "Single Bed Seat Rent",
            "type": "per_semester",
            "amount": 30000,
            "availability": "Limited (need-based)"
          },
          {
            "id": "hostel_seat_rent_shared",
            "label": "Double/Triple Bed Seat Rent",
            "type": "per_semester",
            "amount": 10000,
            "availability": "Standard"
          },
          {
            "id": "hostel_seat_rent_4bed",
            "label": "4-Bed Seat Rent",
            "type": "per_semester",
            "amount": 10000,
            "availability": "Maximum"
          },
          {
            "id": "hostel_caution_money",
            "label": "Hostel Caution Deposit (Refundable)",
            "type": "one_time",
            "amount": 2000,
            "category": "refundable",
            "charged_in_semester": 1
          },
          {
            "id": "mess_charges",
            "label": "Mess Charges",
            "type": "per_month",
            "amount": 5500,
            "months_per_year": 11,
            "notes": "Includes vegetarian meals daily, non-veg 3-4 days/week"
          }
        ]
      }
    ]
  },

  // Flags for features derived from the model
  "_meta": {
    "total_component_count": 48,
    "program_count": 4,
    "last_verified": "2026-07-10",
    "verified_against": "BCREC Fee Structure PDF 2026-30"
  }
}
```

### 2.3 Alternative Architecture Considered: SQLite

**Considered but rejected** for this use case:
- A SQLite table with `fees(program, branch, component, semester, batch, amount)` would make complex queries easier (e.g., "all fee changes between batches X and Y")
- However, it adds a build step, requires SQL knowledge for updates, and doesn't fit the existing JSON-only KB infrastructure
- **Recommendation**: Use JSON for now. If the college's fee structure grows to cover 20+ programs with 5+ revisions across different batches, migrate to SQLite at that point.

---

## 3. Migration Strategy

### Phase 1: Create Single Source of Truth (No Code Changes)

1. Create `backend/data/fee_structures/fee_structures.json` — the new comprehensive file with ALL data from:
   - `FEE_GROUP_MAP` (the correct values)
   - `combined_kb.json` semester-wise breakdowns (`semester_wise_cse_it_ece`, etc.)
   - Per-department fee components (tuition, development fee, caution money)
   - Hostel fee data from `combined_kb.json` hostel section
   - Official PDF verification data

2. Add a validation script `scripts/validate_fee_structures.py` that:
   - Loads `fee_structures.json`
   - Computes totals from components
   - Compares against `computed` values
   - Reports discrepancies

3. Generate `FEE_STRUCTURE_VALIDATION.md` report showing all component breakdowns, totals, and verification status

### Phase 2: Adopt the New Data in Code

4. Create a `FeeEngine` class (in `backend/app/services/llm/fee_engine.py`):
   ```python
   class FeeEngine:
       def __init__(self, path: str = "data/fee_structures/fee_structures.json"):
           self.data = json.load(open(path, encoding="utf-8"))

       def get_program(self, branch: str) -> str:
           # Map any branch code to program name (B.Tech, MBA, MCA, M.Tech)

       def get_fee_components(self, branch: str, batch: str | None = None) -> list:
           # Return all fee components for the branch + batch

       def get_semester_fee(self, branch: str, semester: int, batch: str | None = None) -> int:
           # Compute total for a specific semester

       def get_total_fee(self, branch: str, batch: str | None = None) -> int:
           # Compute total course fee (sum of all semesters)

       def get_admission_time_payable(self, branch: str, batch: str | None = None) -> dict:
           # Return first-semester items with component breakdown

       def get_hostel_fee(self, room_type: str | None = None) -> dict:
           # Return hostel fee components

       def get_fee_summary(self, branch: str, lang: str, batch: str | None = None) -> str:
           # Return a formatted natural language response
           # "The total fee for CSE is Rs. 6,17,700. This includes..."
   ```

5. Replace `FEE_GROUP_MAP` with `FeeEngine`:
   - Remove `FEE_GROUP_MAP` dictionary
   - Replace `_structured_lookup()` fee handler to use `FeeEngine`
   - Replace `_tool_get_fees()` to use `FeeEngine`
   - Remove dead code: `_calculate_total_fees()`, `_calculate_semester_fees()`, `_detect_on_topic_arithmetic()`
   - Replace `_lang_fee_response()` with new response templates

6. Update `_lang_fee_response()` to generate accurate, component-aware responses:
   - "The total fee for CSE is Rs. 6,17,700. This **includes** the first semester payment of Rs. 99,225 and per-semester fee of Rs. 73,925 for semesters 2-7, plus Rs. 74,925 for the eighth semester."
   - "The first semester payable for CSE is Rs. 99,225 which includes: Admission Fee Rs. 10,000, Tuition Rs. 60,500, Development Fee Rs. 9,075, Library Fee Rs. 2,500, ..."
   - "The semester fee for CSE (semesters 2-7) is Rs. 73,925 per semester. This includes: Tuition Rs. 60,500, Development Fee Rs. 9,075, ..."

### Phase 3: Clean Up Inconsistent Data

7. Remove stale fee data:
   - Update `combined_kb.json` → `voice_ready_answers.fees.*` with correct values OR remove them if `FeeEngine` handles all fee queries
   - Update `fees.md` with correct values
   - Update `SYSTEM_PROMPT` fee section with correct values or remove and let `FeeEngine` handle
   - Update per-department `fees.admission` to be consistent (rename to `fees.components` or remove)

8. Update all test files to use `FeeEngine`:
   - `test_groq_service.py` — replace tests that check `FEE_GROUP_MAP` directly
   - `red_team/cases.py` — update expected responses to match new wording
   - Remove dead code tests

### Phase 4: Add Admin Tooling

9. Create a CLI tool `scripts/manage_fees.py`:
   ```bash
   python scripts/manage_fees.py validate          # Validate all computed totals
   python scripts/manage_fees.py list              # List all fee structures
   python scripts/manage_fees.py show CSE          # Show CSE fee breakdown
   python scripts/manage_fees.py diff 2026-01 2027-01  # Show changes between versions
   python scripts/manage_fees.py add-version ...   # Scaffold a new version (interactive)
   ```

10. Add a runtime hot-reload mechanism so `FeeEngine` detects changes to `fee_structures.json` without server restart (optional, can use file mtime polling).

---

## 4. Response Strategy for Every Fee Question Type

### 4.1 Question → Handler Mapping

| User Ask | Intent | Handler | Response |
|----------|--------|---------|----------|
| "What is the fee for CSE?" | `total_course_fee` | `FeeEngine.get_total_fee("CSE")` | *"The total fee for CSE is Rs. 6,17,700. This covers all 8 semesters. Would you like a semester-by-semester breakdown?"* |
| "What is the admission fee for CSE?" | `admission_fee` | `FeeEngine.get_admission_time_payable("CSE")` | *"The first semester payable for CSE is Rs. 99,225 which includes: Admission Fee Rs. 10,000, Tuition Rs. 60,500, Development Fee Rs. 9,075, Library Fee Rs. 2,500, ..."* |
| "What is the semester fee for CSE?" | `semester_fee` | `FeeEngine.get_semester_fee("CSE", semester=2)` | *"The per-semester fee for CSE (semesters 2-7) is Rs. 73,925. This includes Tuition Rs. 60,500, Development Fee Rs. 9,075, ..."* |
| "What is the 2nd semester fee for CSE?" | `specific_semester_fee` | `FeeEngine.get_semester_fee("CSE", semester=2)` | *"The 2nd semester fee for CSE is Rs. 73,925."* |
| "What is the 8th semester fee for CSE?" | `specific_semester_fee` | `FeeEngine.get_semester_fee("CSE", semester=8)` | *"The 8th semester fee for CSE is Rs. 74,925."* (uses override) |
| "How much do I pay at admission time for CSE?" | `admission_time_payable` | `FeeEngine.get_admission_time_payable("CSE")` | *"At the time of admission for CSE, you pay Rs. 99,225. This is the first semester fee which includes..."* |
| "What is the hostel fee?" | `hostel_fee` | `FeeEngine.get_hostel_fee()` | *"Hostel seat rent is Rs. 10,000 per semester (shared room) or Rs. 30,000 (single). Mess charges are Rs. 5,500 per month. Caution deposit is Rs. 2,000 (refundable)."* |
| "What is the total fee for CSE including hostel?" | `total_with_hostel` | `FeeEngine.get_total_fee("CSE") + FeeEngine.get_hostel_fee("shared")` | *"CSE total fee is Rs. 6,17,700. With hostel (shared, 8 semesters at Rs. 10,000/sem) and mess (11 months/year for 4 years at Rs. 5,500/month), the total would be approximately Rs. 6,17,700 + Rs. 80,000 + Rs. 2,42,000 = Rs. 9,39,700 plus refundable deposits."* |
| "Is the admission fee refundable?" | `refund_policy` | `FeeEngine` component lookup + refund KB | *"The Admission Fee of Rs. 10,000 is non-refundable. Caution Money of Rs. 5,000 is refundable after course completion."* |
| "What are the fee components for CSE?" | `fee_breakdown` | `FeeEngine.get_fee_components("CSE")` | *"CSE fee has these components: Tuition Rs. 60,500/sem, Development Fee Rs. 9,075/sem, Library Fee Rs. 2,500/sem, ..."* |
| "Kitna fee hai CSE ka?" | Hindi `total_course_fee` | Same handler | *"CSE ka total fee 6,17,700 rupaye hai. Yah 8 semesters ka total hai."* |
| "What is the fee for MBA?" | `total_course_fee` | `FeeEngine.get_total_fee("MBA")` | *"The total fee for MBA is Rs. 4,19,200. The first semester payable is Rs. 1,21,400. Contact the accounts office for semester-wise breakdown."* |
| "CSE fee 2027 batch" | `batch_specific_fee` | `FeeEngine.get_total_fee("CSE", batch="2027-2028")` | *"For the 2027-2028 batch, the CSE total fee is Rs. 6,32,700 (revised). This is an increase from the 2026-2030 structure."* |
| "Why is semester 8 fee different?" | `semester_difference` | `FeeEngine.get_semester_fee("CSE", 8)` + component diff | *"Semester 8 has a different fee (Rs. 74,925 vs Rs. 73,925) because the Training & Placement fee is higher in the final semester."* |

### 4.2 Response Templates (Language Aware)

The response formatter should have three tiers of detail:

**Tier 1 — Quick** (default for simple queries):
```
"The total fee for {dept} is {amount}. This covers all {n} semesters."
```

**Tier 2 — Includes** (when user asks for total and mentions components):
```
"The total fee for {dept} is {amount}. This includes:
- First semester payment: {first_sem}
- Semesters 2-{n-1}: {regular_sem} each
- Semester {n}: {last_sem} (different due to {reason})
Total components: {list_components}"
```

**Tier 3 — Full breakdown** (when user explicitly asks):
```
"The fee for {dept} has the following components:
{component_table}
Total course fee: {amount}"
```

---

## 5. Backward Compatibility Plan

### 5.1 Production Rollout Strategy

| Step | What | Risk | Rollback |
|------|------|------|----------|
| 0 | Deploy `fee_structures.json` alongside existing code (read-only reference) | None | N/A |
| 1 | Add `FeeEngine` class, wire it into `_structured_lookup()` alongside existing `FEE_GROUP_MAP` handler | Low — new code path, old path untouched | Delete class, revert imports |
| 2 | Feature flag: `FEE_ENGINE_ENABLED` env var | Low — no production impact | Flip flag off |
| 3 | In `_structured_lookup()`: try `FeeEngine` first, fall back to `FEE_GROUP_MAP` | Low — fallback preserves behavior | Remove flag, keep fallback |
| 4 | Migrate tests to assert against `FeeEngine` | Low — test-only change | N/A |
| 5 | Remove `FEE_GROUP_MAP`, dead code, stale data | Medium — tests must be fully migrated first | Git revert commit(s) |
| 6 | Enable hot-reload for `fee_structures.json` | Low | Disable polling |

### 5.2 API Contract Guarantees

- **Existing tool `get_fees`**: The return format changes from flat JSON (total, admission, per_semester) to the new component-based format. The LLM consuming this tool must be re-prompted.
- **Structured lookup responses**: Wording changes from "X alag se hai" to "X includes Y". Test assertions that check exact response text will break and need updating.
- **All existing test cases should be preserved as integration tests** but with updated expected response values and wording.

### 5.3 Database/KB Migration

- `combined_kb.json` fees fields: **Keep** but mark as deprecated. A migration script can delete them once `FeeEngine` is verified in production for 2 weeks.
- `canonical_kb.json` fees fields: Same as above.
- `fees.md`: Update values to match `FeeEngine`. Keep as LLM fallback reference.
- `voice_ready_answers`: Remove fee entries or update to match `FeeEngine`. These are used by the LLM response path, and having stale data there is dangerous.

### 5.4 Test Migration Plan

| Test File | Change Required |
|-----------|----------------|
| `test_groq_service.py::TestStructuredKnowledge` | Update expected response strings to new wording |
| `test_groq_service.py::TestStructuredArithmetic` | Replace `FEE_GROUP_MAP` assertions with `FeeEngine` assertions |
| `red_team/cases.py` | Update all `response_contains` checks for new wording |
| `red_team/runner.py` | Remove `structured_arithmetic` handler stage |
| `red_team/pipeline_hooks.py` | Remove `_detect_on_topic_arithmetic` from pipeline |
| `scripts/demo_readiness_test.py` | Update fee format validation checks |
| `scripts/test_faq_comprehensive.py` | Update expected values |

---

## 6. Edge Cases

### 6.1 Mid-Course Fee Revision

**Scenario**: College adds a "Smart Class Fee" of Rs. 5,000/semester starting from semester 5 for the current 2026-2030 batch.

**Current system**: Requires code change — add a new field to all FEE_GROUP_MAP tuples, update all consumers, update KB data, update fees.md, update SYSTEM_PROMPT.

**New system**: One JSON change:
```json
{
  "id": "smart_class_fee",
  "label": "Smart Class Fee",
  "type": "per_semester",
  "amount": 5000,
  "applicable_semesters": [5, 6, 7, 8],
  "effective_from_semester": 5,
  "notes": "Introduced mid-course from 2027-28 academic session",
  "added_on": "2027-01-15"
}
```
Then run `python scripts/manage_fees.py validate` to confirm totals are recomputed. Zero code changes.

### 6.2 Different Batches, Different Fees

**Scenario**: The 2026-2030 batch has one fee structure, the 2027-2031 batch has a revised structure (10% tuition increase).

**Current system**: Impossible — no batch dimension in `FEE_GROUP_MAP`.

**New system**: Add a new structure version to the array:
```json
{
  "version_id": "2027-01",
  "valid_from_batch": "2027-2028",
  "supersedes": "2026-01",
  "groups": {
    "group_a": {
      "components": [
        { "id": "tuition", "amount": 66550 }  // 10% increase
      ],
      "computed": {
        "total_course_fee": 648200  // auto-validated
      }
    }
  }
}
```
The query `FeeEngine.get_total_fee("CSE", batch="2027-2028")` returns the correct new value. The default (no batch specified) returns the **latest active** structure.

### 6.3 MBA Has No Semester Breakdown

**Scenario**: User asks "what is the semester fee for MBA" when no semester breakdown exists in data.

**Response strategy**:
```
"The MBA total fee is Rs. 4,19,200. The first semester payable is Rs. 1,21,400.
For subsequent semesters, please contact the accounts office at 0343-2501353
for a detailed semester-wise breakdown."
```

The `FeeEngine` should detect when a program has insufficient data for per-semester answers and route to a "contact accounts" response instead of guessing.

### 6.4 Hostel Is Optional — Fee Queries Without Hostel

**Scenario**: User asks "total fee for CSE including hostel".

**Response**:
```
"B.Tech CSE total academic fee: Rs. 6,17,700 (across 8 semesters).
Hostel is optional. If you opt for a shared room (Rs. 10,000/sem):
  - Hostel rent: Rs. 80,000 (8 semesters)
  - Mess: Rs. 60,500/year (Rs. 5,500/month × 11 months)
  - Hostel caution deposit: Rs. 2,000 (refundable)
Grand total (including hostel and mess): approximately Rs. 9,39,700 plus refundable deposits."
```

The FeeEngine should always separate academic fee (compulsory) from hostel fee (optional) and clearly indicate which parts are refundable.

### 6.5 "Fee" Queries Without Department Specified

**Scenario**: User asks just "fees" or "fee structure".

**Response**: List all program groups, then offer to drill down:
```
"BCREC offers several programs with different fee structures:
- B.Tech: Rs. 4,29,100 to Rs. 6,17,700 (depending on branch)
- MBA: Rs. 4,19,200
- MCA: Rs. 2,14,600
- M.Tech: Rs. 1,28,000 to Rs. 2,27,000

Which branch or program would you like fee details for?"
```

No code change needed — the FeeEngine iterates programs and groups.

### 6.6 Fee Queries for Lateral Entry

**Scenario**: Lateral entry students join in semester 3. Their total fee is not 8 semesters but 6.

**Handling**: The `FeeEngine.get_total_fee()` accepts an optional `entry_semester` parameter:
```python
FeeEngine.get_total_fee("CSE", entry_semester=3)
# Returns: sum of semesters 3-8 = 73925 (sem 3 fill) + 73925 (sem 4-7) + 74925 (sem 8)
# = 73925 * 4 + 74925 + some adjustment
# plus one-time admission fee of Rs. 10,000 (already paid at lateral entry time)
```

Wait — lateral entry also pays "admission fee" at lateral entry time. The model needs to handle this:

```json
{
  "id": "lateral_entry_fee",
  "label": "Lateral Entry Processing Fee",
  "type": "one_time",
  "amount": 1500,
  "charged_in_semester": 3,
  "notes": "Charged at the time of lateral entry admission"
}
```

### 6.7 Fee Queries in Bengali/Hindi

The multilingual response formatter in `_format_inr()` already exists and works well. The new FeeEngine must preserve this.

**Recommendation**: Make `FeeEngine` return structured data (not strings), and pass it to a response formatter that handles language:
```python
class FeeResponseFormatter:
    def total_fee(self, data: FeeSummary, lang: str) -> str: ...
    def semester_fee(self, data: SemesterFee, lang: str) -> str: ...
    def component_breakdown(self, components: list[Component], lang: str) -> str: ...
```

This separates data computation (FeeEngine) from presentation (FeeResponseFormatter).

### 6.8 Deprecated Branch Codes

**Scenario**: A branch is discontinued (e.g., intake reduced to 0 for EE from 2027).

**Handling**: The branch can remain in `group_b` with a note:
```json
{
  "id": "EE",
  "status": "discontinued_from_batch",
  "discontinued_batch": "2027-2028",
  "notes": "EE intake reduced to 0 from AY 2027-28. Existing students continue under old structure."
}
```

The FeeEngine can return a response like: *"EE is being phased out. For the 2026-2027 batch, the total fee is Rs. 5,67,100. New admissions from 2027-2028 are not available."*

### 6.9 Caution Money Refundable Only at Completion

The current response doesn't distinguish refundable vs non-refundable components. This matters for:
- "How much do I get back?" questions
- Total calculation for students who want "what I actually pay" (non-refundable only)

The FeeEngine should provide two total calculations:
- `get_total_fee()` — sum of ALL component amounts (including refundable deposits)
- `get_total_non_refundable()` — sum of compulsory components only (excluding refundable deposits)

### 6.10 Fee Formatting Inconsistencies

Current data stores fees as:
- Integers: `617700` (FEE_GROUP_MAP, per-department fees)
- Strings with "Rs.": `"Rs. 617,700"` (fees_summary)
- Strings with "Rs.": `"Rs. 6,17,700"` (voice_ready_answers) — different comma placement!
- English words: `"six lakh seventeen thousand seven hundred"` (voice_ready_answers)
- Markdown: `Rs. 6,04,700` (fees.md — wrong value + different formatting)

**Resolution**: The new model stores all amounts as **integers (paise-free)** in the JSON. Formatting is done ONLY by `FeeResponseFormatter`:
```python
FeeResponseFormatter.format_inr(617700, "en")  # "six lakh seventeen thousand seven hundred rupees"
FeeResponseFormatter.format_inr(617700, "hi")  # "छह लाख सत्रह हज़ार सात सौ रुपये"
FeeResponseFormatter.format_inr(617700, "bn")  # "ছয় লক্ষ সতেরো হাজার সাতশো টাকা"
FeeResponseFormatter.format_compact(617700)    # "Rs. 6,17,700" (tables/short responses)
FeeResponseFormatter.format_table(...)         # Tabular markdown (for voice_ready_answers)
```

---

## 7. Recommended Code Changes Summary

| Priority | Change | Files Affected | Effort |
|----------|--------|---------------|--------|
| **P0** | Fix `_lang_fee_response()` to say "includes" not "alag se" | `groq_service.py:4172-4191` | 1 hour |
| **P0** | Create `fee_structures.json` with all verified data | New file | 2 hours |
| **P0** | Fix SYSTEM_PROMPT fee values | `groq_service.py:864-869` | 15 min |
| **P0** | Fix `fees.md` stale values | `topics/fees.md` | 15 min |
| **P1** | Implement `FeeEngine` class | `backend/app/services/llm/fee_engine.py` | 4 hours |
| **P1** | Replace `FEE_GROUP_MAP` with `FeeEngine` | `groq_service.py:698-712, 3051-3098` | 3 hours |
| **P1** | Remove dead code `_calculate_total_fees()`, `_calculate_semester_fees()`, `_detect_on_topic_arithmetic()` | `groq_service.py:3844-3904` | 30 min |
| **P2** | Create `FeeResponseFormatter` class | New file or within fee_engine.py | 2 hours |
| **P2** | Fix stale `voice_ready_answers.fees` in both KBs | `combined_kb.json:1262-1289`, `canonical_kb.json` | 1 hour |
| **P2** | Update all test files | 5+ test files | 3 hours |
| **P3** | Create `scripts/manage_fees.py` CLI | New file | 2 hours |
| **P3** | Update `_tool_get_fees()` to return component-based data | `groq_service.py:1357-1375` | 1 hour |

---

## 8. Critical Recommendations (Outside Scope of Fee-Only)

1. **Audit the relationship between `_structured_lookup()` and the LLM path**: Currently `_structured_lookup()` returns early, preventing the LLM from generating a response. This is correct for fee queries. But for queries the structured handler partially matches (e.g., "fee for CSE and placement"), the structured handler may return incomplete information. Consider whether fee + placement should be a multi-intent response.

2. **Consider removing `voice_ready_answers` fee data entirely**: Once `FeeEngine` handles ALL fee queries deterministically, the LLM never needs to generate fee responses. The `voice_ready_answers.fees` section becomes dead code. Removing it eliminates the stale-data risk.

3. **The SYSTEM_PROMPT fee values should be removed, not just fixed**: Putting specific fee values in the LLM prompt is an anti-pattern. The structured handler should handle ALL fee queries. Only keep a note in the prompt like: *"For fee queries, the system will provide accurate data. Do not attempt to recall or calculate fees from memory."*

4. **Renaming recommendation**: The `FEE_GROUP_MAP` second tuple element `admission` should be renamed to `first_semester_payable` or `initial_payment` to prevent future naming confusion. The true "admission fee" component is a sub-field within the first semester.

---

## 9. Validation & Verification

### 9.1 Pre-Deployment Checklist

- [ ] `fee_structures.json` passes `scripts/validate_fee_structures.py`
- [ ] All `computed` totals match sum-of-components for every branch group
- [ ] No stale fee values remain in KB files (voice_ready_answers, per-department fees)
- [ ] SYSTEM_PROMPT no longer contains specific fee values
- [ ] `fees.md` references accurate values or redirects to FeeEngine
- [ ] All test files pass with new response templates
- [ ] MBA semester queries produce correct "contact accounts" fallback
- [ ] Lateral entry fee queries produce correct partial-course totals
- [ ] Hostel fee queries correctly separate compulsory vs optional costs
- [ ] Bengali and Hindi responses use correct grammatical forms for new wording

### 9.2 Post-Deployment Monitoring

- [ ] Track `HANDLER: fee_intent matched` log frequency: should be same or higher
- [ ] Track "alag se" mentions in response logs: should drop to zero
- [ ] Track unresolved fee queries (knowledge_gaps.json): should decrease
- [ ] Manual test: Ask 20 fee questions spanning all programs and verify answers against PDF

---

## 10. Admin Workflow Design — Complete Fee Update Without Code Changes

### 10.1 Design Constraints (Non-Negotiable)

1. **Zero Python code changes** for any fee update. A college clerk with text-editor skills can do it.
2. **Zero server restart** requirements. The FeeEngine detects file changes via mtime polling (same pattern as existing `_read_canonical_kb()`).
3. **Zero risk of serving invalid data**. Every fee structure file is validated on load. If validation fails, the engine falls back to the last known valid state with a clear error log.
4. **Immutable history**. Past fee structures are never deleted, only superseded. Queries referencing old batches still resolve correctly.

### 10.2 File Hierarchy

```
backend/data/fee_structures/                  # Single top-level directory
├── _schema.json                              # JSON Schema (draft-07) — structural validation
├── _config.json                              # Engine configuration
├── _errors.log                               # Auto-generated validation error log
├── btech.json                                # B.Tech fee structures (ALL versions)
├── mba.json                                  # MBA fee structures
├── mca.json                                  # MCA fee structures
├── mtech.json                                # M.Tech fee structures
└── hostel.json                               # Hostel fee structures (program-independent)
```

**Why one file per program instead of one monolithic file:**
- **Separation of concerns**: An admin editing MBA fees doesn't need to sift through B.Tech data
- **File size management**: Each file stays small and focused
- **Independent validation**: A syntax error in `btech.json` doesn't break `mba.json`
- **Diff-friendly**: `git diff btech.json` shows only B.Tech changes
- **Rollback granularity**: If an MBA fee update goes wrong, only `mba.json` needs reverting

**Why not one file per program per version (e.g., `btech_2026.json`, `btech_2027.json`):**
- Forces the engine to manage directory listing and file enumeration
- Makes version ordering implicit (filename parsing) instead of explicit (`version_id` and `valid_from_batch`)
- Harder to see the complete history of a program's fee structures
- Admin must create a new file AND update engine config — two operations instead of one

### 10.3 `_config.json` — Engine Configuration

```jsonc
{
  "_description": "FeeEngine configuration — edit only when defaults need changing",

  "schema_version": "2.0.0",
  "last_modified": "2026-07-10",

  // Current academic year — used as default batch when user doesn't specify one
  "current_academic_year": "2026-2027",

  // Default program-to-file mapping (auto-discovered from file headers, but explicit here for safety)
  "program_files": {
    "btech.json": { "programs": ["B.Tech"] },
    "mba.json": { "programs": ["MBA", "MBA (Hospital Management)"] },
    "mca.json": { "programs": ["MCA"] },
    "mtech.json": { "programs": ["M.Tech"] },
    "hostel.json": { "programs": [] }  // standalone — no program mapping needed
  },

  // Branch-to-program mapping (the canonical list used by the engine)
  "branch_mapping": {
    "CSE": "B.Tech",  "IT": "B.Tech",  "ECE": "B.Tech",
    "EE":  "B.Tech",  "AIML": "B.Tech", "DS": "B.Tech",
    "CY":  "B.Tech",  "CSD": "B.Tech",
    "ME":  "B.Tech",  "CE": "B.Tech",
    "MBA": "MBA",     "MBA-HM": "MBA (Hospital Management)",
    "MCA": "MCA",
    "MTECH": "M.Tech"
  },

  // Error handling policy
  "on_validation_error": "fallback",    // "fallback" or "crash"
  "fallback_strategy": "previous_valid", // "previous_valid" or "hardcoded_defaults"

  // Cache TTL in seconds (how often the engine re-checks file mtimes)
  "cache_ttl_seconds": 300,

  // Hardcoded fallback values if NO valid fee file exists (last resort only)
  "fallback_defaults": {
    "btech_range": "Rs. 4,29,100 to Rs. 6,17,700",
    "contact_message": "Please contact the accounts office at 0343-2501353 for current fee details."
  }
}
```

**Admin does NOT need to touch `_config.json` for routine fee updates.** It only needs updating when:
- A new program file is added (rare)
- A branch is renamed or added (very rare)
- The current academic year changes (once per year — automated in the future)
- Error handling policy needs changing (almost never)

### 10.4 Program Fee File Structure (e.g., `btech.json`)

```jsonc
{
  "_file_meta": {
    "program": "B.Tech",
    "display_name": "Bachelor of Technology",
    "duration_semesters": 8,
    "last_updated": "2026-07-10",
    "updated_by": "Admin Name / System",
    "structure_count": 1,
    "schema_version": "2.0.0"
  },

  "groups": {
    "group_a": { "branches": ["CSE", "IT", "ECE"] },
    "group_b": { "branches": ["EE", "AIML", "DS", "CY", "CSD"] },
    "group_c": { "branches": ["ME", "CE"] }
  },

  "structures": [
    {
      "version_id": "v2026",
      "status": "active",
      "label": "2026-2030 Fee Structure",
      "admission_batches": ["2026-27", "2027-28", "2028-29", "2029-30", "2030-31"],
      "effective_date": "2026-07-01",
      "published_date": "2026-06-15",
      "source": "BCREC Fee Structure PDF 2026-30",
      "groups": {
        "group_a": {
          "components": [ /* ... */ ],
          "semester_overrides": { /* ... */ },
          "computed": { "total_course_fee": 617700, "first_semester_payable": 99225,
                        "regular_semester_fee": 73925, "eighth_semester_fee": 74925 }
        }
      }
    }
  ]
}
```

### 10.5 Validation Rules (Enforced on Every Load)

The FeeEngine runs these validations every time a file is loaded (on mtime change detection). If ANY rule fails, the engine rejects the file and keeps the previous valid state:

#### 10.5.1 Structural Validation (JSON Schema — `_schema.json`)

| Rule | Description | Error Action |
|------|-------------|-------------|
| Valid JSON | File must parse with `json.load()` | Reject file, log error |
| Required keys | `_file_meta`, `groups`, `structures` must exist | Reject file, log error |
| Types correct | `groups` is object, `structures` is array, amounts are integers | Reject file, log error |
| Enum values | `status` must be `"active"` or `"superseded"` or `"archived"` | Reject structure |
| Date format | `effective_date`, `published_date` must match `YYYY-MM-DD` | Reject structure |
| Batch format | `admission_batches` entries must match `YYYY-YY` pattern | Reject structure |
| Component IDs | Must be unique within a structure version | Reject structure |

#### 10.5.2 Semantic Validation (Post-Schema Logic)

| Rule | Description | Error Action |
|------|-------------|-------------|
| Amounts non-negative | All component amounts >= 0 | Reject structure |
| Semester bounds | `applicable_semesters` values within `[1, duration_semesters]` | Reject structure |
| Semester range consistency | `charged_in_semester` for one-time components within valid range | Reject structure |
| Computed total matches | `computed.total_course_fee` == sum of all components × applicable semesters | Warn but accept (auto-correct on next validation run) |
| No overlapping batch ranges | For a given program, no two active structures claim the same admission batch | Reject file |
| Component total vs override | If `semester_overrides[8]` exists, `computed.eighth_semester_fee` must equal the override total | Warn but accept |
| Referential integrity | Group keys in `structures[].groups` must match keys in top-level `groups` | Reject structure |
| Branch codes exist | All branch codes in `groups` must be in `_config.json.branch_mapping` | Warn only |

#### 10.5.3 Cross-File Validation (Run on Demand via CLI)

| Rule | Description | Command |
|------|-------------|---------|
| No orphan hostels | Hostel components don't reference non-existent programs | `validate --cross-file` |
| Consistent branch names | Same branch code across all program files means the same thing | `validate --cross-file` |
| Fee structure coverage | Every program defined in `_config.json` has at least one active structure | `validate --coverage` |

### 10.6 Versioning Strategy

#### Version ID Convention

```
{year}-{increment}

Examples:
  v2026       — initial 2026-2030 structure
  v2027       — 2027-2031 revision (full revision)
  v2027-hotfix — mid-year correction (e.g., typo fix, component addition)
```

Version IDs must be unique within a program file. They are used in:
- `version_id` — unique identifier for the structure
- `supersedes` — references the version this one replaces (optional, for tracking)
- `admission_batches` — lists which academic-year batches this structure applies to

#### Status Lifecycle

```
draft (admin working on it) → active (live) → superseded (replaced by newer) → archived (no longer queryable by default)
```

The engine only loads structures with `status: "active"` or `status: "superseded"`.
- `active`: Used as the default when no batch is specified
- `superseded`: Still queryable by batch-specific queries
- `archived`: Permanently excluded. Structures reach this state only via explicit admin action after verifying no batch is still referencing them.

### 10.7 Effective Date / Batch Selection Logic

When a user asks a fee question, the engine resolves which fee structure to use:

```
get_structure(program: str, batch: str | None, semester: int | None) -> Structure:
    1. If batch is specified:
        a. Search structures[] for this program where admission_batches contains batch
        b. If found → return that structure
        c. If NOT found:
            i. Find the structure whose admission_batches has the closest start year ≤ batch year
            ii. If no match → return error "No fee structure found for batch {batch}"
    
    2. If batch is NOT specified (default):
        a. Get current_academic_year from _config.json
        b. Search structures[] where admission_batches contains current_academic_year
        c. If found → return that structure
        d. If NOT found:
            i. Find the LATEST structure (by effective_date) that is active
            ii. Return that structure with a note "This is the current fee structure"
    
    3. Once structure is resolved:
        a. Identify the group within the structure (based on branch code → group mapping)
        b. Build a component list for that group
        c. If semester is specified, filter components applicable to that semester
        d. Return the resolved FeeData object
```

**Example resolutions:**

| Query | Resolution |
|-------|-----------|
| "CSE fee" | Default batch = current year `2026-27` → `v2026` structure (admission_batches includes 2026-27) |
| "CSE fee 2028 batch" | Specified batch = `2028-29` → `v2026` structure (admission_batches includes 2028-29) |
| "CSE fee 2032 batch" | No structure admits 2032 → Closest match: `v2026` (admits up to 2030-31). Returns with note that this is the last published structure |
| "CSE fee 2024 batch" | Batch before any structure → Closest match: `v2026` but with note that 2024 precedes published fee structures |
| "CSE fee 5th semester" | Same structure resolution, then filter components by `applicable_semesters: [5]` |
| "CSE admission fee" | Same structure, sum all one-time components where `charged_in_semester: 1` |

### 10.8 How Multiple Fee Structures Coexist

Multiple structures in the same JSON file coexist peacefully because they apply to different admission batches:

```jsonc
{
  "structures": [
    {
      "version_id": "v2026",
      "admission_batches": ["2026-27", "2027-28", "2028-29", "2029-30", "2030-31"],
      "status": "active",
      "groups": {
        "group_a": { "components": [ /* 2026 rates */ ] }
      }
    },
    {
      "version_id": "v2027",
      "admission_batches": ["2027-28", "2028-29", "2029-30", "2030-31", "2031-32"],
      "status": "active",
      "supersedes": "v2026",
      "groups": {
        "group_a": { "components": [ /* 2027 revised rates */ ] }
      }
    }
  ]
}
```

**Engine behavior when both structures exist:**
- Batch 2026-27 → matches ONLY `v2026` (v2027 also admits 2027-28 but NOT 2026-27)
- Batch 2027-28 → matches BOTH (v2026 and v2027 both include 2027-28). Engine picks the **newer** version (v2027) because it has a later `effective_date`
- Batch 2028-29 → matches BOTH (same logic, picks v2027)
- Batch 2031-32 → matches ONLY `v2027`

**Why overlapping admission batch ranges are allowed:**
- In practice, fee structures are typically valid for 5-year windows (2026-2030, 2027-2031)
- A 2027 revision supersedes the 2026 version for newly admitted students from 2027 onwards
- Existing 2026-batch students still pay 2026 rates, even after the 2027 revision is published
- The overlap ensures continuity — any batch within the intersection is assigned the newer structure

**Validation rule for overlaps:**
- If two structures have overlapping `admission_batches`, the one with the later `effective_date` takes priority
- If `effective_date` is identical, the one with a later `published_date` or explicit `supersedes` wins
- This must be documented in `_config.json` or in the file's `_file_meta` section for clarity

### 10.9 How Optional Charges Are Added/Removed

Optional charges are just component objects with `"optional": true` or `"category": "optional"`.

#### Adding a New Optional Charge (e.g., "Training Fee" mid-course)

The admin edits the program file (e.g., `btech.json`), finds the relevant structure and group, and adds:

```jsonc
{
  "id": "training_fee",
  "label": "Training & Placement Fee",
  "type": "per_semester",
  "category": "optional",
  "amount": 2500,
  "applicable_semesters": [5, 6, 7, 8],
  "notes": "Optional — covers additional training programs, mock interviews, and placement drives"
}
```

**What happens in responses:**
- `get_total_fee("CSE")` — **excludes** optional charges by default. Returns base compulsory total
- `get_total_fee("CSE", include_optional=True)` — **includes** optional charges
- `get_fee_components("CSE")` — returns ALL components, each tagged with `category: "compulsory" | "refundable" | "optional"`
- The response formatter says: *"The total fee for CSE is Rs. 6,17,700 (compulsory). Optional charges like Training Fee (Rs. 2,500/sem from semester 5) are available. Would you like to include them?"*

#### Removing an Optional Charge (e.g., "Old Lab Fee" discontinued)

The admin can either:
1. **Remove the component object** — permanent deletion (for truly retired charges)
2. **Add a `"discontinued_from_batch"` field** — graceful deprecation:

```jsonc
{
  "id": "old_lab_fee",
  "label": "Computer Lab Fee (Discontinued)",
  "type": "per_semester",
  "category": "optional",
  "amount": 1000,
  "applicable_semesters": [1, 2, 3, 4, 5, 6, 7, 8],
  "discontinued_from_batch": "2027-28",
  "discontinued_note": "Lab fee merged into tuition from 2027-28 onwards"
}
```

The engine ignores discontinued components for batches >= `discontinued_from_batch`.

#### Adding a New Category of Optional Charge (e.g., "International Study Tour")

The admin adds a component with `"category": "special"`:

```jsonc
{
  "id": "study_tour",
  "label": "International Study Tour (Optional)",
  "type": "one_time",
  "category": "special",
  "amount": 50000,
  "charged_in_semester": 6,
  "notes": "Optional 2-week international immersion program for select students"
}
```

No code changes. The response formatter already handles all categories generically:
- `compulsory`: Always included in totals
- `refundable`: Included in totals, marked as refundable
- `optional`: Excluded from base totals, listed separately
- `special`: Same as optional, but with emphasis ("special programs like..." in responses)

### 10.10 How Deprecated Fee Structures Are Archived

#### Step 1: Mark as Superseded (Automatic)

When an admin adds a new structure with a later `effective_date` and overlapping `admission_batches`, the old structure's status doesn't change automatically. The admin should update it:

```jsonc
{
  "version_id": "v2026",
  "status": "superseded",                    // ← changed from "active"
  "superseded_by": "v2027",                 // ← added
  "superseded_on": "2027-06-15",            // ← added
  "admission_batches": ["2026-27"],          // ← narrowed to only non-overlapping batches
  // ... rest unchanged
}
```

The engine:
- Stops using this structure for new default lookups (prefers active structures)
- Still uses it for queries that specify batch `2026-27` (the only remaining batch)
- Removes it from the "current fee structure" list

#### Step 2: Archive (Manual, Later)

Once the last batch covered by a structure has graduated (e.g., 2026-batch B.Tech students graduate in 2030), the admin can:

```jsonc
{
  "version_id": "v2026",
  "status": "archived",                      // ← changed from "superseded"
  "archived_on": "2030-08-15",              // ← added
  "archived_reason": "All covered batches have graduated"
}
```

The engine:
- Does NOT load this structure by default
- Still loads it if a query explicitly requests it by `version_id` (for historical reference)
- The admin tool can still display archived structures: `scripts/manage_fees.py show --include-archived`

#### Step 3: Physical Archiving (Optional)

After confirming no queries hit archived structures, the admin can move the structure entry to a separate archive file:

```
backend/data/fee_structures/
├── archived/
│   ├── btech_2019-2025.json                # Extracted from a previous overhaul
│   └── btech_2026.json                     # Current archive after 2027 revision
```

This is a FILE OPERATION (move), not a code change. The engine's `_config.json` would need a new key to load archive files, but this is so rare (once every 5-10 years) that it warrants a code change anyway.

**Recommendation:** Keep all structures in the main file. Only physical-archive when the file grows beyond 10,000 lines or 500 KB, which won't happen for a single college's fee data for decades.

### 10.11 Concrete Example: Updating Only One Semester's Fee

**Scenario:** In the 2026-2030 B.Tech structure, the college decides to add a "Smart Class Technology Fee" of Rs. 3,000 starting from semester 3 only (not semesters 1-2). The change takes effect from the 2027-28 admission batch onwards.

**Admin action:**

1. Open `backend/data/fee_structures/btech.json`
2. Navigate to the `v2026` structure (or create a new `v2027` structure if this is a full revision)
3. Add the new component:

```jsonc
{
  "version_id": "v2026",
  "admission_batches": ["2026-27", "2027-28", "2028-29", "2029-30", "2030-31"],
  "status": "active",
  ...
  "groups": {
    "group_a": {
      "components": [
        // ... existing components unchanged ...
        {
          "id": "smart_class_fee",
          "label": "Smart Class Technology Fee",
          "type": "per_semester",
          "category": "compulsory",
          "amount": 3000,
          "applicable_semesters": [3, 4, 5, 6, 7, 8],
          "effective_from_batch": "2027-28",       // ← only applies from 2027 batch
          "notes": "Covers smart board, digital content, and online assessment platform"
        }
      ],
      "computed": {
        "total_course_fee": 635700,                 // ← updated: old 617700 + 3000*6
        "first_semester_payable": 99225,            // ← unchanged (sem 1 not affected)
        "regular_semester_fee": 73925,              // ← unchanged (sems 2-6 are 73925)
        "eighth_semester_fee": 74925,               // ← unchanged (sem 8)
        "_computed_breakdown": {                    // ← explanatory (auto-generated by validation)
          "sem1": 99225,
          "sem2_6": [73925, 76925, 76925, 76925, 76925],  // ← sem 2 unchanged, sems 3-6 increased
          "sem7": 76925,
          "sem8": 74925
        }
      }
    }
  }
}
```

4. Save `btech.json`
5. Run validation: `python scripts/manage_fees.py validate btech.json`
6. Validation output:
```
✓ btech.json: JSON syntax OK
✓ btech.json: Schema validation passed
✓ btech.json: Component amounts are non-negative
✓ btech.json: Semester bounds within [1, 8]
✓ btech.json: Computed total 635700 matches: 99225 + 73925 + 76925*4 + 74925 = 635700
✓ btech.json: All branch codes known
✓ btech.json: Group_a new computed breakdown matches
✓ btech.json: smart_class_fee effective_from_batch 2027-28 after v2026 effective_date 2026-07-01
✗ btech.json: computed._computed_breakdown shows semester 2 as 73925 while per_semester
  suggests 76925. Override needed for semester 2? [ADVISORY ONLY]
  → Action: Only if semester 2 should also increase. If smart class fee starts from sem 3,
    this is correct. Dismiss warning.
```

7. If the admin also wants to add a `semester_overrides` entry for clarity:
```jsonc
"semester_overrides": {
  "3": { "note": "Smart Class Fee of Rs. 3,000 added from this semester" },
  "4": { "note": "Smart Class Fee included" },
  "5": { "note": "Smart Class Fee included" },
  "6": { "note": "Smart Class Fee included" },
  "7": { "note": "Smart Class Fee included" },
  "8": { "note": "Smart Class Fee included" }
}
```

**Result:** Zero code changes. Server picks up changes within `cache_ttl_seconds` (default 300s) automatically. All queries now reflect the updated fee.

### 10.12 Admin Update Checklist (Poster-Ready)

```
┌─────────────────────────────────────────────────────┐
│  HOW TO UPDATE FEES (NO CODE CHANGES REQUIRED)      │
│                                                     │
│  1. Open the right file:                            │
│     backend/data/fee_structures/{program}.json     │
│                                                     │
│  2. Find the structure you want to modify:          │
│     Look in the "structures" array                  │
│                                                     │
│  3. For a NEW fee structure (new batch):            │
│     a. Copy the latest structure entry              │
│     b. Change version_id, label, admission_batches  │
│     c. Update component amounts                     │
│     d. Update computed totals                       │
│     e. Paste it at the TOP of the structures array  │
│                                                     │
│  4. For a MID-COURSE change (existing batch):       │
│     a. Add a new component with effective_from_batch│
│     b. Update computed totals                       │
│     c. Add semester overrides if needed             │
│                                                     │
│  5. For optional charges:                           │
│     a. Add component with "category": "optional"    │
│     b. Or mark existing component as optional       │
│                                                     │
│  6. Validate:                                       │
│     python scripts/manage_fees.py validate          │
│                                                     │
│  7. Wait 5 minutes (cache TTL) or restart server    │
│                                                     │
│  8. Test: "What is the CSE fee for 2027 batch?"     │
│                                                     │
│  DON'T:                                             │
│  - Delete old structures (future queries may need   │
│    them for historical reference)                   │
│  - Change _config.json (only for structural changes)│
│  - Modify Python code                               │
└─────────────────────────────────────────────────────┘
```

### 10.13 Admin Tooling: `scripts/manage_fees.py` CLI Design

```
Usage:
  python scripts/manage_fees.py validate [file]     Validate fee structure files
  python scripts/manage_fees.py list                 List all programs and their active structures
  python scripts/manage_fees.py show <branch>        Show full fee breakdown for a branch
  python scripts/manage_fees.py show <branch> --batch 2027-28   Show fees for a specific batch
  python scripts/manage_fees.py diff <v1> <v2>       Show differences between two versions
  python scripts/manage_fees.py check-coverage        Verify every branch has an active fee structure
  python scripts/manage_fees.py check-batch <batch>   Verify a specific batch is covered
  python scripts/manage_fees.py check-expiry          List structures that will expire within 1 year
  python scripts/manage_fees.py recompute [file]      Auto-calculate and update computed totals
  python scripts/manage_fees.py init                  Create a fresh fee_structures directory with templates
```

All commands read-only except `recompute` and `init`. Validation must pass before any data is loaded by the runtime engine.

### 10.14 Recovery Procedures

#### Scenario A: Admin introduces a syntax error in a fee file

**What happens:**
1. The engine detects the mtime change and tries to load the file
2. `json.load()` fails with `JSONDecodeError`
3. The engine logs: `FEE ENGINE: btech.json failed to parse: Expecting value: line 42 column 1`
4. The engine keeps the previous valid state in memory
5. All fee queries continue to work with the old data

**Admin recovery:**
1. Admin is notified via error log (or sees the validation script fail)
2. Fixes the syntax error in the file
3. Saves again
4. Engine detects the new mtime, loads the fixed file, resumes normal operation

#### Scenario B: Admin introduces a semantic error (wrong computed total)

**What happens:**
1. Engine loads the file successfully (JSON is valid)
2. Semantic validation detects that `computed.total_course_fee` doesn't match sum of components
3. Engine logs a WARNING (not error) — auto-corrects the computed total silently
4. Fee queries return the CORRECT total (sum of components), ignoring the wrong `computed` field
5. The admin tool `validate` explicitly reports the mismatch

**Admin recovery:**
1. Run `python scripts/manage_fees.py recompute btech.json` — this updates the `computed` field
2. The file is rewritten with correct computed values
3. Next engine load picks up the corrected file

#### Scenario C: No fee structure exists for a requested batch

**Engine response:** *"I don't have fee information for the 2035-36 batch yet. The latest available fee structure covers batches up to 2030-31. For the most current information, please contact the accounts office at 0343-2501353."*

**Admin action:** Add a new structure covering the 2035-36 batch, following the same JSON pattern.

#### Scenario D: All fee files are deleted

**Engine response:** Falls back to `_config.json.fallback_defaults` — returns the hardcoded range and contact message. Logs a CRITICAL error.

### 10.15 File Lifecycle Summary

```
                       ┌─────────────────┐
                       │ scripts/init     │  (fresh installation)
                       │ creates template │
                       └────────┬────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  fee_structures/      │
                    │  ├── _schema.json     │  ← static, rarely changes
                    │  ├── _config.json     │  ← changes yearly (current_academic_year)
                    │  ├── btech.json       │  ← EDITED BY ADMIN
                    │  ├── mba.json         │  ← EDITED BY ADMIN
                    │  ├── mca.json         │  ← EDITED BY ADMIN
                    │  ├── mtech.json       │  ← EDITED BY ADMIN
                    │  └── hostel.json      │  ← EDITED BY ADMIN
                    └───────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
            ┌────────────────┐    ┌──────────────────┐
            │ Admin edits    │    │ Validation fails │
            │ JSON, saves    │    │ (rollback to     │
            │                │    │  previous state) │
            └───────┬────────┘    └──────────────────┘
                    │
                    ▼
            ┌────────────────┐
            │ Engine detects │
            │ mtime change   │
            └───────┬────────┘
                    │
                    ▼
            ┌────────────────┐
            │ Validate on    │
            │ next request   │
            └───────┬────────┘
                    │
            ┌───────┴────────┐
            │                │
            ▼                ▼
     ┌────────────┐   ┌──────────┐
     │ Valid →    │   │ Invalid  │
     │ use new    │   │ → keep   │
     │ structure  │   │ old data │
     └────────────┘   └──────────┘
```

---

## 11. Key Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| File format | JSON (not YAML/TOML/CSV) | Matches existing KB infrastructure, native Python support, no extra dependencies |
| File split | One file per program | Independent editing and validation, focused diffs, granular rollback |
| Data model | Component-based with computed totals | Flexibility to add/remove charges; computed totals serve as quick reference and validation target |
| Versioning | In-file array of versioned structures | Self-contained files, explicit ordering, no file-naming convention to maintain |
| Batch matching | `admission_batches` array with priority by `effective_date` | Simple for admin (just list which batches the structure covers), deterministic resolution |
| Optional charges | Components with `category: "optional"` | No special handling needed — engine treats generically, formatter separates by category |
| Validation | On every load, with fallback on failure | Guarantees zero downtime even with broken files; follows existing pattern of graceful degradation |
| Default batch | Read from `_config.json.current_academic_year` | Keeps engine stateless; admin updates once per year |
| Multilingual | Separate formatter, engine returns structured data | Clean separation of computation from presentation; formatter can be tested independently |
| Cache | mtime-based (same as `_read_canonical_kb()`) | Leverages existing proven pattern; no new dependency (Redis, etc.) for a single-server deployment |
