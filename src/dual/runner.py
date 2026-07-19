from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.conversation.state import ConversationState
from src.pipeline import PipelineOrchestrator, PipelineResult
from src.telemetry.store import save_run

logger = logging.getLogger(__name__)

_OLD_SERVICE = None


def _get_old_service() -> Any:
    global _OLD_SERVICE
    if _OLD_SERVICE is not None:
        return _OLD_SERVICE
    try:
        from app.services.llm import get_groq_service
        _OLD_SERVICE = get_groq_service()
        return _OLD_SERVICE
    except ImportError:
        logger.warning("Old GroqService not available (not running in backend context)")
        return None
    except Exception as exc:
        logger.warning("Old GroqService init failed: %s", exc)
        return None


@dataclass
class DualResult:
    text: str
    old_response: str = ""
    old_error: str | None = None
    new_response: str = ""
    new_result: PipelineResult | None = None
    new_error: str | None = None
    new_telemetry_id: str = ""
    errors: list[str] = field(default_factory=list)


def run_dual(
    text: str,
    state: ConversationState | None = None,
    conversation_id: str = "",
    pipeline: PipelineOrchestrator | None = None,
) -> DualResult:
    result = DualResult(text=text)

    # Run old system
    svc = _get_old_service()
    if svc is not None:
        try:
            if hasattr(svc, "answer_question"):
                result.old_response = svc.answer_question(text) or ""
            elif hasattr(svc, "handle_query"):
                result.old_response = svc.handle_query(text) or ""
            else:
                result.old_error = "Old service has no recognized handler method"
        except Exception as exc:
            result.old_error = str(exc)
            logger.warning("Old system failed: %s", exc)
    else:
        result.old_error = "Old GroqService not available"

    # Run new pipeline
    p = pipeline or PipelineOrchestrator()
    try:
        result.new_result = p.run(text, state=state)
        result.new_response = result.new_result.response
        if result.new_result.errors:
            result.new_error = "; ".join(result.new_result.errors)
        result.new_telemetry_id = save_run(result.new_result, conversation_id=conversation_id)
    except Exception as exc:
        result.new_error = str(exc)
        result.errors.append(f"New pipeline failed: {exc}")
        logger.warning("New pipeline failed: %s", exc)

    return result
