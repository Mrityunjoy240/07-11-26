import pytest

from src.conversation.state import ConversationState
from src.understanding.engine import UnderstandingEngine
from src.understanding.profile import (
    PATHWAY_REQUIRED_FIELDS,
    AcademicProfile,
    CareerProfile,
    PersonalProfile,
    StudentProfile,
    compute_missing,
    get_field,
    is_field_set,
    set_field,
)


# ── StudentProfile model ───────────────────────────────────────────────

class TestAcademicProfile:
    def test_defaults(self):
        a = AcademicProfile()
        assert a.rank is None
        assert a.pcm_percentage is None
        assert a.board == ""
        assert a.is_empty is True

    def test_is_empty_with_values(self):
        a = AcademicProfile(rank=48000)
        assert a.is_empty is False

    def test_is_empty_with_zero_rank(self):
        a = AcademicProfile(rank=0)
        assert a.is_empty is True


class TestPersonalProfile:
    def test_defaults(self):
        p = PersonalProfile()
        assert p.category == ""
        assert p.budget is None
        assert p.is_empty is True

    def test_is_empty_with_values(self):
        p = PersonalProfile(category="general")
        assert p.is_empty is False


class TestCareerProfile:
    def test_defaults(self):
        c = CareerProfile()
        assert c.interest == ""
        assert c.is_empty is True

    def test_is_empty_with_values(self):
        c = CareerProfile(interest="CSE")
        assert c.is_empty is False


class TestStudentProfile:
    def test_to_dict(self):
        p = StudentProfile()
        p.academic.rank = 48000
        p.personal.category = "general"
        p.career.interest = "CSE"
        d = p.to_dict()
        assert d["academic"]["rank"] == 48000
        assert d["personal"]["category"] == "general"
        assert d["career"]["interest"] == "CSE"

    def test_from_dict(self):
        d = {
            "academic": {"rank": 48000, "pcm_percentage": 85.0},
            "personal": {"category": "obc"},
            "career": {"interest": "ECE"},
        }
        p = StudentProfile.from_dict(d)
        assert p.academic.rank == 48000
        assert p.academic.pcm_percentage == 85.0
        assert p.personal.category == "obc"
        assert p.career.interest == "ECE"

    def test_from_dict_empty(self):
        p = StudentProfile.from_dict({})
        assert p.academic.rank is None
        assert p.admission_pathway == "regular"


# ── Field access helpers ──────────────────────────────────────────────

class TestGetField:
    def test_rank(self):
        p = StudentProfile()
        p.academic.rank = 48000
        assert get_field(p, "academic.rank") == 48000

    def test_interest(self):
        p = StudentProfile()
        p.career.interest = "CSE"
        assert get_field(p, "career.interest") == "CSE"

    def test_missing_field(self):
        p = StudentProfile()
        assert get_field(p, "nonexistent.field") is None


class TestSetField:
    def test_rank(self):
        p = StudentProfile()
        set_field(p, "academic.rank", 48000)
        assert p.academic.rank == 48000

    def test_category(self):
        p = StudentProfile()
        set_field(p, "personal.category", "sc")
        assert p.personal.category == "sc"


class TestIsFieldSet:
    def test_none(self):
        assert is_field_set(StudentProfile(), "academic.rank") is False

    def test_empty_string(self):
        p = StudentProfile()
        p.career.interest = ""
        assert is_field_set(p, "career.interest") is False

    def test_value_set(self):
        p = StudentProfile()
        p.academic.rank = 48000
        assert is_field_set(p, "academic.rank") is True

    def test_string_set(self):
        p = StudentProfile()
        p.personal.category = "general"
        assert is_field_set(p, "personal.category") is True


# ── Deterministic missing info ────────────────────────────────────────

