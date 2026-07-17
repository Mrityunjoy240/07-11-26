"""Department, HOD, seats, placement, hostel, scholarship handlers."""

from __future__ import annotations

import re

from .base import BaseHandler
from ..core.models import ConversationState, Intent, Language
from ..knowledge.loader import get_kb


class DepartmentHandler(BaseHandler):
    """Handles department queries."""

    def can_handle(self, intent: Intent) -> bool:
        return intent == Intent.DEPARTMENT

    async def handle(self, query: str, lang: Language, state: ConversationState | None) -> str | None:
        kb = get_kb()
        dept_code = self.extract_department(query)

        if dept_code:
            dept = kb.get_department(dept_code)
            if dept:
                name = dept.get("full_name", dept_code)
                intake = dept.get("intake", "")
                return self.format_response(
                    en=f"{name} ({dept_code}) — {intake} seats.",
                    hi=f"{name} ({dept_code}) — {intake} seats.",
                    bn=f"{name} ({dept_code}) — {intake} seats।",
                    lang=lang,
                )

        # List all departments
        depts = kb.get_all_departments()
        dept_list = [f"{code}" for code in depts.keys()]
        return self.format_response(
            en=f"BCREC offers B.Tech in: {', '.join(dept_list)}.",
            hi=f"BCREC mein B.Tech programs: {', '.join(dept_list)}.",
            bn=f"BCREC তে B.Tech programs: {', '.join(dept_list)}।",
            lang=lang,
        )


class HODHandler(BaseHandler):
    """Handles HOD queries."""

    def can_handle(self, intent: Intent) -> bool:
        return intent == Intent.HOD

    async def handle(self, query: str, lang: Language, state: ConversationState | None) -> str | None:
        kb = get_kb()
        dept_code = self.extract_department(query)

        if dept_code:
            dept = kb.get_department(dept_code)
            if dept:
                hod = dept.get("hod", "")
                return self.format_response(
                    en=f"The HOD of {dept_code} is {hod}.",
                    hi=f"{dept_code} ke HOD {hod} hain.",
                    bn=f"{dept_code} এর HOD {hod}।",
                    lang=lang,
                )

        # List all HODs
        depts = kb.get_all_departments()
        hod_list = [f"{code}: {data.get('hod', 'N/A')}" for code, data in depts.items() if data.get("hod")]
        return self.format_response(
            en=f"Department Heads: {'; '.join(hod_list[:6])}.",
            hi=f"Department Heads: {'; '.join(hod_list[:6])}.",
            bn=f"বিভাগীয় প্রধান: {'; '.join(hod_list[:6])}।",
            lang=lang,
        )


class PlacementHandler(BaseHandler):
    """Handles placement queries."""

    def can_handle(self, intent: Intent) -> bool:
        return intent == Intent.PLACEMENT

    async def handle(self, query: str, lang: Language, state: ConversationState | None) -> str | None:
        kb = get_kb()
        dept_code = self.extract_department(query)
        q = query.lower()

        # Department-specific placement
        if dept_code:
            dept = kb.get_department(dept_code)
            if dept:
                placement = dept.get("placement", {})
                rate = placement.get("rate", "")
                avg = placement.get("avg_package", "")
                if rate:
                    return self.format_response(
                        en=f"{dept_code} has {rate} placement rate with average package {avg}.",
                        hi=f"{dept_code} mein placement {rate} hai, average package {avg}.",
                        bn=f"{dept_code} এ placement {rate}, গড় প্যাকেজ {avg}।",
                        lang=lang,
                    )

        # Overall placement
        placements = kb.get("placements", {})
        overall = placements.get("overall_rate", "")
        avg = placements.get("avg_package", "")
        if overall:
            return self.format_response(
                en=f"BCREC overall placement rate is {overall} with average package {avg}.",
                hi=f"BCREC ka overall placement {overall} hai, average package {avg}.",
                bn=f"BCREC এর overall placement {overall}, গড় প্যাকেজ {avg}।",
                lang=lang,
            )

        return None


