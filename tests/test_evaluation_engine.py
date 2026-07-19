from src.engines.interfaces import DecisionOutput, EvaluationInput
from src.evaluation.engine import EvaluationEngine


class TestEvaluationEngine:
    def test_completed_high_confidence(self):
        engine = EvaluationEngine()
        decision = DecisionOutput(action="recommend_branches", confidence=0.85)
        result = engine.process(EvaluationInput(decision=decision, outcome="completed"))
        assert result.correct is True
        assert result.confidence_adjustment > 0

    def test_abandoned(self):
        result = EvaluationEngine().process(EvaluationInput(outcome="abandoned"))
        assert result.correct is False
        assert result.follow_up_needed is True

    def test_escalation_appropriate(self):
        decision = DecisionOutput(action="reassure", escalate=True)
        result = EvaluationEngine().process(EvaluationInput(decision=decision, outcome="escalated"))
        assert result.correct is True

    def test_escalation_unexpected(self):
        decision = DecisionOutput(action="provide_fee_info", escalate=False)
        result = EvaluationEngine().process(EvaluationInput(decision=decision, outcome="escalated"))
        assert result.correct is False

    def test_clarified(self):
        result = EvaluationEngine().process(EvaluationInput(outcome="clarified"))
        assert result.correct is True

    def test_error_with_feedback(self):
        result = EvaluationEngine().process(EvaluationInput(
            outcome="error", user_feedback="API returned 500",
        ))
        assert result.correct is False
        assert result.confidence_adjustment < -0.15

    def test_unknown_outcome(self):
        result = EvaluationEngine().process(EvaluationInput(outcome="something_strange"))
        assert result.correct is False
        assert result.confidence_adjustment < 0
        assert result.follow_up_needed is True

    def test_completed_no_adjustment_for_low_confidence(self):
        decision = DecisionOutput(action="clarify", confidence=0.3)
        result = EvaluationEngine().process(EvaluationInput(decision=decision, outcome="completed"))
        assert result.confidence_adjustment == 0.0
