# Fee Response Pipeline Audit

Generated: 2026-07-11

---

## 0. Official Source Verification

### Sources found on bcrec.ac.in

| Program | PDF | URL |
|---------|-----|-----|
| B.Tech 2026-2030 | `B.Tech Fee Structure 2026-2030.pdf` | `https://www.bcrec.ac.in/display-pdf-download/B.Tech-Fee-Structure-2026-2030-1.pdf/Fee%20Structure%20B.Tech` |
| B.Tech Lateral 2026-2029 | `B Tech Lat N.pdf` | `https://www.bcrec.ac.in/display-pdf-download/B-Tech-Lat-N-1.pdf/Fee%20Structure%20B.Tech%20Lateral` |
| MCA 2026-2028 | `MCA Fee 2026.pdf` | `https://www.bcrec.ac.in/display-pdf-download/MCA-Fee-2026-1.pdf/Fee%20Structure%20MCA` |
| MBA 2026-2028 | `Fee Structure MBA 2026-2028.pdf` | `https://www.bcrec.ac.in/display-pdf-download/Fee%20Structure%20MBA%202026-2028.pdf/Fee%20Structure%20MBA` |
| MBA (Hospital Management) 2026-2028 | `MBA-(HM).pdf` | `https://www.bcrec.ac.in/display-pdf-download/MBA-%28HM%29-1.pdf/Fee%20Structure%20MBA%20%28Hospital%20Management%29` |
| M.Tech 2026-2028 | `M Tech Fees 2026 (F)-new.pdf` | `https://www.bcrec.ac.in/display-pdf-download/M-Tech-Fees-2026-1.pdf/Fee%20Structure%20M.Tech` |

The B.Tech PDF is a scanned image (1700x2200 px, ~222 KB) — text cannot be extracted programmatically.  
However, the `combined_kb.json` fee data cross-verifies against semester-wise arithmetic:

### Cross-verification: `combined_kb.json` vs `FEE_GROUP_MAP`

| Group | First Sem | Per Sem (x6) | Eighth Sem | Calculated Total | FEE_GROUP_MAP Total | Match? |
|-------|-----------|-------------|------------|-----------------|-------------------|--------|
| CSE/IT/ECE | 99,225 | 73,925 | 74,925 | **6,17,700** | 6,17,700 | ✅ |
| EE/AIML/DS/CY/CSD | 92,900 | 67,600 | 68,600 | **5,67,100** | 5,67,100 | ✅ |
| ME/CE | 75,650 | 50,350 | 51,350 | **4,29,100** | 4,29,100 | ✅ |

**Verification:** CSE = 99225 + 73925*6 + 74925 = 617700 ✅  
All three branch groups are internally consistent between `combined_kb.json` and `FEE_GROUP_MAP`.

### MBA fee (per_sem = 0 in code)
MBA has no per-semester breakdown — it's a 2-year program with different fee structure.  
`combined_kb.json` shows MBA: `{total: 419200, admission: 121400}` — no per_semester field.  
This confirms the code's `per_sem=0` for MBA is intentional.

### WBJEEB Affiliated PDF (older data)
A separate WBJEEB document (`https://wbjeeb.in/assets/ALPG/PVTENGG/BCROY.pdf`) shows a different fee structure:
- 1st Sem: 97,525 / 2nd-8th: ~72,425 each
- Total ~6,06,100
This appears to be from an earlier academic year (metadata shows PDF created 2013). **Not the current 2026-2030 rate.**

---

## 1. Where "Admission aur semester fee alag se hain" Is Generated

### Single source of truth: `_lang_fee_response()`

**File:** `backend/app/services/llm/groq_service.py:4172-4191`

When `fee_type == "total"`, this function always appends the "alag se" (separate) clause:

| Language | Line | Output |
|----------|------|--------|
| Hindi | 4180 | `"{dept} ka total fee {amount} hai. Admission aur semester fee alag se hain."` |
| Bengali | 4186 | `"{dept} এর মোট ফি {amount}। ভর্তি এবং সেমিস্টার ফি আলাদা।"` |
| English | 4191 | `"The total fee for {dept} is {amount}. Admission and semester fees are separate."` |

### Trigger paths (2 callers):

**Path A — `_structured_lookup()` fee handler, fall-through case (line 3069):**
```python
# groq_service.py:3051-3069
fee_intent = re.search(r"\b(fee|fees|total\s*fee|semester\s*fee|admission\s*fee|course\s*fee)\b", q)
if fee_intent:
    ...
    if re.search(r"\bsemester\s*fee\b|\bper\s*semester\b|\bsem\s*fee\b", q):
        return self._lang_fee_response(lang, "semester", dept_name, per_sem, 0, 0)
    if re.search(r"\badmission\s*fee\b", q):
        return self._lang_fee_response(lang, "admission", dept_name, 0, admission, 0)
    # ⚠️ FALL-THROUGH (total fee query, or just "fee" without qualifier):
    return self._lang_fee_response(lang, "total", dept_name, total, 0, 0)
```

