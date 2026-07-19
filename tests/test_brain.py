from src.brain import CollegeBrain
from src.brain.interfaces import BrainQuery, BrainResponse, PolicyResult


class TestCollegeBrain:
    def test_instantiate(self):
        brain = CollegeBrain()
        assert brain.admission is not None
        assert brain.placement is not None

    def test_query_returns_brain_response(self):
        brain = CollegeBrain()
        q = BrainQuery(rank=52000, interest="CSE")
        r = brain.query(q)
        assert isinstance(r, BrainResponse)
        assert r.admission is not None
        assert r.placement is not None

    def test_estimate_eligibility_low_rank(self):
        brain = CollegeBrain()
        r = brain.estimate_eligibility(rank=5000)
        assert isinstance(r, PolicyResult)
        assert r.applicable is True
        assert "CSE" in r.data["eligible_branches"]

    def test_estimate_eligibility_high_rank(self):
        brain = CollegeBrain()
        r = brain.estimate_eligibility(rank=250000)
        assert r.applicable is False

    def test_estimate_eligibility_no_rank(self):
        brain = CollegeBrain()
        r = brain.estimate_eligibility()
        assert r.applicable is False
        assert r.confidence == 0.0

    def test_estimate_eligibility_with_pcm_below_minimum(self):
        brain = CollegeBrain()
        r = brain.estimate_eligibility(rank=15000, pcm=40)
        assert r.confidence < 0.5
        assert "PCM below" in r.details

    def test_estimate_eligibility_obc_category(self):
        brain = CollegeBrain()
        r = brain.estimate_eligibility(rank=15000, category="obc")
        assert r.applicable is True
        assert "CSE" in r.data["eligible_branches"]

    def test_placement_specific_branch(self):
        brain = CollegeBrain()
        q = BrainQuery(interest="CSE")
        r = brain.placement.evaluate(q)
        assert r.applicable is True
        assert "Avg" in r.details

    def test_placement_generic(self):
        brain = CollegeBrain()
        q = BrainQuery()
        r = brain.placement.evaluate(q)
        assert r.applicable is True
        assert "branches" in r.data

    def test_fees_general(self):
        brain = CollegeBrain()
        q = BrainQuery(category="general")
        r = brain.fees.evaluate(q)
        assert r.applicable is True
        assert r.data["total_per_year"] > 0

    def test_fees_sc(self):
        brain = CollegeBrain()
        q = BrainQuery(category="sc")
        r = brain.fees.evaluate(q)
        assert r.data["total_per_year"] < 30000

    def test_hostel(self):
        brain = CollegeBrain()
        q = BrainQuery()
        r = brain.hostel.evaluate(q)
        assert r.applicable is True
        assert "hostel" in r.details.lower()
        assert r.data["boys_hostel"] is True
        assert r.data["girls_hostel"] is True

    def test_scholarship_sc_st(self):
        brain = CollegeBrain()
        q = BrainQuery(category="sc")
        r = brain.scholarship.evaluate(q)
        assert r.applicable is True
        assert any("SC/ST" in s["name"] for s in r.data["scholarships"])

    def test_scholarship_general(self):
        brain = CollegeBrain()
        q = BrainQuery(category="general")
        r = brain.scholarship.evaluate(q)
        assert r.applicable is True
        assert len(r.data["scholarships"]) > 0

    def test_overall_confidence_no_data(self):
        brain = CollegeBrain()
        q = BrainQuery(category="")
        assert brain._overall_confidence(q) == 0.0

    def test_overall_confidence_with_rank_and_interest(self):
        brain = CollegeBrain()
        q = BrainQuery(rank=50000, interest="CSE")
        assert brain._overall_confidence(q) > 0.5

    def test_admission_policy_category_normalization(self):
        brain = CollegeBrain()
        for alias in ("gen", "ur", "unreserved"):
            r = brain.admission.evaluate(BrainQuery(category=alias, rank=10000))
            assert r.applicable is True
