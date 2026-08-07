from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from src.brain import CollegeBrain
from src.composer.engine import ResponseComposer
from src.conversation.state import ConversationState
from src.decision.engine import DecisionEngine
from src.engines.interfaces import DecisionInput, ReasoningInput, UnderstandingInput
from src.llm.interfaces import LLMAdapter
from src.llm.mock import MockLLM
from src.pipeline.response import format_plan_as_response

try:
    from src.llm.groq import GroqLLM
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False
    GroqLLM = None  # type: ignore[assignment]
from src.planner.engine import MinimalPlanner
from src.planner.models import Plan
from src.reasoning.engine import ReasoningEngine
from src.reasoning.observation import Observer
from src.registry import CapabilityRegistry
from src.understanding.engine import UnderstandingEngine

PIPELINE_VERSION = "1.0.0"


def _elapsed_ms(t_start: float) -> int:
    return int((time.perf_counter() - t_start) * 1000)


logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    text: str
    response: str = ""
    understanding: Any = None
    reasoning: Any = None
    brain_response: Any = None
    decision: Any = None
    plan: Plan | None = None
    llm_prompt: str = ""
    llm_diagnostics: Any = None
    confidence: float = 0.0
    errors: list[str] = field(default_factory=list)
    latency_ms: dict[str, int] = field(default_factory=dict)
    versions: dict[str, str] = field(default_factory=dict)


