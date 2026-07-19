"""
Golden Conversation Suite — real multi-turn admission conversations.

These are NOT unit tests. They simulate real student conversations
through the full pipeline (Understanding → Reasoning → Brain → Decision → Planner → LLM).

Each conversation tests a different scenario:
  C1: Standard admission — rank, PCM, interest → branch recommendations
  C2: Backlog + rules + supplementary + placement impact + reassure
  C3: Parents asking about fees, loan, installments, scholarship
  C4: Low rank → alternative branches, trade-offs, backup plan
  C5: Hostel — safety, girls hostel, transport, mess

Run: pytest tests/test_golden_conversations.py -v
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.conversation.state import ConversationState
from src.llm.interfaces import LLMResponse
from src.pipeline import PipelineOrchestrator


@dataclass
class TurnLog:
    user: str
    response: str
    action: str
    confidence: float
    errors: list[str]
    has_plan: bool


@dataclass
class ConversationLog:
    name: str
    turns: list[TurnLog] = field(default_factory=list)
    all_ok: bool = True


class RecordingMockLLM:
    """Mock LLM that echoes the first turn's content from the plan embedded in the prompt."""

    def __init__(self) -> None:
        self.last_prompt: str = ""
        self.call_count: int = 0

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        self.last_prompt = prompt
        self.call_count += 1
        text = self._extract_response(prompt)
        return LLMResponse(text=text)

    def _extract_response(self, prompt: str) -> str:
        lines = prompt.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("1. [") and "] " in line:
                content = line.split("] ", 1)[1]
                content = content.split(" [expects:")[0]
                return content
        return "I understand. Could you tell me more about what you're looking for?"


def _update_state_from_understanding(state: ConversationState, understanding: Any, response_text: str = "") -> None:
    if not understanding:
        return
    for f in getattr(understanding, "facts", []):
        if hasattr(f, "field") and hasattr(f, "value"):
            state.profile[f.field] = f.value
    state.history.append({"role": "user", "content": str(getattr(understanding, "text", ""))[:200]})
    if response_text:
        state.history.append({"role": "assistant", "content": response_text[:200]})


def run_conversation(
    name: str,
    turns: list[str],
    state: ConversationState | None = None,
) -> ConversationLog:
    llm = RecordingMockLLM()
    pipeline = PipelineOrchestrator(
        llm=llm,
    )
    log = ConversationLog(name=name)
    state = state or ConversationState(session_id=name, profile={})

    for user_msg in turns:
        result = pipeline.run(user_msg, state=state)

        if result.understanding:
            _update_state_from_understanding(state, result.understanding, result.response)

        action = result.decision.action if result.decision else "none"
        log.turns.append(TurnLog(
            user=user_msg[:80],
            response=result.response[:120] if result.response else "",
            action=action,
            confidence=result.confidence,
            errors=list(result.errors),
            has_plan=result.plan is not None,
        ))

        if result.errors:
            log.all_ok = False

    return log


# ---------------------------------------------------------------------------
# Conversation 1: Standard admission
# ---------------------------------------------------------------------------

def test_c1_standard_admission():
    """Student: 48k rank, 82 PCM, interested in AI → branch recommendations."""
    log = run_conversation("C1-Standard-Admission", [
        "I got 48k rank in WBJEE",
        "my PCM percentage is 82",
        "I am interested in AI and machine learning",
    ])

    for i, t in enumerate(log.turns):
        assert not t.errors, f"Turn {i+1} errored: {t.errors}"
        assert t.response, f"Turn {i+1} has empty response"
        assert t.has_plan, f"Turn {i+1} has no plan"

    assert log.turns[-1].action in ("recommend_branches", "collect_profile", "provide_branch_guidance")


# ---------------------------------------------------------------------------
# Conversation 2: Backlog + rules + supplementary + placement impact + reassure
# ---------------------------------------------------------------------------

def test_c2_backlog_scenario():
    """Student worried about backlog, rules, supplementary exams, placement impact."""
    state = ConversationState(session_id="c2", profile={"rank": 55000, "pcm_percentage": 72})
    log = run_conversation("C2-Backlog-Scenario", [
        "I have a backlog in Mathematics. Will that affect my admission?",
        "Can I appear for supplementary exams?",
        "Will backlogs affect my placement opportunities?",
        "I'm really worried I won't get a good college because of this",
    ], state=state)

    for i, t in enumerate(log.turns):
        assert not t.errors, f"Turn {i+1} errored: {t.errors}"
        assert t.response, f"Turn {i+1} has empty response"

    assert log.all_ok


