"""Contact information handler."""

from __future__ import annotations

import re

from .base import BaseHandler
from ..core.models import ConversationState, Intent, Language
from ..knowledge.loader import get_kb


class ContactHandler(BaseHandler):
    """Handles contact/principal/phone queries."""

    def can_handle(self, intent: Intent) -> bool:
        return intent in (Intent.CONTACT, Intent.PRINCIPAL)

    async def handle(self, query: str, lang: Language, state: ConversationState | None) -> str | None:
        kb = get_kb()
        q = query.lower()

        # Principal + Vice Principal
        if re.search(r"\bvice[\s-]?principal\b", q) and re.search(r"\bprincipal\b", q):
            principal = kb.get("principal", {})
            vp = kb.get("vice_principal", {})
            p_name = principal.get("name", "")
            vp_name = vp.get("name", "")
            return self.format_response(
                en=f"The principal of BCREC is {p_name} and the vice principal is {vp_name}.",
                hi=f"BCREC ke principal {p_name} hain aur vice principal {vp_name} hain.",
                bn=f"BCREC এর principal {p_name} এবং vice principal {vp_name}।",
                lang=lang,
            )

        # Vice Principal
        if re.search(r"\bvice[\s-]?principal\b", q):
            vp = kb.get("vice_principal", {})
            name = vp.get("name", "")
            return self.format_response(
                en=f"The vice principal of BCREC is {name}.",
                hi=f"BCREC ke vice principal {name} hain.",
                bn=f"BCREC এর vice principal {name}।",
                lang=lang,
            )

        # Principal
        if re.search(r"\bprincipal\b", q):
            principal = kb.get("principal", {})
            name = principal.get("name", "")
            phone = principal.get("phone", "")
            return self.format_response(
                en=f"The principal of BCREC is {name}. Phone: {phone}.",
                hi=f"BCREC ke principal {name} hain. Phone: {phone}.",
                bn=f"BCREC এর principal {name}। ফোন: {phone}।",
                lang=lang,
            )

        # Contact info
        if re.search(r"\b(contact|phone|mobile|call|helpline|number|email)\b", q):
            college = kb.get("college", {})
            phone = college.get("phone", "")
            email = college.get("email", "")
            return self.format_response(
                en=f"BCREC can be reached at {phone} or email {email}.",
                hi=f"BCREC se {phone} ya email {email} par contact kar sakte hain.",
                bn=f"BCREC এ যোগাযোগ করতে পারেন {phone} অথবা ইমেইল {email}।",
                lang=lang,
            )

        return None
