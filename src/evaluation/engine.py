import logging

from src.engines.interfaces import EvaluationInput, EvaluationOutput

logger = logging.getLogger(__name__)

_KNOWN_OUTCOMES = {"completed", "abandoned", "escalated", "clarified", "error"}


class EvaluationEngine:
    def process(self, input: EvaluationInput) -> EvaluationOutput:
        decision = input.decision
        outcome = input.outcome.lower().strip()
        feedback = input.user_feedback

        if outcome not in _KNOWN_OUTCOMES:
            return EvaluationOutput(
                correct=False,
                confidence_adjustment=-0.1,
                notes=f"Unrecognized outcome '{outcome}'",
                follow_up_needed=True,
            )

        if outcome == "abandoned":
            return EvaluationOutput(
                correct=False,
                confidence_adjustment=-0.2,
                notes="Student abandoned — decision may have been wrong",
                follow_up_needed=True,
            )

        if outcome == "escalated":
            if decision and decision.escalate:
                return EvaluationOutput(
                    correct=True,
                    confidence_adjustment=0.05,
                    notes="Escalation was appropriate",
                )
            return EvaluationOutput(
                correct=False,
                confidence_adjustment=-0.1,
                notes="Unexpected escalation — review decision criteria",
                follow_up_needed=True,
            )

        if outcome == "completed":
            adj = 0.0
            if decision and decision.confidence > 0.7:
                adj = 0.1
            return EvaluationOutput(
                correct=True,
                confidence_adjustment=adj,
                notes="Decision led to successful completion",
            )

        if outcome == "clarified":
            return EvaluationOutput(
                correct=True,
                confidence_adjustment=0.0,
                notes="Clarification resolved the query",
            )

        if outcome == "error":
            adj = -0.15
            if feedback:
                adj = -0.25
            return EvaluationOutput(
                correct=False,
                confidence_adjustment=adj,
                notes=f"Error encountered{': ' + feedback if feedback else ''}",
                follow_up_needed=True,
            )

        return EvaluationOutput(
            correct=False,
            confidence_adjustment=-0.05,
            notes=f"Unhandled outcome '{outcome}'",
        )
