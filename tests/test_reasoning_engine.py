import pytest

from src.conversation.state import ConversationState
from src.reasoning.engine import ReasoningEngine
from src.understanding.models import (
    ConversationSignals,
    UnderstandingIntent,
    UnderstandingResult,
)
from src.understanding.profile import StudentProfile


@pytest.fixture
def engine():
    return ReasoningEngine()


@pytest.fixture
def empty_understanding():
    return UnderstandingResult(text="")


@pytest.fixture
def rank_understanding():
    p = StudentProfile()
    p.academic.rank = 48000
    p.academic.pcm_percentage = 85.0
    p.academic.board = "WBCHSE"
    return UnderstandingResult(
        text="my rank is 48000 and I have 85 PCM from WBCHSE",
        intent=UnderstandingIntent(primary="admission", confidence=0.8),
        profile=p,
        confidence=0.85,
    )


class TestStageDetection:
    def test_initial_stage_is_discovery(self, engine: ReasoningEngine, empty_understanding: UnderstandingResult):
        result = engine.reason(empty_understanding)
        assert result.student_stage == "discovery"

    def test_still_discovery_without_interest(self, engine: ReasoningEngine, rank_understanding: UnderstandingResult):
        result = engine.reason(rank_understanding)
        assert result.student_stage == "discovery"

    def test_evaluation_with_rank_pcm_and_interest(self, engine: ReasoningEngine):
        p = StudentProfile()
        p.academic.rank = 48000
        p.academic.pcm_percentage = 85.0
        p.career.interest = "CSE"
        understanding = UnderstandingResult(
            text="my rank is 48000, 85 PCM, interested in CSE",
            intent=UnderstandingIntent(primary="admission", confidence=0.8),
            profile=p,
            confidence=0.85,
        )
        result = engine.reason(understanding)
        assert result.student_stage == "evaluation"

    def test_evaluation_from_state(self, engine: ReasoningEngine, empty_understanding: UnderstandingResult):
        state = ConversationState(
            session_id="test",
            profile={"rank": 48000, "pcm_percentage": 85, "interest": "CSE"},
            history=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}] * 3,
        )
        result = engine.reason(empty_understanding, state)
        assert result.student_stage == "evaluation"

    def test_discovery_with_little_history(self, engine: ReasoningEngine):
        understanding = UnderstandingResult(
            text="hello",
            intent=UnderstandingIntent(primary="greeting", confidence=0.9),
        )
        state = ConversationState(
            session_id="test",
            history=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        )
        result = engine.reason(understanding, state)
        assert result.student_stage == "discovery"


class TestProfileCompleteness:
    def test_zero_when_empty(self, engine: ReasoningEngine, empty_understanding: UnderstandingResult):
        result = engine.reason(empty_understanding)
        assert result.profile_completeness == 0.0

    def test_partial_with_rank(self, engine: ReasoningEngine, rank_understanding: UnderstandingResult):
        result = engine.reason(rank_understanding)
        assert 0.0 < result.profile_completeness < 1.0


class TestEligibility:
    def test_unknown_when_no_data(self, engine: ReasoningEngine, empty_understanding: UnderstandingResult):
        result = engine.reason(empty_understanding)
        assert result.eligibility.likely is False
        assert result.eligibility.confidence == 0.0

    def test_likely_for_good_rank(self, engine: ReasoningEngine, rank_understanding: UnderstandingResult):
        result = engine.reason(rank_understanding)
        assert result.eligibility.likely is True
        assert len(result.eligibility.branches) >= 1
        assert result.eligibility.confidence > 0

    def test_moderate_rank(self, engine: ReasoningEngine):
        p = StudentProfile()
        p.academic.rank = 80000
        understanding = UnderstandingResult(
            text="my rank is 80000",
            profile=p,
        )
        result = engine.reason(understanding)
        assert result.eligibility.likely is True
        assert "ME" in result.eligibility.branches or "CE" in result.eligibility.branches


class TestProblemIdentification:
    def test_needs_profile_initial(self, engine: ReasoningEngine, empty_understanding: UnderstandingResult):
        result = engine.reason(empty_understanding)
        assert result.current_problem == "needs_profile_initial"

    def test_needs_fee_information(self, engine: ReasoningEngine):
        understanding = UnderstandingResult(
            text="what are the fees",
            intent=UnderstandingIntent(primary="fee", confidence=0.8),
        )
        result = engine.reason(understanding)
        assert result.current_problem == "needs_fee_information"

    def test_needs_reassurance_for_anxious(self, engine: ReasoningEngine):
        understanding = UnderstandingResult(
            text="I am very worried",
            signals=ConversationSignals(anxiety=0.8),
        )
        result = engine.reason(understanding)
        assert result.current_problem == "needs_reassurance"


class TestRisksAndOpportunities:
    def test_risk_from_anxiety(self, engine: ReasoningEngine):
        understanding = UnderstandingResult(
            text="worried",
            signals=ConversationSignals(anxiety=0.7),
        )
        result = engine.reason(understanding)
        assert "student_shows_anxiety" in result.risks

    def test_opportunity_from_rank(self, engine: ReasoningEngine, rank_understanding: UnderstandingResult):
        result = engine.reason(rank_understanding)
        assert "competitive_rank" in result.opportunities


class TestConfidence:
    def test_zero_when_empty(self, engine: ReasoningEngine, empty_understanding: UnderstandingResult):
        result = engine.reason(empty_understanding)
        assert result.confidence == 0.0

    def test_nonzero_with_data(self, engine: ReasoningEngine, rank_understanding: UnderstandingResult):
        result = engine.reason(rank_understanding)
        assert result.confidence > 0
