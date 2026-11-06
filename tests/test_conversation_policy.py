"""
Conversation-policy regression tests.

The agent must answer a greeting, a bare help request, a question about the
assistant itself, and a social return directly — never defaulting into
admission-profile collection. Profile collection is a follow-up mechanism
reserved for explicit admission intents or questions that need personalization.

The conversational front door is a hybrid semantic NLU: a fast deterministic
semantic reading (typo/Banglish-aware) handles clear turns without an LLM, and
the LLM is consulted only when that reading is not confident. When the LLM is
absent, unparseable, or declines (unknown/out_of_scope), the deterministic
engine keeps control. Tests drive the LLM with a scripted MockLLM; the live
demo uses Groq.
"""

import json

from src.conversation.state import ConversationState
from src.llm.interfaces import LLMResponse
from src.llm.mock import MockLLM
from src.pipeline import PipelineOrchestrator
from src.understanding.engine import UnderstandingEngine


def _response(intent="unknown", out_of_scope=False, profile=None):
    return LLMResponse(text=json.dumps({
        "intent": intent,
        "out_of_scope": out_of_scope,
        "profile": profile or {},
    }))


class _RaisesLLM(MockLLM):
    """Simulates an unavailable / timed-out LLM for the understanding layer."""

    def generate(self, prompt, **kwargs):
        if "You are the understanding layer" in prompt:
            raise RuntimeError("LLM backend unavailable")
        return super().generate(prompt, **kwargs)


class _InvalidOutputLLM(MockLLM):
    """Simulates an LLM that returns non-JSON prose instead of the schema."""

    def generate(self, prompt, **kwargs):
        self.last_prompt = prompt
        return LLMResponse(text="I think the student is asking about weather.")


class ScriptedLLM(MockLLM):
    """Scripted MockLLM for the understanding layer.

    Understanding prompts embed the student message, so the mapping is keyed on
    the exact message text. All other (composer) prompts fall through to the
    plain MockLLM default.
    """

    def __init__(self, mapping: dict[str, dict]):
        super().__init__()
        self.mapping = mapping
        self.understanding_calls = 0

    def generate(self, prompt, **kwargs):
        self.last_prompt = prompt
        if "You are the understanding layer" in prompt:
            self.understanding_calls += 1
            marker = "Student message: "
            message = prompt.split(marker, 1)[1].splitlines()[0].strip()
            for phrase, resp in self.mapping.items():
                if message == phrase.strip():
                    return _response(**resp)
            return _response()
        return super().generate(prompt, **kwargs)


_CANONICAL = {
    "hi": {"intent": "greeting"},
    "helo": {"intent": "greeting"},
    "i need help": {"intent": "help_request"},
    "i need healp": {"intent": "help_request"},
    "who are you?": {"intent": "self_introduction"},
    "who r yopu?": {"intent": "self_introduction"},
    "im back": {"intent": "social_return"},
    "am i going to disqualify from scholership/": {"intent": "scholarship"},
    "i got back in one sub": {"intent": "backlog"},
    "what is the procedure to clear my arrear?": {"intent": "backlog"},
    "what is the weather today?": {"intent": "unknown", "out_of_scope": True},
    "25k, 65% , it": {
        "intent": "admission",
        "profile": {"rank": 25000, "pcm_percentage": 65.0, "interest": "IT"},
    },
}


def _pipeline(llm=None) -> PipelineOrchestrator:
    return PipelineOrchestrator(llm=llm or ScriptedLLM(dict(_CANONICAL)))


def _run(text, session_id="s", pipeline=None):
    pipe = pipeline or _pipeline()
    state = ConversationState(session_id=session_id, profile={})
    result = pipe.run(text, state=state)
    assert len(result.errors) == 0
    return result


def _content(result) -> str:
    if result.plan and result.plan.turns:
        return " ".join(t.content for t in result.plan.turns)
    return result.response or ""


