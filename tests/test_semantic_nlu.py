"""Unit tests for the hybrid semantic NLU layer (fast path + LLM fallback)."""

import json

import pytest

from src.llm.interfaces import LLMResponse
from src.llm.mock import MockLLM
from src.understanding.semantic_nlu import SemanticNLU


def _nlu_json(intent="unknown", subtopic="", entities=None, confidence=0.9,
              language="en"):
    return json.dumps({
        "intent": intent,
        "subtopic": subtopic,
        "entities": entities or {},
        "language": language,
        "confidence": confidence,
    })


class _ScriptedLLM(MockLLM):
    def __init__(self, *responses):
        super().__init__()
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt, **kwargs):
        self.calls += 1
        self.last_prompt = prompt
        if self._responses:
            return LLMResponse(text=self._responses.pop(0))
        return LLMResponse(text="{}")


class TestFastPathMatrix:
    """Known and unseen paraphrases (typo / informal / Banglish / Hinglish)
    must resolve deterministically without any LLM call."""

    @pytest.mark.parametrize(
        "text, intent, entities, subtopic",
        [
            ("gen", "category", {"category": "general"}, ""),
            ("genral", "category", {"category": "general"}, ""),
            ("genral chatagory", "category", {"category": "general"}, ""),
            ("general category", "category", {"category": "general"}, ""),
            ("meri category general hai", "category", {"category": "general"}, ""),
            ("main general category se hun", "category", {"category": "general"}, ""),
            ("genral quota wala hun", "category", {"category": "general"}, ""),
            ("i am obc category", "category", {"category": "obc"}, ""),
            ("st student", "category", {"category": "st"}, ""),
            ("is there a scholarship for sc students?", "scholarship", {"category": "sc"}, ""),
            ("i need healp", "help_request", {}, ""),
            ("can u help me", "help_request", {}, ""),
            ("bhai help karo", "help_request", {}, ""),
            ("meri madad karo", "help_request", {}, ""),
            ("helo", "greeting", {}, ""),
            ("good morning", "greeting", {}, ""),
            ("who r yopu?", "self_introduction", {}, ""),
            ("tell me about yourself", "self_introduction", {}, ""),
            ("kya tum kaun ho?", "self_introduction", {}, ""),
            ("im back", "social_return", {}, ""),
            ("amar akta sub a back ase gehe", "backlog", {"subject_count": 1}, ""),
            ("i got back in one sub", "backlog", {"subject_count": 1}, ""),
            ("mujhe ek sub me back hai", "backlog", {"subject_count": 1}, ""),
            ("i failed in two subjects", "backlog", {"subject_count": 2}, ""),
            ("i have arrear in one paper", "backlog", {"subject_count": 1}, ""),
            ("how do I clear my backlogs?", "backlog", {}, "clearance"),
            ("what is the procedure to clear my arrear?", "backlog", {}, "clearance"),
            ("what is the fee?", "fee", {}, "total_cost"),
            ("fees kitna hai?", "fee", {}, "total_cost"),
            ("college ke fees kitne hain?", "fee", {}, "total_cost"),
            ("what is the total cost of btech?", "fee", {}, "total_cost"),
            ("bhai ece te bochore koto taka lage?", "fee", {"branch": "ECE"}, "total_cost"),
            ("what is the syllabus for cse?", "program", {"branch": "CSE"}, "curriculum"),
            ("cse me kaun se subjects hote hain?", "program", {"branch": "CSE"}, "curriculum"),
            ("what r the subjects in ece", "program", {"branch": "ECE"}, "curriculum"),
            ("ece curriculum kya hai?", "program", {"branch": "ECE"}, "curriculum"),
            ("what subjects do you teach?", "program", {}, "subjects"),
            ("kya yahan hostel hai?", "hostel", {}, "facilities"),
            ("hostel ka khana kaisa hai?", "hostel", {}, "facilities"),
            ("what facilities does the hostel have?", "hostel", {}, "facilities"),
            ("mujhe admission chahiye", "admission", {}, ""),
            ("how do i apply?", "admission", {}, ""),
            ("admission ke liye kya karna hoga?", "admission", {}, ""),
            ("can i get in with 15000 rank?", "admission", {"rank": 15000}, ""),
            ("25k, 65% , it", "admission", {"rank": 25000, "percentage": 65.0, "branch": "IT"}, ""),
            ("am i going to disqualify from scholership/", "scholarship", {}, "criteria"),
            ("am i eligible for scholarship with obc?", "scholarship", {"category": "obc"}, "criteria"),
            ("what's the cutoff for ECE?", "cutoff", {"branch": "ECE"}, ""),
            ("tell me about placements", "placement", {}, ""),
            ("loan mil sakta hai?", "loan", {}, ""),
            ("where is the college located?", "institution", {}, ""),
        ],
    )
    def test_fast_path_resolution(self, text, intent, entities, subtopic):
        nlu = SemanticNLU()
        result = nlu.interpret(text)
        assert result.intent == intent
        assert result.subtopic == subtopic
        assert result.source == "deterministic"
        assert result.confidence >= 0.55
        for key, value in entities.items():
            assert result.entities.get(key) == value

    def test_fast_path_never_calls_llm(self):
        llm = _ScriptedLLM()
        nlu = SemanticNLU(llm)
        for text, intent in [("gen", "category"), ("what is the fee?", "fee"),
                             ("i need healp", "help_request")]:
            assert nlu.interpret(text).intent == intent
        assert llm.calls == 0
        assert nlu.summary == {
            "deterministic_calls": 3, "fast_path_hits": 3,
            "llm_calls": 0, "llm_failures": 0,
        }


