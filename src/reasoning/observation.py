"""Observational telemetry around the Reasoning boundary.

ReasoningObservation is a frozen snapshot of reasoning output and context,
derived *after* the ReasoningResult is constructed. It must not influence
reasoning behavior — telemetry on/off must produce identical results.

Schema evolution policy:
  - SCHEMA_VERSION is incremented on breaking changes (field removal, type change).
  - Adding new fields is always forward-compatible (from_dict ignores unknown keys).
  - to_dict() wraps the observation in a versioned envelope.
  - Required fields are documented in REQUIRED_FIELDS but not enforced at the
    dataclass level (all fields have defaults for ergonomic construction).
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable

from src.reasoning.context import ReasoningContext
from src.reasoning.models import ReasoningResult

logger = logging.getLogger(__name__)

OBSERVATION_SCHEMA_VERSION: int = 1
"""Current schema version for the serialized envelope.
Increment on breaking changes (field removal, type change).
"""


@dataclass(frozen=True)
class ReasoningObservation:
    """Frozen snapshot of reasoning output, derived after ReasoningResult
    construction.  Never influences reasoning behavior."""

    SCHEMA_VERSION: int = OBSERVATION_SCHEMA_VERSION
    """Serialized schema version — embedded so parsers can detect version."""

    REQUIRED_FIELDS: frozenset[str] = frozenset({
        "reasoning_stage",
        "identified_problem",
        "intent_primary",
        "readiness_domain",
        "confidence_score",
        "latency_ms",
    })
    """Fields that should always be populated in a real observation."""

    # --- Core reasoning output ---
    reasoning_stage: str = ""
    identified_problem: str = ""
    confidence_score: float = 0.0

    # --- Readiness ---
    readiness_domain: str = ""
    readiness_ready: bool = False
    readiness_blocked: bool = False
    missing_critical_fields: tuple[str, ...] = ()
    completeness: float = 0.0

    # --- Intent ---
    intent_primary: str = ""
    intent_confidence: float = 0.0

    # --- Signals ---
    dominant_signal_name: str | None = None
    dominant_signal_score: float = 0.0
    structured_signal_types: tuple[str, ...] = ()
    structured_signal_confidences: dict[str, float] = field(default_factory=dict)
    signal_interaction_primary_dimension: str = ""

    # --- Timing & identity ---
    latency_ms: float = 0.0
    observation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a versioned envelope dict.

        Canonical internal representation.  Tuples become lists for JSON
        compatibility.  The envelope carries schema_version so consumers
        can detect version without peering into the observation body.
        """
        body: dict[str, Any] = {}
        for f in self.__dataclass_fields__:
            if f in ("SCHEMA_VERSION", "REQUIRED_FIELDS"):
                continue
            val = getattr(self, f)
            if isinstance(val, tuple):
                body[f] = list(val)
            else:
                body[f] = val
        return {
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "observation_id": body.pop("observation_id", "") or str(uuid.uuid4())[:12],
            "observation": body,
        }

    def to_json(self, indent: int | None = None) -> str:
        """Transport format — JSON string of the versioned envelope."""
        return json.dumps(self.to_dict(), default=str, ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReasoningObservation:
        """Deserialize from a versioned envelope dict.

        Forward-compatible: unknown keys in ``observation`` are silently
        ignored.  Missing keys fall back to field defaults.
        """
        body = data.get("observation", data)
        known = {f for f in cls.__dataclass_fields__ if f not in ("SCHEMA_VERSION", "REQUIRED_FIELDS")}
        kwargs: dict[str, Any] = {}
        for f in known:
            if f not in body:
                continue
            val = body[f]
            if isinstance(val, list):
                kwargs[f] = tuple(val)
            else:
                kwargs[f] = val
        return cls(**kwargs)

    def validate(self) -> list[str]:
        """Return list of missing required fields (empty = valid)."""
        missing: list[str] = []
        for f in self.REQUIRED_FIELDS:
            val = getattr(self, f)
            if val is None or val == "" or (isinstance(val, (int, float)) and val == 0):
                missing.append(f)
        return missing


def observe(
    result: ReasoningResult,
    ctx: ReasoningContext,
    latency_ms: float = 0.0,
    observation_id: str = "",
) -> ReasoningObservation:
    """Derive an observation from a ReasoningResult and its context.

    This function is read-only — it does not mutate result or ctx.
    ``observation_id`` defaults to a short UUID if not provided.
    """
    readiness = result.readiness
    dominant_name, dominant_score = ctx.signals.dominant if ctx.signals else (None, 0.0)
    if dominant_score == 0.0:
        dominant_name = None

    sig_types: list[str] = []
    sig_confidences: dict[str, float] = {}
    if ctx.structured_signals:
        for name in ("grievance", "decision", "emotion"):
            sig = getattr(ctx.structured_signals, name, None)
            if sig is not None:
                sig_types.append(name)
                sig_confidences[name] = sig.confidence

    return ReasoningObservation(
        observation_id=observation_id or str(uuid.uuid4())[:12],
        reasoning_stage=result.student_stage,
        identified_problem=result.current_problem,
        confidence_score=result.confidence,
        readiness_domain=readiness.domain if readiness else "",
        readiness_ready=readiness.ready if readiness else False,
        readiness_blocked=readiness.blocked if readiness else False,
        missing_critical_fields=tuple(readiness.missing_critical) if readiness else (),
        completeness=result.profile_completeness,
        intent_primary=ctx.intent_primary,
        intent_confidence=ctx.intent_confidence,
        dominant_signal_name=dominant_name,
        dominant_signal_score=dominant_score,
        structured_signal_types=tuple(sig_types),
        structured_signal_confidences=sig_confidences,
        signal_interaction_primary_dimension=(
            ctx.signal_interaction.primary_dimension
            if ctx.signal_interaction else ""
        ),
        latency_ms=latency_ms,
    )


Observer = Callable[[ReasoningObservation], None]
"""Type alias for a telemetry callback that receives an observation."""


class InMemorySink:
    """Collects observations in memory.  Useful for testing."""

    def __init__(self) -> None:
        self.observations: list[ReasoningObservation] = []

    def __call__(self, obs: ReasoningObservation) -> None:
        self.observations.append(obs)

    @property
    def count(self) -> int:
        return len(self.observations)

    def clear(self) -> None:
        self.observations.clear()


class LoggingSink:
    """Logs each observation as JSON via the standard logger."""

    def __init__(self, level: int = logging.INFO) -> None:
        self._level = level

    def __call__(self, obs: ReasoningObservation) -> None:
        logger.log(self._level, "ReasoningObservation: %s", obs.to_json())


class TeeSink:
    """Fan-out to multiple sinks."""

    def __init__(self, sinks: list[Observer]) -> None:
        self._sinks = list(sinks)

    def __call__(self, obs: ReasoningObservation) -> None:
        for sink in self._sinks:
            try:
                sink(obs)
            except Exception:
                logger.exception("Observation sink %r failed", sink)


def safe_observer(inner: Observer | None) -> Observer | None:
    """Wrap an observer so that exceptions are logged but not propagated."""
    if inner is None:
        return None

    def wrapper(obs: ReasoningObservation) -> None:
        try:
            inner(obs)
        except Exception:
            logger.exception("Observation sink failed")

    return wrapper
