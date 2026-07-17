"""
Verify canonical facts from college_facts.json

Run: cd backend && python3 tests/verify_facts.py
"""

import json
import os

# Load canonical facts
FACTS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'college_facts.json')
with open(FACTS_PATH) as f:
    FACTS = json.load(f)

print("=" * 60)
print("VERIFYING CANONICAL COLLEGE FACTS")
print("=" * 60)

errors = []

# 1. Fee Verification
print("\n1. FEE VERIFICATION")
print("-" * 40)

expected_fees = {
    "CSE/IT/ECE total": 617700,
    "EE/AIML/DS/CY/CSD total": 567100,
    "ME/CE total": 429100,
    "CSE first semester": 99225,
    "Hostel mess/month": 5500,
}

actual_fees = {
    "CSE/IT/ECE total": FACTS["fees"]["btech"]["group_a"]["total_4yr"],
    "EE/AIML/DS/CY/CSD total": FACTS["fees"]["btech"]["group_b"]["total_4yr"],
    "ME/CE total": FACTS["fees"]["btech"]["group_c"]["total_4yr"],
    "CSE first semester": FACTS["fees"]["btech"]["group_a"]["first_semester"],
    "Hostel mess/month": FACTS["fees"]["hostel"]["mess_charges_month"],
}

for key in expected_fees:
    expected = expected_fees[key]
    actual = actual_fees[key]
    status = "✓" if expected == actual else "✗"
    print(f"  {status} {key}: expected={expected}, actual={actual}")
    if expected != actual:
        errors.append(f"Fee mismatch: {key}")

# 2. Cutoff Verification
print("\n2. CUTOFF VERIFICATION")
print("-" * 40)

expected_cutoffs = {
    "CSE 2024": 16059,
    "CSE 2025": 67761,
    "AIML 2025": 78384,
    "IT 2025": 97611,
}

actual_cutoffs = {
    "CSE 2024": FACTS["cutoffs"]["2024"]["CSE"],
    "CSE 2025": FACTS["cutoffs"]["2025"]["CSE"],
    "AIML 2025": FACTS["cutoffs"]["2025"]["AIML"],
    "IT 2025": FACTS["cutoffs"]["2025"]["IT"],
}

for key in expected_cutoffs:
    expected = expected_cutoffs[key]
    actual = actual_cutoffs[key]
    status = "✓" if expected == actual else "✗"
    print(f"  {status} {key}: expected={expected}, actual={actual}")
    if expected != actual:
        errors.append(f"Cutoff mismatch: {key}")

# 3. Placement Verification
print("\n3. PLACEMENT VERIFICATION")
print("-" * 40)

expected_placement = {
    "Overall 2025": 91,
    "CSE 2025": 93.6,
    "Highest package": 7.0,
    "Median package": 4.25,
}

actual_placement = {
    "Overall 2025": FACTS["placements"]["overall_2025"],
    "CSE 2025": FACTS["placements"]["cse_2025"],
    "Highest package": FACTS["placements"]["highest_package_on_campus"],
    "Median package": FACTS["placements"]["median_package"],
}

for key in expected_placement:
    expected = expected_placement[key]
    actual = actual_placement[key]
    status = "✓" if expected == actual else "✗"
    print(f"  {status} {key}: expected={expected}, actual={actual}")
    if expected != actual:
        errors.append(f"Placement mismatch: {key}")

# 4. Identity Verification
print("\n4. IDENTITY VERIFICATION")
print("-" * 40)

identity_checks = [
    ("College name", FACTS["college"]["name"], "Dr. Bidhan Chandra Roy Engineering College"),
    ("Established", FACTS["college"]["established"], "August 2000"),
    ("NAAC grade", FACTS["accreditation"]["naac"]["grade"], "B+"),
    ("Principal", FACTS["leadership"]["principal"]["name"], "Dr. Sanjay S. Pawar"),
    ("Vice Principal", FACTS["leadership"]["vice_principal"]["name"], "Prof. (Dr.) K. M. Hossain"),
    ("Primary phone", FACTS["contacts"]["primary_phone"], "0343-2501353"),
    ("Email", FACTS["contacts"]["email"], "info@bcrec.ac.in"),
]

for label, actual, expected in identity_checks:
    status = "✓" if actual == expected else "✗"
    print(f"  {status} {label}: {actual}")
    if actual != expected:
        errors.append(f"Identity mismatch: {label}")

# 5. Department Verification
print("\n5. DEPARTMENT VERIFICATION")
print("-" * 40)

dept_checks = [
    ("CSE intake", FACTS["departments"]["CSE"]["intake"], 180),
    ("CSE HOD", FACTS["departments"]["CSE"]["hod"]["name"], "Dr. Pabitra Kumar Dey"),
    ("AIML intake", FACTS["departments"]["AIML"]["intake"], 60),
]

for label, actual, expected in dept_checks:
    status = "✓" if actual == expected else "✗"
    print(f"  {status} {label}: {actual}")
    if actual != expected:
        errors.append(f"Department mismatch: {label}")

# 6. Hostel Verification
print("\n6. HOSTEL VERIFICATION")
print("-" * 40)

hostel_checks = [
    ("Total hostels", FACTS["hostel"]["total_hostels"], 5),
    ("Total capacity", FACTS["hostel"]["total_capacity"], 1500),
    ("Boys hostels", FACTS["hostel"]["boys_hostels"], 3),
    ("Girls hostels", FACTS["hostel"]["girls_hostels"], 2),
]

for label, actual, expected in hostel_checks:
    status = "✓" if actual == expected else "✗"
    print(f"  {status} {label}: {actual}")
    if actual != expected:
        errors.append(f"Hostel mismatch: {label}")

# Summary
print("\n" + "=" * 60)
if errors:
    print(f"FAILED: {len(errors)} errors found")
    for e in errors:
        print(f"  - {e}")
else:
    print("ALL CHECKS PASSED ✓")
print("=" * 60)
