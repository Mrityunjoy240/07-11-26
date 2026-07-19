from src.brain import CollegeBrain
from src.engines.interfaces import DecisionOutput
from src.planner.engine import MinimalPlanner
from src.planner.models import Plan


class TestMinimalPlanner:
    def test_plan_has_turns(self):
        decision = DecisionOutput(action="collect_profile", confidence=0.7)
        plan = MinimalPlanner().process(decision)
        assert isinstance(plan, Plan)
        assert len(plan.turns) >= 1

    def test_turns_have_content(self):
        decision = DecisionOutput(action="collect_profile", required_info=["rank", "pcm_percentage"])
        plan = MinimalPlanner().process(decision)
        for t in plan.turns:
            assert t.content

    def test_recommend_branches_with_brain(self):
        brain = CollegeBrain()
        q = brain.estimate_eligibility(rank=10000)
        brain_response = type("BR", (), {"admission": q})()
        decision = DecisionOutput(action="recommend_branches", confidence=0.85)
        plan = MinimalPlanner().process(decision, brain_response)
        assert len(plan.turns) >= 1

    def test_unknown_action_falls_back(self):
        decision = DecisionOutput(action="nonexistent_action")
        plan = MinimalPlanner().process(decision)
        assert len(plan.turns) == 1
        assert "help" in plan.turns[0].content.lower()

    def test_collect_profile_asks_for_missing(self):
        decision = DecisionOutput(action="collect_profile", required_info=["rank", "category"])
        plan = MinimalPlanner().process(decision)
        assert any("rank" in t.expected_input for t in plan.turns)
        assert any("category" in t.expected_input for t in plan.turns)

    def test_plan_metadata_includes_action(self):
        decision = DecisionOutput(action="provide_fee_info")
        plan = MinimalPlanner().process(decision)
        assert plan.metadata["action"] == "provide_fee_info"

    def test_plan_escalate_flag(self):
        decision = DecisionOutput(action="reassure", escalate=True, confidence=0.6)
        plan = MinimalPlanner().process(decision)
        assert plan.escalate is True
        assert len(plan.turns) >= 1

    def test_clarify_action(self):
        decision = DecisionOutput(action="clarify")
        plan = MinimalPlanner().process(decision)
        assert any("rephrase" in t.content for t in plan.turns)

    def test_reassure_action(self):
        decision = DecisionOutput(action="reassure")
        plan = MinimalPlanner().process(decision)
        assert any("worry" in t.content.lower() for t in plan.turns)
