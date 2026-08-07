"""Shadow-mode signal routing evaluation.

Evaluates what routing decisions WOULD be made based on structured signal
detector output, WITHOUT changing any behavior. Pure observation.

Key constraints (v1.8 shadow-mode scope):
  - Eligible signal types: emotion, grievance (NOT decision — 60% recall is too low)
  - Only utterance-local signals qualify (conversation-context deferred to v1.9)
  - Routing is evaluated per-turn, not per-conversation

Usage:
    router = ShadowSignalRouter(threshold=0.8)
    decision = router.evaluate(text, structured_signals, scope="utterance_local")
    print(decision.would_route, decision.signal_type)
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.reasoning.observation import ReasoningObservation
from src.understanding.signals.conversation import StructuredSignals

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShadowRoutingDecision:
    """Record of one shadow-routing evaluation — never influences behavior."""

    text: str
    signal_type: str | None
    confidence: float
    threshold: float
    would_route: bool
    scope: str = "utterance_local"
    eligible: bool = False
    latency_ms: float = 0.0
    timestamp: float = 0.0


class ShadowSignalRouter:
    """Evaluates signal-aware routing decisions in shadow mode.

    Logs what would route without changing any behavior.
    Intended for threshold calibration and safety analysis before
    enabling behavioral routing.
    """

    # Eligible signal types — only emotion and grievance for v1.8
    ELIGIBLE_SIGNALS = frozenset({"emotion", "grievance"})

    # Ineligible scopes — conversation-context signals need cross-turn state
    INELIGIBLE_SCOPES = frozenset({"conversation_context_required"})

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        self.decisions: list[ShadowRoutingDecision] = []

    def evaluate(
        self,
        text: str,
        structured_signals: StructuredSignals | None,
        scope: str = "utterance_local",
    ) -> ShadowRoutingDecision:
        t0 = time.perf_counter()

        would_route = False
        selected_signal: str | None = None
        selected_confidence = 0.0
        eligible = True

        # Scope gate: conversation-context signals are ineligible
        if scope in self.INELIGIBLE_SCOPES:
            eligible = False
        else:
            # Find the first eligible signal meeting the confidence threshold
            if structured_signals is not None:
                for sig_name in sorted(self.ELIGIBLE_SIGNALS):
                    sig = getattr(structured_signals, sig_name, None)
                    if sig is not None and sig.confidence >= self.threshold:
                        would_route = True
                        selected_signal = sig_name
                        selected_confidence = sig.confidence
                        break

        latency = (time.perf_counter() - t0) * 1000

        decision = ShadowRoutingDecision(
            text=text[:80],
            signal_type=selected_signal,
            confidence=selected_confidence,
            threshold=self.threshold,
            would_route=would_route,
            scope=scope,
            eligible=eligible,
            latency_ms=round(latency, 3),
            timestamp=time.time(),
        )
        self.decisions.append(decision)
        return decision

    def evaluate_detector_output(
        self,
        text: str,
        detector_output: dict,
        scope: str = "utterance_local",
    ) -> ShadowRoutingDecision:
        """Evaluate using raw detector_output dict (from mined_candidates)."""
        from src.understanding.signals.base import Signal

        sigs: dict[str, Signal | None] = {}
        for name in ("emotion", "grievance", "decision"):
            d = detector_output.get(name, {})
            val = d.get("value")
            if val:
                sigs[name] = Signal(value=val, confidence=d.get("confidence", 0.0), source="detector")
            else:
                sigs[name] = None

        structured = StructuredSignals(
            grievance=sigs.get("grievance"),
            decision=sigs.get("decision"),
            emotion=sigs.get("emotion"),
        )
        return self.evaluate(text, structured, scope=scope)

    def evaluate_all(
        self,
        entries: list[dict],
        text_key: str = "text",
        detector_key: str = "detector_output",
        scope_key: str = "scope",
        label_key: str | None = "labels",
    ) -> list[ShadowRoutingDecision]:
        """Evaluate a list of entry dicts (from annotations or mined_candidates).

        Returns decisions list and populates self.decisions.
        """
        results = []
        for e in entries:
            scope = e.get(scope_key, "utterance_local")
            text = e.get(text_key, "")
            det = e.get(detector_key, {})
            d = self.evaluate_detector_output(text, det, scope=scope)
            results.append(d)
        return results

    def threshold_sweep(
        self,
        entries: list[dict],
        thresholds: list[float] | None = None,
        label_key: str | None = "labels",
    ) -> dict[float, dict]:
        """Run evaluate_all at multiple thresholds and compute precision/recall.

        Requires entries to have gold labels (annotations_merged format).
        Returns {threshold: {precision, recall, f1, fp_rate, would_route_count}}.

        Args:
            entries: List of entry dicts with optional gold labels.
            thresholds: Confidence thresholds to sweep.
            label_key: Dict key for gold labels. None if no labels available.
        """
        if thresholds is None:
            thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]

        results: dict[float, dict] = {}

        for thresh in thresholds:
            router = ShadowSignalRouter(threshold=thresh)
            decisions = router.evaluate_all(entries)

            # Compute metrics against gold labels
            tp = 0
            fp = 0
            tn = 0
            fn = 0
            would_route_count = 0

            for i, d in enumerate(decisions):
                e = entries[i]
                labels = e.get(label_key, {}) if label_key else {}
                has_gold_label = any(
                    labels.get(s, {}).get("present", False)
                    for s in ("emotion", "grievance")
                )

                if d.would_route:
                    would_route_count += 1
                    if has_gold_label:
                        tp += 1
                    else:
                        fp += 1
                else:
                    if has_gold_label:
                        fn += 1
                    else:
                        tn += 1

            precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            fp_rate = fp / (fp + tn) * 100 if (fp + tn) > 0 else 0.0

            results[thresh] = {
                "threshold": thresh,
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
                "precision": round(precision, 1),
                "recall": round(recall, 1),
                "f1": round(f1, 1),
                "fp_rate": round(fp_rate, 1),
                "would_route_count": would_route_count,
                "total_eligible": tp + fp + tn + fn,
            }

        return results


def _confidence_band(confidence: float) -> str:
    """Map a confidence value to a band label."""
    if confidence >= 1.0:
        return "1.0"
    if confidence >= 0.90:
        return "0.90-0.99"
    if confidence >= 0.80:
        return "0.80-0.89"
    return "below_0.80"


def format_threshold_table(sweep: dict[float, dict]) -> str:
    """Format threshold sweep results as a readable table."""
    lines = [
        "Threshold sweep results (emotion + grievance, utterance-local only):",
        "",
        f"  {'threshold':>10s}  {'would_route':>11s}  {'precision':>10s}  {'recall':>7s}  {'f1':>5s}  {'fp_rate':>8s}  {'tp':>4s}  {'fp':>4s}  {'fn':>4s}",
        "  " + "-" * 75,
    ]
    for thresh in sorted(sweep):
        r = sweep[thresh]
        lines.append(
            f"  {thresh:>10.1f}  {r['would_route_count']:>11d}  "
            f"{r['precision']:>9.1f}%  {r['recall']:>6.1f}%  {r['f1']:>4.1f}  "
            f"{r['fp_rate']:>7.1f}%  {r['tp']:>4d}  {r['fp']:>4d}  {r['fn']:>4d}"
        )
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
#  ShadowRoutingSink  —  pipeline-integrated shadow telemetry
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_TELEMETRY_PATH = Path("data/telemetry/shadow_routing.jsonl")


class ShadowRoutingSink:
    """Observer sink that logs shadow routing decisions during real traffic.

    Attach to the pipeline via TeeSink:
        sink = ShadowRoutingSink()
        pipeline.run(text, observer=TeeSink([existing_observer, sink]))

    Logs one JSONL record per turn.  Does NOT change production behavior.

    Safeguards:
      - Deduplicates by observation_id (in-memory + existing log on init).
      - Logs text, scope, and language if provided via record_text/record_scope.
    """

    def __init__(
        self,
        path: str | Path = DEFAULT_TELEMETRY_PATH,
        threshold: float = 0.8,
        eligible_signals: frozenset[str] | None = None,
    ) -> None:
        self.path = Path(path)
        self.threshold = threshold
        self.eligible_signals = eligible_signals or frozenset({"emotion", "grievance"})
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # ── Deduplication safeguard ─────────────────────────────────
        self._seen: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    try:
                        rec = json.loads(line)
                        oid = rec.get("observation_id")
                        if oid:
                            self._seen.add(oid)
                    except (json.JSONDecodeError, KeyError):
                        continue
        logger.info(
            "ShadowRoutingSink initialized: path=%s threshold=%.1f seen=%d",
            self.path, threshold, len(self._seen),
        )

    def __call__(self, obs: ReasoningObservation) -> None:
        """Receive an observation, evaluate shadow routing, append to log."""
        # Deduplicate
        if obs.observation_id in self._seen:
            return
        self._seen.add(obs.observation_id)

        decision = self._evaluate(obs)
        self._append(decision)

    def set_context(
        self,
        conversation_id: str = "",
        turn_id: int = -1,
        text: str = "",
        scope: str = "utterance_local",
    ) -> None:
        """Set per-turn context for enrichment.  Call before pipeline.run()."""
        self._ctx_conversation_id = conversation_id
        self._ctx_turn_id = turn_id
        self._ctx_text = text
        self._ctx_scope = scope

    def _evaluate(self, obs: ReasoningObservation) -> dict:
        """Determine whether this turn would route.  Pure function."""
        would_route = False
        selected_signal: str | None = None
        selected_confidence = 0.0
        scope = getattr(self, "_ctx_scope", "utterance_local")
        text = getattr(self, "_ctx_text", "")

        # Check each eligible signal against the threshold
        for sig_name in sorted(self.eligible_signals):
            if sig_name in obs.structured_signal_types:
                conf = obs.structured_signal_confidences.get(sig_name, 0.0)
                if conf >= self.threshold:
                    would_route = True
                    selected_signal = sig_name
                    selected_confidence = conf
                    break

        # Simple language heuristic: check for Devanagari characters
        has_devanagari = bool(set(text) & set("अआइईउऊएऐओऔकखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहािीुूृेैोौंः")) if text else False

        return {
            "event": "shadow_routing",
            "observation_id": obs.observation_id,
            "conversation_id": getattr(self, "_ctx_conversation_id", ""),
            "turn_id": getattr(self, "_ctx_turn_id", -1),
            "text": text[:120],
            "scope": scope,
            "language_hint": "hindi" if has_devanagari else "english",
            "reasoning_stage": obs.reasoning_stage,
            "identified_problem": obs.identified_problem,
            "intent_primary": obs.intent_primary,
            "threshold": self.threshold,
            "would_route": would_route,
            "signal_type": selected_signal,
            "signal_confidence": selected_confidence,
            "confidence_band": _confidence_band(selected_confidence) if would_route else None,
            "structured_signal_types": list(obs.structured_signal_types),
            "structured_signal_confidences": dict(obs.structured_signal_confidences),
            "dominant_signal_name": obs.dominant_signal_name,
            "dominant_signal_score": obs.dominant_signal_score,
            "latency_ms": obs.latency_ms,
        }

    def _append(self, record: dict) -> None:
        """Write one JSON line to the telemetry log."""
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            logger.exception("Failed to write shadow routing decision to %s", self.path)


# ═══════════════════════════════════════════════════════════════════════
#  Shadow routing adjudication helpers
# ═══════════════════════════════════════════════════════════════════════


def load_telemetry(path: str | Path = DEFAULT_TELEMETRY_PATH) -> list[dict]:
    """Load all shadow routing telemetry records from a JSONL file."""
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").strip().split("\n") if l.strip()]


def telemetry_summary(records: list[dict]) -> dict:
    """Summarize shadow routing telemetry."""
    from collections import Counter

    total = len(records)
    routed = [r for r in records if r.get("would_route")]
    by_signal: Counter[str] = Counter()
    by_problem: Counter[str] = Counter()
    for r in routed:
        by_signal[r.get("signal_type", "unknown")] += 1
        by_problem[r.get("identified_problem", "unknown")] += 1

    return {
        "total_turns": total,
        "would_route": len(routed),
        "would_route_pct": round(len(routed) / total * 100, 1) if total > 0 else 0.0,
        "by_signal": dict(by_signal),
        "by_problem": dict(by_problem),
        "threshold": routed[0].get("threshold") if routed else None,
    }
