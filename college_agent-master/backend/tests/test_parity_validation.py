"""
Parity Validation Tests — Chat vs Voice Pipeline
=================================================
Verifies that generate_response() and stream_response() produce identical
business logic results when given the same input.

The service's chat entry point (generate_response) returns a dict payload and
the voice entry point (stream_response) yields word chunks. Both must resolve
the same deterministic short-circuit branches (out-of-domain, exit, greeting,
acknowledgment) and share session state (language, profile, history) so that
chat and voice answers never diverge.

Run: python -m pytest backend/tests/test_parity_validation.py -v
"""

import uuid

import pytest

from app.services.llm.groq_service import get_groq_service


@pytest.fixture
def service():
    """Get the singleton GroqService with stub clients so the availability
    guard passes without any network call. Deterministic branches never touch
    the client; the LLM branch is mocked per-test."""
    svc = get_groq_service()
    svc.client = object()
    svc.async_client = object()
    return svc


@pytest.fixture(autouse=True)
def _no_safe_point(monkeypatch):
    """Disable the DEMO_SAFEPOINT overlay.

    generate_response() runs a safepoint pre-check (Bengali low-confidence
    interception) that stream_response() does not, so parity is only well-defined
    with the overlay off. The .env may enable DEMO_SAFEPOINT; force it off here
    so the parity assertions test the core pipeline deterministically."""
    monkeypatch.setattr("app.services.llm.groq_service._sp_enabled", lambda: False)
    monkeypatch.setattr("app.services.llm.safe_point._is_safe_point", lambda: False)


@pytest.fixture
def fresh_session():
    """Generate a unique session ID for isolation."""
    return f"parity_test_{uuid.uuid4().hex[:8]}"


async def _collect_stream(service, query, session_id):
    """Run the voice pipeline and join all yielded chunks."""
    chunks = []
    async for chunk in service.stream_response(query, session_id):
        chunks.append(chunk)
    return "".join(chunks).strip()


# ── Test 1: Chat vs Voice Parity — same conversation, both pipelines ──

class TestChatVoiceParity:
    """Run the same conversation through both pipelines and compare results."""

    @pytest.mark.asyncio
    async def test_greeting_deterministic(self, service, fresh_session):
        """Greeting short-circuits in the chat pipeline without the LLM."""
        result = await service.generate_response("hi", fresh_session)
        assert isinstance(result, dict)
        assert result.get("source") == "greeting_deterministic"
        assert result.get("answer")

    @pytest.mark.asyncio
    async def test_out_of_domain_parity(self, service, fresh_session):
        """Out-of-domain query should produce identical text in both pipelines."""
        query = "what is the weather in kolkata today"
        chat = await service.generate_response(query, fresh_session)
        assert chat.get("source") == "out_of_domain"
        voice = await _collect_stream(service, query, fresh_session)
        assert voice == chat.get("answer", "").strip()

    @pytest.mark.asyncio
    async def test_exit_parity(self, service, fresh_session):
        """Exit intent should produce identical text in both pipelines."""
        query = "bye"
        chat = await service.generate_response(query, fresh_session)
        assert chat.get("source") == "conversation_policy_exit"
        voice = await _collect_stream(service, query, fresh_session)
        assert voice == chat.get("answer", "").strip()

    @pytest.mark.asyncio
    async def test_acknowledgment_parity(self, service, fresh_session):
        """Filler acknowledgment should produce identical text in both pipelines."""
        query = "okay"
        chat = await service.generate_response(query, fresh_session)
        voice = await _collect_stream(service, query, fresh_session)
        assert voice == chat.get("answer", "").strip()

    @pytest.mark.asyncio
    async def test_llm_path_parity(self, service, fresh_session, monkeypatch):
        """LLM-path answers must be streamed unchanged by the voice pipeline."""

        async def fake_llm(messages, session_id, query, start, lang):
            return "The CSE total fee is Rs. 6,04,700 for four years."

        monkeypatch.setattr(service, "_call_llm_with_tools", fake_llm)
        query = "what is the total CSE fee"
        chat = await service.generate_response(query, fresh_session)
        assert chat.get("source") == "llm_tools"
        voice = await _collect_stream(service, query, fresh_session)
        assert voice == chat.get("answer", "").strip()


