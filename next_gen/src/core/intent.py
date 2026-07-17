"""Unified intent router — single decision point for all queries."""

from __future__ import annotations

import re
from ..core.models import ConversationState, Intent, Language


class IntentRouter:
    """Routes queries to intents using regex patterns with priority ordering."""

    # Greeting patterns
    _GREETING = re.compile(
        r"^(hi+|hello+|hey+|namaste|namaskar|nomoshkar|hola|good\s+(morning|afternoon|evening))$",
        re.IGNORECASE,
    )

    # Out-of-domain patterns
    _OOD = re.compile(
        r"\b(weather|cricket|ipl|movie|bollywood|hollywood|politics|election|"
        r"recipe|cook|food|pizza|biryani|translate|joke|poem|song|lyrics)\b",
        re.IGNORECASE,
    )

    # Repeat patterns
    _REPEAT = re.compile(
        r"^(repeat|again|pardon|come\s+again|what\s+did\s+you\s+say)$",
        re.IGNORECASE,
    )

    # Intent patterns (ordered by priority)
    _PATTERNS: list[tuple[Intent, re.Pattern]] = [
        (Intent.PRINCIPAL, re.compile(r"\b(principal|vice[\s-]?principal|princepal)\b", re.I)),
        (Intent.CONTACT, re.compile(r"\b(contact|phone|mobile|call|helpline|number|email)\b", re.I)),
        (Intent.FEE, re.compile(r"\b(fee|fees|total\s*fee|semester\s*fee|admission\s*fee|course\s*fee|kitna|koto)\b", re.I)),
        (Intent.ADMISSION, re.compile(r"\b(admission|admit|apply|eligibility|entrance|wbjee|jee)\b", re.I)),
        (Intent.PLACEMENT, re.compile(r"\b(placement|placed|recruit|package|lpa|job|company)\b", re.I)),
        (Intent.HOSTEL, re.compile(r"\b(hostel|accommodation|room|mess|food)\b", re.I)),
        (Intent.SCHOLARSHIP, re.compile(r"\b(scholarships?|scholership|tfw|kanyashree|aid)\b", re.I)),
        (Intent.HOD, re.compile(r"\b(hod|hods|head\s*of\s*department|department\s*head)\b", re.I)),
        (Intent.FACULTY, re.compile(r"\b(professor|faculty|teacher|sir|madam|dr\.?|prof\.?)\b", re.I)),
        (Intent.DEPARTMENT, re.compile(r"\b(department|branch|course|program|b\.tech|offer|subject)\b", re.I)),
        (Intent.CUTOFF, re.compile(r"\b(cutoff|cut.off|rank|closing|opening)\b", re.I)),
        (Intent.SEATS, re.compile(r"\b(seats|intake|capacity)\b", re.I)),
        (Intent.SAFETY, re.compile(r"\b(safety|safe|ragging|security|women.*safe)\b", re.I)),
        (Intent.TIMINGS, re.compile(r"\b(timing|hours|schedule|when.*open|when.*close)\b", re.I)),
    ]

    async def route(self, query: str, lang: Language, state: ConversationState | None) -> Intent:
        """Route query to intent."""
        q = query.strip().lower()

        if not q:
            return Intent.UNKNOWN

        # Check greeting
        if self._GREETING.match(q):
            return Intent.GREETING

        # Check out-of-domain
        if self._OOD.search(q):
            return Intent.OUT_OF_DOMAIN

        # Check repeat
        if self._REPEAT.match(q):
            return Intent.REPEAT

        # Check structured intents
        for intent, pattern in self._PATTERNS:
            if pattern.search(q):
                return intent

        return Intent.UNKNOWN
