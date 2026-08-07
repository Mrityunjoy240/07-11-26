"""Tests for the structured decision-intent signal detector (v1.1.2)."""
import pytest

from src.understanding.signals.base import Signal
from src.understanding.signals.decision import detect_decision_intent
from src.understanding.signals.conversation import StructuredSignals
from src.understanding.engine import UnderstandingEngine


# =========================================================================
# 1. Compare detection
# =========================================================================

class TestCompareDetection:
    def test_cse_or_ece(self):
        s = detect_decision_intent("CSE or ECE?")
        assert s is not None
        assert s.value == "compare"
        assert s.confidence >= 0.5

    def test_which_is_better_cse_or_it(self):
        s = detect_decision_intent("Which is better, CSE or IT?")
        assert s is not None
        assert s.value == "compare"
        assert s.confidence >= 0.5

    def test_difference_between_cse_and_ece(self):
        s = detect_decision_intent("What is the difference between CSE and ECE?")
        assert s is not None
        assert s.value == "compare"

    def test_how_does_it_compare_with_cse(self):
        s = detect_decision_intent("How does IT compare with CSE?")
        assert s is not None
        assert s.value == "compare"

    def test_cse_vs_ece(self):
        s = detect_decision_intent("CSE vs ECE, which one is better?")
        assert s is not None
        assert s.value == "compare"
        assert s.confidence >= 0.8

    def test_compare_cse_and_it_with_options(self):
        s = detect_decision_intent("Compare CSE and IT for me")
        assert s is not None
        assert s.value == "compare"
        assert s.target is not None

    def test_compare_extracts_target(self):
        s = detect_decision_intent("CSE or ECE?")
        assert s is not None
        assert s.target is not None
        assert "CSE" in s.target
        assert "ECE" in s.target

    def test_how_is_cse_compared_to_ece(self):
        s = detect_decision_intent("How is CSE compared to ECE?")
        assert s is not None
        assert s.value == "compare"


# =========================================================================
# 2. Recommend detection
# =========================================================================

class TestRecommendDetection:
    def test_which_should_i_choose(self):
        s = detect_decision_intent("Which one should I choose?")
        assert s is not None
        assert s.value == "recommend"
        assert s.confidence >= 0.5

    def test_what_would_you_recommend(self):
        s = detect_decision_intent("What would you recommend?")
        assert s is not None
        assert s.value == "recommend"

    def test_can_you_suggest(self):
        s = detect_decision_intent("Can you suggest the best option?")
        assert s is not None
        assert s.value == "recommend"

    def test_which_branch_better_for_me(self):
        s = detect_decision_intent("Which branch is better for me?")
        assert s is not None
        assert s.value == "recommend"

    def test_best_option_for_me(self):
        s = detect_decision_intent("What is the best option for me?")
        assert s is not None
        assert s.value == "recommend"

    def test_please_suggest(self):
        s = detect_decision_intent("Please suggest a good branch")
        assert s is not None
        assert s.value == "recommend"

    def test_what_should_i_pick(self):
        s = detect_decision_intent("What should I pick?")
        assert s is not None
        assert s.value == "recommend"


# =========================================================================
# 3. Choose detection
# =========================================================================

class TestChooseDetection:
    def test_which_should_i_take(self):
        s = detect_decision_intent("Which should I take?")
        assert s is not None
        assert s.value == "choose"
        assert s.confidence >= 0.5

    def test_should_i_choose(self):
        s = detect_decision_intent("Should I choose CSE or ECE?")
        assert s is not None
        assert s.value in ("choose", "compare")

    def test_what_should_i_go_for(self):
        s = detect_decision_intent("What should I go for?")
        assert s is not None
        assert s.value == "choose"

    def test_help_me_decide(self):
        s = detect_decision_intent("Help me decide between CSE and ECE")
        assert s is not None
        assert s.value == "choose"

    def test_help_me_choose(self):
        s = detect_decision_intent("Help me choose a branch")
        assert s is not None
        assert s.value == "choose"

    def test_cant_decide(self):
        s = detect_decision_intent("I can't decide between CSE and ECE")
        assert s is not None
        assert s.value == "choose"

    def test_confused_between(self):
        s = detect_decision_intent("I am confused between CSE and IT")
        assert s is not None
        assert s.value == "choose"

    def test_what_to_choose(self):
        s = detect_decision_intent("What to choose for engineering?")
        assert s is not None
        assert s.value == "choose"


# =========================================================================
# 4. Alternative detection
# =========================================================================

