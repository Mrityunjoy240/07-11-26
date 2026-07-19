from src.brain import CollegeBrain
from src.brain.interfaces import Reason


class TestBrainExplainability:
    def test_admission_why_has_reasons(self):
        brain = CollegeBrain()
        r = brain.estimate_eligibility(rank=10000)
        assert len(r.why) > 0
        assert any(isinstance(x, Reason) for x in r.why)

    def test_admission_why_includes_rank_provided(self):
        brain = CollegeBrain()
        r = brain.estimate_eligibility(rank=5000)
        reasons = {x.condition for x in r.why}
        assert "rank_provided" in reasons

    def test_admission_why_includes_cutoff_checks(self):
        brain = CollegeBrain()
        r = brain.estimate_eligibility(rank=10000)
        cutoff_reasons = [x for x in r.why if x.condition.endswith("_cutoff")]
        assert len(cutoff_reasons) >= 3
        assert any("CSE" in x.condition for x in cutoff_reasons)

    def test_admission_why_pcm_check(self):
        brain = CollegeBrain()
        r = brain.estimate_eligibility(rank=10000, pcm=40)
        pcm_reason = next((x for x in r.why if x.condition == "pcm_minimum_met"), None)
        assert pcm_reason is not None
        assert pcm_reason.met is False

    def test_admission_why_pcm_check_passes(self):
        brain = CollegeBrain()
        r = brain.estimate_eligibility(rank=10000, pcm=75)
        pcm_reason = next((x for x in r.why if x.condition == "pcm_minimum_met"), None)
        assert pcm_reason is not None
        assert pcm_reason.met is True

    def test_no_rank_why(self):
        brain = CollegeBrain()
        r = brain.estimate_eligibility()
        assert len(r.why) == 1
        assert r.why[0].condition == "rank_provided"
        assert r.why[0].met is False

    def test_cutoff_reason_detail_contains_rank_and_cutoff(self):
        brain = CollegeBrain()
        r = brain.estimate_eligibility(rank=15000)
        cse_reason = next((x for x in r.why if x.condition == "CSE_cutoff"), None)
        assert cse_reason is not None
        assert "15000" in cse_reason.detail
