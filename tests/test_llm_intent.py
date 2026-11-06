"""Unit tests for the LLM-first structured understanding layer."""

import json

from src.llm.interfaces import LLMResponse
from src.llm.mock import MockLLM
from src.understanding.llm_intent import (
    CONVERSATIONAL_INTENTS,
    VALID_INTENTS,
    LLMFirstUnderstanding,
)


def _json(intent="admission", out_of_scope=False, profile=None):
    return json.dumps({
        "intent": intent,
        "out_of_scope": out_of_scope,
        "profile": profile or {},
    })


class _FakeLLM(MockLLM):
    def __init__(self, responses):
        super().__init__()
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt, **kwargs):
        self.calls += 1
        self.last_prompt = prompt
        if self._responses:
            return LLMResponse(text=self._responses.pop(0))
        return LLMResponse(text=_json("unknown"))


class TestLLMFirstUnderstanding:
    def test_plain_json(self):
        llm = _FakeLLM([_json("scholarship")])
        result = LLMFirstUnderstanding(llm).understand("am i going to disqualify from scholership/")
        assert result is not None
        assert result.intent == "scholarship"
        assert result.out_of_scope is False

    def test_code_fenced_json(self):
        llm = _FakeLLM(["```json\n" + _json("backlog") + "\n```"])
        result = LLMFirstUnderstanding(llm).understand("i got back in one sub")
        assert result is not None
        assert result.intent == "backlog"

    def test_profile_fields_are_validated(self):
        llm = _FakeLLM([json.dumps({
            "intent": "admission",
            "out_of_scope": False,
            "profile": {
                "rank": 25000, "pcm_percentage": 65, "category": "General",
                "interest": "IT", "budget_lakh": 8.0,
            },
        })])
        result = LLMFirstUnderstanding(llm).understand("25k, 65%, it")
        assert result.profile == {
            "rank": 25000, "pcm_percentage": 65.0, "category": "general",
            "interest": "IT", "budget_lakh": 8.0,
        }

    def test_string_profile_values_are_normalized(self):
        llm = _FakeLLM([json.dumps({
            "intent": "admission",
            "out_of_scope": False,
            "profile": {"rank": "25000", "pcm_percentage": "65", "interest": "IT"},
        })])
        result = LLMFirstUnderstanding(llm).understand("25k 65 it")
        assert result.profile["rank"] == 25000
        assert result.profile["pcm_percentage"] == 65.0
        assert result.profile["interest"] == "IT"

    def test_invalid_profile_values_are_dropped(self):
        llm = _FakeLLM([json.dumps({
            "intent": "admission",
            "out_of_scope": False,
            "profile": {
                "rank": "abc", "pcm_percentage": 150, "category": "weird",
                "interest": 123,
            },
        })])
        result = LLMFirstUnderstanding(llm).understand("x")
        assert result.profile == {}

    def test_out_of_scope_flag(self):
        llm = _FakeLLM([json.dumps({
            "intent": "unknown", "out_of_scope": True, "profile": {},
        })])
        result = LLMFirstUnderstanding(llm).understand("what is the weather?")
        assert result is not None
        assert result.out_of_scope is True

    def test_invalid_json_returns_none(self):
        llm = _FakeLLM(["this is not json at all"])
        assert LLMFirstUnderstanding(llm).understand("whatever") is None

    def test_unexpected_label_returns_none(self):
        llm = _FakeLLM([_json("buy_pizza")])
        assert LLMFirstUnderstanding(llm).understand("pizza") is None

    def test_missing_intent_field_returns_none(self):
        llm = _FakeLLM(['{"profile": {}}'])
        assert LLMFirstUnderstanding(llm).understand("x") is None

    def test_empty_response_returns_none(self):
        llm = _FakeLLM([""])
        assert LLMFirstUnderstanding(llm).understand("") is None

    def test_llm_raises_returns_none(self):
        class Boom(MockLLM):
            def generate(self, prompt, **kwargs):
                raise TimeoutError("slow")

        assert LLMFirstUnderstanding(Boom()).understand("i need help") is None

    def test_missing_llm_returns_none(self):
        assert LLMFirstUnderstanding(None).understand("i need help") is None

    def test_non_dict_profile_is_tolerated(self):
        llm = _FakeLLM(['{"intent": "fee", "out_of_scope": false, "profile": "none"}'])
        result = LLMFirstUnderstanding(llm).understand("how much are the fees?")
        assert result is not None
        assert result.intent == "fee"
        assert result.profile == {}

    def test_prompt_embeds_student_message(self):
        llm = _FakeLLM([_json()])
        c = LLMFirstUnderstanding(llm)
        c.understand("who r yopu?")
        assert "who r yopu?" in llm.last_prompt
        assert "backlog" in llm.last_prompt
        assert "pcm_percentage" in llm.last_prompt

    def test_valid_intents_are_complete(self):
        assert "backlog" in VALID_INTENTS
        assert "scholarship" in VALID_INTENTS
        assert "admission" in VALID_INTENTS
        assert "unknown" in VALID_INTENTS
        assert set(CONVERSATIONAL_INTENTS) == {
            "greeting", "help_request", "self_introduction", "social_return", "general",
        }