class TestAlternativeDetection:
    def test_what_other_branches(self):
        s = detect_decision_intent("What other branches are similar to CSE?")
        assert s is not None
        assert s.value == "alternative"
        assert s.confidence >= 0.5

    def test_if_i_cant_get_cse(self):
        s = detect_decision_intent("If I can't get CSE, what are my alternatives?")
        assert s is not None
        assert s.value == "alternative"

    def test_what_else_can_i_choose(self):
        s = detect_decision_intent("What else can I choose?")
        assert s is not None
        assert s.value == "alternative"

    def test_any_other_options(self):
        s = detect_decision_intent("Any other options?")
        assert s is not None
        assert s.value == "alternative"

    def test_backup_option(self):
        s = detect_decision_intent("I need a backup option")
        assert s is not None
        assert s.value == "alternative"

    def test_plan_b(self):
        s = detect_decision_intent("What is my plan B?")
        assert s is not None
        assert s.value == "alternative"

    def test_what_are_my_options(self):
        s = detect_decision_intent("What are my options?")
        assert s is not None
        assert s.value == "alternative"


# =========================================================================
# 5. Tradeoff detection
# =========================================================================

class TestTradeoffDetection:
    def test_pros_and_cons(self):
        s = detect_decision_intent("What are the pros and cons of CSE vs ECE?")
        assert s is not None
        assert s.value == "tradeoff"
        assert s.confidence >= 0.8

    def test_is_cse_worth_it(self):
        s = detect_decision_intent("Is CSE worth it compared to ECE?")
        assert s is not None
        assert s.value == "tradeoff"

    def test_tradeoff(self):
        s = detect_decision_intent("What is the tradeoff between CSE and IT?")
        assert s is not None
        assert s.value == "tradeoff"

    def test_advantages_and_disadvantages(self):
        s = detect_decision_intent("Advantages and disadvantages of CSE?")
        assert s is not None
        assert s.value == "tradeoff"

    def test_which_has_better_but(self):
        s = detect_decision_intent("Which has better placements but lower cutoff?")
        assert s is not None
        assert s.value == "tradeoff"

    def test_benefit_of_cse_over_ece(self):
        s = detect_decision_intent("What are the benefits of CSE over ECE?")
        assert s is not None
        assert s.value == "tradeoff"

    def test_drawback(self):
        s = detect_decision_intent("What is the drawback of choosing IT?")
        assert s is not None
        assert s.value == "tradeoff"


# =========================================================================
# 6. False-positive prevention — these should NOT trigger
# =========================================================================

class TestFalsePositivePrevention:
    def test_can_i_get_cse(self):
        """Eligibility question."""
        s = detect_decision_intent("Can I get CSE with rank 12000?")
        assert s is None

    def test_cutoff_for_cse(self):
        """Factual cutoff question."""
        s = detect_decision_intent("What is the cutoff for CSE?")
        assert s is None

    def test_i_want_cse(self):
        """Preference statement."""
        s = detect_decision_intent("I want CSE")
        assert s is None

    def test_i_prefer_it(self):
        """Preference statement."""
        s = detect_decision_intent("I prefer IT")
        assert s is None

    def test_can_i_choose_cse(self):
        """Ability question, not decision."""
        s = detect_decision_intent("Can I choose CSE?")
        assert s is None

    def test_fees_for_cse(self):
        """Fee question."""
        s = detect_decision_intent("What are the fees for CSE?")
        assert s is None

    def test_is_cse_available(self):
        """Availability question."""
        s = detect_decision_intent("Is CSE available in this college?")
        assert s is None

    def test_hostel_fee(self):
        """Hostel question."""
        s = detect_decision_intent("What is the hostel fee?")
        assert s is None

    def test_placement_record(self):
        """Informational placement question."""
        s = detect_decision_intent("What is the placement record?")
        assert s is None

    def test_tell_me_about_cse(self):
        """Informational question."""
        s = detect_decision_intent("Tell me about CSE department")
        assert s is None

    def test_how_much_fee(self):
        """Fee question."""
        s = detect_decision_intent("How much is the fee?")
        assert s is None

    def test_will_i_get_admission(self):
        """Eligibility question."""
        s = detect_decision_intent("Will I get admission with 80 percent?")
        assert s is None

    def test_hello_greeting(self):
        """Greeting."""
        s = detect_decision_intent("Hello, how are you?")
        assert s is None

    def test_empty_text(self):
        """Empty text."""
        s = detect_decision_intent("")
        assert s is None

    def test_whitespace_only(self):
        """Whitespace only."""
        s = detect_decision_intent("   ")
        assert s is None

    def test_none_text(self):
        """None text."""
        s = detect_decision_intent(None)
        assert s is None

    def test_profile_data(self):
        """Profile data without decision intent."""
        s = detect_decision_intent("My rank is 15000, 78 percent PCM, CBSE board")
        assert s is None

    def test_normal_academic_question(self):
        """Normal academic question."""
        s = detect_decision_intent("What is the syllabus for CSE?")
        assert s is None

    def test_single_branch_no_comparison(self):
        """Mentioning a single branch without comparison."""
        s = detect_decision_intent("I am interested in CSE")
        assert s is None

    def test_grievance_no_decision(self):
        """Grievance text should not trigger decision."""
        s = detect_decision_intent("Nobody responded for 5 days, this is unacceptable")
        assert s is None