class PipelineOrchestrator:
    def __init__(
        self,
        understanding: UnderstandingEngine | None = None,
        reasoning: ReasoningEngine | None = None,
        brain: CollegeBrain | None = None,
        registry: CapabilityRegistry | None = None,
        decision: DecisionEngine | None = None,
        planner: MinimalPlanner | None = None,
        llm: LLMAdapter | None = None,
        composer: ResponseComposer | None = None,
    ) -> None:
        self.understanding = understanding or UnderstandingEngine()
        self.reasoning = reasoning or ReasoningEngine()
        self.brain = brain or CollegeBrain()
        self.registry = registry or CapabilityRegistry()
        self.decision = decision or DecisionEngine()
        self.planner = planner or MinimalPlanner()
        self._llm = llm or self._default_llm()
        self.composer = composer or ResponseComposer(self._llm)

    @staticmethod
    def _default_llm() -> LLMAdapter:
        import os
        api_key = os.getenv("GROQ_API_KEY", "")
        if HAS_GROQ and api_key:
            try:
                return GroqLLM(api_key=api_key)
            except Exception as exc:
                logger.warning("GroqLLM init failed: %s, falling back to MockLLM", exc)
        return MockLLM()

    def run(
        self,
        text: str,
        state: ConversationState | None = None,
        debug: bool = False,
        observer: Observer | None = None,
    ) -> PipelineResult:
        errors: list[str] = []
        latencies: dict[str, int] = {}
        versions: dict[str, str] = {
            "pipeline": PIPELINE_VERSION,
            "understanding": getattr(self.understanding, "VERSION", "?"),
            "reasoning": getattr(self.reasoning, "VERSION", "?"),
            "brain": getattr(self.brain, "VERSION", "?"),
            "decision": getattr(self.decision, "VERSION", "?"),
            "planner": getattr(self.planner, "VERSION", "?"),
            "composer": getattr(self.composer, "VERSION", "?"),
        }
        t0 = time.perf_counter()

        try:
            t = time.perf_counter()
            understanding = self.understanding.process(UnderstandingInput(text=text, state=state, debug=debug))
            latencies["understanding"] = _elapsed_ms(t)
        except Exception as e:
            errors.append(f"Understanding failed: {e}")
            return PipelineResult(text=text, errors=errors)

        try:
            t = time.perf_counter()
            reasoning = self.reasoning.process(
                ReasoningInput(understanding=understanding, state=state, college_brain=self.brain, debug=debug),
                observer=observer,
            )
            latencies["reasoning"] = _elapsed_ms(t)
        except Exception as e:
            errors.append(f"Reasoning failed: {e}")
            return PipelineResult(text=text, understanding=understanding, errors=errors)

        try:
            t = time.perf_counter()
            brain_q = self._build_brain_query(understanding, state)
            brain_response = self.brain.query(brain_q)
            latencies["brain"] = _elapsed_ms(t)
        except Exception as e:
            errors.append(f"CollegeBrain failed: {e}")
            brain_response = None

        try:
            t = time.perf_counter()
            decision = self.decision.process(
                DecisionInput(
                    reasoning=reasoning,
                    brain_response=brain_response,
                    capabilities=self.registry,
                    metadata={"student_text": text},
                    debug=debug,
                )
            )
            latencies["decision"] = _elapsed_ms(t)
        except Exception as e:
            errors.append(f"Decision failed: {e}")
            decision = None

        plan = None
        if decision:
            try:
                t = time.perf_counter()
                plan = self.planner.process(decision, brain_response, debug=debug)
                latencies["planner"] = _elapsed_ms(t)
            except Exception as e:
                errors.append(f"Planner failed: {e}")

        response = ""
        llm_diagnostics = None
        if plan:
            try:
                t = time.perf_counter()
                history = self._get_history(state)
                composer_result = self.composer.compose(
                    plan=plan,
                    decision=decision,
                    brain_response=brain_response,
                    user_text=text,
                    history=history,
                    debug=debug,
                )
                response = composer_result.text
                llm_diagnostics = composer_result.diagnostics
                latencies["llm"] = _elapsed_ms(t)
                llm_prompt = getattr(self.composer._llm, "last_prompt", "")
            except Exception as e:
                errors.append(f"LLM failed: {e}")
                response = format_plan_as_response(plan)
        else:
            response = ("I understand you're asking about admissions. "
                        "Could you share your rank and PCM percentage?")

        latencies["total"] = _elapsed_ms(t0)

        # Persist profile and history back to state for multi-turn conversations
        if state is not None and understanding is not None:
            profile = getattr(understanding, "profile", None)
            if profile is not None and hasattr(profile, "to_dict"):
                new_data = profile.to_dict()
                existing = getattr(state, "profile", None) or {}
                if isinstance(existing, dict):
                    merged = dict(existing)
                    # Flatten nested profile: academic.rank -> rank, personal.category -> category
                    for section in ("academic", "personal", "career"):
                        section_data = new_data.get(section, {})
                        if isinstance(section_data, dict):
                            for k, v in section_data.items():
                                if v is not None and v != "" and v != 0:
                                    merged[k] = v
                    state.profile = merged
                else:
                    state.profile = new_data
            if response:
                state.history.append({"role": "user", "content": text})
                state.history.append({"role": "assistant", "content": response})
            # Track resolved intent and problem for multi-turn context
            if understanding and hasattr(understanding, 'intent'):
                state.goals["primary"] = understanding.intent.primary
            if reasoning and reasoning.current_problem:
                prev = state.metadata.get("previous_problem", "")
                current = reasoning.current_problem
                if current == "needs_admission_guidance" and prev == "needs_admission_guidance":
                    state.metadata["admission_guidance_turns"] = state.metadata.get("admission_guidance_turns", 1) + 1
                elif current == "needs_admission_guidance":
                    state.metadata["admission_guidance_turns"] = 1
                else:
                    state.metadata["admission_guidance_turns"] = 0
                state.metadata["previous_problem"] = current

        logger.info(
            "pipeline.run latencies_ms=%s errors=%d version=%s",
            latencies,
            len(errors),
            versions.get("pipeline", "?"),
        )

        return PipelineResult(
            text=text,
            response=response,
            understanding=understanding,
            reasoning=reasoning,
            brain_response=brain_response,
            decision=decision,
            plan=plan,
            llm_prompt=llm_prompt,
            llm_diagnostics=llm_diagnostics,
            confidence=getattr(reasoning, "confidence", 0.0),
            errors=errors,
            latency_ms=latencies,
            versions=versions,
        )

    @staticmethod
    def _build_brain_query(
        understanding: Any, state: ConversationState | None
    ) -> Any:
        from src.brain.interfaces import BrainQuery

        profile = getattr(understanding, "profile", None)
        state_profile = state.profile if state else {}

        if profile is not None:
            acad = profile.academic
            pers = profile.personal
            care = profile.career
            return BrainQuery(
                rank=acad.rank if acad.rank is not None else state_profile.get("rank"),
                pcm_percentage=acad.pcm_percentage if acad.pcm_percentage is not None else state_profile.get("pcm_percentage"),
                category=pers.category or state_profile.get("category", "general"),
                board=acad.board or state_profile.get("board", ""),
                interest=care.interest or state_profile.get("interest", ""),
                budget=pers.budget or state_profile.get("budget"),
                location=pers.location or state_profile.get("location", ""),
            )

        # Fallback: read from state profile (legacy)
        return BrainQuery(
            rank=state_profile.get("rank"),
            pcm_percentage=state_profile.get("pcm_percentage"),
            category=state_profile.get("category", "general"),
            board=state_profile.get("board", ""),
            interest=state_profile.get("interest", ""),
            budget=state_profile.get("budget"),
            location=state_profile.get("location", ""),
        )

    @staticmethod
    def _get_history(state: ConversationState | None) -> list[dict]:
        if state is None:
            return []
        return list(getattr(state, "history", []) or [])[-10:]