class TestConversationPolicy:
    def test_greeting_does_not_collect_profile(self):
        """'hi' must be greeted — never asked for a WBJEE rank."""
        result = _run("hi")
        assert result.decision.action == "greet"
        assert result.reasoning.current_problem == "needs_greeting"
        content = _content(result)
        assert "WBJEE rank" not in content
        assert "Hi!" in content

    def test_help_request_does_not_collect_profile(self):
        """'i need help' must offer topics — never ask for the profile."""
        result = _run("i need help")
        assert result.decision.action == "offer_help"
        assert result.reasoning.current_problem == "needs_help_request"
        content = _content(result)
        assert "WBJEE rank" not in content
        assert "help" in content.lower()

    def test_who_are_you_does_not_collect_profile(self):
        """'who are you?' gets a self-introduction, not a profile ask."""
        result = _run("who are you?")
        assert result.decision.action == "introduce"
        assert result.reasoning.current_problem == "needs_self_introduction"
        content = _content(result)
        assert "WBJEE rank" not in content
        assert "assistant" in content.lower()

    def test_informational_program_question_answers_first(self):
        """A curriculum question is answered before any admission follow-up."""
        result = _run("what do we study in ECE?")
        assert result.decision.action == "provide_program_curriculum"
        content = _content(result)
        assert "ECE covers" in content
        assert "Are you looking for admission to ECE?" in content

    def test_explicit_admission_enters_profile_collection(self):
        """A real admission request still starts profile collection."""
        result = _run("I'm looking for admission in ECE")
        assert result.decision.action == "collect_profile"
        content = _content(result)
        assert "rank" in content.lower()

    def test_admission_with_supplied_rank_does_not_ask_again(self):
        """A supplied rank must not be re-asked; remaining fields only."""
        result = _run("I want admission in ECE, my WBJEE rank is 80000")
        assert result.decision.action == "collect_profile"
        content = _content(result)
        assert "WBJEE rank" not in content
        assert "category" in content.lower()

    def test_greeting_then_admission_still_enters_flow(self):
        """Session isolation: a greeting first does not suppress a later
        explicit admission request."""
        state = ConversationState(session_id="iso", profile={})
        pipeline = _pipeline()
        first = pipeline.run("hi", state=state)
        assert first.decision.action == "greet"
        second = pipeline.run("I want admission in ECE, my WBJEE rank is 80000", state=state)
        assert second.decision.action == "collect_profile"
        assert "WBJEE rank" not in _content(second)