# =========================================================================
# 7. Negation handling
# =========================================================================

class TestNegationHandling:
    def test_not_comparing(self):
        s = detect_decision_intent("I am not comparing CSE and ECE")
        assert s is None

    def test_dont_recommend(self):
        s = detect_decision_intent("Don't recommend anything")
        assert s is None


# =========================================================================
# 8. Signal output structure
# =========================================================================

class TestSignalOutput:
    def test_value_is_string(self):
        s = detect_decision_intent("CSE or ECE?")
        assert s is not None
        assert isinstance(s.value, str)

    def test_source_is_correct(self):
        s = detect_decision_intent("CSE or ECE?")
        assert s is not None
        assert s.source == "understanding.decision_detector"

    def test_confidence_between_0_and_1(self):
        s = detect_decision_intent("CSE or ECE?")
        assert s is not None
        assert 0.0 <= s.confidence <= 1.0

    def test_target_is_optional_string_or_none(self):
        s = detect_decision_intent("What should I pick?")
        assert s is not None
        # recommend subtype may not extract target
        assert s.target is None or isinstance(s.target, str)

    def test_compare_extracts_branches_as_target(self):
        s = detect_decision_intent("CSE or ECE?")
        assert s is not None
        assert s.target is not None
        assert "CSE" in s.target
        assert "ECE" in s.target


# =========================================================================
# 9. StructuredSignals integration
# =========================================================================

class TestStructuredSignalsDecision:
    def test_no_decision(self):
        sig = StructuredSignals()
        assert sig.decision is None
        assert sig.has_decision_intent() is False

    def test_with_decision(self):
        s = Signal(value="compare", confidence=0.9, source="test")
        sig = StructuredSignals(decision=s)
        assert sig.has_decision_intent() is True

    def test_as_dict_includes_decision(self):
        s = Signal(value="compare", confidence=0.9, source="test", target="CSE vs ECE")
        sig = StructuredSignals(decision=s)
        d = sig.as_dict()
        assert "decision" in d
        assert d["decision"]["value"] == "compare"
        assert d["decision"]["target"] == "CSE vs ECE"

    def test_as_dict_includes_both_signals(self):
        g = Signal(value="waiting", confidence=0.9, source="g")
        d = Signal(value="recommend", confidence=0.8, source="d")
        sig = StructuredSignals(grievance=g, decision=d)
        result = sig.as_dict()
        assert "grievance" in result
        assert "decision" in result

    def test_frozen(self):
        sig = StructuredSignals()
        with pytest.raises(AttributeError):
            sig.decision = None


# =========================================================================
# 10. Pipeline integration
# =========================================================================

class TestPipelineIntegrationDecision:
    def test_decision_signal_in_result(self):
        engine = UnderstandingEngine()
        result = engine.understand("CSE or ECE, which is better?")
        assert result.structured_signals is not None
        assert result.structured_signals.has_decision_intent() is True

    def test_no_decision_in_result(self):
        engine = UnderstandingEngine()
        result = engine.understand("What is the cutoff for CSE?")
        assert result.structured_signals is not None
        assert result.structured_signals.has_decision_intent() is False

    def test_recommend_in_result(self):
        engine = UnderstandingEngine()
        result = engine.understand("Which one should I choose?")
        assert result.structured_signals is not None
        assert result.structured_signals.has_decision_intent() is True
        assert result.structured_signals.decision.value == "recommend"

    def test_tradeoff_in_result(self):
        engine = UnderstandingEngine()
        result = engine.understand("What are the pros and cons of CSE vs ECE?")
        assert result.structured_signals is not None
        assert result.structured_signals.has_decision_intent() is True
        assert result.structured_signals.decision.value == "tradeoff"

    def test_grievance_still_works(self):
        """Ensure grievance detection is not broken."""
        engine = UnderstandingEngine()
        result = engine.understand("Nobody responded for 5 days, this is unacceptable")
        assert result.structured_signals.has_grievance() is True

    def test_both_signals_can_coexist(self):
        engine = UnderstandingEngine()
        result = engine.understand(
            "CSE or ECE? Nobody responded to my earlier query about this."
        )
        # At least one should be present
        assert (result.structured_signals.has_grievance() or
                result.structured_signals.has_decision_intent())
