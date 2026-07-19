from src.understanding.models import (
    ConversationSignals,
    MissingInformation,
    UnderstandingIntent,
    UnderstandingResult,
)
from src.understanding.profile import StudentProfile


def test_conversation_signals_defaults():
    s = ConversationSignals()
    assert s.anxiety == 0.0
    assert s.dominant == ("anxiety", 0.0)


def test_conversation_signals_dominant():
    s = ConversationSignals(anxiety=0.8, confusion=0.3, urgency=0.6)
    assert s.dominant == ("anxiety", 0.8)


def test_missing_information():
    m = MissingInformation(items=["pcm_percentage", "category"])
    assert len(m.items) == 2
    assert "pcm_percentage" in m.items


def test_understanding_intent():
    i = UnderstandingIntent(primary="fee", confidence=0.85)
    assert i.primary == "fee"
    assert i.confidence == 0.85


def test_understanding_result_defaults():
    r = UnderstandingResult(text="hello")
    assert r.text == "hello"
    assert r.language == "en"
    assert r.intent.primary == "unknown"
    assert r.profile.academic.rank is None
    assert r.signals.anxiety == 0.0
    assert r.missing_info.items == []
    assert r.references_previous is False
    assert r.confidence == 0.0


def test_understanding_result_full():
    r = UnderstandingResult(
        text="my rank is 48000",
        language="en",
        intent=UnderstandingIntent(primary="admission", confidence=0.8),
        profile=StudentProfile(),
        signals=ConversationSignals(anxiety=0.7),
        missing_info=MissingInformation(items=["pcm_percentage"]),
        references_previous=False,
        confidence=0.85,
    )
    assert r.profile.academic.rank is None
    assert r.signals.anxiety == 0.7
