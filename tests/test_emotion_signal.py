"""Tests for the structured emotion signal detector (v1.1.3)."""
import pytest

from src.understanding.signals.base import Signal
from src.understanding.signals.emotion import detect_emotion
from src.understanding.signals.conversation import StructuredSignals
from src.understanding.engine import UnderstandingEngine


# =========================================================================
# 1. Frustration detection
# =========================================================================

class TestFrustrationDetection:
    def test_frustrated_detected(self):
        s = detect_emotion("I am so frustrated with this system")
        assert s is not None
        assert s.value == "frustration"
        assert s.confidence >= 0.5

    def test_fed_up_detected(self):
        s = detect_emotion("I am fed up with waiting")
        assert s is not None
        assert s.value == "frustration"
        assert s.confidence >= 0.8

    def test_useless_detected(self):
        s = detect_emotion("This is completely useless")
        assert s is not None
        assert s.value == "frustration"
        assert s.confidence >= 0.5

    def test_unacceptable_detected(self):
        s = detect_emotion("This is absolutely unacceptable!")
        assert s is not None
        assert s.value == "frustration"
        assert s.confidence >= 0.5

    def test_terrible_detected(self):
        s = detect_emotion("The service here is terrible")
        assert s is not None
        assert s.value == "frustration"
        assert s.confidence >= 0.5

    def test_waste_of_time_detected(self):
        s = detect_emotion("This is a waste of time")
        assert s is not None
        assert s.value == "frustration"
        assert s.confidence >= 0.5

    def test_sick_of_detected(self):
        s = detect_emotion("I am sick of this process")
        assert s is not None
        assert s.value == "frustration"
        assert s.confidence >= 0.5


# =========================================================================
# 2. Anxiety detection
# =========================================================================

class TestAnxietyDetection:
    def test_very_worried_detected(self):
        s = detect_emotion("I am very worried about my admission")
        assert s is not None
        assert s.value == "anxiety"
        assert s.confidence >= 0.5

    def test_worried_about_detected(self):
        s = detect_emotion("I am worried about the results")
        assert s is not None
        assert s.value == "anxiety"
        assert s.confidence >= 0.5

    def test_nervous_detected(self):
        s = detect_emotion("I am nervous about the exam")
        assert s is not None
        assert s.value == "anxiety"
        assert s.confidence >= 0.5

    def test_scared_detected(self):
        s = detect_emotion("I am scared about my future")
        assert s is not None
        assert s.value == "anxiety"
        assert s.confidence >= 0.5

    def test_panicking_detected(self):
        s = detect_emotion("I am panicking about the deadline")
        assert s is not None
        assert s.value == "anxiety"
        assert s.confidence >= 0.8

    def test_freaking_out_detected(self):
        s = detect_emotion("I am freaking out about the results")
        assert s is not None
        assert s.value == "anxiety"
        assert s.confidence >= 0.8

    def test_anxious_detected(self):
        s = detect_emotion("I feel anxious about the whole process")
        assert s is not None
        assert s.value == "anxiety"
        assert s.confidence >= 0.5

    def test_tense_detected(self):
        s = detect_emotion("I am feeling very tense")
        assert s is not None
        assert s.value == "anxiety"
        assert s.confidence >= 0.5


# =========================================================================
# 3. Confusion detection
# =========================================================================

class TestConfusionDetection:
    def test_confused_between_detected(self):
        s = detect_emotion("I am confused between CSE and ECE")
        assert s is not None
        assert s.value == "confusion"
        assert s.confidence >= 0.5

    def test_confused_about_detected(self):
        s = detect_emotion("I am confused about the process")
        assert s is not None
        assert s.value == "confusion"
        assert s.confidence >= 0.5

    def test_dont_understand_detected(self):
        s = detect_emotion("I don't understand the admission process")
        assert s is not None
        assert s.value == "confusion"
        assert s.confidence >= 0.5

    def test_not_sure_detected(self):
        s = detect_emotion("I am not sure which branch to choose")
        assert s is not None
        assert s.value == "confusion"
        assert s.confidence >= 0.5

    def test_what_should_i_do_detected(self):
        s = detect_emotion("What should I do?")
        assert s is not None
        assert s.value == "confusion"
        assert s.confidence >= 0.5

    def test_cant_decide_detected(self):
        s = detect_emotion("I can't decide between CSE and IT")
        assert s is not None
        assert s.value == "confusion"
        assert s.confidence >= 0.5

    def test_dilemma_detected(self):
        s = detect_emotion("I am in a dilemma about my career")
        assert s is not None
        assert s.value == "confusion"
        assert s.confidence >= 0.5

    def test_no_idea_detected(self):
        s = detect_emotion("I have no idea what to do")
        assert s is not None
        assert s.value == "confusion"
        assert s.confidence >= 0.5


# =========================================================================
# 4. Urgency detection
# =========================================================================

