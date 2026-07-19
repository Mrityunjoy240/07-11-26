from src.brain.interfaces import BrainQuery, PolicyResult

# illustrative placement data — sourced from NIRF / college reports
_BRANCH_PLACEMENTS: dict[str, dict] = {
    "CSE": {"avg_package": 12.5, "highest": 45, "placement_pct": 92},
    "AIML": {"avg_package": 11.0, "highest": 40, "placement_pct": 90},
    "IT": {"avg_package": 10.0, "highest": 35, "placement_pct": 88},
    "ECE": {"avg_package": 8.5, "highest": 30, "placement_pct": 82},
    "EE": {"avg_package": 7.5, "highest": 28, "placement_pct": 78},
    "ME": {"avg_package": 6.5, "highest": 22, "placement_pct": 72},
    "CE": {"avg_package": 6.0, "highest": 20, "placement_pct": 68},
}


class PlacementPolicy:
    def evaluate(self, query: BrainQuery) -> PolicyResult:
        branch = query.interest.upper() if query.interest else ""
        data = _BRANCH_PLACEMENTS.get(branch)
        if data:
            return PolicyResult(
                applicable=True,
                confidence=0.85,
                details=(
                    f"{branch}: Avg ₹{data['avg_package']}L, "
                    f"Highest ₹{data['highest']}L, "
                    f"{data['placement_pct']}% placed"
                ),
                data=data,
            )

        # no specific branch — return aggregate summary
        return PolicyResult(
            applicable=True,
            confidence=0.6,
            details=(
                "Placement data available for CSE, AIML, IT, ECE, EE, ME, CE. "
                "Specify your branch of interest for detailed information."
            ),
            data={"branches": list(_BRANCH_PLACEMENTS.keys())},
        )
