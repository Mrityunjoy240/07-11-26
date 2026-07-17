#!/usr/bin/env python3
"""
validate_kb.py — Validates knowledge_base.json (flat format)

Checks:
1. Valid JSON + required sections exist
2. No null values
3. Cross-field consistency (intakes, fees coverage, HOD coverage)
4. Report any data issues

Usage:
    python scripts/validate_kb.py                # Full validation
    python scripts/validate_kb.py --quiet        # Summary only
"""

import json
import sys
from pathlib import Path

KB_PATH = Path("backend/data/knowledge_base.json")


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {path}: {e}")
        sys.exit(1)


def check_schema(kb):
    errors = 0
    required = [
        "meta",
        "college",
        "principal",
        "courses",
        "admission",
        "infrastructure",
        "student_life",
        "placements",
        "hostel",
        "scholarships",
        "anti_ragging",
        "academics",
        "departments",
    ]
    for key in required:
        if key not in kb:
            print(f"  ERROR: Missing required section '{key}'")
            errors += 1
        elif not isinstance(kb[key], dict):
            print(f"  ERROR: Section '{key}' must be an object")
            errors += 1
    if errors == 0:
        print("  OK")
    return errors


def check_null_values(kb):
    errors = 0

    def _scan(obj, path=""):
        nonlocal errors
        if isinstance(obj, dict):
            for key, val in obj.items():
                if key.startswith("_"):
                    continue
                current = f"{path}.{key}" if path else key
                if val is None:
                    print(f"  ERROR: '{current}' is null")
                    errors += 1
                else:
                    _scan(val, current)
        elif isinstance(obj, list):
            for i, val in enumerate(obj):
                _scan(val, f"{path}[{i}]")

    _scan(kb)
    if errors == 0:
        print("  OK")
    return errors


def check_cross_field(kb, quiet=False):
    errors = 0
    warnings = 0

    courses = kb.get("courses", {})
    btech = courses.get("btech", {})

    for code, dept in btech.items():
        if not isinstance(dept, dict):
            continue
        if dept.get("intake") is None:
            warnings += 1
            if not quiet:
                print(f"  WARNING: '{code}' has no intake value")
        fees = dept.get("fees", {})
        if isinstance(fees, dict):
            if fees.get("total") is None:
                warnings += 1
                if not quiet:
                    print(f"  WARNING: '{code}' has no total fee")
            if fees.get("admission") is None:
                warnings += 1
                if not quiet:
                    print(f"  WARNING: '{code}' has no admission fee")

    depts = kb.get("departments", {})
    btech_codes = set(btech.keys())
    dept_codes = set(depts.keys())
    missing_depts = btech_codes - dept_codes
    extra_depts = dept_codes - btech_codes - {"MBA", "MCA"}
    if missing_depts and not quiet:
        print(f"  WARNING: No HOD defined for: {missing_depts}")
        warnings += 1
    if extra_depts and not quiet:
        print(f"  WARNING: HOD defined for no-course depts: {extra_depts}")
        warnings += 1

    if not quiet and errors == 0 and warnings == 0:
        print("  OK")

    return errors, warnings


def main():
    quiet = "--quiet" in sys.argv

    print("=" * 60)
    print("BCREC KB Validation")
    print("=" * 60)

    kb = load_json(KB_PATH)
    print(f"\nLoaded: {KB_PATH}")
    print(f"Size: {len(json.dumps(kb))} bytes")

    total_errors = 0
    total_warnings = 0

    print("\n[1/3] Schema structure check...")
    e = check_schema(kb)
    total_errors += e

    print("\n[2/3] Null value check...")
    e = check_null_values(kb)
    total_errors += e

    print("\n[3/3] Cross-field consistency check...")
    e, w = check_cross_field(kb, quiet)
    total_errors += e
    total_warnings += w

    print("\n" + "=" * 60)
    print(f"RESULTS: {total_errors} errors, {total_warnings} warnings")
    print("=" * 60)

    if total_errors > 0:
        print("VALIDATION FAILED")
        sys.exit(1)
    else:
        print("VALIDATION PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