Note: `per_sem` and `admission` are passed as `0` to `_lang_fee_response` for the "total" case, even though `FEE_GROUP_MAP` has the actual values. The function ignores these params for `fee_type == "total"` anyway.

**Path B — `_structured_lookup()` semester handler, per_sem=0 fallback (line 3065-3066):**
```python
# Only for departments with per_sem=0 (MBA: 48600 → wait, MBA has per_sem=0?)
# FEE_GROUP_MAP: "MBA": (419200, 121400, 0)
if per_sem > 0:
    return self._lang_fee_response(lang, "semester", dept_name, per_sem, 0, 0)
# ⚠️ If per_sem == 0 (MBA), falls back to "total" response with "alag se":
return self._lang_fee_response(lang, "total", dept_name, total, 0, 0)
```

---

## 2. What the Knowledge Base Stores

### 2a. `FEE_GROUP_MAP` (hardcoded dict) — `groq_service.py:697-712`

The **primary fee data source** for deterministic responses:

| Dept | Total Fee | Admission Fee | Per Semester |
|------|-----------|---------------|-------------|
| CSE | 6,17,700 | 99,225 | 73,925 |
| IT | 6,17,700 | 99,225 | 73,925 |
| ECE | 6,17,700 | 99,225 | 73,925 |
| EE | 5,67,100 | 92,900 | 67,600 |
| AIML | 5,67,100 | 92,900 | 67,600 |
| DS | 5,67,100 | 92,900 | 67,600 |
| CY | 5,67,100 | 92,900 | 67,600 |
| CSD | 5,67,100 | 92,900 | 67,600 |
| ME | 4,29,100 | 75,650 | 50,350 |
| CE | 4,29,100 | 75,650 | 50,350 |
| MBA | 4,19,200 | 1,21,400 | **0** |
| MCA | 2,14,600 | 67,800 | 48,600 |

### 2b. `backend/data/knowledge_base/combined_kb.json` — `fees_summary`

Contains extended data NOT used by the deterministic fee handler:
- Semester-wise breakdowns (`semester_wise_cse_it_ece`, `semester_wise_ee_group`, `semester_wise_me_ce`)
  - `first` semester total (includes admission + caution deposit + library + tuition)
  - `per_semester` amount (semesters 2-7)
  - `eighth` semester amount (final semester)
- Payment modes, refund policy, installments

This data is only accessible via the LLM tool path (not deterministic handler).

### 2c. `backend/data/canonical/canonical_kb.json`

Has `fees: {}` (empty). The `fees` key exists but contains no data.

### 2d. `backend/data/knowledge_base/topics/fees.md`

Markdown reference document with fee tables. Used only for LLM context, not deterministic lookup.

---

## 3. The "Alag Se" Problem

### Current behavior for "total fee" / "fee" query:
```
"AIML ka total fee ₹5,67,100 hai. Admission aur semester fee alag se hain."
```

### Why it's misleading:
- **Factually correct**: The total fee IS composed of admission + semester components that are listed separately in the fee structure.
- **User interpretation risk**: "Alag se hain" (are separate) implies additional charges beyond the stated total, creating a contradiction: "If the total is 5,67,100 AND admission AND semester are separate, how much do I actually pay?"

### The data exists to do better:
`FEE_GROUP_MAP` already has all three values. The `_calculate_total_fees()` method (line 3844-3853) already demonstrates the correct wording — but it's **dead code** (never called in the production path):

```python
def _calculate_total_fees(self, dept_code: str, lang: str) -> str | None:
    if dept_code.upper() in FEE_GROUP_MAP:
        total, admission, per_sem = FEE_GROUP_MAP[dept_code.upper()]
        return (
            f"The total fee for {dept_code.upper()} is "
            f"{self._format_inr(total, lang)}. "
            f"This includes an admission fee of {self._format_inr(admission, lang)} "
            f"and per semester fee of {self._format_inr(per_sem, lang)}."
        )
```

---

## 4. Admission Fee Handler Audit

### Current behavior (line 3067-3068):
```python
if re.search(r"\badmission\s*fee\b", q):
    return self._lang_fee_response(lang, "admission", dept_name, 0, admission, 0)
```

This correctly returns the admission fee value from `FEE_GROUP_MAP`:

| Language | Output |
|----------|--------|
| Hindi | `"{dept} ka admission fee ₹{amount} hai. Semester fee alag hai."` |
| Bengali | `"{dept} এর ভর্তি ফি {amount}। সেমিস্টার ফি আলাদা।"` |
| English | `"The admission fee for {dept} is ₹{amount}. Semester fee is separate."` |

**Potential issue:** The admission handler still says "Semester fee alag hai" even when the user only asked for admission fee. This could be interpreted as "you also need to pay semester fee separately on top of this admission fee."

### Admission intent classification check (line 2948):
```python
r"\b(admission\s*(process|procedure|criteria|requirements?)|...)\b"
```
- "admission fee" does NOT match this pattern (requires "process", "procedure", etc. after "admission")
- So the admission_general handler does NOT steal admission_fee queries
- ✅ No routing conflict between admission_general and fee handler

