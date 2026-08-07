"""Tests for the structured grievance signal detector (v1.1.1)."""
import pytest

from src.understanding.signals.base import Signal
from src.understanding.signals.grievance import detect_grievance
from src.understanding.signals.conversation import StructuredSignals
from src.understanding.engine import UnderstandingEngine


class TestGrievanceDetection:
    def test_waiting_detected(self):
        s = detect_grievance("I have been waiting for 3 days and nobody replied")
        assert s is not None
        assert s.value == "waiting"
        assert s.confidence >= 0.5

    def test_ignored_detected(self):
        s = detect_grievance("I submitted my form two weeks ago and nobody has responded")
        assert s is not None
        assert s.value == "ignored"
        assert s.confidence >= 0.5

    def test_website_detected(self):
        s = detect_grievance("The website is not working, I cannot submit my form")
        assert s is not None
        assert s.value == "website"
        assert s.confidence >= 0.5

    def test_staff_detected(self):
        s = detect_grievance("I want to speak to someone in charge right now")
        assert s is not None
        assert s.value == "staff"
        assert s.confidence >= 0.5

    def test_process_detected(self):
        s = detect_grievance("This system is useless! I have been asking the same question for 10 minutes and getting the same stupid answer")
        assert s is not None
        assert s.confidence >= 0.5

    def test_unacceptable_detected(self):
        s = detect_grievance("This is absolutely unacceptable!")
        assert s is not None
        assert s.confidence >= 0.5

    def test_negated_grievance_not_detected(self):
        s = detect_grievance("This is not useless at all, the system works fine")
        assert s is None

    def test_negated_nobody_not_detected(self):
        s = detect_grievance("It is not true that nobody responded to me")
        assert s is None

    def test_empty_text_returns_none(self):
        assert detect_grievance("") is None

    def test_whitespace_returns_none(self):
        assert detect_grievance("   ") is None

    def test_none_returns_none(self):
        assert detect_grievance(None) is None

    def test_normal_question_no_grievance(self):
        s = detect_grievance("What is the cutoff for CSE?")
        assert s is None

    def test_anxiety_no_grievance(self):
        s = detect_grievance("I am very worried about my admission")
        assert s is None

    def test_profile_data_no_grievance(self):
        s = detect_grievance("My rank is 15000, 78 percent PCM, CBSE board")
        assert s is None

    def test_grievance_with_profile_data(self):
        s = detect_grievance("I had WBJEE rank 15000. I applied two weeks ago and got no reply.")
        assert s is not None
        assert s.confidence >= 0.5

    def test_high_confidence_for_strong_grievance(self):
        s = detect_grievance(
            "This is absolutely unacceptable! I submitted my admission form "
            "two weeks ago and nobody has responded. The whole process is a mess. "
            "I want to speak to someone in charge right now!"
        )
        assert s is not None
        assert s.confidence >= 0.8

    def test_subtype_is_string(self):
        s = detect_grievance("nobody responded for 5 days")
        assert s is not None
        assert isinstance(s.value, str)

    def test_source_is_correct(self):
        s = detect_grievance("nobody responded for 5 days")
        assert s is not None
        assert s.source == "understanding.grievance_detector"

    def test_confidence_between_0_and_1(self):
        s = detect_grievance("nobody responded for 5 days")
        assert s is not None
        assert 0.0 <= s.confidence <= 1.0


class TestStructuredSignals:
    def test_no_grievance(self):
        sig = StructuredSignals()
        assert sig.grievance is None
        assert sig.has_grievance() is False
        assert sig.as_dict() == {}

    def test_with_grievance(self):
        s = Signal(value="waiting", confidence=0.9, source="test")
        sig = StructuredSignals(grievance=s)
        assert sig.has_grievance() is True
        d = sig.as_dict()
        assert d["grievance"]["value"] == "waiting"
        assert d["grievance"]["confidence"] == 0.9

    def test_frozen(self):
        sig = StructuredSignals()
        with pytest.raises(AttributeError):
            sig.grievance = None


class TestPipelineIntegration:
    def test_grievance_signal_in_result(self):
        engine = UnderstandingEngine()
        result = engine.understand("Nobody responded for 5 days, this is unacceptable")
        assert result.structured_signals is not None
        assert result.structured_signals.has_grievance() is True

    def test_no_grievance_in_result(self):
        engine = UnderstandingEngine()
        result = engine.understand("What is the cutoff for CSE?")
        assert result.structured_signals is not None
        assert result.structured_signals.has_grievance() is False

    def test_grievance_subtype_in_result(self):
        engine = UnderstandingEngine()
        result = engine.understand(
            "I want to speak to someone in charge, nobody has responded to my complaint"
        )
        sig = result.structured_signals
        assert sig is not None
        assert sig.grievance is not None
        assert sig.grievance.value in ("waiting", "ignored", "staff", "process", "website")
