import pytest
from fastapi.testclient import TestClient
from app.main import app
import os

client = TestClient(app)


def test_monitoring_check():
    """Check monitoring endpoint."""
    response = client.get("/monitoring/")
    assert response.status_code == 200


def test_stt_worst_case_invalid_format():
    """Worst Case: User sends a non-audio file to STT."""
    files = {"audio": ("test.txt", b"this is not audio", "text/plain")}
    response = client.post("/qa/stt", files=files, data={"language": "en-IN"})
    assert response.status_code == 400
    assert "Unsupported audio format" in response.json()["detail"]


def test_stt_worst_case_too_small():
    """Worst Case: User sends an empty/tiny audio file."""
    files = {"audio": ("test.wav", b"too small", "audio/wav")}
    response = client.post("/qa/stt", files=files)
    assert response.status_code == 400
    assert "Audio file too small" in response.json()["detail"]


def test_tts_worst_case_empty_text():
    """Worst Case: User sends empty text for TTS."""
    response = client.post("/qa/tts", json={"text": ""})
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

    response = client.post("/qa/query", json={"message": "Hello", "session_id": "test"})
    assert response.status_code == 200
    assert "Mocked" in response.json()["answer"]
