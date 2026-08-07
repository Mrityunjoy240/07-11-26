"""Regression tests for the anti-fabrication conversation policy.

Guards against the production bug where the agent invented caller attributes
(rank=345, percentage=92.5, board=WBCHSE, state=WB) when the caller said vague
things like "I need help" or "I want admission".
"""

import pytest

from app.services.llm.groq_service import GroqService
from app.utils.language_detect import detect_language


@pytest.fixture
def groq_service():
    return GroqService()


# ── Language detection: English "help" must not flip to Bengali ──

class TestLanguageLoanwordGuard:
    def test_english_help_stays_english(self):
        assert detect_language("I need help") == "en"
        assert detect_language("help me") == "en"
        assert detect_language("I really need some help please") == "en"

    def test_english_problem_stays_english(self):
        assert detect_language("I have a problem") == "en"

    def test_banglish_with_real_markers_stays_bangla(self):
        assert detect_language("help lagbe") == "bn"
        assert detect_language("amar help lagbe") == "bn"

    def test_hinglish_me_stays_hindi_with_other_markers(self):
        assert detect_language("CSE me kitne seats hain") == "hi"

    def test_resolve_language_english_help_fresh_session(self, groq_service):
        assert groq_service._resolve_language("loan-fresh-1", "I need help") == "en"
        assert groq_service._resolve_language("loan-fresh-2", "help me") == "en"

    def test_resolve_language_banglish_help_fresh_session(self, groq_service):
        assert groq_service._resolve_language("loan-fresh-3", "help lagbe") == "bn"

    def test_me_branch_not_detected_as_hindi(self, groq_service):
        # "ME" (Mechanical Engineering) must never flip a fresh session to Hindi.
        assert groq_service._resolve_language("loan-fresh-4", "ME") == "en"

    def test_garbl_banglish_help_detected_as_bangla(self):
        assert detect_language("amar healp lagbe") == "bn"

    def test_garbl_hindi_help_detected_as_hindi(self):
        assert detect_language("mughe healp chyea") == "hi"

    def test_garbl_hindi_placement_detected_as_hindi(self):
        assert detect_language("mughe placement k bare me janna he") == "hi"

    def test_garbl_help_never_detected_as_bengali(self):
        # Regression: "healp" used to be a Bengali marker, so a Hindi "help"
        # request was answered in Bengali. It must now resolve to Hindi.
        assert detect_language("mughe healp chyea") != "bn"

    def test_mid_session_hindi_switch_after_banglish(self, groq_service):
        # Real bug transcript: a Banglish turn locked the session to bn, then a
        # Hindi user was answered in Bengali/Banglish. A strong Hindi signal
        # must switch the session language even mid-conversation.
        sid = "switch-bug-1"
        assert groq_service._resolve_language(sid, "amar healp lagbe") == "bn"
        assert groq_service._resolve_language(sid, "mughe healp chyea") == "hi"
        assert groq_service._resolve_language(sid, "mughe placement k bare me janna he") == "hi"

    def test_mid_session_long_path_switches_back_to_bangla(self, groq_service):
        # 4-word Banglish query after a Hindi session must flip back to Bengali.
        sid = "switch-bug-2"
        assert groq_service._resolve_language(sid, "mughe madat chyea") == "hi"
        assert groq_service._resolve_language(sid, "amar akta healp lahbe") == "bn"

    def test_madat_intercepted_as_open_help(self, groq_service):
        out = groq_service._detect_open_intent("mughe madat chyea", "hi")
        assert out is not None
        assert "madad" in out.lower() or "madat" in out.lower()


# ── Open-ended intent clarification ──

class TestOpenIntentClarification:
    def test_need_help_asks_what(self, groq_service):
        out = groq_service._detect_open_intent("I need help", "en")
        assert out is not None
        assert "help" in out.lower()

    def test_help_me_asks_what(self, groq_service):
        out = groq_service._detect_open_intent("help me", "en")
        assert out is not None

    def test_want_admission_asks_department(self, groq_service):
        out = groq_service._detect_open_intent("I want admission", "en")
        assert out is not None
        assert any(k in out.lower() for k in ("department", "course", "cse", "mechanical"))

    def test_want_admission_with_branch_passes_through(self, groq_service):
        out = groq_service._detect_open_intent("I want admission in CSE", "en")
        assert out is None

    def test_specific_help_passes_through(self, groq_service):
        out = groq_service._detect_open_intent("I need help with hostel fees", "en")
        assert out is None

    def test_healp_misspelling_is_intercepted(self, groq_service):
        assert groq_service._detect_open_intent("amar healp lagbe", "bn") is not None
        assert groq_service._detect_open_intent("mughe healp chyea", "hi") is not None

    def test_hindi_help_phrase_is_intercepted(self, groq_service):
        assert groq_service._detect_open_intent("help chahiye", "hi") is not None
        assert groq_service._detect_open_intent("madad chahiye", "hi") is not None

    def test_normal_question_passes_through(self, groq_service):
        assert groq_service._detect_open_intent("What is the CSE fee?", "en") is None


