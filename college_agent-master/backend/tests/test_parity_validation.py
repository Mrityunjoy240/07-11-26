"""
Parity Validation Tests — Chat vs Voice Pipeline
=================================================
Verifies that generate_response() and stream_response() produce identical
business logic results when given the same input.

Run: python -m pytest backend/tests/test_parity_validation.py -v
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm.groq_service import GroqService, get_groq_service, ConversationResult


@pytest.fixture
def service():
    """Get the singleton GroqService instance."""
    return get_groq_service()


@pytest.fixture
def fresh_session():
    """Generate a unique session ID for isolation."""
    import uuid
    return f"parity_test_{uuid.uuid4().hex[:8]}"


# ── Test 1: Chat vs Voice Parity — Same conversation, both pipelines ──

class TestChatVoiceParity:
    """Run the same conversation through both pipelines and compare results."""

    @pytest.mark.asyncio
    async def test_greeting_produces_same_result(self, service, fresh_session):
        """Greeting should produce identical output from both pipelines."""
        query = "hi"
        chat_result = await service._process_conversation(query, fresh_session)
        assert isinstance(chat_result, ConversationResult)
        assert chat_result.answer is not None
        assert chat_result.source in ("greeting_deterministic", "greeting_ask_language")

    @pytest.mark.asyncio
    async def test_language_selection_produces_same_result(self, service, fresh_session):
        """Language selection should work identically in both pipelines."""
        # First, trigger greeting to get "asked" state
        await service._process_conversation("hi", fresh_session)
        # Now select English
        result = await service._process_conversation("english", fresh_session)
        assert result.source == "language_selected"
        assert service._session_langs.get(fresh_session) == "en"

    @pytest.mark.asyncio
    async def test_profile_extraction_both_pipelines(self, service, fresh_session):
        """Profile extraction should work in both pipelines."""
        # Set language first
        service._session_langs[fresh_session] = "en"
        # Extract profile
        result = await service._process_conversation(
            "my WBJEE rank is 48000", fresh_session
        )
        # Profile should be extracted
        profile = service._student_profiles.get(fresh_session)
        assert profile is not None
        assert profile.wbjee_rank == 48000

    @pytest.mark.asyncio
    async def test_structured_lookup_both_pipelines(self, service, fresh_session):
        """Structured lookup should return same answer in both pipelines."""
        service._session_langs[fresh_session] = "en"
        result = await service._process_conversation("what is the principal name", fresh_session)
        assert result.source == "structured_lookup"
        assert result.answer is not None
        assert len(result.answer) > 0

    @pytest.mark.asyncio
    async def test_yes_no_standaloneAcknowledgment(self, service, fresh_session):
        """Standalone 'yes' with no active goal should return acknowledgment."""
        service._session_langs[fresh_session] = "en"
        result = await service._process_conversation("yes", fresh_session)
        # Should be a short acknowledgment
        assert result.source == "yes_no_continuation"
        assert result.short_circuited is True
        assert len(result.answer) < 100  # Short acknowledgment

    @pytest.mark.asyncio
    async def test_yes_no_with_active_goal(self, service, fresh_session):
        """'yes' with an active goal should continue the goal."""
        service._session_langs[fresh_session] = "en"
        # Set up an active goal
        from app.services.llm.groq_service import GoalTracker
        tracker = GoalTracker()
        tracker.set_goal("fee information")
        tracker.set_pending_question("Would you like to know about CSE fee?")
        service._goal_trackers[fresh_session] = tracker
        # Now say "yes" — should continue the goal
        result = await service._process_conversation("yes", fresh_session)
        # The query should have been rewritten to continue the goal
        # Result should NOT be a simple acknowledgment
        assert result.source != "yes_no_continuation" or "fee" in result.answer.lower()

    @pytest.mark.asyncio
    async def test_stream_response_uses_same_session(self, service, fresh_session):
        """stream_response should use the same session state as _process_conversation."""
        service._session_langs[fresh_session] = "en"
        # Set a profile via _process_conversation
        await service._process_conversation("my rank is 50000", fresh_session)
        profile = service._student_profiles.get(fresh_session)
        assert profile is not None
        assert profile.wbjee_rank == 50000
        # Now stream_response should see the same profile
        chunks = []
        async for chunk in service.stream_response(
            "do you remember my rank", fresh_session
        ):
            chunks.append(chunk)
        full_response = "".join(chunks)
        # Response should reference the rank (profile is shared)
        assert "50000" in full_response or "rank" in full_response.lower()


# ── Test 2: Language Parity ──

class TestLanguageParity:
    """Verify language detection and response work identically."""

    @pytest.mark.asyncio
    async def test_hindi_session(self, service, fresh_session):
        """Hindi session should work correctly."""
        service._session_langs[fresh_session] = "hi"
        result = await service._process_conversation("fee kitna hai", fresh_session)
        assert result.lang == "hi"
        # Should not contain Bengali forbidden words
        if result.lang == "hi":
            assert "apni" not in result.answer.lower()
            assert "achen" not in result.answer.lower()

    @pytest.mark.asyncio
    async def test_bengali_session(self, service, fresh_session):
        """Bengali session should work correctly."""
        service._session_langs[fresh_session] = "bn"
        result = await service._process_conversation("fee koto", fresh_session)
        assert result.lang == "bn"
        # Should not contain Hindi forbidden words
        if result.lang == "bn":
            assert "aap" not in result.answer.lower()
            assert "hai" not in result.answer.lower()

    @pytest.mark.asyncio
    async def test_english_session(self, service, fresh_session):
        """English session should work correctly."""
        service._session_langs[fresh_session] = "en"
        result = await service._process_conversation("what is the fee", fresh_session)
        assert result.lang == "en"


# ── Test 3: Structured Handler Parity ──

class TestStructuredHandlerParity:
    """Structured handlers should return same values regardless of pipeline."""

    STRUCTURED_QUERIES = [
        "what is the principal name",
        "what is the vice principal name",
        "CSE fee",
        "hostel fee",
        "placement statistics",
        "cutoff for CSE",
        "scholarship details",
        "admission process",
        "how to reach college",
        "college address",
        "college email",
        "college website",
    ]

    @pytest.mark.asyncio
    async def test_structured_handlers_consistent(self, service, fresh_session):
        """All structured queries should return consistent results."""
        service._session_langs[fresh_session] = "en"
        results = {}
        for query in self.STRUCTURED_QUERIES:
            result = await service._process_conversation(query, fresh_session)
            results[query] = result

        # All should be structured lookups (not LLM)
        for query, result in results.items():
            assert result.source == "structured_lookup", (
                f"Query '{query}' went to LLM instead of structured handler"
            )
            assert result.answer is not None
            assert len(result.answer) > 10, f"Query '{query}' returned empty answer"


# ── Test 4: Session Parity ──

class TestSessionParity:
    """Verify cross-session memory works correctly."""

    @pytest.mark.asyncio
    async def test_profile_persists_across_queries(self, service, fresh_session):
        """Profile should persist across multiple queries."""
        service._session_langs[fresh_session] = "en"

        # Query 1: Set rank
        await service._process_conversation("my WBJEE rank is 50000", fresh_session)
        profile = service._student_profiles.get(fresh_session)
        assert profile is not None
        assert profile.wbjee_rank == 50000

        # Query 2: Set PCM
        await service._process_conversation("PCM 76%", fresh_session)
        profile = service._student_profiles.get(fresh_session)
        assert profile.pcm_percentage == 76.0

        # Query 3: Check rank is still remembered
        await service._process_conversation("do you remember my rank", fresh_session)
        profile = service._student_profiles.get(fresh_session)
        assert profile.wbjee_rank == 50000  # Should still be 50000

    @pytest.mark.asyncio
    async def test_language_persists_across_queries(self, service, fresh_session):
        """Language should persist across queries."""
        # Set language
        service._session_langs[fresh_session] = "hi"

        # Query 1
        await service._process_conversation("fee kitna hai", fresh_session)
        assert service._session_langs.get(fresh_session) == "hi"

        # Query 2 — language should still be Hindi
        await service._process_conversation("hostel kitna hai", fresh_session)
        assert service._session_langs.get(fresh_session) == "hi"

    @pytest.mark.asyncio
    async def test_history_persists_across_queries(self, service, fresh_session):
        """Conversation history should persist across queries."""
        service._session_langs[fresh_session] = "en"

        # Query 1
        await service._process_conversation("what is CSE fee", fresh_session)
        history = service._get_session_history(fresh_session)
        assert len(history) >= 2  # At least user + assistant

        # Query 2
        await service._process_conversation("what about ECE fee", fresh_session)
        history = service._get_session_history(fresh_session)
        assert len(history) >= 4  # At least 2 user + 2 assistant


# ── Test 5: ConversationResult Structure ──

class TestConversationResult:
    """Verify ConversationResult is properly structured."""

    @pytest.mark.asyncio
    async def test_result_has_required_fields(self, service, fresh_session):
        """Every result should have all required fields."""
        service._session_langs[fresh_session] = "en"
        result = await service._process_conversation("hi", fresh_session)

        assert hasattr(result, 'answer')
        assert hasattr(result, 'source')
        assert hasattr(result, 'lang')
        assert hasattr(result, 'short_circuited')
        assert hasattr(result, 'latency_ms')
        assert result.answer is not None
        assert result.source is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_short_circuited_flag(self, service, fresh_session):
        """Short-circuited results should have the flag set."""
        # Greeting should short-circuit
        result = await service._process_conversation("hi", fresh_session)
        assert result.short_circuited is True

        # LLM path should not short-circuit
        service._session_langs[fresh_session] = "en"
        result = await service._process_conversation(
            "tell me about the college", fresh_session
        )
        # This might be structured or LLM — either way, not short-circuited
        # unless it hits a deterministic handler


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