class HostelHandler(BaseHandler):
    """Handles hostel queries."""

    def can_handle(self, intent: Intent) -> bool:
        return intent == Intent.HOSTEL

    async def handle(self, query: str, lang: Language, state: ConversationState | None) -> str | None:
        kb = get_kb()
        hostel = kb.get("hostel", {})
        available = hostel.get("available", False)

        if available:
            total = hostel.get("total", 0)
            boys = hostel.get("boys", 0)
            girls = hostel.get("girls", 0)
            capacity = hostel.get("capacity", 0)
            return self.format_response(
                en=f"Yes, hostel is available. {total} hostels — {boys} for boys, {girls} for girls — capacity {capacity} students.",
                hi=f"Haan, hostel available hai. {total} hostels — {boys} boys ke liye, {girls} girls ke liye — capacity {capacity} students.",
                bn=f"হ্যাঁ, হোস্টেল আছে। {total}টি হোস্টেল — {boys}টি ছেলেদের, {girls}টি মেয়েদের — ধারণক্ষমতা {capacity}।",
                lang=lang,
            )

        return self.format_response(
            en="Hostel accommodation is not currently available.",
            hi="Hostel abhi available nahi hai.",
            bn="হোস্টেল এখন উপলব্ধ নেই।",
            lang=lang,
        )


class ScholarshipHandler(BaseHandler):
    """Handles scholarship queries."""

    def can_handle(self, intent: Intent) -> bool:
        return intent == Intent.SCHOLARSHIP

    async def handle(self, query: str, lang: Language, state: ConversationState | None) -> str | None:
        kb = get_kb()
        scholarships = kb.get("scholarships", [])
        if scholarships:
            return self.format_response(
                en=f"BCREC offers scholarships: {', '.join(scholarships)}.",
                hi=f"BCREC mein scholarships hain: {', '.join(scholarships)}.",
                bn=f"BCREC তে scholarships আছে: {', '.join(scholarships)}।",
                lang=lang,
            )
        return None


class ChatHandler(BaseHandler):
    """Handles greetings, repeat, out-of-domain."""

    def can_handle(self, intent: Intent) -> bool:
        return intent in (Intent.GREETING, Intent.REPEAT, Intent.OUT_OF_DOMAIN)

    async def handle(self, query: str, lang: Language, state: ConversationState | None) -> str | None:
        intent = self._detect_intent(query)

        if lang == Language.HI:
            if intent == "greeting":
                return "Namaste! Main BCREC AI assistant hoon. Admissions, fees, courses, ya hostel ke baare mein koi sawal hai?"
            if intent == "repeat":
                return state.history[-1]["content"] if state and state.history else "Please ask your question again."
            if intent == "ood":
                return "Main sirf BCREC ke baare mein sawalon ka jawab de sakta hoon. Kripya college se related sawal puchen."

        if lang == Language.BN:
            if intent == "greeting":
                return "নমস্কার! আমি BCREC AI assistant। Admissions, fees, courses, বা hostel সম্পর্কে কোনো প্রশ্ন আছে?"
            if intent == "repeat":
                return state.history[-1]["content"] if state and state.history else "Please ask your question again."
            if intent == "ood":
                return "আমি শুধুমাত্র BCREC সম্পর্কে প্রশ্নের উত্তর দিতে পারি। অনুগ্রহ করে কলেজ সংক্রান্ত প্রশ্ন করুন।"

        # English
        if intent == "greeting":
            return "Hello! I'm the BCREC AI assistant. How can I help you with admissions, fees, courses, or hostel details?"
        if intent == "repeat":
            return state.history[-1]["content"] if state and state.history else "Please ask your question again."
        if intent == "ood":
            return "I can only answer questions about BCREC. Please ask a college-related question."

        return None

    def _detect_intent(self, query: str) -> str:
        """Detect which sub-intent this is."""
        import re
        q = query.strip().lower()
        if re.match(r"^(hi+|hello+|hey+|namaste|namaskar|nomoshkar)$", q):
            return "greeting"
        if re.match(r"^(repeat|again|pardon|come\s+again)$", q):
            return "repeat"
        # Default to OOD for this handler (since can_handle already filtered)
        return "ood"