# ── Vague "I have a back/backlog" statements → ask which subject/semester ──

class TestBacklogOpenStatement:
    def test_banglish_back_asks_which_subject(self, groq_service):
        out = groq_service._detect_backlog_open_statement("amar back aseche", "bn")
        assert out is not None
        assert "backlog" in out.lower() or "ব্যাক" in out

    def test_hinglish_backlog_asks_which_subject(self, groq_service):
        out = groq_service._detect_backlog_open_statement("mera backlog he", "hi")
        assert out is not None

    def test_back_in_one_subject_asks_which(self, groq_service):
        out = groq_service._detect_backlog_open_statement("ak sub me back aya he", "hi")
        assert out is not None

    def test_policy_question_passes_through(self, groq_service):
        out = groq_service._detect_backlog_open_statement("backlog policy kya hai", "hi")
        assert out is None

    def test_how_to_clear_passes_through(self, groq_service):
        out = groq_service._detect_backlog_open_statement("mera back kaise clear hoga", "hi")
        assert out is None

    def test_generic_back_question_passes_through(self, groq_service):
        out = groq_service._detect_backlog_open_statement("back kyu aata hai", "hi")
        assert out is None

    def test_no_back_word_passes_through(self, groq_service):
        out = groq_service._detect_backlog_open_statement("my admission is confirmed", "en")
        assert out is None

    def test_english_back_statement_asks_which_subject(self, groq_service):
        out = groq_service._detect_backlog_open_statement("I have a back", "en")
        assert out is not None


# ── Caller attribute extraction must never fabricate ──

class TestProfileExtractionNoFabrication:
    def test_rank_not_extracted_from_generic_question(self, groq_service):
        sid = "pol-no-rank"
        groq_service._extract_user_profile(sid, "What is the cutoff rank for CSE?")
        assert groq_service._get_or_create_state(sid).rank is None

    def test_rank_extracted_from_first_person(self, groq_service):
        sid = "pol-rank-yes"
        groq_service._extract_user_profile(sid, "my rank is 48000")
        assert groq_service._get_or_create_state(sid).rank == 48000

    def test_pcm_not_extracted_from_college_stats(self, groq_service):
        sid = "pol-no-pcm"
        groq_service._extract_user_profile(sid, "What is the 91% placement rate?")
        assert groq_service._get_or_create_state(sid).pcm_percent is None

    def test_pcm_extracted_from_first_person(self, groq_service):
        sid = "pol-pcm-yes"
        groq_service._extract_user_profile(sid, "I got 92.5 percent in PCM")
        assert groq_service._get_or_create_state(sid).pcm_percent == 92.5

    def test_board_extracted_from_first_person(self, groq_service):
        sid = "pol-board"
        groq_service._extract_user_profile(sid, "I studied in WBCHSE board")
        assert groq_service._get_or_create_state(sid).board == "WBCHSE"

    def test_board_not_extracted_from_generic(self, groq_service):
        sid = "pol-no-board"
        groq_service._extract_user_profile(sid, "Do you accept WBCHSE students?")
        assert groq_service._get_or_create_state(sid).board is None

    def test_state_extracted_from_first_person(self, groq_service):
        sid = "pol-state"
        groq_service._extract_user_profile(sid, "I am from West Bengal")
        assert groq_service._get_or_create_state(sid).state == "WB"

    def test_profile_context_never_invents(self, groq_service):
        sid = "pol-empty"
        groq_service._extract_user_profile(sid, "What are the fees?")
        ctx = groq_service._format_profile_context(sid)
        assert ctx == ""


# ── Fallback / clarify anti-repetition ──

class TestClarifyAntiRepetition:
    def test_clarify_escalates_not_repeats(self, groq_service):
        sid = "pol-rep"
        first = groq_service._clarify_repeat_message("en", sid)
        second = groq_service._clarify_repeat_message("en", sid)
        assert first != second
        assert "rephrase" in first.lower() or "bengali or english" in first.lower()

    def test_fallback_escalates_not_repeats(self, groq_service):
        sid = "pol-fb"
        first = groq_service._safe_fallback("en", sid)
        second = groq_service._safe_fallback("en", sid)
        assert first != second

    def test_sessions_are_isolated(self, groq_service):
        groq_service._clarify_repeat_message("en", "sess-a")
        first_b = groq_service._clarify_repeat_message("en", "sess-b")
        second_a = groq_service._clarify_repeat_message("en", "sess-a")
        # sess-b starts fresh: its first message equals sess-a's first message
        assert first_b == (
            "Sorry, I didn't catch that clearly. "
            "Could you please rephrase it in Bengali or English?"
        )
        assert second_a != first_b
