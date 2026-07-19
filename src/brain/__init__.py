from src.brain.admission import AdmissionPolicy
from src.brain.fees import FeesPolicy
from src.brain.hostel import HostelPolicy
from src.brain.interfaces import BrainQuery, BrainResponse, PolicyResult
from src.brain.placement import PlacementPolicy
from src.brain.scholarship import ScholarshipPolicy


class CollegeBrain:
    VERSION = "v1"
    def __init__(
        self,
        admission: AdmissionPolicy | None = None,
        placement: PlacementPolicy | None = None,
        fees: FeesPolicy | None = None,
        hostel: HostelPolicy | None = None,
        scholarship: ScholarshipPolicy | None = None,
    ) -> None:
        self.admission = admission or AdmissionPolicy()
        self.placement = placement or PlacementPolicy()
        self.fees = fees or FeesPolicy()
        self.hostel = hostel or HostelPolicy()
        self.scholarship = scholarship or ScholarshipPolicy()

    def query(self, q: BrainQuery) -> BrainResponse:
        return BrainResponse(
            admission=self.admission.evaluate(q),
            placement=self.placement.evaluate(q),
            fees=self.fees.evaluate(q),
            hostel=self.hostel.evaluate(q),
            scholarship=self.scholarship.evaluate(q),
            confidence=self._overall_confidence(q),
        )

    def estimate_eligibility(
        self, rank: int | float | None = None,
        category: str = "general", pcm: float | None = None,
    ) -> PolicyResult:
        return self.admission.evaluate(
            BrainQuery(rank=rank, category=category, pcm_percentage=pcm)
        )

    @staticmethod
    def _overall_confidence(q: BrainQuery) -> float:
        score = 0.0
        if q.rank is not None:
            score += 0.4
        if q.pcm_percentage is not None:
            score += 0.2
        if q.category:
            score += 0.1
        if q.interest:
            score += 0.15
        if q.budget is not None:
            score += 0.15
        return min(1.0, score)
