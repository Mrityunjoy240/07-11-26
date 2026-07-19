from src.brain.interfaces import BrainQuery, PolicyResult

_FEE_STRUCTURE: dict[str, dict] = {
    "general": {
        "tuition_per_year": 85000,
        "development_fee": 15000,
        "other_fees": 10000,
        "total_per_year": 110000,
    },
    "obc": {
        "tuition_per_year": 45000,
        "development_fee": 10000,
        "other_fees": 10000,
        "total_per_year": 65000,
    },
    "sc": {
        "tuition_per_year": 5000,
        "development_fee": 5000,
        "other_fees": 10000,
        "total_per_year": 20000,
    },
    "st": {
        "tuition_per_year": 5000,
        "development_fee": 5000,
        "other_fees": 10000,
        "total_per_year": 20000,
    },
}


class FeesPolicy:
    def evaluate(self, query: BrainQuery) -> PolicyResult:
        cat = query.category.lower().replace("ur", "general").replace(
            "unreserved", "general"
        ).replace("gen", "general")
        cat = cat if cat in _FEE_STRUCTURE else "general"
        fee = _FEE_STRUCTURE[cat]
        return PolicyResult(
            applicable=True,
            confidence=0.9,
            details=(
                f"Tuition: ₹{fee['tuition_per_year']:,}/year | "
                f"Total: ₹{fee['total_per_year']:,}/year (approx)"
            ),
            data=fee,
        )
