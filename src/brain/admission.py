from dataclasses import dataclass

from src.brain.interfaces import BrainQuery, PolicyResult, Reason

_PCM_MINIMUM = 45.0

_DEFAULT_CUTOFFS: dict[str, dict[str, tuple[int, int]]] = {
    "general": {
        "CSE": (1, 15000), "AIML": (1, 18000), "IT": (1, 22000),
        "ECE": (1, 28000), "EE": (1, 40000), "ME": (1, 55000), "CE": (1, 70000),
    },
    "obc": {
        "CSE": (1, 22000), "AIML": (1, 26000), "IT": (1, 32000),
        "ECE": (1, 40000), "EE": (1, 55000), "ME": (1, 75000), "CE": (1, 95000),
    },
    "sc": {
        "CSE": (1, 40000), "AIML": (1, 48000), "IT": (1, 55000),
        "ECE": (1, 65000), "EE": (1, 85000), "ME": (1, 110000), "CE": (1, 140000),
    },
    "st": {
        "CSE": (1, 50000), "AIML": (1, 60000), "IT": (1, 70000),
        "ECE": (1, 85000), "EE": (1, 110000), "ME": (1, 140000), "CE": (1, 180000),
    },
}


@dataclass
class CutoffRepository:
    cutoffs: dict[str, dict[str, tuple[int, int]]] | None = None
    year: int = 2026
    source: str = "wbjee"

    def get_cutoffs(self, category: str) -> dict[str, tuple[int, int]]:
        data = self.cutoffs or _DEFAULT_CUTOFFS
        cat = category.lower().replace("ur", "general").replace(
            "unreserved", "general"
        ).replace("gen", "general")
        return data.get(cat, data["general"])


class AdmissionPolicy:
    def __init__(self, cutoff_repo: CutoffRepository | None = None) -> None:
        self._repo = cutoff_repo or CutoffRepository()

    def evaluate(self, query: BrainQuery) -> PolicyResult:
        why: list[Reason] = []

        if query.rank is None:
            return PolicyResult(
                applicable=False, confidence=0.0,
                details="No rank provided for eligibility check",
                why=[Reason("rank_provided", False, "No rank in query or profile")],
            )

        rank = float(query.rank)
        cutoffs = self._repo.get_cutoffs(query.category)
        why.append(Reason(
            "rank_provided", True,
            f"Rank {rank} provided for {query.category} category",
        ))

        eligible_branches: list[str] = []
        borderline_branches: list[str] = []
        for branch, (_, hi) in cutoffs.items():
            within = rank <= hi
            margin = (hi - rank) / hi if within else 0.0
            confident = margin > 0.15
            if within:
                if confident:
                    eligible_branches.append(branch)
                else:
                    borderline_branches.append(branch)
            why.append(Reason(
                f"{branch}_cutoff",
                within,
                f"Rank {rank} <= {branch} cutoff {hi} (margin {margin:.0%})",
            ))

        pcm_ok = True
        if query.pcm_percentage is not None and query.pcm_percentage < _PCM_MINIMUM:
            pcm_ok = False
        why.append(Reason(
            "pcm_minimum_met", pcm_ok,
            f"PCM {query.pcm_percentage}% >= {_PCM_MINIMUM}% minimum" if pcm_ok
            else f"PCM {query.pcm_percentage}% < {_PCM_MINIMUM}% minimum",
        ))

        likely = len(eligible_branches) > 0 or len(borderline_branches) > 0
        confidence = 0.0
        if query.rank:
            confidence = min(0.9, max(0.2, 1.0 - (rank / 300000)))
        if not pcm_ok:
            confidence *= 0.5

        note_parts: list[str] = []
        if eligible_branches:
            note_parts.append(f"Likely: {', '.join(eligible_branches)}")
        if borderline_branches:
            note_parts.append(f"Borderline: {', '.join(borderline_branches)}")
        if not pcm_ok:
            note_parts.append(f"PCM below {_PCM_MINIMUM}% may restrict eligibility")
        if not note_parts:
            note_parts.append("Rank above typical cutoff ranges")

        return PolicyResult(
            applicable=likely,
            confidence=round(confidence, 2),
            details=" | ".join(note_parts),
            data={
                "eligible_branches": eligible_branches,
                "borderline_branches": borderline_branches,
                "category": self._normalize(query.category),
                "pcm_minimum_met": pcm_ok,
            },
            why=why,
        )

    def _normalize(self, category: str) -> str:
        c = category.lower().replace("ur", "general").replace(
            "unreserved", "general"
        ).replace("gen", "general")
        return c if c in _DEFAULT_CUTOFFS else "general"
