from __future__ import annotations

import logging
import re
from typing import Any

from src.conversation.state import ConversationState
from src.engines.interfaces import ReasoningInput
from src.reasoning.models import (
    EligibilityEstimate,
    FeatureContribution,
    ReadinessResult,
    ReasoningDiagnostics,
    ReasoningResult,
    RuleExplanation,
    RuleEval,
)
from src.understanding.models import UnderstandingResult
from src.understanding.profile import is_field_set, PATHWAY_REQUIRED_FIELDS

logger = logging.getLogger(__name__)

# Intents that can be answered without critical profile data
# (domain readiness is informational — does not block routing)
ANSWERABLE_GENERALLY = {
    "fee", "hostel", "placement", "transfer", "management",
    "management_quota", "campus", "general", "department",
    "institution", "hod", "seats", "document", "safety",
    "distance_ed", "distance_education", "loan",
    "grievance", "lateral_entry", "sports", "sports_quota",
    "nri", "nri_admission", "counseling_info",
}

# Minimum fields that truly block routing for non-answerable intents.
# If the student has at least these, the intent can still be answered
# even if other pathway-required fields are missing.
BLOCKING_MINIMUM_FIELDS = {
    "admission": ["academic.rank"],
    "cutoff": ["academic.rank"],
    "scholarship": ["personal.category"],
}

# Intent → domain pathway mapping
INTENT_TO_PATHWAY = {
    "admission": "regular", "fee": "fee", "hostel": "hostel",
    "placement": "placement", "scholarship": "scholarship",
    "cutoff": "regular", "transfer": "transfer",
    "sports": "sports_quota", "sports_quota": "sports_quota",
    "nri": "nri", "nri_admission": "nri_admission",
    "management": "management_quota", "management_quota": "management_quota",
    "grievance": "grievance", "lateral_entry": "lateral_entry",
    "career_confusion": "career_confusion",
    "distance_ed": "distance_education", "distance_education": "distance_education",
    "counseling_info": "counseling_info",
    "department": "regular", "institution": "regular", "hod": "regular",
    "seats": "regular", "repeat": "regular", "loan": "regular",
    "document": "regular", "safety": "regular",
}


