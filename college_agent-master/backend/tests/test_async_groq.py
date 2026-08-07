"""Regression tests: verify the Groq client integration preserves behavior.

The legacy monolith routes every LLM call through ``_call_llm_with_tools``,
which wraps the sync Groq client in ``asyncio.to_thread`` so the event loop
is never blocked. ``generate_response`` awaits that helper; ``stream_response``
additionally guards on ``self.async_client`` before yielding.
"""

import inspect

import pytest


class TestAsyncClientBehavior:
    """Verify async-safe client behavior is preserved."""

    def test_async_client_is_available(self):
        from app.config import settings

        assert settings.async_groq_client is not None, (
            "async_groq_client must be initialized. "
            "Check config.py — both groq_client and async_groq_client "
            "are set together in __init__."
        )

    def test_async_client_is_not_sync_client(self):
        from app.config import settings

        assert settings.async_groq_client is not settings.groq_client

    def test_llm_call_is_non_blocking(self):
        """The LLM call must be wrapped in asyncio.to_thread, never awaited
        directly on the sync client, so the event loop stays responsive."""
        from app.services.llm.groq_service import GroqService

        source = inspect.getsource(GroqService._call_llm_with_tools)
        assert "asyncio.to_thread" in source, (
            "_call_llm_with_tools must offload the sync client to a thread"
        )
        assert "self.client.chat.completions.create" in source

    def test_generate_response_awaits_llm_helper(self):
        """generate_response must await _call_llm_with_tools (not block)."""
        from app.services.llm.groq_service import GroqService

        source = inspect.getsource(GroqService.generate_response)
        assert "await self._call_llm_with_tools" in source, (
            "generate_response must await the non-blocking LLM helper"
        )

    def test_stream_response_guards_on_async_client(self):
        """stream_response must guard on self.async_client and await the
        same non-blocking helper."""
        from app.services.llm.groq_service import GroqService

        source = inspect.getsource(GroqService.stream_response)
        assert "self.async_client" in source
        assert "await self._call_llm_with_tools" in source

    def test_fallback_models_preserved(self):
        """The model fallback chain must be unchanged."""
        from app.services.llm.groq_service import FALLBACK_MODELS

        assert "llama-3.1-8b-instant" in FALLBACK_MODELS
        assert "groq/compound-mini" in FALLBACK_MODELS


class TestGenerateResponseApiContract:
    """Verify the return dict shape is unchanged."""

    @pytest.mark.asyncio
    async def test_return_contract(self, mocker):
        from app.services.llm.groq_service import GroqService

        svc = GroqService()

        # Mock the non-blocking LLM helper to avoid real API calls
        svc._call_llm_with_tools = mocker.AsyncMock(
            return_value="Mocked answer about B.Tech fees."
        )
        # Also mock dependencies so the pipeline short-circuits to the LLM path
        svc._rate_limiter.acquire = mocker.AsyncMock(return_value=0)
        svc._rate_limiter.record_success = mocker.AsyncMock()
        svc._cache = None
        svc._sessions = {}
        svc._session_langs = {}

        mocker.patch.object(svc, "_retrieve_context", return_value=("", 0.0))
        mocker.patch.object(svc, "_get_session_history", return_value=[])
        mocker.patch.object(svc, "_validate_answer", return_value=(True, ""))
        mocker.patch.object(svc, "_is_greeting", return_value=False)
        mocker.patch.object(svc, "_is_out_of_domain", return_value=False)
        mocker.patch.object(svc, "_detect_exit_intent", return_value=None)
        mocker.patch.object(svc, "_validate_transcript", return_value=None)
        mocker.patch.object(svc, "_detect_noisy_transcript", return_value=False)
        mocker.patch.object(svc, "_resolve_short_followup", return_value="")
        mocker.patch.object(svc, "_prepare_for_tts", side_effect=lambda x, y: x)
        mocker.patch.object(svc, "_safe_fallback", return_value="fallback")
        mocker.patch.object(svc, "_format_kb_context", return_value="")
        mocker.patch.object(svc, "_format_profile_context", return_value="")

        result = await svc.generate_response("What is the B.Tech fee?")

        assert "answer" in result
        assert "source" in result
        assert "model" in result
        assert "latency_ms" in result
        assert "hallucination_validated" in result
        assert "tokens" in result
        assert "cache_hit" in result
        assert result["answer"] == "Mocked answer about B.Tech fees."
        assert result["source"] == "llm_tools"
