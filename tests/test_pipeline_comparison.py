"""
Comparison test: new pipeline vs old GroqService for admission counseling.
The old GroqService is a 5200-line monolith that can't be cleanly instantiated
in a test. Instead, this test proves the new pipeline produces a complete,
explainable, structured output for a realistic admission query.

Key differences the new pipeline provides:
  1. Each layer produces typed, inspectable output
  2. College Brain provides explainable eligibility (why + because)
  3. Decision Engine selects an explicit action with rationale
  4. Planner produces ordered, content-rich conversation turns
  5. Every layer can be tested independently
"""

from src.brain import CollegeBrain
from src.brain.interfaces import BrainQuery, Reason
from src.conversation.state import ConversationState
from src.decision.engine import DecisionEngine
from src.engines.interfaces import DecisionInput, ReasoningInput, UnderstandingInput
from src.pipeline import PipelineOrchestrator
from src.planner.engine import MinimalPlanner
from src.reasoning.engine import ReasoningEngine
from src.understanding.engine import UnderstandingEngine


class TestPipelineComparison:
    def test_full_admission_query_structured_output(self):
        """Simulate: 'I got 48k rank and 82% PCM. I like AI.'"""
        text = "my rank is 48000 and 82 PCM. I am interested in AI."

        ue = UnderstandingEngine()
        re = ReasoningEngine()
        brain = CollegeBrain()
        de = DecisionEngine()
        planner = MinimalPlanner()

        # Step 1: Understanding
        understanding = ue.process(UnderstandingInput(text=text))
        assert understanding.text == text
        assert understanding.profile.academic.rank == 48000
        assert understanding.profile.academic.pcm_percentage == 82.0
        assert "ai" in understanding.profile.career.interest.lower()
        assert understanding.confidence > 0

        # Step 2: Reasoning
        reasoning = re.process(ReasoningInput(understanding=understanding, college_brain=brain))
        assert reasoning.profile_completeness > 0
        assert reasoning.eligibility is not None

        # Step 3: College Brain
        brain_q = BrainQuery(rank=48000, pcm_percentage=82, interest="AI")
        brain_response = brain.query(brain_q)
        assert brain_response.admission is not None
        assert brain_response.admission.applicable is True
        assert len(brain_response.admission.why) > 0
        assert any(isinstance(r, Reason) for r in brain_response.admission.why)

        # Step 4: Decision
        decision = de.process(DecisionInput(reasoning=reasoning, brain_response=brain_response))
        assert decision.action in ("recommend_branches", "collect_profile", "provide_admission_guidance")
        assert decision.confidence > 0
        assert decision.rationale

        # Step 5: Planner
        plan = planner.process(decision, brain_response)
        assert len(plan.turns) >= 1
        for t in plan.turns:
            assert t.content  # every turn has content
            assert t.action  # every turn has an action type
            assert t.speaker == "assistant"

    def test_pipeline_orchestrator_runs_end_to_end(self):
        """Run the full pipeline through the orchestrator."""
        pipeline = PipelineOrchestrator()
        result = pipeline.run("my rank is 48000 and 82 PCM. I am interested in AI.")

        assert result.understanding is not None
        assert result.reasoning is not None
        assert result.brain_response is not None
        assert result.decision is not None
        assert result.plan is not None
        assert len(result.errors) == 0

        # Verify plan has usable turns
        assert len(result.plan.turns) >= 1

    def test_pipeline_handles_greeting(self):
        """Greeting should flow through gracefully."""
        pipeline = PipelineOrchestrator()
        result = pipeline.run("Hello")
        assert len(result.errors) == 0
        assert result.understanding is not None
        assert result.plan is not None
        assert len(result.plan.turns) >= 1

    def test_pipeline_with_full_profile(self):
        """Full profile with category should produce recommend_branches."""
        state = ConversationState(
            session_id="test",
            profile={"category": "general"},
        )
        pipeline = PipelineOrchestrator()
        result = pipeline.run(
            "my rank is 48000 and 82 PCM. I am interested in AI.",
            state=state,
        )
        assert result.decision.action == "recommend_branches"
        assert result.plan is not None
        assert any("eligible" in t.content for t in result.plan.turns)

    def test_pipeline_produces_decision_rationale(self):
        """Decision must include a human-readable rationale."""
        pipeline = PipelineOrchestrator()
        result = pipeline.run("What are the fees for CSE?")
        assert result.decision is not None
        assert len(result.decision.rationale) > 10

    def test_pipeline_plan_is_ordered_conversation(self):
        """Plan turns should be in a speakable order."""
        pipeline = PipelineOrchestrator()
        result = pipeline.run("Tell me about placements")
        plan = result.plan
        assert plan is not None
        for t in plan.turns:
            assert t.speaker == "assistant"
            assert t.action in ("ask", "inform", "recommend", "reassure", "clarify")

    def test_understanding_confidence_above_threshold(self):
        """Understanding confidence should be > 0.3 for a detailed query."""
        ue = UnderstandingEngine()
        r = ue.process(UnderstandingInput(text="my rank is 48000 and I have 82 PCM from WBCHSE"))
        assert r.confidence > 0.3

    def test_reasoning_confidence_above_threshold(self):
        """Reasoning confidence should be > 0.3 for a detailed query."""
        ue = UnderstandingEngine()
        re = ReasoningEngine()
        u = ue.process(UnderstandingInput(
            text="my rank is 48000, 82 PCM, interested in CSE",
        ))
        r = re.process(ReasoningInput(understanding=u))
        assert r.confidence > 0.3

    def test_college_brain_explainability(self):
        """College Brain should explain why a decision was made."""
        brain = CollegeBrain()
        result = brain.estimate_eligibility(rank=48000)
        assert len(result.why) > 1
        assert any("rank" in r.condition for r in result.why)
        assert any("cutoff" in r.condition for r in result.why)