# ── Test 2: Language Parity ──

class TestLanguageParity:
    """Language-aware responses must be identical across pipelines."""

    @pytest.mark.asyncio
    async def test_hindi_exit_parity(self, service, fresh_session):
        """Hindi session should produce the same Hindi exit in both pipelines."""
        service._session_langs[fresh_session] = "hi"
        query = "bye"
        chat = await service.generate_response(query, fresh_session)
        voice = await _collect_stream(service, query, fresh_session)
        assert voice == chat.get("answer", "").strip()
        assert any(ch in voice for ch in ("Alvida", "अलविदा", "Bye"))

    @pytest.mark.asyncio
    async def test_bengali_exit_parity(self, service, fresh_session):
        """Bengali session should produce the same Bengali exit in both pipelines."""
        service._session_langs[fresh_session] = "bn"
        query = "bye"
        chat = await service.generate_response(query, fresh_session)
        voice = await _collect_stream(service, query, fresh_session)
        assert voice == chat.get("answer", "").strip()

    @pytest.mark.asyncio
    async def test_language_persists_across_queries(self, service, fresh_session):
        """Language should persist across queries in both pipelines."""
        service._session_langs[fresh_session] = "hi"
        await service.generate_response("bye", fresh_session)
        await _collect_stream(service, "bye", fresh_session)
        assert service._session_langs.get(fresh_session) == "hi"


# ── Test 3: Session State Parity ──

class TestSessionParity:
    """Chat and voice pipelines must share profile, language, and history."""

    @pytest.mark.asyncio
    async def test_profile_extracted_by_both_pipelines(self, service, fresh_session):
        """Profile statements must be captured by both pipelines."""
        service._session_langs[fresh_session] = "en"
        await service.generate_response("my WBJEE rank is 48000", fresh_session)
        state = service._get_or_create_state(fresh_session)
        assert state.rank == 48000

        await _collect_stream(service, "my PCM is 76 percent", fresh_session)
        state = service._get_or_create_state(fresh_session)
        assert state.pcm_percent == 76.0

    @pytest.mark.asyncio
    async def test_stream_uses_same_profile(self, service, fresh_session, monkeypatch):
        """Streaming should see profile data captured by the chat pipeline."""

        async def fake_llm(messages, session_id, query, start, lang):
            profile = service._format_profile_context(session_id)
            if "48000" in profile:
                return "Your WBJEE rank is 48000."
            return "No profile found."

        monkeypatch.setattr(service, "_call_llm_with_tools", fake_llm)
        await service.generate_response("my WBJEE rank is 48000", fresh_session)
        voice = await _collect_stream(service, "do you remember my rank", fresh_session)
        assert "48000" in voice

    @pytest.mark.asyncio
    async def test_history_persists_across_queries(self, service, fresh_session):
        """Conversation history should persist across queries."""
        service._session_langs[fresh_session] = "en"

        await service.generate_response("what is CSE fee", fresh_session)
        history = service._get_session_history(fresh_session)
        assert len(history) >= 2  # At least user + assistant

        await service.generate_response("what about ECE fee", fresh_session)
        history = service._get_session_history(fresh_session)
        assert len(history) >= 4  # At least 2 user + 2 assistant


# ── Test 4: Response Payload Structure ──

class TestResponsePayload:
    """Verify the dict payload contract returned by generate_response."""

    @pytest.mark.asyncio
    async def test_payload_has_required_fields(self, service, fresh_session):
        """Every result should include answer, voice_text, source, latency_ms."""
        result = await service.generate_response("hi", fresh_session)
        assert isinstance(result, dict)
        assert result.get("answer")
        assert result.get("voice_text")
        assert result.get("source")
        assert isinstance(result.get("latency_ms"), (int, float))
        assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_short_circuit_source(self, service, fresh_session):
        """Deterministic branches are marked with their policy source."""
        result = await service.generate_response("hi", fresh_session)
        assert result["source"] == "greeting_deterministic"
        assert result.get("model") == "none"
        assert result.get("cache_hit") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
