#!/usr/bin/env python3
"""Generate .md files from knowledge_base.json (topics + departments)."""

import json
import sys
from pathlib import Path

KB_PATH = Path("backend/data/knowledge_base.json")
TOPICS_DIR = Path("backend/data/knowledge_base/topics")
DEPTS_DIR = Path("backend/data/knowledge_base/departments")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_md(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Written: {path}")


def fmt(val):
    if isinstance(val, bool):
        return "Yes" if val else "No"
    if val is None:
        return "N/A"
    return str(val)


def generate_college(kb):
    c = kb["college"]
    lines = [
        f"# {c['name']} ({c['short_name']})",
        "",
        "## College Overview",
        "",
        f"**{c['name']}** is a {'private' if 'Private' in c.get('type', '') else ''} engineering college located in Durgapur, West Bengal. Established in **{c['established']}**.",
        "",
        "## Key Facts",
        "",
        "| Attribute | Details |",
        "|-----------|---------|",
        f"| **Established** | {c['established']} |",
        f"| **Location** | Durgapur, West Bengal |",
        f"| **Campus Area** | {c.get('campus_size_acres', '')} acres |",
        f"| **Affiliation** | {c['affiliation']} |",
        f"| **Autonomous** | {c.get('autonomous', '')} |",
        f"| **Accreditation** | NAAC {c.get('naac', {}).get('grade', '')} |",
        f"| **Approval** | {c.get('approved_by', '')} |",
        f"| **NBA Programs** | {', '.join(c.get('nba_programs', []))} |",
        f"| **NIRF Ranking** | {c.get('nirf', '')} |",
        f"| **AICTE IDEA Lab Rank** | {c.get('aicte_idea_lab_rank', '')} |",
        "",
        "## Contact Information",
        "",
        f"- **Address**: {c['address']}",
        f"- **Phone**: {', '.join(c.get('phones', []))}",
        f"- **Mobile**: {c.get('mobile', '')}",
        f"- **Email**: {c['email']}",
        f"- **Website**: {c['website']}",
        f"- **Office Hours**: {c.get('timings', '')}",
        "",
    ]

    if "why_bcrec" in c:
        lines += [
            "## Why Choose BCREC?",
            "",
            c["why_bcrec"]["en"],
            "",
        ]

    if "alumni" in c:
        lines += [
            "## Alumni",
            "",
            c["alumni"]["en"],
            "",
        ]

    return "\n".join(lines) + "\n"


def generate_admissions(kb):
    a = kb["admission"]
    lines = [
        "# Admission at BCREC",
        "",
        "## Eligibility",
        "",
        f"- **B.Tech**: {a.get('eligibility', {}).get('btech', '')}",
        f"- **Entrance Exams**: {a.get('eligibility', {}).get('entrance', '')}",
        "",
        "## Seat Distribution",
        "",
        "| Source | Percentage |",
        "|--------|-----------|",
        f"| WBJEE | {a.get('seat_distribution', {}).get('wbjee', '')} |",
        f"| JEE Main | {a.get('seat_distribution', {}).get('jee_main', '')} |",
        f"| Management Quota | {a.get('seat_distribution', {}).get('management', '')} |",
        "",
        f"- **Lateral Entry**: {a.get('lateral_entry', '')}",
        f"- **Spot Round**: {a.get('spot_round', '')}",
        f"- **Counseling**: {a.get('counseling', '')}",
        f"- **Application Portal**: {a.get('portal', '')}",
        "",
    ]

    if "age_limit" in a:
        lines += ["## Age Limit", "", a["age_limit"]["en"], ""]

    if "nri_quota" in a:
        nri = a["nri_quota"]
        lines += [
            "## NRI Quota",
            "",
            f"- **Seats**: {nri.get('seats', '')}",
            f"- **Fee Range**: {nri.get('fee_range', '')}",
            f"- **Contact**: {nri.get('contact', '')}",
            "",
        ]

    return "\n".join(lines) + "\n"


def generate_placements(kb):
    p = kb["placements"]
    lines = [
        "# Placements at BCREC",
        "",
        "## Placement Highlights",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| **Overall Placement Rate (2025)** | {p.get('overall_rate_2025', '')} |",
        f"| **CSE Placement Rate (2025)** | {p.get('cse_rate_2025', '')} |",
        f"| **Rate (2023)** | {p.get('rate_2023', '')} |",
        f"| **Rate (2024)** | {p.get('rate_2024', '')} |",
        f"| **Highest Package** | Rs. {p.get('highest_package', {}).get('amount', '')} LPA |",
        f"| **Median Package** | {p.get('median_package', '')} |",
        f"| **Average Package** | {p.get('average_package', '')} |",
        f"| **Companies Visited (2025)** | {p.get('companies_visited_2025', '')} |",
        f"| **Students Placed (2025)** | {p.get('students_placed_2025', '')} |",
        "",
        "## Top Recruiters",
        "",
    ]

    if "top_recruiters" in p:
        for r in p["top_recruiters"]:
            lines.append(f"- {r}")
        lines.append("")

    if "internship" in p:
        lines += [
            "## Internships",
            "",
            f"Internships are available. Top partners: {', '.join(p['internship'].get('top_partners', []))}.",
            "",
        ]

    if "training_cell" in p:
        lines += [
            "## Training & Placement Cell",
            "",
            f"The {p['training_cell']['name']} provides {', '.join(p['training_cell'].get('programs', []))} training. Preparation starts from {p['training_cell'].get('starts_from', '')}.",
            "",
        ]

    return "\n".join(lines) + "\n"


def generate_fees(kb):
    f = kb["fees_summary"]
    lines = [
        "# Fee Structure at BCREC",
        "",
        "## B.Tech Fees",
        "",
        "| Branch Group | Total Fee | Admission Fee | Per Semester |",
        "|-------------|-----------|---------------|-------------|",
    ]
    for group_key, group_label in [
        ("btech_cse_it_ece", "CSE, IT, ECE"),
        ("btech_ee_aiml_ds_cy_csd", "EE, AIML, DS, CY, CSD"),
        ("btech_me_ce", "ME, CE"),
    ]:
        g = f.get(group_key, {})
        lines.append(
            f"| **{group_label}** | {g.get('total', '')} | {g.get('admission', '')} | {g.get('per_semester', '')} |"
        )

    lines += [
        "",
        "| Program | Total Fee | Admission Fee |",
        "|---------|-----------|---------------|",
        f"| **MBA** | {f.get('mba', {}).get('total', '')} | {f.get('mba', {}).get('admission', '')} |",
        f"| **MCA** | {f.get('mca', {}).get('total', '')} | {f.get('mca', {}).get('admission', '')} |",
        f"| **M.Tech** | {f.get('mtech', {}).get('total', '')} | {f.get('mtech', {}).get('admission', '')} |",
        "",
        "## Payment Modes",
        "",
        f"Accepted: {', '.join(f.get('payment_modes', []))}",
        f"Not accepted: {', '.join(f.get('not_accepted', []))}",
        "",
        f"## Hidden Charges",
        "",
        f"{f.get('hidden_charges', '')}",
        "",
        f"## Refund Policy",
        "",
        f"- **Guidelines**: {f.get('refund_policy', {}).get('guidelines', '')}",
        f"- **Within timeline**: {f.get('refund_policy', {}).get('within_timeline', '')}",
        f"- **Post-timeline (with replacement)**: {f.get('refund_policy', {}).get('post_timeline_with_replacement', '')}",
        f"- **Post-timeline (no replacement)**: {f.get('refund_policy', {}).get('post_timeline_no_replacement', '')}",
        "",
        f"## Installments",
        "",
        f"{f.get('installments', '')}",
        "",
    ]
    return "\n".join(lines) + "\n"


def generate_hostel(kb):
    h = kb["hostel"]
    lines = [
        "# BCREC Hostel Information",
        "",
        f"BCREC provides on-campus hostel facilities for both boys and girls. Hostel is {'compulsory' if h.get('compulsory') else 'optional'}.",
        "",
        "## General Information",
        "",
        f"- **Total Capacity**: {h.get('total_capacity', '')} students",
        f"- **Total Hostels**: {h.get('total_hostels', '')} ({h.get('boys_hostels', '')} Boys, {h.get('girls_hostels', '')} Girls)",
        f"- **Caution Money**: Rs. {h.get('caution_money', '')} (one-time, refundable)",
        "",
        "## Room Categories & Rent",
        "",
        "| Room Type | Rent (Per Semester) | Availability |",
        "|-----------|--------------------|--------------|",
    ]
    for room in h.get("room_types", []):
        lines.append(
            f"| **{room.get('type', '')}** | Rs. {room.get('rent_per_sem', '')} | {room.get('availability', '')} |"
        )

    if "mess" in h:
        m = h["mess"]
        lines += [
            "",
            "## Mess & Food",
            "",
            f"- **Monthly Charge**: Rs. {m.get('monthly_charge', '')} per month ({m.get('months_per_year', '')} months/year)",
            f"- **Meals Per Day**: {m.get('meals_per_day', '')}",
            f"- **Vegetarian**: {'Yes' if m.get('veg') else 'No'}",
            f"- **Non-Veg**: {m.get('non_veg', '')}",
            f"- **Veg Options**: {m.get('veg_options', '')}",
            "",
            "### Mess Timings",
            "",
        ]
        if "timings" in m:
            for meal, time in m["timings"].items():
                lines.append(f"- **{meal.capitalize()}**: {time}")
            lines.append("")

    lines += [
        "## Curfew & Rules",
        "",
        f"- **Boys Curfew**: {h.get('rules', {}).get('boys_curfew', '')}",
        f"- **Girls Curfew**: {h.get('rules', {}).get('girls_curfew', '')}",
        f"- **Guests**: {h.get('rules', {}).get('guests', '')}",
        f"- **Sign-in/out**: {h.get('rules', {}).get('entry_exit', '')}",
        "",
        "## Contact",
        "",
        f"- **Helpline**: {h.get('contacts', {}).get('helpline', '')}",
        f"- **Emergency**: {h.get('contacts', {}).get('emergency', '')}",
        f"- **Women's Safety**: {h.get('contacts', {}).get('womens_safety', '')}",
        "",
    ]
    return "\n".join(lines) + "\n"


def generate_contacts(kb):
    c = kb["college"]
    p = kb["principal"]
    vp = kb["vice_principal"]
    lines = [
        "# Contact Information",
        "",
        "## College",
        "",
        f"- **Address**: {c['address']}",
        f"- **Phone**: {', '.join(c.get('phones', []))}",
        f"- **Mobile**: {c.get('mobile', '')}",
        f"- **Fax**: {', '.join(c.get('fax', []))}",
        f"- **Email**: {c['email']}",
        f"- **Website**: {c['website']}",
        f"- **Office Hours**: {c.get('timings', '')}",
        "",
        "## Principal",
        "",
        f"- **Name**: {p.get('name', '')}",
        f"- **Email**: {p.get('email', '')}",
        f"- **Phone**: {p.get('phone', '')}",
        "",
        "## Vice Principal",
        "",
        f"- **Name**: {vp.get('name', '')}",
        f"- **Email**: {vp.get('email', '')}",
        f"- **Phone**: {vp.get('phone', '')}",
        "",
    ]

    if "kolkata_office" in c:
        ko = c["kolkata_office"]
        lines += [
            "## Kolkata Office",
            "",
            f"- **Address**: {ko.get('address', '')}",
            f"- **Phones**: {', '.join(ko.get('phones', []))}",
            f"- **Emails**: {', '.join(ko.get('emails', []))}",
            "",
        ]

    adm = kb.get("admission", {})
    if "contacts" in adm:
        lines += ["## Admission Contacts", ""]
        for label, nums in adm["contacts"].items():
            if isinstance(nums, list):
                lines.append(f"- **{label.capitalize()}**: {', '.join(nums)}")
            else:
                lines.append(f"- **{label.capitalize()}**: {nums}")
        lines.append("")

    return "\n".join(lines) + "\n"


def generate_faculty(kb):
    ac = kb["academics"]
    depts = kb.get("departments", {})
    lines = [
        "# Faculty at BCREC",
        "",
        f"- **Total Faculty**: {ac.get('faculty', {}).get('total', '')}",
        f"- **Student-Teacher Ratio**: {ac.get('student_teacher_ratio', '')}",
        f"- **Teaching Methodology**: {ac.get('teaching_methodology', '')}",
        "",
        "## Department Heads",
        "",
        "| Department | HOD Name | Contact |",
        "|------------|----------|---------|",
    ]
    for code, dept in sorted(depts.items()):
        hod = dept.get("hod", {})
        name = hod.get("name", "")
        email = hod.get("email", "")
        mobile = hod.get("mobile", "")
        contact = email or mobile or ""
        lines.append(f"| **{code}** | {name} | {contact} |")

    lines.append("")

    if "teaching_quality" in ac:
        tq = ac["teaching_quality"]
        lines += [
            "## Teaching Quality",
            "",
            f"**Approach**: {tq.get('approach', '')}",
            "",
            "**Methods**:",
            "",
        ]
        for m in tq.get("methods", []):
            lines.append(f"- {m}")
        lines.append("")
        lines += [
            f"**Evaluation**: {tq.get('evaluation', '')}",
            "",
            f"**Support**: {tq.get('support', '')}",
            "",
            f"**Faculty Development**: {tq.get('faculty_development', '')}",
            "",
        ]

    return "\n".join(lines) + "\n"


def generate_departments_overview(kb):
    btech = kb.get("courses", {}).get("btech", {})
    lines = [
        "# Departments at BCREC",
        "",
        "## B.Tech Programs",
        "",
        "| Department | Full Name | Intake | Duration | NBA Accredited |",
        "|------------|-----------|--------|----------|---------------|",
    ]
    for code, dept in sorted(btech.items()):
        if not isinstance(dept, dict):
            continue
        lines.append(
            f"| **{code}** | {dept.get('full_name', '')} | {dept.get('intake', '')} | {dept.get('duration', '')} | {'Yes' if dept.get('nba_accredited') else 'No'} |"
        )

    lines += [
        "",
        "## Other Programs",
        "",
        "| Program | Intake | Duration |",
        "|---------|--------|----------|",
    ]
    courses = kb.get("courses", {})
    for prog in ["mba", "mca"]:
        p = courses.get(prog, {})
        if isinstance(p, dict):
            lines.append(
                f"| **{prog.upper()}** | {p.get('intake', '')} | {p.get('duration', '')} |"
            )

    mtech = courses.get("mtech", {})
    if isinstance(mtech, dict):
        mtech_progs = mtech.get("programs", [])
        if mtech_progs:
            lines += ["", "### M.Tech Programs", ""]
            for prog in mtech_progs:
                lines.append(f"- {prog}")
            lines.append("")
            lines += [
                f"- **Intake**: {mtech.get('intake', '')}",
                f"- **Duration**: {mtech.get('duration', '')}",
                f"- **Stipend**: {mtech.get('stipend', '')}",
                "",
            ]

    return "\n".join(lines) + "\n"


def generate_student_life(kb):
    sl = kb.get("student_life", {})
    lines = [
        "# Student Life at BCREC",
        "",
        f"{sl.get('description', '')}",
        "",
    ]

    if "tech_fest" in sl:
        tf = sl["tech_fest"]
        lines += [
            f"## Technical Fest",
            "",
            f"- **Name**: {tf.get('name', '')}",
            f"- **Month**: {tf.get('month', '')}",
            f"- **Latest**: {tf.get('latest', '')}",
            "",
        ]

    if "cultural_fest" in sl:
        cf = sl["cultural_fest"]
        lines += [
            f"## Cultural Fest",
            "",
            f"- **Name**: {cf.get('name', '')}",
            f"- **Month**: {cf.get('month', '')}",
            "",
        ]

    if "events" in sl:
        lines += ["## Events", ""]
        for ev in sl["events"]:
            name = ev.get("name", "")
            month = ev.get("month", "")
            etype = ev.get("type", "")
            details = f"{name}"
            if month:
                details += f" ({month})"
            if etype:
                details += f" - {etype}"
            lines.append(f"- {details}")
        lines.append("")

    if "clubs" in sl:
        lines += ["## Clubs & Societies", ""]
        for club in sl["clubs"]:
            lines.append(f"- {club}")
        lines.append("")

    if "gate_forum" in sl:
        lines += [
            "## GATE Forum",
            "",
            sl["gate_forum"]["en"],
            "",
        ]

    return "\n".join(lines) + "\n"


def generate_anti_ragging(kb):
    ar = kb.get("anti_ragging", {})
    lines = [
        "# Anti-Ragging Policy",
        "",
        f"BCREC has a **{ar.get('policy', '')}** policy against ragging.",
        "",
        "## Measures",
        "",
    ]
    for m in ar.get("measures", []):
        lines.append(f"- {m}")
    lines.append("")
    lines += [
        "## Reporting",
        "",
        f"{ar.get('reporting', '')}",
        "",
        f"**Women's Safety Helpline**: {ar.get('safety', '')}",
        "",
    ]
    return "\n".join(lines) + "\n"


TOPIC_GENERATORS = {
    "college": generate_college,
    "admissions": generate_admissions,
    "placements": generate_placements,
    "fees": generate_fees,
    "hostel": generate_hostel,
    "contacts": generate_contacts,
    "faculty": generate_faculty,
    "departments_overview": generate_departments_overview,
    "student_life": generate_student_life,
    "anti_ragging": generate_anti_ragging,
}

DEPT_FULL_NAMES = {
    "CSE": "Computer Science and Engineering",
    "IT": "Information Technology",
    "ECE": "Electronics and Communication Engineering",
    "EE": "Electrical Engineering",
    "ME": "Mechanical Engineering",
    "CE": "Civil Engineering",
    "CSD": "Computer Science and Design",
    "AIML": "CSE (Artificial Intelligence and Machine Learning)",
    "DS": "CSE (Data Science)",
    "CY": "CSE (Cyber Security)",
    "MBA": "Master of Business Administration",
    "MCA": "Master of Computer Applications",
}


def generate_department_md(code, dept_info, btech_info):
    hod = dept_info.get("hod", {})
    lines = [
        f"# {dept_info.get('full_name', DEPT_FULL_NAMES.get(code, code))}",
        "",
        "## Program Overview",
        "",
    ]

    if btech_info:
        lines += [
            f"**{btech_info.get('duration', '')}** program with an intake of **{btech_info.get('intake', '')}** students.",
            "",
            "## Key Details",
            "",
            "| Attribute | Value |",
            "|-----------|-------|",
            f"| **Duration** | {btech_info.get('duration', '')} |",
            f"| **Intake** | {btech_info.get('intake', '')} |",
            f"| **Established** | {btech_info.get('established', '')} |",
            f"| **NBA Accredited** | {'Yes' if btech_info.get('nba_accredited') else 'No'} |",
            "",
        ]
        fees = btech_info.get("fees", {})
        if fees:
            lines += [
                "## Fee Structure",
                "",
                f"- **Total Fee**: Rs. {fees.get('total', '')}",
                f"- **Admission Fee**: Rs. {fees.get('admission', '')}",
                "",
            ]

        placement = btech_info.get("placement", {})
        if placement:
            lines += [
                "## Placement Statistics",
                "",
            ]
            for key, label in [
                ("rate_2023_24", "Placement Rate (2023-24)"),
                ("rate_2024_25", "Placement Rate (2024-25)"),
                ("rate_2025_26", "Placement Rate (2025-26)"),
                ("min_lpa", "Minimum Package"),
                ("avg_lpa", "Average Package"),
                ("max_lpa", "Highest Package"),
            ]:
                val = placement.get(key, "")
                if val:
                    suffix = " LPA" if key.endswith("_lpa") else ""
                    lines.append(f"- **{label}**: {val}{suffix}")
            lines.append("")

        cutoff = btech_info.get("cutoff", {})
        if cutoff:
            lines += [
                "## WBJEE Cutoff",
                "",
            ]
            for year_key in ["2024", "2025", "2026_est"]:
                val = cutoff.get(year_key, "")
                if val:
                    label = year_key.replace("_est", " (Estimated)")
                    lines.append(f"- **{label}**: {val}")
            lines.append("")

    lines += [
        "## Contact",
        "",
        f"**Head of Department**: {hod.get('name', '')}",
    ]
    if hod.get("email"):
        lines.append(f"- Email: {hod['email']}")
    if hod.get("mobile"):
        lines.append(f"- Phone: {hod['mobile']}")
    lines.append("")

    return "\n".join(lines) + "\n"


def main():
    validate_only = "--validate" in sys.argv
    print("=" * 60)
    print("BCREC Markdown Generator")
    print("=" * 60)

    kb = load_json(KB_PATH)
    courses = kb.get("courses", {})
    btech = courses.get("btech", {})
    depts = kb.get("departments", {})

    if validate_only:
        print("\nValidation mode: checking all topics can be generated...")
        for name, gen in TOPIC_GENERATORS.items():
            try:
                gen(kb)
                print(f"  OK: {name}.md")
            except Exception as e:
                print(f"  ERROR: {name}.md - {e}")
        for code in sorted(depts.keys()):
            try:
                dept_info = depts.get(code, {})
                dept_info["full_name"] = dept_info.get(
                    "full_name",
                    btech.get(code, {}).get("full_name", DEPT_FULL_NAMES.get(code, code)),
                )
                generate_department_md(code, dept_info, btech.get(code, {}))
                print(f"  OK: departments/{code.lower()}.md")
            except Exception as e:
                print(f"  ERROR: departments/{code.lower()}.md - {e}")
        print("\nValidation passed.")
        return

    print(f"\nGenerating topic markdown files in {TOPICS_DIR}...")
    count = 0
    for name, gen in TOPIC_GENERATORS.items():
        content = gen(kb)
        path = TOPICS_DIR / f"{name}.md"
        save_md(path, content)
        count += 1
    print(f"  Generated {count} topic files.")

    print(f"\nGenerating department markdown files in {DEPTS_DIR}...")
    dcount = 0
    for code, dept_info in sorted(depts.items()):
        if not isinstance(dept_info, dict):
            continue
        dept_info["full_name"] = dept_info.get(
            "full_name",
            btech.get(code, {}).get("full_name", DEPT_FULL_NAMES.get(code, code)),
        )
        content = generate_department_md(code, dept_info, btech.get(code, {}))
        path = DEPTS_DIR / f"{code.lower()}.md"
        save_md(path, content)
        dcount += 1
    print(f"  Generated {dcount} department files.")

    print(f"\nDone. Generated {count + dcount} markdown files total.")


if __name__ == "__main__":
    main()
