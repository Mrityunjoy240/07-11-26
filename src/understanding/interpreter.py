"""
Domain Interpreter — maps raw entities and text to admission domain concepts.

Sits between Entity Extraction and Signal Detection in the Understanding pipeline.
Its job is NOT to extract more regexes — it's to reason about what the extracted
entities mean in the context of college admissions.

Example:
    Input:  entities=[{field: "qualification", value: "diploma"}]
    Output: pathway=lateral_entry, exam=jexpo, suggested_year=2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.understanding.vocabulary import (
    ADMISSION_ENTITIES,
    INTENT_CONCEPTS,
    PATHWAYS,
    QUALIFICATIONS,
    STUDENT_TYPES,
    Concept,
    match_concept,
)


@dataclass
class DomainInterpretation:
    """
    High-level interpretation of what the student's query means.

    This is the bridge between raw text → admission knowledge.
    """
    pathway: str = "regular"
    qualification: str = "12th"
    student_type: str = "prospective"
    primary_intent: str = "unknown"
    all_intents: list[str] = field(default_factory=list)
    domain_entities: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class DomainInterpreter:
    """
    Interprets student text and extracted entities against college admission concepts.

    This replaces the pattern of adding more regexes. Instead, new admission
    knowledge goes into vocabulary.py as concept definitions, and the interpreter
    maps them to meaningful domain inferences.
    """

    def interpret(self, text: str, extracted_facts: list | None = None) -> DomainInterpretation:
        result = DomainInterpretation()

        if not text:
            return result

        # ── 1. Detect admission pathway ─────────────────────────────
        matched_pathways = match_concept(text, PATHWAYS)
        if matched_pathways:
            result.pathway = matched_pathways[0].id
            result.notes.append(f"pathway={matched_pathways[0].id}")

        # ── 2. Detect qualification ────────────────────────────────
        matched_quals = match_concept(text, QUALIFICATIONS)
        if matched_quals:
            result.qualification = matched_quals[0].id
            result.notes.append(f"qualification={matched_quals[0].id}")

        # ── 3. Detect student type ─────────────────────────────────
        matched_types = match_concept(text, STUDENT_TYPES)
        if matched_types:
            result.student_type = matched_types[0].id

        # ── 4. Detect all intents (not just one) ───────────────────
        matched_intents = match_concept(text, INTENT_CONCEPTS)
        result.all_intents = [c.id for c in matched_intents]
        if matched_intents:
            result.primary_intent = matched_intents[0].id

        # ── 5. Admission-specific domain entities ──────────────────
        matched_entities = match_concept(text, ADMISSION_ENTITIES)
        for c in matched_entities:
            result.domain_entities[c.id] = True
            result.notes.append(f"entity={c.id}")

        # ── 6. Derived inferences from combinations ────────────────
        self._apply_derived_inferences(result, text)

        return result

    def _apply_derived_inferences(self, result: DomainInterpretation, text: str) -> None:
        """
        Apply higher-order reasoning based on combinations of detected concepts.

        This is where admission knowledge lives: if pathway=diploma, then
        exam=jexpo, year=2nd, etc. These are NOT regexes — they're rules
        about how the admission domain works.
        """
        tl = text.lower()

        # Lateral entry → exam is JEXPO, entry is 2nd year
        if result.pathway == "lateral_entry":
            result.domain_entities["exam"] = "jexpo"
            result.domain_entities["suggested_year"] = 2
            result.domain_entities["needs_diploma_percentage"] = True

        # Management quota → budget likely high
        if result.pathway == "management_quota":
            result.domain_entities["likely_budget"] = "high"
            result.domain_entities["requires_policy_explanation"] = True

        # Sports quota → needs certificates
        if result.pathway == "sports_quota":
            result.domain_entities["needs_certificate_verification"] = True
            result.domain_entities["may_have_cutoff_relaxation"] = True

        # NRI → separate fee structure
        if result.pathway == "nri":
            result.domain_entities["fee_structure"] = "nri"
            result.domain_entities["needs_document_equivalency"] = True

        # Transfer → needs current college info
        if result.pathway == "transfer":
            result.domain_entities["needs_current_college"] = True
            result.domain_entities["needs_current_branch"] = True
            result.domain_entities["needs_current_year"] = True
            result.domain_entities["needs_transfer_reason"] = True

        # Scholarship → needs category info
        if result.pathway == "scholarship":
            result.domain_entities["needs_category"] = True
            if "renewal" in tl or "renew" in tl or "hasn't been renewed" in tl:
                result.domain_entities["scholarship_type"] = "renewal"
                result.domain_entities["existing_student"] = True

        # Existing student having problems
        if result.student_type == "existing":
            if "scholarship" in tl or "renewal" in tl or "re-evaluation" in tl or "marks" in tl:
                result.domain_entities["needs_administrative_help"] = True

        # Parent mode
        if result.student_type == "parent":
            result.domain_entities["parent_mode"] = True
            if "safety" in tl or "safe" in tl or "secure" in tl or "girl" in tl:
                result.domain_entities["needs_reassurance"] = True

        # Career confusion
        if "anthropology" in tl or "history" in tl or "sociology" in tl or "not engineering" in tl:
            result.domain_entities["career_conflict"] = True
            result.domain_entities["needs_career_counseling"] = True

        # Distance education
        if "distance" in tl or "online" in tl:
            result.domain_entities["clarify_no_distance_btech"] = True
            result.domain_entities["suggest_regular_with_hostel"] = True

        # Counseling info
        if "counseling" in tl or "document" in tl:
            result.domain_entities["needs_counseling_schedule"] = True
            result.domain_entities["needs_document_checklist"] = True