class TestOffTopicAndAmbiguity:
    def test_off_topic_is_unknown_low_confidence(self):
        nlu = SemanticNLU()
        result = nlu.interpret("what is the weather today?")
        assert result.intent == "unknown"
        assert result.confidence == 0.2
        assert result.source == "deterministic"

    def test_ambiguous_domain_reading_is_low_confidence(self):
        nlu = SemanticNLU()
        result = nlu.interpret("is hostel safe for girls?")
        assert result.intent == "unknown"
        assert result.confidence == 0.35

    def test_off_topic_routes_to_llm_when_present(self):
        llm = _ScriptedLLM(_nlu_json("unknown"))
        nlu = SemanticNLU(llm)
        result = nlu.interpret("what is the weather today?")
        assert llm.calls == 1
        assert result.source == "deterministic"
        assert result.unknown_override is True
        assert result.intent == "unknown"

    def test_ambiguous_routes_to_llm_when_present(self):
        llm = _ScriptedLLM(_nlu_json("hostel", "facilities", confidence=0.85))
        nlu = SemanticNLU(llm)
        result = nlu.interpret("is hostel safe for girls?")
        assert llm.calls == 1
        assert result.intent == "hostel"
        assert result.source == "semantic_nlu"
        assert result.confidence == 0.85


class TestContextFollowUps:
    def test_topic_continuation_fact(self):
        nlu = SemanticNLU()
        result = nlu.interpret("general category", topic="fee")
        assert result.intent == "category"
        assert result.entities["category"] == "general"
        assert result.entities["topic"] == "fee"

    def test_short_topic_continuation(self):
        nlu = SemanticNLU()
        result = nlu.interpret("yes", topic="admission")
        assert result.intent == "admission"
        assert result.confidence == 0.5

    def test_rank_continuation(self):
        nlu = SemanticNLU()
        result = nlu.interpret("25k", topic="admission")
        assert result.intent == "admission"
        assert result.entities["rank"] == 25000

    def test_topic_switch_to_new_domain(self):
        nlu = SemanticNLU()
        result = nlu.interpret("what about hostel", topic="fee")
        assert result.intent == "hostel"

    def test_fee_trigger_within_fee_topic(self):
        nlu = SemanticNLU()
        result = nlu.interpret("how much", topic="fee")
        assert result.intent == "fee"


