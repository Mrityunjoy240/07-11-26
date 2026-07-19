import pytest

from src.conversation.state import ConversationState
from src.understanding.engine import UnderstandingEngine


@pytest.fixture
def engine():
    return UnderstandingEngine()


class TestLanguageDetection:
    def test_detect_english(self, engine: UnderstandingEngine):
        result = engine.understand("Hello, I want to know about admission")
        assert result.language == "en"

    def test_detect_hindi(self, engine: UnderstandingEngine):
        result = engine.understand("मुझे एडमिशन के बारे में जानना है")
        assert result.language == "hi"

    def test_detect_bengali(self, engine: UnderstandingEngine):
        result = engine.understand("আমি ভর্তি সম্পর্কে জানতে চাই")
        assert result.language == "bn"


class TestProfileExtraction:
    def test_extract_rank(self, engine: UnderstandingEngine):
        result = engine.understand("my rank is 48000")
        assert result.profile.academic.rank == 48000

    def test_extract_rank_alternative(self, engine: UnderstandingEngine):
        result = engine.understand("I got 25000 rank in JEE")
        assert result.profile.academic.rank == 25000

    def test_extract_pcm(self, engine: UnderstandingEngine):
        result = engine.understand("I have 85% PCM")
        assert result.profile.academic.pcm_percentage == 85.0

    def test_extract_board(self, engine: UnderstandingEngine):
        result = engine.understand("I studied in WBCHSE")
        assert result.profile.academic.board == "WBCHSE"

    def test_extract_interest(self, engine: UnderstandingEngine):
        result = engine.understand("I am interested in Computer Science")
        assert result.profile.career.interest == "CSE"

    def test_extract_category(self, engine: UnderstandingEngine):
        result = engine.understand("I am from SC category")
        assert result.profile.personal.category == "sc"

    def test_extract_budget(self, engine: UnderstandingEngine):
        result = engine.understand("my budget is around 2 lakh")
        assert result.profile.personal.budget == 200000.0

    def test_no_fields_for_greeting(self, engine: UnderstandingEngine):
        result = engine.understand("Hello")
        assert result.profile.academic.rank is None
        assert result.profile.personal.category == ""
        assert result.profile.career.interest == ""


class TestIntentClassification:
    def test_intent_fee(self, engine: UnderstandingEngine):
        result = engine.understand("What are the fees for CSE?")
        assert result.intent.primary == "fee"

    def test_intent_admission(self, engine: UnderstandingEngine):
        result = engine.understand("When will the admission start?")
        assert result.intent.primary == "admission"

    def test_intent_placement(self, engine: UnderstandingEngine):
        result = engine.understand("What is the placement record?")
        assert result.intent.primary == "placement"

    def test_intent_greeting(self, engine: UnderstandingEngine):
        result = engine.understand("Hello")
        assert result.intent.primary == "greeting"

    def test_intent_unknown(self, engine: UnderstandingEngine):
        result = engine.understand("this is just random text xyz")
        assert result.intent.primary == "unknown"

    def test_intent_confidence_scored(self, engine: UnderstandingEngine):
        result = engine.understand("What are the fees for CSE?")
        assert result.intent.confidence > 0


class TestSignalDetection:
    def test_anxiety_detected(self, engine: UnderstandingEngine):
        result = engine.understand("I am very worried about my admission")
        assert result.signals.anxiety > 0

    def test_urgency_detected(self, engine: UnderstandingEngine):
        result = engine.understand("This is urgent, when is the last date?")
        assert result.signals.urgency > 0

    def test_confusion_detected(self, engine: UnderstandingEngine):
        result = engine.understand("I am confused about which branch to choose")
        assert result.signals.confusion > 0

    def test_financial_concern(self, engine: UnderstandingEngine):
        result = engine.understand("The fees are too expensive for me")
        assert result.signals.financial_concern > 0

    def test_multiple_signals(self, engine: UnderstandingEngine):
        result = engine.understand("I am confused and worried about the fees")
        assert result.signals.confusion > 0
        assert result.signals.anxiety > 0
        assert result.signals.financial_concern > 0

    def test_no_false_positives(self, engine: UnderstandingEngine):
        result = engine.understand("I got 85 percent in class 12")
        assert result.signals.anxiety == 0.0
        assert result.signals.urgency == 0.0


class TestMissingInformation:
    def test_missing_fields_when_empty(self, engine: UnderstandingEngine):
        result = engine.understand("Hello")
        assert len(result.missing_info.items) >= 3

    def test_rank_provided_removes_from_missing(self, engine: UnderstandingEngine):
        result = engine.understand("my rank is 48000")
        assert "academic.rank" not in result.missing_info.items

    def test_missing_from_state(self, engine: UnderstandingEngine):
        state = ConversationState(session_id="test", profile={"rank": 48000, "pcm_percentage": 85})
        result = engine.understand("Hello", state)
        assert "academic.rank" not in result.missing_info.items
        assert "academic.pcm_percentage" not in result.missing_info.items


class TestConversationReferences:
    def test_reference_detected(self, engine: UnderstandingEngine):
        result = engine.understand("tell me more about it")
        assert result.references_previous is True

    def test_no_reference(self, engine: UnderstandingEngine):
        result = engine.understand("What are the fees for CSE?")
        assert result.references_previous is False


class TestConfidence:
    def test_low_confidence_for_short(self, engine: UnderstandingEngine):
        result = engine.understand("Hi")
        assert result.confidence < 0.6

    def test_higher_confidence_with_profile(self, engine: UnderstandingEngine):
        result = engine.understand("My rank is 48000 and I am from WBCHSE board")
        assert result.confidence > 0.5
