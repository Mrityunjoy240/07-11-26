"""
StudentProfile — a strongly typed profile that fills across conversation turns.

Every conversation progressively builds this profile.
Missing information is derived deterministically from pathway required fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Sub-profile sections ───────────────────────────────────────────────

@dataclass
class AcademicProfile:
    rank: int | None = None
    exam: str = ""
    pcm_percentage: float | None = None
    board: str = ""
    qualification: str = ""
    diploma_percentage: float | None = None
    diploma_branch: str = ""
    current_college: str = ""
    current_branch: str = ""
    current_year: int | None = None

    @property
    def is_empty(self) -> bool:
        return all(v is None or v == "" or v == 0 for v in [
            self.rank, self.exam, self.pcm_percentage, self.board,
            self.diploma_percentage, self.diploma_branch,
            self.current_college, self.current_branch, self.current_year,
        ])


@dataclass
class PersonalProfile:
    category: str = ""
    gender: str = ""
    location: str = ""
    budget: float | None = None
    hostel_required: bool | None = None

    @property
    def is_empty(self) -> bool:
        return all(v is None or v == "" for v in [
            self.category, self.gender, self.location,
        ]) and self.budget is None and self.hostel_required is None


@dataclass
class CareerProfile:
    interest: str = ""
    preferred_branch: str = ""
    career_goal: str = ""

    @property
    def is_empty(self) -> bool:
        return all(v is None or v == "" for v in [
            self.interest, self.preferred_branch, self.career_goal,
        ])


# ── StudentProfile ─────────────────────────────────────────────────────

@dataclass
class StudentProfile:
    academic: AcademicProfile = field(default_factory=AcademicProfile)
    personal: PersonalProfile = field(default_factory=PersonalProfile)
    career: CareerProfile = field(default_factory=CareerProfile)
    admission_pathway: str = "regular"
    student_type: str = "prospective"
    conversation_stage: str = "discovery"
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize for telemetry / storage."""
        return {
            "academic": {
                "rank": self.academic.rank,
                "exam": self.academic.exam,
                "pcm_percentage": self.academic.pcm_percentage,
                "board": self.academic.board,
                "qualification": self.academic.qualification,
                "diploma_percentage": self.academic.diploma_percentage,
                "diploma_branch": self.academic.diploma_branch,
                "current_college": self.academic.current_college,
                "current_branch": self.academic.current_branch,
                "current_year": self.academic.current_year,
            },
            "personal": {
                "category": self.personal.category,
                "gender": self.personal.gender,
                "location": self.personal.location,
                "budget": self.personal.budget,
                "hostel_required": self.personal.hostel_required,
            },
            "career": {
                "interest": self.career.interest,
                "preferred_branch": self.career.preferred_branch,
                "career_goal": self.career.career_goal,
            },
            "admission_pathway": self.admission_pathway,
            "student_type": self.student_type,
            "conversation_stage": self.conversation_stage,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StudentProfile:
        acad = data.get("academic", {})
        pers = data.get("personal", {})
        car = data.get("career", {})
        return cls(
            academic=AcademicProfile(
                rank=acad.get("rank"),
                exam=acad.get("exam", ""),
                pcm_percentage=acad.get("pcm_percentage"),
                board=acad.get("board", ""),
                qualification=acad.get("qualification", "12th"),
                diploma_percentage=acad.get("diploma_percentage"),
                diploma_branch=acad.get("diploma_branch", ""),
                current_college=acad.get("current_college", ""),
                current_branch=acad.get("current_branch", ""),
                current_year=acad.get("current_year"),
            ),
            personal=PersonalProfile(
                category=pers.get("category", ""),
                gender=pers.get("gender", ""),
                location=pers.get("location", ""),
                budget=pers.get("budget"),
                hostel_required=pers.get("hostel_required"),
            ),
            career=CareerProfile(
                interest=car.get("interest", ""),
                preferred_branch=car.get("preferred_branch", ""),
                career_goal=car.get("career_goal", ""),
            ),
            admission_pathway=data.get("admission_pathway", "regular"),
            student_type=data.get("student_type", "prospective"),
            conversation_stage=data.get("conversation_stage", "discovery"),
            confidence=data.get("confidence", 0.0),
        )


# ── Pathway required fields ────────────────────────────────────────────
# Each pathway lists the profile fields required for meaningful counseling.
# Missing information = required fields that are still None/empty.

PATHWAY_REQUIRED_FIELDS: dict[str, list[str]] = {
    "regular": [
        "academic.rank", "academic.pcm_percentage",
        "personal.category", "career.interest",
    ],
    "lateral_entry": [
        "academic.diploma_percentage", "academic.diploma_branch",
        "academic.exam",
    ],
    "nri": [
        "personal.category", "academic.board",
        "academic.qualification", "academic.pcm_percentage",
    ],
    "sports_quota": [
        "personal.category", "career.interest",
        "academic.rank",
    ],
    "management_quota": [
        "personal.category", "academic.rank", "academic.pcm_percentage",
    ],
    "transfer": [
        "academic.current_college", "academic.current_branch",
        "academic.current_year",
    ],
    "scholarship": [
        "personal.category", "academic.rank", "academic.pcm_percentage",
    ],
    "hostel": [
        "personal.category", "personal.hostel_required",
    ],
    "fee": [
        "personal.category", "academic.rank",
    ],
    "placement": [
        "career.interest",
    ],
    "grievance": [],
    "career_confusion": [
        "career.interest", "career.career_goal",
    ],
    "distance_education": [
        "personal.location",
    ],
    "counseling_info": [
        "academic.rank",
    ],
    "lateral_entry_intent": [  # when intent is lateral_entry but pathway not yet set
        "academic.diploma_percentage", "academic.diploma_branch",
    ],
    "management_quota_intent": [
        "personal.category", "academic.rank",
    ],
    "sports_quota_intent": [
        "personal.category", "career.interest",
    ],
    "nri_admission": [
        "personal.category", "academic.board",
    ],
}

# All possible field paths for validation
ALL_FIELD_PATHS: list[str] = [
    "academic.rank", "academic.exam", "academic.pcm_percentage",
    "academic.board", "academic.qualification",
    "academic.diploma_percentage", "academic.diploma_branch",
    "academic.current_college", "academic.current_branch", "academic.current_year",
    "personal.category", "personal.gender", "personal.location",
    "personal.budget", "personal.hostel_required",
    "career.interest", "career.preferred_branch", "career.career_goal",
]


def get_field(profile: StudentProfile, field_path: str) -> Any:
    """Get a field value from StudentProfile by dotted path.
    
    Example: get_field(profile, "academic.rank") → profile.academic.rank
    """
    parts = field_path.split(".")
    val: Any = profile
    for part in parts:
        if hasattr(val, part):
            val = getattr(val, part)
        else:
            return None
    return val


def set_field(profile: StudentProfile, field_path: str, value: Any) -> None:
    """Set a field value on StudentProfile by dotted path."""
    parts = field_path.split(".")
    obj: Any = profile
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


def is_field_set(profile: StudentProfile, field_path: str) -> bool:
    """Check if a profile field has a meaningful value."""
    val = get_field(profile, field_path)
    if val is None:
        return False
    if isinstance(val, str) and val.strip() == "":
        return False
    if isinstance(val, (int, float)) and val == 0:
        return False
    return True


def compute_missing(profile: StudentProfile, pathway: str | None = None) -> list[str]:
    """Determine which required fields are still missing for the given pathway.
    
    This is fully deterministic — no heuristics, no regex guessing.
    """
    pw = pathway or profile.admission_pathway
    required = PATHWAY_REQUIRED_FIELDS.get(pw, PATHWAY_REQUIRED_FIELDS["regular"])
    return [f for f in required if not is_field_set(profile, f)]
