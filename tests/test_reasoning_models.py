from src.reasoning.models import EligibilityEstimate, ReasoningResult


def test_eligibility_estimate_defaults():
    e = EligibilityEstimate()
    assert e.likely is False
    assert e.branches == []
    assert e.confidence == 0.0
    assert e.note == ""


def test_eligibility_estimate_full():
    e = EligibilityEstimate(
        likely=True,
        branches=["CSE", "IT"],
        confidence=0.85,
        note="Strong rank",
    )
    assert e.likely is True
    assert len(e.branches) == 2
    assert e.confidence == 0.85


def test_reasoning_result_defaults():
    r = ReasoningResult()
    assert r.student_stage == "discovery"
    assert r.profile_completeness == 0.0
    assert r.unknowns == []
    assert r.risks == []
    assert r.opportunities == []
    assert r.knowledge_needed == []
    assert r.confidence == 0.0


def test_reasoning_result_full():
    r = ReasoningResult(
        student_stage="evaluation",
        profile_completeness=0.6,
        eligibility=EligibilityEstimate(likely=True, branches=["CSE"], confidence=0.7),
        current_problem="needs_branch_guidance",
        unknowns=["pcm_percentage"],
        risks=["student_shows_anxiety"],
        opportunities=["competitive_rank"],
        knowledge_needed=["fee_information"],
        confidence=0.72,
    )
    assert r.student_stage == "evaluation"
    assert r.eligibility.likely is True
    assert len(r.opportunities) == 1