class ReasoningEngine:
    VERSION = "v2"

    def process(self, input: ReasoningInput) -> ReasoningResult:
        return self.reason(
            input.understanding, input.state, input.college_brain,
            debug=input.debug,
        )

    def reason(
        self,
        understanding: UnderstandingResult,
        state: ConversationState | None = None,
        college_brain: Any | None = None,
        debug: bool = False,
    ) -> ReasoningResult:
        stage = self._determine_stage(understanding, state)
        intent = understanding.intent.primary
        readiness = self._domain_readiness(intent, understanding, state)
        if intent not in ANSWERABLE_GENERALLY and not readiness.ready:
            blocking = BLOCKING_MINIMUM_FIELDS.get(intent, readiness.missing_critical)
            readiness.blocked = any(m in readiness.missing_critical for m in blocking)
        else:
            readiness.blocked = False
        eligibility = self._estimate_eligibility(understanding, state, college_brain)
        problem = self._identify_problem(understanding, readiness, state)
        unknowns = self._find_unknowns(understanding)
        risks = self._identify_risks(understanding, readiness)
        opportunities = self._identify_opportunities(understanding, state)
        knowledge = self._determine_knowledge_needed(understanding, stage)
        confidence = self._score_confidence(understanding, readiness)

        result = ReasoningResult(
            student_stage=stage,
            profile_completeness=readiness.completeness,
            readiness=readiness,
            eligibility=eligibility,
            current_problem=problem,
            unknowns=unknowns,
            risks=risks,
            opportunities=opportunities,
            knowledge_needed=knowledge,
            confidence=confidence,
        )

        if debug:
            trace = self._trace_problem(understanding, readiness)
            result.metadata["reasoning_diagnostics"] = ReasoningDiagnostics(
                input_intent=intent,
                intent_confidence=understanding.intent.confidence,
                dominant_signal=trace.get("signal_name", ""),
                signal_score=trace.get("signal_score", 0.0),
                profile_completeness=readiness.completeness,
                stage=stage,
                confidence_score=confidence,
                problems_traced=trace.get("rules", []),
                explanations=trace.get("explanations", []),
                runner_up=trace.get("runner_up", ""),
                margin=trace.get("margin", 0.0),
                winner=problem,
            )

        return result

    # ── Profile helpers ───────────────────────────────────────────────

    @staticmethod
    def _get_profile(understanding: UnderstandingResult):
        return getattr(understanding, "profile", None)

    @staticmethod
    def _has_field(understanding: UnderstandingResult, field: str) -> bool:
        profile = ReasoningEngine._get_profile(understanding)
        if profile is not None:
            return is_field_set(profile, field)
        return False

    @staticmethod
    def _get_field(understanding: UnderstandingResult, field: str) -> Any:
        profile = ReasoningEngine._get_profile(understanding)
        if profile is not None:
            from src.understanding.profile import get_field
            return get_field(profile, field)
        return None

    # ── Stage detection ───────────────────────────────────────────────

    def _determine_stage(
        self, understanding: UnderstandingResult, state: ConversationState | None
    ) -> str:
        profile = state.profile if state else {}
        history_count = len(state.history) // 2 if state else 0

        primary = str(understanding.intent.primary)
        if "decision" in primary or "choice" in primary:
            return "decision"
        if "apply" in primary or "form" in primary:
            return "application"

        has_rank = profile.get("rank") or self._has_field(understanding, "academic.rank")
        has_interest = profile.get("interest") or self._has_field(understanding, "career.interest")
        if history_count >= 4 and has_rank and has_interest:
            return "evaluation"

        known = set(profile.keys())
        if self._has_field(understanding, "academic.rank"):
            known.add("rank")
        if self._has_field(understanding, "academic.pcm_percentage"):
            known.add("pcm_percentage")
        if self._has_field(understanding, "career.interest"):
            known.add("interest")
        required = ["rank", "pcm_percentage", "interest"]
        if all(r in known for r in required):
            return "evaluation"

        if history_count >= 2:
            return "discovery"

        return "discovery"

    # ── Domain readiness ──────────────────────────────────────────────

    def _domain_readiness(
        self, intent: str, understanding: UnderstandingResult, state: ConversationState | None
    ) -> ReadinessResult:
        """Check if the student's profile has all critical fields for this intent's domain."""
        pathway = INTENT_TO_PATHWAY.get(intent, "regular")
        required = PATHWAY_REQUIRED_FIELDS.get(pathway, PATHWAY_REQUIRED_FIELDS["regular"])
        if not required:
            return ReadinessResult(domain=pathway, ready=True, completeness=1.0)

        profile = self._get_profile(understanding)
        if profile is None:
            return ReadinessResult(
                domain=pathway, ready=False,
                missing_critical=list(required), completeness=0.0,
            )

        missing = [f for f in required if not self._has_field(understanding, f)]
        filled = len(required) - len(missing)
        completeness = filled / len(required)

        if missing:
            return ReadinessResult(
                domain=pathway, ready=False,
                missing_critical=missing, completeness=completeness,
            )
        return ReadinessResult(domain=pathway, ready=True, completeness=1.0)

    # ── Admission stage detection ──────────────────────────────────────

    @staticmethod
    def _is_decision_request(text: str) -> bool:
        """Detect if the query is asking for a decision/recommendation."""
        tl = text.lower().strip()
        patterns = [
            r'\bcan i get\b', r'\bwhat about\b',
            r'\btell me straight\b', r'\btell me.*possible\b',
            r'\btell me about\b',
            r'\bother branches?\b', r'\bshould i\b',
            r'\brecommend\b', r'\bworth (taking|it)\b',
            r'\breally want\b', r'\bwhich (branch|stream|one|subject|field)\b',
            r'\bchoose\b', r'\bconfused\b',
            r'\bwhat are my chances\b', r'\bpossible or not\b',
            r'\bcan.*(get|do).*(anywhere|something)\b',
            r'\bconfirm.*(will|get|possible)\b',
        ]
        return bool(re.search('|'.join(patterns), tl))

    @staticmethod
    def _should_revert_to_guidance(
        understanding: UnderstandingResult,
        state: ConversationState | None,
    ) -> bool:
        """Check if personalized guidance should revert to admission guidance
        because the student is providing new critical profile data."""
        prev = (state.metadata or {}).get("previous_problem", "") if state else ""
        if prev != "needs_personalized_guidance":
            return False
        profile = understanding.profile or {}
        has_new_critical = bool(
            profile.get("academic", {}).get("rank")
            or profile.get("academic", {}).get("pcm")
            or profile.get("personal", {}).get("category")
            or profile.get("preferences", {}).get("interest")
        )
        return has_new_critical

    def _should_personalize_admission(
        self, understanding: UnderstandingResult, readiness: ReadinessResult,
        state: ConversationState | None,
    ) -> bool:
        """Check if admission guidance should transition to personalized guidance."""
        if not readiness.ready:
            return False
        prev = (state.metadata or {}).get("previous_problem", "") if state else ""
        if prev != "needs_admission_guidance":
            return False
        if not self._is_decision_request(understanding.text):
            return False
        # Require at least 2 consecutive admission_guidance turns before transitioning
        guidance_turns = (state.metadata or {}).get("admission_guidance_turns", 0) if state else 0
        if guidance_turns < 2:
            return False
        return True

    # ── Eligibility ───────────────────────────────────────────────────

    def _estimate_eligibility(
        self,
        understanding: UnderstandingResult,
        state: ConversationState | None,
        college_brain: Any | None,
    ) -> EligibilityEstimate:
        if college_brain is not None:
            return self._estimate_via_brain(understanding, state, college_brain)
        return self._estimate_fallback(understanding, state)

    def _estimate_via_brain(
        self,
        understanding: UnderstandingResult,
        state: ConversationState | None,
        college_brain: Any,
    ) -> EligibilityEstimate:
        rank = self._resolve_rank(understanding, state)
        pcm = self._resolve_pcm(understanding, state)
        category = self._resolve_category(understanding, state)
        try:
            pr = college_brain.estimate_eligibility(
                rank=rank, category=category, pcm=pcm,
            )
            return EligibilityEstimate(
                likely=pr.applicable,
                branches=pr.data.get("eligible_branches", []),
                confidence=pr.confidence,
                note=pr.details,
            )
        except Exception:
            logger.warning("CollegeBrain.estimate_eligibility failed", exc_info=True)
            return EligibilityEstimate(
                likely=False, branches=[], confidence=0.0,
                note="Eligibility check unavailable at this time",
            )

    def _resolve_rank(
        self, understanding: UnderstandingResult, state: ConversationState | None
    ) -> int | float | None:
        val = self._get_field(understanding, "academic.rank")
        if val is not None:
            return val
        if state:
            return state.profile.get("rank")
        return None

    def _resolve_pcm(
        self, understanding: UnderstandingResult, state: ConversationState | None
    ) -> float | None:
        val = self._get_field(understanding, "academic.pcm_percentage")
        if val is not None:
            return val
        if state:
            return state.profile.get("pcm_percentage")
        return None

    def _resolve_category(
        self, understanding: UnderstandingResult, state: ConversationState | None
    ) -> str:
        val = self._get_field(understanding, "personal.category")
        if val:
            return str(val)
        if state:
            return state.profile.get("category", "general")
        return "general"

    def _estimate_fallback(
        self,
        understanding: UnderstandingResult,
        state: ConversationState | None,
    ) -> EligibilityEstimate:
        rank = self._resolve_rank(understanding, state)
        pcm = self._resolve_pcm(understanding, state)

        if rank is None and pcm is None:
            return EligibilityEstimate(
                likely=False,
                branches=[],
                confidence=0.0,
                note="Insufficient data to estimate eligibility",
            )

        likely = False
        branches: list[str] = []
        note = ""
        confidence = 0.0

        if rank is not None and isinstance(rank, (int, float)):
            if rank <= 30000:
                likely = True
                branches = ["CSE", "AIML", "IT", "ECE"]
                note = "Strong rank — likely eligible for most branches"
                confidence = 0.85
            elif rank <= 60000:
                likely = True
                branches = ["IT", "ECE", "EE", "ME"]
                note = "Good rank — eligible for multiple branches"
                confidence = 0.7
            elif rank <= 120000:
                likely = True
                branches = ["ME", "CE", "EE"]
                note = "Moderate rank — eligible for core branches"
                confidence = 0.55
            else:
                branches = []
                note = "Rank may be above typical cutoff — verify with counseling data"
                confidence = 0.3

        if pcm is not None and isinstance(pcm, (int, float)):
            if pcm < 45:
                note += " | PCM below 45% — eligibility may be restricted"
                confidence *= 0.8

        return EligibilityEstimate(
            likely=likely,
            branches=branches,
            confidence=round(confidence, 2),
            note=note.strip(),
        )

    # ── Problem identification ────────────────────────────────────────

    def _identify_problem(
        self, understanding: UnderstandingResult, readiness: ReadinessResult,
        state: ConversationState | None = None,
    ) -> str:
        intent = understanding.intent.primary
        dominant_signal, signal_score = understanding.signals.dominant

        if signal_score > 0.4 and dominant_signal == "anxiety":
            if signal_score > 0.7:
                return "needs_reassurance"
            if intent not in ("hostel", "placement", "cutoff", "fee",
                              "scholarship", "grievance"):
                return "needs_reassurance"
        if signal_score > 0.5 and dominant_signal == "confusion":
            return "needs_clarification"
        if signal_score > 0.5 and dominant_signal == "frustration":
            return "needs_clarification"

        # Domain readiness gate — only block intents that cannot be answered generally
        if readiness.blocked:
            if len(readiness.missing_critical) >= 3:
                return "needs_profile_initial"
            return "needs_profile_completion"

        if intent == "fee":
            return "needs_fee_information"
        if intent == "admission":
            if self._should_revert_to_guidance(understanding, state):
                return "needs_admission_guidance"
            if self._should_personalize_admission(understanding, readiness, state):
                return "needs_personalized_guidance"
            # Collect category before giving admission guidance
            if "personal.category" in (readiness.missing_critical or []):
                return "needs_profile_completion"
            return "needs_admission_guidance"
        if intent == "placement":
            return "needs_placement_information"
        if intent == "hostel":
            return "needs_hostel_information"
        if intent == "scholarship":
            return "needs_scholarship_information"
        if intent == "cutoff":
            return "needs_cutoff_information"
        if intent == "department":
            return "needs_institution_info"
        if intent in ("counseling_info",):
            return "needs_personalized_guidance"
        if intent in ("transfer",):
            return "needs_transfer_information"
        if intent in ("sports", "sports_quota"):
            return "needs_sports_quota_information"
        if intent in ("nri", "nri_admission"):
            return "needs_nri_admission_information"
        if intent in ("management", "management_quota"):
            return "needs_management_quota_information"
        if intent in ("distance_ed", "distance_education"):
            return "needs_distance_education_information"
        if intent in ("grievance",):
            return "needs_grievance_resolution"
        if intent in ("lateral_entry",):
            return "needs_lateral_entry_information"
        if intent in ("institution", "hod"):
            return "needs_institution_info"
        if intent in ("seats",):
            return "needs_seat_info"
        if intent in ("repeat",):
            return "needs_clarification"
        if intent in ("loan",):
            return "needs_loan_info"
        if intent in ("document",):
            return "needs_document_info"
        if intent in ("safety",):
            return "needs_safety_info"
        if intent in ("career_confusion",):
            return "needs_career_guidance"
        return "needs_personalized_guidance"

    def _trace_problem(
        self, understanding: UnderstandingResult, readiness: ReadinessResult
    ) -> dict:
        intent = understanding.intent.primary
        dominant_signal, signal_score = understanding.signals.dominant
        rules: list[RuleEval] = []
        explanations: list[RuleExplanation] = []
        signal_name = dominant_signal

        def _feat(name: str, value: float, contribution: float, desc: str = "") -> FeatureContribution:
            return FeatureContribution(feature=name, value=value, contribution=contribution, description=desc)

        def _explain_intent(rule_name: str, target_intent: str, result_label: str, matched: bool):
            """Build explanation for an intent-matching rule."""
            feats = []
            im = 1.0 if matched else 0.0
            feats.append(_feat("intent_match", im, 0.6 if matched else 0.0,
                               f"intent is '{intent}', target is '{target_intent}'"))
            feats.append(_feat("intent_confidence", understanding.intent.confidence, 0.2 if matched else 0.0,
                               "confidence of intent detection"))
            if dominant_signal in ("anxiety",) and signal_score > 0.4:
                pen = -0.15 if matched else 0.0
                feats.append(_feat("signal_penalty", signal_score, pen, f"strong {dominant_signal} signal"))
            feats.append(_feat("domain_readiness", 1.0 if readiness.ready else 0.0, 0.0,
                               f"{'blocked' if readiness.blocked else 'partial'}: {readiness.format()}"))
            final = 1.0 if matched else 0.0
            explanations.append(RuleExplanation(
                rule_name=rule_name, result=result_label, base_score=0.0,
                features=feats, final_score=final, matched=matched,
            ))

        def _eval(condition: str, matched: bool, result: str = ""):
            score = signal_score if "signal" in condition else (1.0 if matched else 0.0)
            rules.append(RuleEval(condition=condition, matched=matched, score=score, result=result))
            return matched

        # Signals first
        sig_anxiety_exempt = intent in ("hostel", "placement", "cutoff", "fee", "scholarship", "grievance")
        if _eval("anxiety > 0.4 AND anxiety dominant AND intent not in (hostel, placement, cutoff, fee, scholarship, grievance)",
                 signal_score > 0.4 and dominant_signal == "anxiety" and not sig_anxiety_exempt,
                 "needs_reassurance"):
            feats = [
                _feat("signal_strength", signal_score, signal_score, f"anxiety={signal_score:.2f}"),
                _feat("signal_dominance", 1.0, 0.0, f"dominant={dominant_signal}"),
                _feat("intent_blocked", 0.0, 0.0, f"no exemption ({intent})"),
                _feat("anxiety_override", 1.0 if signal_score > 0.7 else 0.0, 0.2 if signal_score > 0.7 else 0.0, "high anxiety > 0.7"),
            ]
            final = signal_score + (0.2 if signal_score > 0.7 else 0.0)
            explanations.append(RuleExplanation(
                rule_name="anxiety > 0.4, no intent exemption",
                result="needs_reassurance", base_score=0.0,
                features=feats, final_score=final, matched=True,
            ))
        else:
            # Build explanation even when not matched
            feats = [
                _feat("signal_strength", signal_score, 0.0, f"anxiety={signal_score:.2f} (need > 0.4)"),
                _feat("signal_dominance", 1.0 if dominant_signal == "anxiety" else 0.0, 0.0, f"dominant={dominant_signal}"),
                _feat("intent_blocked", 1.0 if sig_anxiety_exempt else 0.0, -0.5 if sig_anxiety_exempt else 0.0,
                      f"exempted intent={intent}" if sig_anxiety_exempt else "not exempted"),
            ]
            explanations.append(RuleExplanation(
                rule_name="anxiety > 0.4, no intent exemption",
                result="needs_reassurance", base_score=0.0,
                features=feats, final_score=0.0, matched=False,
            ))
        if _eval("confusion > 0.5", signal_score > 0.5 and dominant_signal == "confusion", "needs_clarification"):
            feats = [
                _feat("signal_strength", signal_score, signal_score, f"confusion={signal_score:.2f}"),
                _feat("signal_dominance", 1.0, 0.0, f"dominant={dominant_signal}"),
            ]
            explanations.append(RuleExplanation(
                rule_name="confusion > 0.5", result="needs_clarification", base_score=0.0,
                features=feats, final_score=signal_score, matched=True,
            ))
        elif _eval("frustration > 0.5", signal_score > 0.5 and dominant_signal == "frustration", "needs_clarification"):
            feats = [
                _feat("signal_strength", signal_score, signal_score, f"frustration={signal_score:.2f}"),
                _feat("signal_dominance", 1.0, 0.0, f"dominant={dominant_signal}"),
            ]
            explanations.append(RuleExplanation(
                rule_name="frustration > 0.5", result="needs_clarification", base_score=0.0,
                features=feats, final_score=signal_score, matched=True,
            ))
        # Intent rules
        INTENT_RULES = [
            ("fee", "needs_fee_information"),
            ("admission", "needs_admission_guidance"),
            ("placement", "needs_placement_information"),
            ("hostel", "needs_hostel_information"),
            ("scholarship", "needs_scholarship_information"),
            ("cutoff", "needs_cutoff_information"),
            ("department", "needs_institution_info"),
            ("counseling_info", "needs_personalized_guidance"),
            ("transfer", "needs_transfer_information"),
            ("sports/sports_quota", "needs_sports_quota_information"),
            ("nri/nri_admission", "needs_nri_admission_information"),
            ("management/management_quota", "needs_management_quota_information"),
            ("distance_ed/distance_education", "needs_distance_education_information"),
            ("grievance", "needs_grievance_resolution"),
            ("lateral_entry", "needs_lateral_entry_information"),
            ("institution/hod", "needs_institution_info"),
            ("seats", "needs_seat_info"),
            ("repeat", "needs_clarification"),
            ("loan", "needs_loan_info"),
            ("document", "needs_document_info"),
            ("safety", "needs_safety_info"),
            ("career_confusion", "needs_career_guidance"),
        ]
        intent_match_map = {
            "fee": "fee", "admission": "admission", "placement": "placement",
            "hostel": "hostel", "scholarship": "scholarship", "cutoff": "cutoff",
            "department": "department", "counseling_info": "counseling_info",
            "transfer": "transfer", "sports/sports_quota": ("sports", "sports_quota"),
            "nri/nri_admission": ("nri", "nri_admission"),
            "management/management_quota": ("management", "management_quota"),
            "distance_ed/distance_education": ("distance_ed", "distance_education"),
            "grievance": "grievance", "lateral_entry": "lateral_entry",
            "institution/hod": ("institution", "hod"), "seats": "seats",
            "repeat": "repeat", "loan": "loan", "document": "document",
            "safety": "safety", "career_confusion": "career_confusion",
        }
        for rule_key, rule_result in INTENT_RULES:
            targets = intent_match_map[rule_key]
            matches_intent = intent in (targets if isinstance(targets, tuple) else (targets,))
            cond = f"intent == {rule_key}"
            matched = _eval(cond, matches_intent, rule_result)
            # Build explanation
            if not matched:
                im_v = 0.0
                feats = [
                    _feat("intent_match", 0.0, 0.0, f"intent is '{intent}', target is '{rule_key}'"),
                    _feat("intent_distance", 0.0, 0.0, "no match"),
                ]
                explanations.append(RuleExplanation(
                    rule_name=cond, result=rule_result, base_score=0.0,
                    features=feats, final_score=0.0, matched=False,
                ))
            else:
                feats = [
                    _feat("intent_match", 1.0, 0.6, f"intent '{intent}' == target '{rule_key}'"),
                    _feat("intent_confidence", understanding.intent.confidence, 0.2,
                          "intent detection confidence"),
                ]
                if signal_score > 0.4 and dominant_signal == "anxiety":
                    feats.append(_feat("signal_penalty", signal_score, 0.0,
                                       "intent overrides anxiety signal"))
                explanations.append(RuleExplanation(
                    rule_name=cond, result=rule_result, base_score=0.0,
                    features=feats, final_score=1.0, matched=True,
                ))
                break  # first match wins in waterfall
        else:
            # No intent matched — domain readiness gate (only for non-answerable intents)
            if intent not in ANSWERABLE_GENERALLY and not readiness.ready:
                n_missing = len(readiness.missing_critical)
                missing_str = ", ".join(readiness.missing_critical[:3])
                if n_missing >= 3:
                    _eval("blocked: 3+ critical fields missing", True, "needs_profile_initial")
                    explanations.append(RuleExplanation(
                        rule_name="blocked: 3+ critical fields missing",
                        result="needs_profile_initial", base_score=0.0,
                        features=[_feat("missing_critical", float(n_missing), 0.8,
                                        f"missing {missing_str}"),
                                  _feat("blocked", 1.0, 0.0, f"intent={intent} not answerable generally")],
                        final_score=1.0, matched=True,
                    ))
                elif n_missing > 0:
                    _eval("blocked: some critical fields missing", True, "needs_profile_completion")
                    explanations.append(RuleExplanation(
                        rule_name="blocked: some critical fields missing",
                        result="needs_profile_completion", base_score=0.0,
                        features=[_feat("missing_critical", float(n_missing), 0.8,
                                        f"missing {missing_str}"),
                                  _feat("blocked", 1.0, 0.0, f"intent={intent} not answerable generally")],
                        final_score=1.0, matched=True,
                    ))
                else:
                    _eval("fallback", True, "needs_personalized_guidance")
                    explanations.append(RuleExplanation(
                        rule_name="fallback", result="needs_personalized_guidance", base_score=0.3,
                        features=[_feat("fallback", 1.0, 0.0,
                                        "no intent or blocked readiness rule matched but missing_critical is empty")],
                        final_score=0.3, matched=True,
                    ))
            else:
                # Answerable intent with no intent match, or ready — fallback to guidance
                _eval("fallback", True, "needs_personalized_guidance")
                explanations.append(RuleExplanation(
                    rule_name="fallback", result="needs_personalized_guidance", base_score=0.3,
                    features=[_feat("fallback", 1.0, 0.0, "no intent rule matched")],
                    final_score=0.3, matched=True,
                ))

        # Compute runner-up and margin
        matched_rules = [r for r in rules if r.matched]
        if len(matched_rules) >= 2:
            runner = matched_rules[-2]
            winner_r = matched_rules[-1]
            runner_up_name = runner.result or runner.condition
            margin = (winner_r.score or 1.0) - (runner.score or 0.0)
        elif matched_rules:
            runner_up_name = ""
            margin = 0.0
        else:
            runner_up_name = ""
            margin = 0.0

        return {
            "rules": rules,
            "explanations": explanations,
            "signal_name": signal_name,
            "signal_score": signal_score,
            "runner_up": runner_up_name,
            "margin": margin,
        }

    def _find_unknowns(
        self, understanding: UnderstandingResult
    ) -> list[str]:
        return list(understanding.missing_info.items)

    def _identify_risks(
        self, understanding: UnderstandingResult, readiness: ReadinessResult
    ) -> list[str]:
        risks: list[str] = []
        if understanding.signals.anxiety > 0.5:
            risks.append("student_shows_anxiety")
        if understanding.signals.confusion > 0.5:
            risks.append("student_shows_confusion")
        if understanding.signals.frustration > 0.5:
            risks.append("student_shows_frustration")
        if readiness.blocked and len(readiness.missing_critical) >= 3:
            risks.append("insufficient_profile_for_guidance")
        elif len(readiness.missing_critical) >= 3:
            risks.append("partial_profile_for_guidance")
        return risks

    def _identify_opportunities(
        self, understanding: UnderstandingResult, state: ConversationState | None
    ) -> list[str]:
        opportunities: list[str] = []
        rank = self._resolve_rank(understanding, state)
        if rank is not None and isinstance(rank, (int, float)) and rank <= 60000:
            opportunities.append("competitive_rank")
        if self._has_field(understanding, "career.interest"):
            opportunities.append("clear_interest_identified")
        if understanding.intent.confidence > 0.7:
            opportunities.append("clear_intent_detected")
        return opportunities

    def _determine_knowledge_needed(
        self, understanding: UnderstandingResult, stage: str
    ) -> list[str]:
        needed: list[str] = []
        intent = understanding.intent.primary
        if intent != "unknown":
            needed.append(f"{intent}_information")
        if stage in ("evaluation", "decision"):
            needed.append("comparison_data")
            needed.append("cutoff_data")
        if understanding.signals.financial_concern > 0.3:
            needed.append("scholarship_data")
        if not needed:
            needed.append("general_information")
        return needed

    def _score_confidence(
        self, understanding: UnderstandingResult, readiness: ReadinessResult
    ) -> float:
        score = understanding.confidence * 0.5
        score += readiness.completeness * 0.3
        has_rank = self._has_field(understanding, "academic.rank")
        if has_rank:
            score += 0.1
        if understanding.intent.confidence > 0.5:
            score += 0.1
        return min(1.0, score)
