"""Performance properties of the hybrid semantic NLU.

The fast deterministic reading must resolve clear turns without ever calling
the LLM, and stay fast (sub-millisecond median) so the hybrid adds no latency
on the common path. Absolute bounds are intentionally generous to stay
CI-safe; the call-count assertions are the real contract.
"""

import json
import time

from src.llm.interfaces import LLMResponse
from src.llm.mock import MockLLM
from src.understanding.semantic_nlu import SemanticNLU

_CLEAR_CORPUS = [
    "what is the fee?",
    "genral",
    "i need healp",
    "what is the syllabus for cse?",
    "kya yahan hostel hai?",
    "how do I clear my backlogs?",
    "tell me about placements",
    "am i eligible for scholarship with obc?",
    "where is the college located?",
    "what's the cutoff for ECE?",
]

_AMBIENT_CORPUS = [
    "what is the weather today?",
    "is hostel safe for girls?",
]


def _percentile(values, p):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p))]


class _QuietLLM(MockLLM):
    def __init__(self, response):
        super().__init__()
        self._response = response
        self.calls = 0

    def generate(self, prompt, **kwargs):
        self.calls += 1
        return LLMResponse(text=self._response)


class TestSemanticPerf:
    def test_fast_path_latency_percentiles(self):
        nlu = SemanticNLU()
        latencies = []
        for _ in range(30):
            for text in _CLEAR_CORPUS:
                start = time.perf_counter()
                nlu.interpret(text)
                latencies.append((time.perf_counter() - start) * 1000)

        assert _percentile(latencies, 0.50) < 2.0
        assert _percentile(latencies, 0.95) < 20.0

    def test_clear_corpus_never_calls_llm(self):
        llm = _QuietLLM(json.dumps({
            "intent": "unknown", "subtopic": "", "entities": {},
            "language": "en", "confidence": 0.1,
        }))
        nlu = SemanticNLU(llm)
        for text in _CLEAR_CORPUS:
            assert nlu.interpret(text).source == "deterministic"
        assert llm.calls == 0
        assert nlu.llm_calls == 0
        assert nlu.fast_path_hits == len(_CLEAR_CORPUS)
        assert nlu.deterministic_calls == len(_CLEAR_CORPUS)

    def test_ambiguous_corpus_delegates_to_llm(self):
        llm = _QuietLLM(json.dumps({
            "intent": "hostel", "subtopic": "facilities", "entities": {},
            "language": "en", "confidence": 0.8,
        }))
        nlu = SemanticNLU(llm)
        results = [nlu.interpret(text) for text in _AMBIENT_CORPUS]
        assert [r.source for r in results] == ["semantic_nlu", "semantic_nlu"]
        assert llm.calls == 2
        assert nlu.llm_calls == 2

    def test_missing_llm_still_resolves_every_input(self):
        nlu = SemanticNLU()
        for text in _CLEAR_CORPUS + _AMBIENT_CORPUS:
            assert nlu.interpret(text).source == "deterministic"
        assert nlu.llm_calls == 0
        assert nlu.llm_failures == 0

    def test_fast_reading_is_deterministic(self):
        nlu = SemanticNLU()
        first = [nlu.interpret(text).intent for text in _CLEAR_CORPUS]
        second = [nlu.interpret(text).intent for text in _CLEAR_CORPUS]
        assert first == second