class TestComputeMissing:
    def test_all_missing_for_regular(self):
        p = StudentProfile(admission_pathway="regular")
        missing = compute_missing(p)
        assert "academic.rank" in missing
        assert "academic.pcm_percentage" in missing
        assert "personal.category" in missing
        assert "career.interest" in missing
        assert len(missing) == 4

    def test_rank_supplied(self):
        p = StudentProfile(admission_pathway="regular")
        p.academic.rank = 48000
        missing = compute_missing(p)
        assert "academic.rank" not in missing
        assert len(missing) == 3

    def test_all_supplied(self):
        p = StudentProfile(admission_pathway="regular")
        p.academic.rank = 48000
        p.academic.pcm_percentage = 85.0
        p.personal.category = "general"
        p.career.interest = "CSE"
        missing = compute_missing(p)
        assert len(missing) == 0

    def test_lateral_entry_pathway(self):
        p = StudentProfile(admission_pathway="lateral_entry")
        missing = compute_missing(p)
        assert "academic.diploma_percentage" in missing
        assert "academic.diploma_branch" in missing

    def test_lateral_entry_full(self):
        p = StudentProfile(admission_pathway="lateral_entry")
        p.academic.diploma_percentage = 78.0
        p.academic.diploma_branch = "EE"
        p.academic.exam = "JEXPO"
        missing = compute_missing(p)
        assert len(missing) == 0

    def test_nri_pathway(self):
        p = StudentProfile(admission_pathway="nri")
        missing = compute_missing(p)
        assert "personal.category" in missing
        assert "academic.board" in missing

    def test_grievance_pathway(self):
        p = StudentProfile(admission_pathway="grievance")
        missing = compute_missing(p)
        assert len(missing) == 0  # grievance has no required fields

    def test_career_confusion_pathway(self):
        p = StudentProfile(admission_pathway="career_confusion")
        missing = compute_missing(p)
        assert "career.interest" in missing
        assert "career.career_goal" in missing

    def test_explicit_pathway_override(self):
        p = StudentProfile(admission_pathway="regular")
        p.academic.rank = 48000
        # Override: check lateral_entry requirements
        missing = compute_missing(p, pathway="lateral_entry")
        assert "academic.diploma_percentage" in missing
        assert "academic.rank" not in missing  # rank not required for lateral

    def test_scholarship_pathway(self):
        p = StudentProfile(admission_pathway="scholarship")
        p.academic.rank = 12000
        p.academic.pcm_percentage = 92.0
        missing = compute_missing(p)
        assert "personal.category" in missing
        assert "academic.rank" not in missing
        assert "academic.pcm_percentage" not in missing

    def test_hostel_pathway(self):
        p = StudentProfile(admission_pathway="hostel")
        p.personal.category = "general"
        missing = compute_missing(p)
        assert "hostel_requirement" or "personal.hostel_required" in missing


# ── Cross-turn profile updates ────────────────────────────────────────

class TestCrossTurnProfileBuilding:
    def test_two_turns_build_profile(self):
        engine = UnderstandingEngine()
        state = ConversationState(session_id="test")

        r1 = engine.understand("my rank is 48000 and I have 82 PCM", state)
        assert r1.profile.academic.rank == 48000
        assert r1.profile.academic.pcm_percentage == 82.0
        assert r1.profile.personal.category == ""
        assert r1.profile.career.interest == ""

        # Simulate storing profile in state
        state.profile = r1.profile.to_dict()

        r2 = engine.understand("I am from SC category and interested in CSE", state)
        assert r2.profile.academic.rank == 48000  # preserved from turn 1
        assert r2.profile.academic.pcm_percentage == 82.0  # preserved
        assert r2.profile.personal.category == "sc"
        assert "cse" in r2.profile.career.interest.lower()

    def test_three_turns_full_profile(self):
        engine = UnderstandingEngine()
        state = ConversationState(session_id="test")

        r1 = engine.understand("my rank is 48000", state)
        state.profile = r1.profile.to_dict()

        r2 = engine.understand("I studied in WBCHSE board", state)
        state.profile = r2.profile.to_dict()
        assert r2.profile.academic.rank == 48000
        assert r2.profile.academic.board == "WBCHSE"

        r3 = engine.understand("I am from general category and interested in AI", state)
        state.profile = r3.profile.to_dict()
        assert r3.profile.academic.rank == 48000
        assert r3.profile.academic.board == "WBCHSE"
        assert r3.profile.personal.category == "general"
        assert "ai" in r3.profile.career.interest.lower()

    def test_missing_info_shrinks_as_profile_grows(self):
        engine = UnderstandingEngine()
        state = ConversationState(session_id="test")

        r1 = engine.understand("Hello", state)
        assert len(r1.missing_info.items) >= 3

        state.profile = r1.profile.to_dict()

        r2 = engine.understand("my rank is 48000", state)
        state.profile = r2.profile.to_dict()
        assert "academic.rank" not in r2.missing_info.items
        assert "academic.pcm_percentage" in r2.missing_info.items

        r3 = engine.understand("I have 85 PCM and am from general category", state)
        state.profile = r3.profile.to_dict()
        assert "academic.rank" not in r3.missing_info.items
        assert "academic.pcm_percentage" not in r3.missing_info.items
        assert "personal.category" not in r3.missing_info.items