class TestLLMFallback:
    def test_llm_returns_valid_json(self):
        llm = _ScriptedLLM(_nlu_json("backlog", "clearance",
                                     {"subject_count": 1}, confidence=0.9))
        nlu = SemanticNLU(llm)
        result = nlu.interpret("what is the weather today?")
        assert result.source == "semantic_nlu"
        assert result.intent == "backlog"
        assert result.subtopic == "clearance"

    def test_llm_unparseable_output_falls_back(self):
        llm = _ScriptedLLM("this is not json at all")
        nlu = SemanticNLU(llm)
        result = nlu.interpret("what is the weather today?")
        assert result.source == "deterministic"
        assert result.intent == "unknown"

    def test_llm_unexpected_label_falls_back(self):
        llm = _ScriptedLLM(_nlu_json("buy_pizza"))
        nlu = SemanticNLU(llm)
        result = nlu.interpret("what is the weather today?")
        assert result.source == "deterministic"

    def test_llm_raising_falls_back_and_counts_failure(self):
        class Boom(MockLLM):
            def generate(self, prompt, **kwargs):
                raise TimeoutError("slow")

        nlu = SemanticNLU(Boom())
        result = nlu.interpret("what is the weather today?")
        assert result.source == "deterministic"
        assert result.intent == "unknown"
        assert nlu.llm_failures == 1

    def test_missing_llm_never_calls_and_returns_fast(self):
        nlu = SemanticNLU()
        result = nlu.interpret("what is the weather today?")
        assert result.source == "deterministic"
        assert result.intent == "unknown"
        assert nlu.summary == {
            "deterministic_calls": 1, "fast_path_hits": 0,
            "llm_calls": 0, "llm_failures": 0,
        }

    def test_high_threshold_forces_llm_even_for_clear_intent(self):
        llm = _ScriptedLLM(_nlu_json("fee", "total_cost", confidence=0.9))
        nlu = SemanticNLU(llm, confidence_threshold=1.0)
        result = nlu.interpret("what is the fee?")
        assert llm.calls == 1
        assert result.intent == "fee"
        assert result.source == "semantic_nlu"

    def test_prompt_embeds_text_and_labels(self):
        llm = _ScriptedLLM(_nlu_json("unknown"))
        nlu = SemanticNLU(llm)
        nlu.interpret("what is the weather today?")
        assert "what is the weather today?" in llm.last_prompt
        assert "backlog" in llm.last_prompt
        assert "category" in llm.last_prompt
        assert "intent must be exactly one of" in llm.last_prompt


class TestParseLLM:
    def test_parse_plain_json(self):
        raw = _nlu_json("scholarship", "criteria", {"category": "obc"}, 0.88)
        result = SemanticNLU.parse_llm(raw)
        assert result is not None
        assert result.intent == "scholarship"
        assert result.subtopic == "criteria"
        assert result.entities["category"] == "obc"
        assert result.confidence == 0.88
        assert result.source == "semantic_nlu"

    def test_parse_code_fenced_json(self):
        raw = "```json\n" + _nlu_json("backlog") + "\n```"
        result = SemanticNLU.parse_llm(raw)
        assert result is not None
        assert result.intent == "backlog"

    def test_parse_invalid_json(self):
        assert SemanticNLU.parse_llm("not json") is None

    def test_parse_unexpected_label(self):
        assert SemanticNLU.parse_llm(_nlu_json("buy_pizza")) is None

    def test_parse_missing_intent(self):
        assert SemanticNLU.parse_llm('{"profile": {}}') is None

    def test_parse_empty(self):
        assert SemanticNLU.parse_llm("") is None

    def test_parse_clamps_confidence(self):
        result = SemanticNLU.parse_llm(_nlu_json("fee", confidence=9.9))
        assert result is not None
        assert result.confidence == 0.0

    def test_parse_tolerates_non_dict_entities(self):
        result = SemanticNLU.parse_llm(_nlu_json("fee", entities="none"))
        assert result is not None
        assert result.entities == {}


class TestFastReadingExposed:
    def test_fast_reading_static(self):
        result = SemanticNLU.fast_reading("what is the fee?", topic="fee")
        assert result.intent == "fee"
        assert result.source == "deterministic"