# ---------------------------------------------------------------------------
# Conversation 3: Parents — fees, loan, installments, scholarship
# ---------------------------------------------------------------------------

def test_c3_parents_fees_scenario():
    """Parents asking about fee structure, education loan, installments, scholarships."""
    state = ConversationState(session_id="c3", profile={
        "rank": 18000, "pcm_percentage": 88, "category": "obc",
    })
    log = run_conversation("C3-Parents-Fees", [
        "What is the fee structure for CSE?",
        "Do you offer education loan assistance?",
        "Can we pay fees in installments?",
        "Is there any scholarship for OBC students?",
    ], state=state)

    for i, t in enumerate(log.turns):
        assert not t.errors, f"Turn {i+1} errored: {t.errors}"
        assert t.response, f"Turn {i+1} has empty response"

    assert log.all_ok


# ---------------------------------------------------------------------------
# Conversation 4: Low rank → alternatives, trade-offs, backup plan
# ---------------------------------------------------------------------------

def test_c4_low_rank_scenario():
    """Low rank student exploring alternative branches, trade-offs, backup plan."""
    state = ConversationState(session_id="c4", profile={"rank": 120000, "pcm_percentage": 65})
    log = run_conversation("C4-Low-Rank", [
        "My rank is 1.2 lakh, what branches can I get?",
        "What are the trade-offs between ME and CE?",
        "Which branch has better placement?",
        "Should I consider a backup plan like another exam?",
    ], state=state)

    for i, t in enumerate(log.turns):
        assert not t.errors, f"Turn {i+1} errored: {t.errors}"
        assert t.response, f"Turn {i+1} has empty response"

    assert log.all_ok


# ---------------------------------------------------------------------------
# Conversation 5: Hostel — safety, girls hostel, transport, mess
# ---------------------------------------------------------------------------

def test_c5_hostel_scenario():
    """Student asking about hostel facilities, safety, girls hostel, transport, mess."""
    state = ConversationState(session_id="c5", profile={
        "rank": 35000, "pcm_percentage": 80, "category": "general",
    })
    log = run_conversation("C5-Hostel", [
        "Tell me about hostel facilities",
        "Is the girls hostel safe?",
        "Is there transport from the hostel to campus?",
        "How is the mess food?",
    ], state=state)

    for i, t in enumerate(log.turns):
        assert not t.errors, f"Turn {i+1} errored: {t.errors}"
        assert t.response, f"Turn {i+1} has empty response"

    assert log.all_ok


# ---------------------------------------------------------------------------
# Cross-conversation: Pipeline produces valid plan for every input type
# ---------------------------------------------------------------------------

ALL_TURN_TYPES = {
    "ask", "inform", "recommend", "reassure", "clarify",
    "collect_profile", "recommend_branches", "provide_fee_info",
    "provide_admission_guidance", "provide_placement_info",
    "provide_hostel_info", "provide_scholarship_info",
    "provide_cutoff_info", "provide_branch_guidance",
    "provide_guidance",
}


def test_all_conversations_no_crashes():
    """Every conversation completes without unhandled exceptions."""
    scenarios = [
        ("C1-Minimal", ["hello", "my rank is 48000", "82 PCM", "I like AI"]),
        ("C2-Greeting", ["hi", "what branches can I get with 50k rank"]),
        ("C3-Fees", ["what is the fee", "any scholarship"]),
        ("C4-Placement", ["tell me about placements", "which branch has best package"]),
        ("C5-Hostel", ["hostel facilities", "mess food"]),
        ("C6-Admission", ["admission process", "what documents needed"]),
        ("C7-Rank-Only", ["my rank is 75000"]),
        ("C8-Interest-Only", ["I'm interested in computer science"]),
    ]
    for name, msgs in scenarios:
        log = run_conversation(name, msgs)
        assert log.all_ok, f"{name} had errors"
        assert len(log.turns) == len(msgs), f"{name} missing turns"


def test_each_turn_has_plan_or_fallback():
    """Every pipeline execution produces either a plan or a fallback response."""
    llm = RecordingMockLLM()
    pipeline = PipelineOrchestrator(llm=llm)
    queries = [
        "hello",
        "my rank is 48000",
        "I have 82 PCM",
        "I like AI",
        "what branches can I get",
        "tell me about hostel",
    ]
    state = ConversationState(session_id="plans", profile={})
    for q in queries:
        result = pipeline.run(q, state=state)
        if result.understanding:
            _update_state_from_understanding(state, result.understanding)
        assert result.response, f"Empty response for: {q}"
        if not result.plan:
            assert result.response, f"Fallback response needed for: {q}"