# ── Pathway detection via domain interpreter ──────────────────────────

class TestPathwayDetection:
    def test_lateral_entry_pathway_detected(self):
        engine = UnderstandingEngine()
        r = engine.understand("I have a diploma in EE with 78%")
        assert r.domain.pathway == "lateral_entry"
        assert r.profile.admission_pathway == "lateral_entry"

    def test_nri_pathway_detected(self):
        engine = UnderstandingEngine()
        r = engine.understand("I am an NRI student from CBSE board")
        assert r.domain.pathway == "nri"

    def test_scholarship_pathway_detected(self):
        engine = UnderstandingEngine()
        r = engine.understand("Can I get a scholarship?")
        assert r.domain.pathway == "scholarship"

    def test_pathway_updates_missing_info(self):
        engine = UnderstandingEngine()
        r = engine.understand("I want to apply through lateral entry with my diploma")
        assert r.domain.pathway == "lateral_entry"
        # Lateral entry requires diploma_percentage and diploma_branch
        assert "academic.diploma_percentage" in r.missing_info.items
        assert "academic.diploma_branch" in r.missing_info.items


# ── Edge cases ─────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_text(self):
        engine = UnderstandingEngine()
        r = engine.understand("")
        assert r.profile.academic.rank is None

    def test_whitespace_text(self):
        engine = UnderstandingEngine()
        r = engine.understand("   ")
        assert r.profile.academic.rank is None

    def test_none_state(self):
        engine = UnderstandingEngine()
        r = engine.understand("my rank is 48000", None)
        assert r.profile.academic.rank == 48000

    def test_profile_preserved_from_legacy_state(self):
        state = ConversationState(
            session_id="test",
            profile={"rank": 48000, "pcm_percentage": 85.0, "category": "general"},
        )
        engine = UnderstandingEngine()
        r = engine.understand("Hello", state)
        assert r.profile.academic.rank == 48000
        assert r.profile.academic.pcm_percentage == 85.0
        assert r.profile.personal.category == "general"


# ── PATHWAY_REQUIRED_FIELDS structure ─────────────────────────────────

class TestPathwayRequiredFields:
    def test_all_pathways_have_entries(self):
        """Every defined pathway must have a required fields list."""
        known = [
            "regular", "lateral_entry", "nri", "sports_quota",
            "management_quota", "transfer", "scholarship", "hostel",
            "fee", "placement", "grievance", "career_confusion",
            "distance_education", "counseling_info",
            "lateral_entry_intent", "management_quota_intent",
            "sports_quota_intent", "nri_admission",
        ]
        for p in known:
            assert p in PATHWAY_REQUIRED_FIELDS, f"Missing pathway: {p}"

    def test_field_paths_are_valid(self):
        """Every field in required fields must map to a real profile attribute."""
        from src.understanding.profile import ALL_FIELD_PATHS
        valid_paths = set(ALL_FIELD_PATHS)
        for pathway, fields in PATHWAY_REQUIRED_FIELDS.items():
            for f in fields:
                assert f in valid_paths, (
                    f"Pathway '{pathway}' references unknown field '{f}'"
                )

    def test_to_dict_roundtrip(self):
        p = StudentProfile()
        p.academic.rank = 48000
        p.academic.pcm_percentage = 85.0
        p.personal.category = "general"
        p.career.interest = "AI"
        p.admission_pathway = "lateral_entry"
        d = p.to_dict()
        p2 = StudentProfile.from_dict(d)
        assert p2.academic.rank == 48000
        assert p2.academic.pcm_percentage == 85.0
        assert p2.personal.category == "general"
        assert p2.career.interest == "AI"
        assert p2.admission_pathway == "lateral_entry"
