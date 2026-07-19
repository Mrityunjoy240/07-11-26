from src.engines.interfaces import ReasoningInput, UnderstandingInput
from src.reasoning.engine import ReasoningEngine
from src.understanding.engine import UnderstandingEngine


class TestEngineProtocol:
    def test_understanding_engine_has_process(self):
        ue = UnderstandingEngine()
        result = ue.process(UnderstandingInput(text="hello"))
        assert result.text == "hello"

    def test_understanding_engine_process_matches_understand(self):
        ue = UnderstandingEngine()
        via_process = ue.process(UnderstandingInput(text="my rank is 50000", state=None))
        via_understand = ue.understand("my rank is 50000")
        assert via_process.text == via_understand.text
        assert via_process.intent.primary == via_understand.intent.primary

    def test_reasoning_engine_has_process(self):
        re = ReasoningEngine()
        ue = UnderstandingEngine()
        understanding = ue.understand("my rank is 50000")
        result = re.process(ReasoningInput(understanding=understanding))
        assert result.student_stage == "discovery"

    def test_understanding_via_process_with_state(self):
        from src.conversation.state import ConversationState

        ue = UnderstandingEngine()
        state = ConversationState(
            session_id="test",
            profile={"interest": "CSE"},
        )
        result = ue.process(UnderstandingInput(text="I want to study", state=state))
        assert result.text == "I want to study"
        assert result.missing_info is not None

    def test_reasoning_via_process_with_college_brain(self):
        from src.brain import CollegeBrain

        re = ReasoningEngine()
        ue = UnderstandingEngine()
        brain = CollegeBrain()
        understanding = ue.understand("my rank is 25000, interested in CSE")
        result = re.process(
            ReasoningInput(understanding=understanding, college_brain=brain)
        )
        assert result.eligibility.confidence > 0