class TestUrgencyDetection:
    def test_urgent_detected(self):
        s = detect_emotion("This is urgent, please help!")
        assert s is not None
        assert s.value == "urgency"
        assert s.confidence >= 0.5

    def test_asap_detected(self):
        s = detect_emotion("Please reply ASAP")
        assert s is not None
        assert s.value == "urgency"
        assert s.confidence >= 0.8

    def test_hurry_up_detected(self):
        s = detect_emotion("Please hurry up, the deadline is tomorrow")
        assert s is not None
        assert s.value == "urgency"
        assert s.confidence >= 0.8

    def test_time_running_detected(self):
        s = detect_emotion("Time is running out, I need to decide now")
        assert s is not None
        assert s.value == "urgency"
        assert s.confidence >= 0.8

    def test_deadline_approaching_detected(self):
        s = detect_emotion("The deadline is approaching and I haven't submitted my application yet!")
        assert s is not None
        assert s.value == "urgency"
        assert s.confidence >= 0.5

    def test_deadline_informational_not_detected(self):
        s = detect_emotion("What is the deadline to apply?")
        assert s is None

    def test_last_date_detected(self):
        s = detect_emotion("When is the last date for admission?")
        assert s is not None
        assert s.value == "urgency"
        assert s.confidence >= 0.5

    def test_immediately_detected(self):
        s = detect_emotion("I need to know immediately")
        assert s is not None
        assert s.value == "urgency"
        assert s.confidence >= 0.5


# =========================================================================
# 5. Negation handling
# =========================================================================

class TestNegationHandling:
    def test_not_worried_not_detected(self):
        s = detect_emotion("I am not worried about anything")
        assert s is None

    def test_dont_panic_not_detected(self):
        s = detect_emotion("Don't panic, everything is fine")
        assert s is None

    def test_not_frustrated_not_detected(self):
        s = detect_emotion("I am not frustrated at all")
        assert s is None

    def test_not_urgent_not_detected(self):
        s = detect_emotion("This is not urgent")
        assert s is None

    def test_no_need_to_worry_not_detected(self):
        s = detect_emotion("There is no need to worry")
        assert s is None

    def test_cant_say_not_frustrated(self):
        s = detect_emotion("I can't say I am frustrated")
        assert s is None


# =========================================================================
# 6. Factual question exclusions
# =========================================================================

class TestFactualExclusions:
    def test_cutoff_question_no_emotion(self):
        s = detect_emotion("What is the cutoff for CSE?")
        assert s is None

    def test_fee_question_no_emotion(self):
        s = detect_emotion("What are the fees for CSE?")
        assert s is None

    def test_can_i_get_no_emotion(self):
        s = detect_emotion("Can I get CSE with rank 12000?")
        assert s is None

    def test_hostel_question_no_emotion(self):
        s = detect_emotion("What is the hostel fee?")
        assert s is None

    def test_placement_info_no_emotion(self):
        s = detect_emotion("What is the placement record?")
        assert s is None

    def test_syllabus_question_no_emotion(self):
        s = detect_emotion("What is the syllabus for CSE?")
        assert s is None

    def test_availability_question_no_emotion(self):
        s = detect_emotion("Is CSE available in this college?")
        assert s is None

    def test_how_much_no_emotion(self):
        s = detect_emotion("How much is the fee?")
        assert s is None


# =========================================================================
# 7. Strong emotion overrides exclusion
# =========================================================================

class TestStrongEmotionOverridesExclusion:
    def test_worried_about_cutoff_still_detected(self):
        s = detect_emotion("I am very worried about the cutoff")
        assert s is not None
        assert s.value == "anxiety"

    def test_frustrated_with_fee_still_detected(self):
        s = detect_emotion("I am frustrated with the fee structure")
        assert s is not None
        assert s.value == "frustration"

    def test_panicking_about_hostel_still_detected(self):
        s = detect_emotion("I am panicking about the hostel situation")
        assert s is not None
        assert s.value == "anxiety"


# =========================================================================
# 8. Mixed / co-occurring emotions
# =========================================================================

class TestMixedEmotions:
    def test_frustration_and_anxiety_returns_stronger(self):
        s = detect_emotion("I am very worried and frustrated about this process")
        assert s is not None
        assert s.value in ("frustration", "anxiety")

    def test_confusion_and_urgency_returns_stronger(self):
        s = detect_emotion("I am confused and need an urgent answer")
        assert s is not None
        assert s.value in ("confusion", "urgency")

    def test_frustration_wins_over_weak_confusion(self):
        s = detect_emotion("This is completely useless, I am confused what to do")
        assert s is not None
        assert s.value == "frustration"

    def test_anxiety_wins_over_weak_frustration(self):
        s = detect_emotion("I am very worried, this is a bit annoying")
        assert s is not None
        assert s.value == "anxiety"


# =========================================================================
# 9. No emotion cases
# =========================================================================

class TestNoEmotion:
    def test_empty_text_returns_none(self):
        assert detect_emotion("") is None

    def test_whitespace_returns_none(self):
        assert detect_emotion("   ") is None

    def test_none_returns_none(self):
        assert detect_emotion(None) is None

    def test_normal_question_no_emotion(self):
        s = detect_emotion("What is the cutoff for CSE?")
        assert s is None

    def test_profile_data_no_emotion(self):
        s = detect_emotion("My rank is 15000, 78 percent PCM, CBSE board")
        assert s is None

    def test_greeting_no_emotion(self):
        s = detect_emotion("Hello, how are you?")
        assert s is None

    def test_preference_statement_no_emotion(self):
        s = detect_emotion("I want CSE")
        assert s is None

    def test_information_request_no_emotion(self):
        s = detect_emotion("Tell me about the college")
        assert s is None