### Admission intent classification check (line 2288):
```python
if re.search(r"\b(fee|fees|total\s*fee|semester\s*fee|admission\s*fee|course\s*fee)\b", q):
    return "fee"
```
- "admission fee for CSE" → classified as `"fee"` intent
- ✅ Correctly classified

---

## 5. Complete Pipeline Flow

```
User query
    │
    ▼
generate_response() [line 4218]
    │
    ├── normalization / STT recovery
    ├── yes/no handling
    ├── greeting detection [line 4415]
    ├── out-of-domain detection [line 4444]
    ├── repeat intent [line 4471]
    │
    ▼
_structured_lookup() [line 4507]  ← DETERMINISTIC HANDLERS
    │
    ├── principal / vice_principal [line 2810-2833]
    ├── negativity/complaint [line 2835]
    ├── age limit [line 2904]
    ├── safety / branch change [line 2930]
    ├── available branches [line 2939]
    ├── admission_general [line 2948]
    ├── installment [line 2972]
    ├── hostel [line 2995]
    ├── FEES (line 3051)  ← ⭐ FEE HANDLER
    │   ├── semester fee → _lang_fee_response("semester")
    │   ├── admission fee → _lang_fee_response("admission")
    │   └── total fee / fallback → _lang_fee_response("total")  ← "alag se"
    ├── academic failure [line 3101]
    ├── HOD [line 3127]
    ├── principal (detail) [line 3168]
    ├── seat/intake [line 3210]
    └── placement [line 3300]
    │
    if NOT matched by any handler:
    ▼
_call_llm_with_tools() [line 4547]  ← LLM + TOOL CALLING
    │
    └── get_fees tool (line 893) — LLM may call this if it decides to
```

---

## 6. Summary of Issues Found

| # | Issue | Location | Severity |
|---|-------|----------|----------|
| 1 | "Alag se" wording implies extra payment beyond total fee | `_lang_fee_response()` L4180/4186/4191 | **HIGH** |
| 2 | Dead code `_calculate_total_fees()` has correct "includes" wording but unused | L3844-3853 | **MEDIUM** |
| 3 | Admission fee response appends "semester fee alag hai" creating same implication | L4179/4185/4190 | **LOW** |
| 4 | `per_sem` and `admission` params passed as 0 for "total" response despite being available in `FEE_GROUP_MAP` | L3069 | **LOW** |
| 5 | Semester fee for MBA (per_sem=0) falls through to "total" response with wrong semantics | L3063-3066 | **LOW** |
| 6 | `_calculate_total_fees`, `_calculate_semester_fees`, `_detect_on_topic_arithmetic` are unreachable dead code | L3844-3904 | **INFO** |
| 7 | `canonical_kb.json` has empty `fees: {}` — redundant key | — | **INFO** |
| 8 | Combined KB has detailed semester-wise fee breakdown but LLM tool `get_fees` only returns branch totals | L893-906 | **MEDIUM** |
| 9 | The LLM `get_fees` tool (line 893) says "Returns semester fees and total fees" but only has `branch` param — no implementation detail | L893-906 | **LOW** |

---

## 7. Recommended Fixes (code unchanged per instructions)

### Fix 1 (P0): Change "alag se" to "includes" wording for total fee
In `_lang_fee_response()` (L4180, L4186, L4191):

Replace:
- Hindi: "Admission aur semester fee alag se hain."
- Bengali: "ভর্তি এবং সেমিস্টার ফি আলাদা।"
- English: "Admission and semester fees are separate."

With version that incorporates the actual breakdown:
- Hindi: "Isme admission fee ₹X aur semester fee ₹Y shamil hai."
- Bengali: "এর মধ্যে ভর্তি ফি ₹X এবং সেমিস্টার ফি ₹Y অন্তর্ভুক্ত।"
- English: "This includes an admission fee of ₹X and per semester fee of ₹Y."

**Required data:** The function already receives `admission` and `per_sem` parameters — just needs to use them instead of hardcoding 0.

### Fix 2 (P1): Use `_calculate_total_fees()` instead of `_lang_fee_response()` for total
Replace the fallthrough path at L3069:
```python
return self._lang_fee_response(lang, "total", dept_name, total, 0, 0)
```
With a call to a method that explains the composition.

### Fix 3 (P2): Admission fee response should not mention semester fee
In `_lang_fee_response()` admission branch, remove the trailing "Semester fee alag hai" / equivalent. If user asked for admission fee, just give the admission fee value.

### Fix 4 (P3): Remove dead code or wire it into the handler chain
`_calculate_total_fees`, `_calculate_semester_fees`, and `_detect_on_topic_arithmetic` are defined but never called from production code. Either remove them or integrate into `_structured_lookup`.

### Fix 5 (P3): Add MBA semester handling
MBA has `per_sem=0`. The current code falls through to "total" response. Since MBA is a 2-year program with no per-semester breakdown, it should have a custom message clarifying this.