class TestHybridSemanticUnderstanding:
    """Conversation-policy tests for the hybrid semantic NLU.

    The hybrid runs a fast deterministic semantic reading (typo/Banglish-aware)
    and only consults the LLM when that reading is not confident. The
    conversational front door is therefore handled on the fast path without an
    LLM call; genuinely ambiguous turns still fall back to the LLM safely.
    """

    def test_typo_help_request_routes_to_offer_help(self):
        """'i need healp' resolves on the fast path to offer_help (no LLM)."""
        llm = ScriptedLLM(dict(_CANONICAL))
        result = _run("i need healp", pipeline=_pipeline(llm))
        assert result.understanding.intent.primary == "help_request"
        assert result.decision.action == "offer_help"
        assert result.reasoning.current_problem == "needs_help_request"
        content = _content(result)
        assert "WBJEE rank" not in content
        assert "help" in content.lower()
        assert llm.understanding_calls == 0
        assert result.understanding.metadata["nlu"]["source"] == "deterministic"

    def test_typo_self_introduction_routes(self):
        """'who r yopu?' must resolve to a self-introduction on the fast path."""
        result = _run("who r yopu?")
        assert result.understanding.intent.primary == "self_introduction"
        assert result.decision.action == "introduce"
        assert result.reasoning.current_problem == "needs_self_introduction"

    def test_typo_greeting_routes(self):
        """'helo' must be treated as a greeting."""
        result = _run("helo")
        assert result.understanding.intent.primary == "greeting"
        assert result.decision.action == "greet"
        assert result.reasoning.current_problem == "needs_greeting"

    def test_social_return_routes_to_greeting(self):
        """'im back' resumes the chat, not collect a profile."""
        result = _run("im back")
        assert result.understanding.intent.primary == "social_return"
        assert result.decision.action == "greet"
        assert result.reasoning.current_problem == "needs_greeting"
        assert "WBJEE rank" not in _content(result)

    def test_scholership_typo_routes_to_scholarship(self):
        """'scholership' must resolve to scholarship guidance on the fast path."""
        result = _run("am i going to disqualify from scholership/")
        assert result.understanding.intent.primary == "scholarship"
        assert result.decision.action == "provide_scholarship_info"
        assert result.reasoning.current_problem == "needs_scholarship_information"
        assert "WBJEE rank" not in _content(result)

    def test_backlog_routes_to_backlog_information(self):
        """Backlog/arrear turns must resolve to backlog guidance, not social
        return and not a profile ask."""
        for text in ("i got back in one sub", "what is the procedure to clear my arrear?"):
            result = _run(text)
            assert result.understanding.intent.primary == "backlog"
            assert result.decision.action == "provide_backlog_info"
            assert result.reasoning.current_problem == "needs_backlog_information"
            content = _content(result)
            assert "WBJEE rank" not in content
            assert "backlog" in content.lower() or "arrear" in content.lower()

    def test_banglish_backlog_with_subject_count(self):
        """Banglish backlog with a subject count is understood on the fast path."""
        result = _run("amar akta sub a back ase gehe")
        assert result.understanding.intent.primary == "backlog"
        assert result.understanding.metadata["nlu"]["entities"]["subject_count"] == 1
        assert result.decision.action == "provide_backlog_info"

    def test_shorthand_profile_extraction(self):
        """'25k, 65% , it' must fill rank/PCM/interest from the NLU and only ask
        for the remaining field (category), never re-ask what was stated."""
        result = _run("25k, 65% , it")
        profile = result.understanding.profile
        assert profile.academic.rank == 25000
        assert profile.academic.pcm_percentage == 65.0
        assert profile.career.interest == "IT"
        assert result.decision.action == "collect_profile"
        content = _content(result)
        assert "WBJEE rank" not in content
        assert "PCM percentage" not in content
        assert "category" in content.lower()

    def test_shorthand_profile_persists_across_turns(self):
        """NLU-extracted profile fields must persist in session state."""
        state = ConversationState(session_id="shorthand", profile={})
        pipeline = _pipeline()
        pipeline.run("25k, 65% , it", state=state)
        result = pipeline.run("ok tell me my options", state=state)
        assert result.understanding.profile.academic.rank == 25000

    def test_out_of_scope_stays_clarify(self):
        """A weather question consults the LLM, which declines, so it stays
        unknown → clarify — never profile collection."""
        result = _run("what is the weather today?")
        assert result.understanding.intent.primary == "unknown"
        assert result.decision.action == "clarify"
        assert result.reasoning.current_problem == "needs_clarification"

    def test_domain_questions_stay_fast_path(self):
        """A clear domain question is handled on the fast path without the LLM."""
        llm = ScriptedLLM({})
        result = _run("what are the subjects in ECE?", pipeline=_pipeline(llm))
        assert llm.understanding_calls == 0
        assert result.understanding.intent.primary == "program"
        assert result.decision.action == "provide_program_curriculum"

    def test_multi_turn_session(self):
        """A full session mixing clean and typo turns routes each on the fast
        path without a single LLM call."""
        llm = ScriptedLLM(dict(_CANONICAL))
        pipe = _pipeline(llm)
        state = ConversationState(session_id="multi", profile={})

        r1 = pipe.run("hi", state=state)
        assert r1.decision.action == "greet"
        r2 = pipe.run("i need healp", state=state)
        assert r2.decision.action == "offer_help"
        r3 = pipe.run("im back", state=state)
        assert r3.decision.action == "greet"
        r4 = pipe.run("what are the subjects in ECE?", state=state)
        assert r4.decision.action == "provide_program_curriculum"
        assert llm.understanding_calls == 0

    def test_unavailable_llm_falls_back_to_deterministic(self):
        """An unavailable LLM must degrade safely to the existing clarify path."""
        result = _run("what is the weather today?", pipeline=_pipeline(_RaisesLLM()))
        assert result.understanding.intent.primary == "unknown"
        assert result.decision.action == "clarify"
        assert result.reasoning.current_problem == "needs_clarification"

    def test_invalid_llm_output_falls_back_to_deterministic(self):
        """Non-JSON LLM output must degrade safely to the deterministic result."""
        result = _run("what is the weather today?", pipeline=_pipeline(_InvalidOutputLLM()))
        assert result.understanding.intent.primary == "unknown"
        assert result.decision.action == "clarify"
        assert result.reasoning.current_problem == "needs_clarification"

    def test_unknown_label_keeps_deterministic(self):
        """An explicit 'unknown' label from the LLM keeps the deterministic path."""
        llm = ScriptedLLM({"what is the weather today?": {"intent": "unknown"}})
        result = _run("what is the weather today?", pipeline=_pipeline(llm))
        assert result.understanding.intent.primary == "unknown"
        assert result.decision.action == "clarify"

    def test_unexpected_label_is_rejected(self):
        """A label outside the vocabulary is rejected -> deterministic path."""
        llm = ScriptedLLM({"what is the weather today?": {"intent": "buy_pizza"}})
        result = _run("what is the weather today?", pipeline=_pipeline(llm))
        assert result.understanding.intent.primary == "unknown"
        assert result.decision.action == "clarify"

    def test_explicit_mock_llm_keeps_engine_deterministic_but_hybrid(self):
        """An explicit MockLLM (whose output is not JSON) leaves the engine
        deterministic in control — including the new deterministic backlog and
        typo'd scholarship routing via the NLU fast path."""
        pipe = PipelineOrchestrator(llm=MockLLM())
        assert pipe.understanding._semantic_nlu is not None
        result = _run("i got back in one sub", pipeline=pipe)
        assert result.understanding.intent.primary == "backlog"
        assert result.decision.action == "provide_backlog_info"

        result = _run("am i going to disqualify from scholership/", pipeline=pipe)
        assert result.understanding.intent.primary == "scholarship"
        assert result.decision.action == "provide_scholarship_info"


