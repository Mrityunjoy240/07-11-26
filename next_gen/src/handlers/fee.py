"""Fee query handler — structured fee lookups without LLM."""

from __future__ import annotations

import re

from .base import BaseHandler
from ..core.models import ConversationState, Intent, Language
from ..knowledge.loader import get_kb


class FeeHandler(BaseHandler):
    """Handles fee-related queries using structured JSON data."""

    def can_handle(self, intent: Intent) -> bool:
        return intent == Intent.FEE

    async def handle(self, query: str, lang: Language, state: ConversationState | None) -> str | None:
        kb = get_kb()
        dept_code = self.extract_department(query)
        q = query.lower()

        # General fee overview
        if not dept_code:
            return self._general_fee_response(lang)

        # Department-specific fee
        dept = kb.get_department(dept_code)
        if not dept:
            return None

        fees = dept.get("fees", {})
        total = fees.get("total", 0)
        per_sem = fees.get("per_semester", 0)
        admission = fees.get("admission", 0)
        full_name = dept.get("full_name", dept_code)

        # Determine query type
        if re.search(r"\bsemester\s*fee\b|\bper\s*semester\b|\bsem\s*fee\b", q):
            return self._semester_fee_response(full_name, dept_code, per_sem, lang)
        if re.search(r"\badmission\s*fee\b", q):
            return self._admission_fee_response(full_name, dept_code, admission, lang)
        return self._total_fee_response(full_name, dept_code, total, per_sem, lang)

    def _general_fee_response(self, lang: Language) -> str:
        kb = get_kb()
        depts = kb.get_all_departments()

        # Group by fee tier
        tier1 = []  # 604700
        tier2 = []  # 567100
        tier3 = []  # 429100

        for code, data in depts.items():
            total = data.get("fees", {}).get("total", 0)
            if total >= 600000:
                tier1.append(code)
            elif total >= 500000:
                tier2.append(code)
            else:
                tier3.append(code)

        return self.format_response(
            en=f"BCREC B.Tech fees vary by branch. {', '.join(tier1)}: 6,04,700. {', '.join(tier2)}: 5,67,100. {', '.join(tier3)}: 4,29,100 total. Which branch are you interested in?",
            hi=f"BCREC mein B.Tech fees branch ke hisaab se alag hai. {', '.join(tier1)}: 6,04,700. {', '.join(tier2)}: 5,67,100. {', '.join(tier3)}: 4,29,100 total. Kaunsi branch mein interest hai?",
            bn=f"BCREC তে B.Tech ফি শাখা অনুযায়ী আলাদা। {', '.join(tier1)}: ৬,০৪,৭০০। {', '.join(tier2)}: ৫,৬৭,১০০। {', '.join(tier3)}: ৪,২৯,১০০। কোন শাখায় আগ্রহ?",
            lang=lang,
        )

    def _total_fee_response(self, name: str, code: str, total: int, per_sem: int, lang: Language) -> str:
        total_str = f"{total:,}"
        per_sem_str = f"{per_sem:,}"
        return self.format_response(
            en=f"The total course fee for {name} ({code}) is {total_str} rupees. Per semester fee is approximately {per_sem_str} rupees.",
            hi=f"{name} ({code}) ka total course fee {total_str} rupaye hai. Har semester ka fee lagbhag {per_sem_str} rupaye hai.",
            bn=f"{name} ({code}) এর মোট কোর্স ফি {total_str} টাকা। প্রতি সেমিস্টার ফি প্রায় {per_sem_str} টাকা।",
            lang=lang,
        )

    def _semester_fee_response(self, name: str, code: str, per_sem: int, lang: Language) -> str:
        per_sem_str = f"{per_sem:,}"
        return self.format_response(
            en=f"The per-semester fee for {name} ({code}) is {per_sem_str} rupees.",
            hi=f"{name} ({code}) ka semester fee {per_sem_str} rupaye hai.",
            bn=f"{name} ({code}) এর প্রতি সেমিস্টার ফি {per_sem_str} টাকা।",
            lang=lang,
        )

    def _admission_fee_response(self, name: str, code: str, admission: int, lang: Language) -> str:
        admission_str = f"{admission:,}"
        return self.format_response(
            en=f"The admission fee for {name} ({code}) is {admission_str} rupees.",
            hi=f"{name} ({code}) ka admission fee {admission_str} rupaye hai.",
            bn=f"{name} ({code}) এর ভর্তি ফি {admission_str} টাকা।",
            lang=lang,
        )
