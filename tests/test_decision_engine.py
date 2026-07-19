from src.brain import CollegeBrain
from src.decision.engine import DecisionEngine
from src.engines.interfaces import DecisionInput
from src.reasoning.models import ReasoningResult


class TestDecisionEngine:
    def test_profile_initial(self):
        engine = DecisionEngine()
        r = ReasoningResult(current_problem="needs_profile_initial", confidence=0.3)
        output = engine.process(DecisionInput(reasoning=r))
        assert output.action == "collect_profile"
        assert output.priority == "high"
        assert output.escalate is False

    def test_anxiety_escalates(self):
        engine = DecisionEngine()
        r = ReasoningResult(
            current_problem="needs_reassurance",
            confidence=0.5,
            risks=["student_shows_anxiety"],
        )
        output = engine.process(DecisionInput(reasoning=r))
        assert output.action == "reassure"
        assert output.escalate is True

    def test_unknown_problem(self):
        engine = DecisionEngine()
        r = ReasoningResult(current_problem="does_not_exist")
        output = engine.process(DecisionInput(reasoning=r))
        assert output.action == "clarify"

    def test_decision_stage_high_priority(self):
        engine = DecisionEngine()
        r = ReasoningResult(
            current_problem="needs_personalized_guidance",
            student_stage="decision",
            confidence=0.6,
        )
        output = engine.process(DecisionInput(reasoning=r))
        assert output.priority == "high"

    def test_brain_eligibility_overrides_action(self):
        engine = DecisionEngine()
        brain = CollegeBrain()
        r = ReasoningResult(current_problem="needs_profile_initial", confidence=0.5,
                            profile_completeness=0.5)
        q = brain.estimate_eligibility(rank=5000)
        brain_response = type("BR", (), {"admission": q})()
        output = engine.process(DecisionInput(reasoning=r, brain_response=brain_response))
        assert output.action == "recommend_branches"

    def test_unknowns_passed_through(self):
        engine = DecisionEngine()
        r = ReasoningResult(
            current_problem="needs_profile_initial",
            confidence=0.3,
            unknowns=["rank", "pcm_percentage"],
        )
        output = engine.process(DecisionInput(reasoning=r))
        assert "rank" in output.required_info

    def test_required_info_from_registry(self):
        from src.registry import CapabilityManifest, CapabilityRegistry

        engine = DecisionEngine()
        reg = CapabilityRegistry()
        handler = _LookupHandler("collect_profile", required=["rank", "interest"])
        reg.register(CapabilityManifest(
            name="collect_profile", handler=handler,
            metadata={"required_info": ["rank", "interest"]},
        ))
        r = ReasoningResult(current_problem="collect_profile", confidence=0.4)
        output = engine.process(DecisionInput(reasoning=r, capabilities=reg))
        assert "rank" in output.required_info


class _LookupHandler:
    def __init__(self, intent: str, required: list[str] | None = None):
        self._intent = intent
        self._required = required or []

    def can_handle(self, intent: str, context=None) -> bool:
        return intent == self._intent

    def execute(self, context=None):
        return {}
