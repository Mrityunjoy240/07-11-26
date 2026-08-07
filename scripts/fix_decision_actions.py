#!/usr/bin/env python3
"""Find and fix non-standard decision actions in benchmark conversations."""
import json
from pathlib import Path

# Actions the decision engine can produce
STANDARD_ACTIONS = {
    "collect_profile", "encourage_and_collect_profile", "recommend_branches",
    "provide_admission_info", "provide_fee_info", "provide_placement_info",
    "provide_hostel_info", "provide_scholarship_info", "provide_career_guidance",
    "provide_counseling_schedule", "escalate_to_human", "explain_management_quota_policy",
    "provide_grievance_process", "provide_transfer_info", "provide_nri_admission_info",
    "provide_branch_guidance", "guide_nri_application", "provide_sports_info",
    "provide_distance_ed_info", "provide_lateral_entry_info",
    "provide_sports_quota_info",  # confirmed pipeline produces this
    "clarify",  # confirmed pipeline produces this
}

# Mapping of non-standard -> standard actions
ACTION_FIXES = {
    "provide_branch_guidance": "recommend_branches",
    "guide_nri_application": "provide_nri_admission_info",
    "provide_nri_info": "provide_nri_admission_info",
    "provide_management_info": "explain_management_quota_policy",
    "provide_transfer_guidance": "provide_transfer_info",
    "provide_grievance_info": "provide_grievance_process",
    "provide_lateral_info": "provide_transfer_info",
    "confirm_lateral_eligibility": "clarify",
    "provide_fee_installment_info": "provide_fee_info",
    "investigate_scholarship_renewal": "provide_scholarship_info",
    "guide_sports_quota_application": "provide_sports_quota_info",
}

for version_dir in sorted(Path("data/benchmark").glob("v*")):
    if not version_dir.is_dir():
        continue
    for f in sorted(version_dir.glob("*.json")):
        data = json.loads(f.read_text())
        if not isinstance(data, dict) or "id" not in data:
            continue

        changed = False
        for i, turn in enumerate(data.get("turns", [])):
            d = turn.get("expected", {}).get("decision", {})
            action = d.get("action", "")
            if action and action not in STANDARD_ACTIONS:
                fix = ACTION_FIXES.get(action)
                if fix:
                    print(f"  {data['id']} T{i+1}: '{action}' -> '{fix}'")
                    d["action"] = fix
                    changed = True
                else:
                    print(f"  {data['id']} T{i+1}: UNKNOWN action '{action}' — needs manual fix")

        if changed:
            f.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            print(f"    -> Updated {f.name}")
