from src.brain.interfaces import BrainQuery, PolicyResult

SCHOLARSHIPS: list[dict] = [
    {
        "name": "Merit-cum-Means",
        "criteria": "Family income < ₹2.5L/year, 75%+ in board",
        "amount": "Full tuition waiver",
    },
    {
        "name": "SC/ST Scholarship",
        "criteria": "SC/ST category, 60%+ in board",
        "amount": "Full tuition + ₹500/month stipend",
    },
    {
        "name": "OBC Scholarship",
        "criteria": "OBC category, family income < ₹1L/year",
        "amount": "50% tuition waiver",
    },
    {
        "name": "Sports Quota",
        "criteria": "State/national level participation",
        "amount": "Up to 50% tuition waiver",
    },
    {
        "name": "Girls Scholarship",
        "criteria": "Female student, 70%+ in board",
        "amount": "₹10,000/year",
    },
]


class ScholarshipPolicy:
    def evaluate(self, query: BrainQuery) -> PolicyResult:
        applicable: list[dict] = []
        for s in SCHOLARSHIPS:
            name = s["name"].lower()
            cat = query.category.lower()
            if "sc/st" in name and cat in ("sc", "st"):
                applicable.append(s)
            elif "obc" in name and cat == "obc":
                applicable.append(s)
            elif "merit" in name or "girls" in name or "sports" in name:
                applicable.append(s)

        if not applicable:
            applicable = SCHOLARSHIPS

        lines = [f"{s['name']}: {s['amount']} ({s['criteria']})" for s in applicable]
        return PolicyResult(
            applicable=True,
            confidence=0.8,
            details=" | ".join(lines) if lines else "No scholarships found",
            data={"scholarships": applicable},
        )