def _sem(intent="unknown", confidence=0.9, source="deterministic"):
    from src.understanding.semantic_nlu import SemanticUnderstanding
    return SemanticUnderstanding(
        intent=intent, confidence=confidence, source=source,
    )


class TestOverridePolicy:
    """Unit tests for the semantic-NLU-overrides-deterministic policy."""

    def test_domain_label_overrides_unknown(self):
        sem = _sem("scholarship", 0.95)
        assert UnderstandingEngine()._should_apply_semantic_intent("unknown", 0.0, "scholarship", sem) is True

    def test_domain_label_does_not_override_confident_domain(self):
        """A confident deterministic domain reading is trusted (fast path)."""
        sem = _sem("backlog", 0.95)
        assert UnderstandingEngine()._should_apply_semantic_intent("fee", 0.35, "backlog", sem) is False

    def test_domain_label_overrides_weak_domain(self):
        sem = _sem("backlog", 0.95)
        assert UnderstandingEngine()._should_apply_semantic_intent("fee", 0.09, "backlog", sem) is True

    def test_conversational_label_does_not_demote_confident_domain(self):
        sem = _sem("greeting", 0.97)
        assert UnderstandingEngine()._should_apply_semantic_intent("admission", 0.3, "greeting", sem) is False

    def test_conversational_label_overrides_unknown(self):
        sem = _sem("help_request", 0.98)
        assert UnderstandingEngine()._should_apply_semantic_intent("unknown", 0.0, "help_request", sem) is True

    def test_closing_never_demotes_a_topic(self):
        """'thank you, we will think about IT' must not flip IT → general."""
        sem = _sem("general", 0.9)
        assert UnderstandingEngine()._should_apply_semantic_intent("it", 0.15, "general", sem) is False

    def test_unknown_never_overrides(self):
        sem = _sem("unknown", 0.2)
        assert UnderstandingEngine()._should_apply_semantic_intent("unknown", 0.0, "unknown", sem) is False

    def test_low_confidence_fast_path_does_not_override(self):
        sem = _sem("backlog", 0.5, source="deterministic")
        assert UnderstandingEngine()._should_apply_semantic_intent("unknown", 0.0, "backlog", sem) is False

    def test_agreeing_reading_keeps_deterministic(self):
        """When the semantic reading agrees with the winner, no override fires."""
        sem = _sem("admission", 0.95)
        assert UnderstandingEngine()._should_apply_semantic_intent("admission", 0.16, "admission", sem) is False
