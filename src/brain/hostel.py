from src.brain.interfaces import BrainQuery, PolicyResult


class HostelPolicy:
    def evaluate(self, query: BrainQuery) -> PolicyResult:
        return PolicyResult(
            applicable=True,
            confidence=0.85,
            details=(
                "Hostel accommodation available for boys and girls. "
                "Separate hostels with mess, WiFi, 24/7 security. "
                "Fees: approx ₹60,000–80,000/year depending on room type."
            ),
            data={
                "boys_hostel": True,
                "girls_hostel": True,
                "fee_range": (60000, 80000),
                "amenities": ["mess", "wifi", "security", "common_room"],
            },
        )