# =========================================================================
# 10. Signal properties
# =========================================================================

class TestSignalProperties:
    def test_source_is_correct(self):
        s = detect_emotion("I am worried about admission")
        assert s is not None
        assert s.source == "understanding.emotion_detector"

    def test_confidence_between_0_and_1(self):
        s = detect_emotion("I am worried about admission")
        assert s is not None
        assert 0.0 <= s.confidence <= 1.0

    def test_value_is_string(self):
        s = detect_emotion("I am worried about admission")
        assert s is not None
        assert isinstance(s.value, str)

    def test_high_confidence_for_strong_emotion(self):
        s = detect_emotion(
            "This is completely unacceptable! I am panicking about the "
            "deadline and nobody is helping me!"
        )
        assert s is not None
        assert s.confidence >= 0.8


# =========================================================================
# 11. StructuredSignals integration
# =========================================================================

class TestStructuredSignalsEmotion:
    def test_no_emotion(self):
        sig = StructuredSignals()
        assert sig.emotion is None
        assert sig.has_emotion() is False

    def test_with_emotion(self):
        s = Signal(value="anxiety", confidence=0.8, source="test")
        sig = StructuredSignals(emotion=s)
        assert sig.has_emotion() is True
        d = sig.as_dict()
        assert d["emotion"]["value"] == "anxiety"
        assert d["emotion"]["confidence"] == 0.8

    def test_emotion_in_as_dict(self):
        s = Signal(value="frustration", confidence=0.85, source="test")
        sig = StructuredSignals(emotion=s)
        d = sig.as_dict()
        assert "emotion" in d
        assert d["emotion"]["value"] == "frustration"

    def test_multiple_signals_coexist(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        d = Signal(value="compare", confidence=0.85, source="test")
        e = Signal(value="frustration", confidence=0.8, source="test")
        sig = StructuredSignals(grievance=g, decision=d, emotion=e)
        assert sig.has_grievance() is True
        assert sig.has_decision_intent() is True
        assert sig.has_emotion() is True
        d_out = sig.as_dict()
        assert "grievance" in d_out
        assert "decision" in d_out
        assert "emotion" in d_out

    def test_frozen(self):
        sig = StructuredSignals()
        with pytest.raises(AttributeError):
            sig.emotion = None

    def test_low_confidence_not_has_emotion(self):
        s = Signal(value="anxiety", confidence=0.3, source="test")
        sig = StructuredSignals(emotion=s)
        assert sig.has_emotion() is False


# =========================================================================
# 12. UnderstandingEngine integration
# =========================================================================

class TestPipelineIntegration:
    def test_emotion_signal_in_result(self):
        engine = UnderstandingEngine()
        result = engine.understand("I am very worried about my admission")
        assert result.structured_signals is not None
        assert result.structured_signals.has_emotion() is True
        assert result.structured_signals.emotion.value == "anxiety"

    def test_no_emotion_in_result(self):
        engine = UnderstandingEngine()
        result = engine.understand("What is the cutoff for CSE?")
        assert result.structured_signals is not None
        assert result.structured_signals.has_emotion() is False

    def test_frustration_in_result(self):
        engine = UnderstandingEngine()
        result = engine.understand("This system is completely useless!")
        assert result.structured_signals is not None
        assert result.structured_signals.emotion is not None
        assert result.structured_signals.emotion.value == "frustration"

    def test_confusion_in_result(self):
        engine = UnderstandingEngine()
        result = engine.understand("I am confused between CSE and ECE")
        assert result.structured_signals is not None
        assert result.structured_signals.emotion is not None
        assert result.structured_signals.emotion.value == "confusion"

    def test_urgency_in_result(self):
        engine = UnderstandingEngine()
        result = engine.understand("This is urgent, please help immediately!")
        assert result.structured_signals is not None
        assert result.structured_signals.emotion is not None
        assert result.structured_signals.emotion.value == "urgency"

    def test_grievance_and_emotion_coexist(self):
        engine = UnderstandingEngine()
        result = engine.understand(
            "Nobody responded for 5 days and I am very worried about my admission"
        )
        sig = result.structured_signals
        assert sig.has_grievance() is True
        assert sig.has_emotion() is True

    def test_decision_and_emotion_coexist(self):
        engine = UnderstandingEngine()
        result = engine.understand(
            "I am confused between CSE and ECE, which one should I choose?"
        )
        sig = result.structured_signals
        assert sig.has_decision_intent() is True
        assert sig.has_emotion() is True

    def test_all_three_signals_coexist(self):
        engine = UnderstandingEngine()
        result = engine.understand(
            "Nobody responded for 2 weeks, I am worried and confused between CSE and ECE"
        )
        sig = result.structured_signals
        assert sig.has_grievance() is True
        assert sig.has_emotion() is True
