import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api import qa as qa_module
import os

client = TestClient(app)

TOOL_TOKEN = "test-tool-token"


@pytest.fixture(autouse=True)
def _tool_token():
    """Every test runs against a configured shared token (fail-closed auth)."""
    old = qa_module.settings.sarvam_tool_api_token
    qa_module.settings.sarvam_tool_api_token = TOOL_TOKEN
    yield
    qa_module.settings.sarvam_tool_api_token = old


def _headers(**extra):
    return {"X-API-Key": TOOL_TOKEN, **extra}


def test_monitoring_check():
    """Check monitoring endpoint."""
    response = client.get("/monitoring/")
    assert response.status_code == 200


def test_stt_worst_case_invalid_format():
    """Worst Case: User sends a non-audio file to STT."""
    files = {"audio": ("test.txt", b"this is not audio", "text/plain")}
    response = client.post(
        "/qa/stt", files=files, data={"language": "en-IN"}, headers=_headers()
    )
    assert response.status_code == 400
    assert "Unsupported audio format" in response.json()["detail"]


def test_stt_worst_case_too_small():
    """Worst Case: User sends an empty/tiny audio file."""
    files = {"audio": ("test.wav", b"too small", "audio/wav")}
    response = client.post("/qa/stt", files=files, headers=_headers())
    assert response.status_code == 400
    assert "Audio file too small" in response.json()["detail"]


def test_tts_worst_case_empty_text():
    """Worst Case: User sends empty text for TTS."""
    response = client.post("/qa/tts", json={"text": ""}, headers=_headers())
    assert response.status_code == 400
    assert "Text cannot be empty" in response.json()["detail"]


def test_qa_groq_mocked(mocker):
    """Test QA route with a mocked Groq service."""
    # Now that the import is at the top of qa.py, we can patch it there
    mock_get = mocker.patch("app.api.qa.get_groq_service")
    mock_instance = mock_get.return_value

    # Mock generate_response (the actual method called in endpoint)
    # It must be an AsyncMock because it's awaited
    mock_instance.generate_response = mocker.AsyncMock(
        return_value={"answer": "Mocked Answer", "source": "groq"}
    )

    response = client.post(
        "/qa/query", json={"message": "Hello", "session_id": "test"}, headers=_headers()
    )
    assert response.status_code == 200
    assert "Mocked" in response.json()["answer"]


# ---------------------------------------------------------------------------
# Sarvam HTTPS-tool contract (/qa/query is the production tool target)
# ---------------------------------------------------------------------------
def _mock_qa(mocker):
    mock_get = mocker.patch("app.api.qa.get_groq_service")
    mock_instance = mock_get.return_value
    mock_instance.generate_response = mocker.AsyncMock(
        return_value={"answer": "Admission fee is 6,17,700.", "source": "llm_tools"}
    )
    return mock_instance


def test_qa_tool_accepts_session_context(mocker):
    """The Sarvam HTTPS tool passes utterance + session context; all accepted."""
    mock_instance = _mock_qa(mocker)
    response = client.post(
        "/qa/query",
        json={
            "message": "What is the admission fee?",
            "session_id": "call-abc-123",
            "conversation_id": "conv-1",
            "language": "English",
            "caller_phone": "+919876543210",
            "user_identifier": "019e9110-0000-0000-0000-000000000000",
            "caller_type": "student",
            "query_topic": "admissions",
        },
        headers=_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Admission fee is 6,17,700."
    assert body["session_id"] == "call-abc-123"
    mock_instance.generate_response.assert_called_once_with(
        "What is the admission fee?", session_id="call-abc-123"
    )


def test_qa_tool_ignores_unknown_fields(mocker):
    """Tool body template may send extra fields; they must not 422."""
    _mock_qa(mocker)
    response = client.post(
        "/qa/query",
        json={"message": "fees?", "call_sid": "CA123", "extra_agent_var": "x"},
        headers=_headers(),
    )
    assert response.status_code == 200


def test_qa_tool_empty_message_rejected(mocker):
    """An empty utterance must 400 with a clear detail (tool 'if it fails')."""
    _mock_qa(mocker)
    for bad in ["", "   "]:
        response = client.post("/qa/query", json={"message": bad}, headers=_headers())
        assert response.status_code == 400
        assert "message is empty" in response.json()["detail"]


def test_qa_tool_missing_message_rejected(mocker):
    """Missing message -> 422 (required field), not a silent 200."""
    _mock_qa(mocker)
    response = client.post("/qa/query", json={"session_id": "call-1"}, headers=_headers())
    assert response.status_code == 422


def test_qa_tool_auth_required(mocker):
    """With a shared token configured, /qa/query enforces it."""
    _mock_qa(mocker)

    # No token -> 401
    resp = client.post("/qa/query", json={"message": "fees?"})
    assert resp.status_code == 401

    # Wrong token -> 401
    resp = client.post(
        "/qa/query",
        json={"message": "fees?"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401

    # X-API-Key header -> 200
    resp = client.post(
        "/qa/query",
        json={"message": "fees?"},
        headers={"X-API-Key": TOOL_TOKEN},
    )
    assert resp.status_code == 200

    # Bearer header -> 200
    resp = client.post(
        "/qa/query",
        json={"message": "fees?"},
        headers={"Authorization": f"Bearer {TOOL_TOKEN}"},
    )
    assert resp.status_code == 200


def test_qa_tool_auth_closed_when_not_configured(mocker):
    """No token configured -> 503 (fail closed), never open access."""
    _mock_qa(mocker)
    qa_module.settings.sarvam_tool_api_token = ""
    try:
        response = client.post("/qa/query", json={"message": "fees?"})
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"].lower()
    finally:
        qa_module.settings.sarvam_tool_api_token = TOOL_TOKEN
