"""
Entity Extraction v4 — tests for UnderstandingEngine._update_profile improvements.

120+ tests covering:
  - Rank extraction (k, lakh, thousand, word forms)
  - PCM extraction (percent, word numbers, aggregate)
  - Board/exam extraction
  - Category extraction and normalization
  - Interest extraction and normalization
  - Budget extraction (numeric, keywords)
  - Hostel detection
  - Current education extraction
  - Qualification extraction
  - Multi-language (English, Hindi, Bengali, mixed)
  - Typos/STT noise
  - Cross-turn profile merging
  - Normalization rules
"""

import pytest

from src.conversation.state import ConversationState
from src.understanding.engine import UnderstandingEngine


@pytest.fixture
def engine():
    return UnderstandingEngine()


# ── Rank extraction ───────────────────────────────────────────────────

class TestRankExtraction:
    def test_rank_direct(self, engine):
        r = engine.understand("my rank is 48000")
        assert r.profile.academic.rank == 48000

    def test_rank_alternative(self, engine):
        r = engine.understand("I got 25000 rank in JEE")
        assert r.profile.academic.rank == 25000

    def test_rank_with_k(self, engine):
        r = engine.understand("my rank is 48k")
        assert r.profile.academic.rank == 48000

    def test_rank_with_k_space(self, engine):
        r = engine.understand("rank around 48 K")
        assert r.profile.academic.rank == 48000

    def test_rank_air_format(self, engine):
        r = engine.understand("AIR 48000")
        assert r.profile.academic.rank == 48000

    def test_rank_general_rank(self, engine):
        r = engine.understand("General Rank 48000")
        assert r.profile.academic.rank == 48000

    def test_rank_approximately(self, engine):
        r = engine.understand("approximately 48 thousand rank")
        assert r.profile.academic.rank == 48000

    def test_rank_around(self, engine):
        r = engine.understand("rank around 50 thousand")
        assert r.profile.academic.rank == 50000

    def test_rank_lakh(self, engine):
        r = engine.understand("rank around 1.2 lakh")
        assert r.profile.academic.rank == 120000

    def test_rank_lakh_simple(self, engine):
        r = engine.understand("1 lakh rank")
        assert r.profile.academic.rank == 100000

    def test_rank_lakh_multi(self, engine):
        r = engine.understand("rank around 2 lakh")
        assert r.profile.academic.rank == 200000

    def test_rank_word_around(self, engine):
        r = engine.understand("rank around 48000")
        assert r.profile.academic.rank == 48000

    def test_rank_hi_mera_rank(self, engine):
        r = engine.understand("mera rank 48k hai")
        assert r.profile.academic.rank == 48000

    def test_rank_hi_rank_hai(self, engine):
        r = engine.understand("mera rank 25000 hai")
        assert r.profile.academic.rank == 25000

    def test_rank_bn_amar_rank(self, engine):
        r = engine.understand("amar rank 48k")
        assert r.profile.academic.rank == 48000

    def test_rank_with_ran(self, engine):
        r = engine.understand("mera ran 12000 hai")
        assert r.profile.academic.rank == 12000

    def test_rank_general_rank_lakh(self, engine):
        r = engine.understand("General Rank 1.5 lakh")
        assert r.profile.academic.rank == 150000

    def test_no_rank_in_greeting(self, engine):
        r = engine.understand("Hello, how are you?")
        assert r.profile.academic.rank is None

    def test_rank_comma_format(self, engine):
        r = engine.understand("AIR 48,000")
        assert r.profile.academic.rank == 48000


# ── PCM extraction ────────────────────────────────────────────────────

class TestPCMExtraction:
    def test_pcm_percent(self, engine):
        r = engine.understand("I have 85% PCM")
        assert r.profile.academic.pcm_percentage == 85.0

    def test_pcm_direct(self, engine):
        r = engine.understand("PCM 82")
        assert r.profile.academic.pcm_percentage == 82.0

    def test_pcm_is(self, engine):
        r = engine.understand("PCM = 82")
        assert r.profile.academic.pcm_percentage == 82.0

    def test_pcm_scored(self, engine):
        r = engine.understand("I scored 82 in PCM")
        assert r.profile.academic.pcm_percentage == 82.0

    def test_pcm_aggregate(self, engine):
        r = engine.understand("aggregate 82%")
        assert r.profile.academic.pcm_percentage == 82.0

    def test_pcm_physics_chemistry(self, engine):
        r = engine.understand("physics chemistry aggregate 82")
        assert r.profile.academic.pcm_percentage == 82.0

    def test_pcm_and_rank(self, engine):
        r = engine.understand("my rank is 48000 and 82 PCM")
        assert r.profile.academic.rank == 48000
        assert r.profile.academic.pcm_percentage == 82.0

    def test_pcm_eighty_two(self, engine):
        r = engine.understand("my PCM is eighty two")
        assert r.profile.academic.pcm_percentage == 82.0

    def test_pcm_marks(self, engine):
        r = engine.understand("PCM marks 82")
        assert r.profile.academic.pcm_percentage == 82.0

    def test_pcm_got(self, engine):
        r = engine.understand("I got 85 percent in PCM")
        assert r.profile.academic.pcm_percentage == 85.0

    def test_pcm_secured(self, engine):
        r = engine.understand("I secured 92 in PCM")
        assert r.profile.academic.pcm_percentage == 92.0

    def test_pcm_no_match(self, engine):
        r = engine.understand("Hello")
        assert r.profile.academic.pcm_percentage is None


# ── Board / Exam extraction ───────────────────────────────────────────

class TestBoardExamExtraction:
    def test_board_wbchse(self, engine):
        r = engine.understand("I studied in WBCHSE")
        assert r.profile.academic.board == "WBCHSE"

    def test_board_cbse(self, engine):
        r = engine.understand("I am from CBSE board")
        assert r.profile.academic.board == "CBSE"

    def test_board_icse(self, engine):
        r = engine.understand("ICSE board")
        assert r.profile.academic.board == "ICSE"

    def test_board_isc(self, engine):
        r = engine.understand("ISC board")
        assert r.profile.academic.board == "ISC"

    def test_board_west_bengal(self, engine):
        r = engine.understand("West Bengal Board")
        assert r.profile.academic.board == "WBCHSE"

    def test_board_state_board(self, engine):
        r = engine.understand("State Board")
        assert r.profile.academic.board == "State Board"

    def test_board_central_board(self, engine):
        r = engine.understand("Central Board")
        assert r.profile.academic.board == "CBSE"

    def test_exam_wbjee(self, engine):
        r = engine.understand("I appeared in WBJEE")
        assert r.profile.academic.exam == "wbjee"

    def test_exam_jee_main(self, engine):
        r = engine.understand("I gave JEE Main")
        assert r.profile.academic.exam == "jee_main"

    def test_exam_jee_main_short(self, engine):
        r = engine.understand("JEE exam")
        assert r.profile.academic.exam == "jee_main"

    def test_exam_jee_advanced(self, engine):
        r = engine.understand("JEE Advanced")
        assert r.profile.academic.exam == "jee_advanced"

    def test_exam_jelet(self, engine):
        r = engine.understand("JELET exam")
        assert r.profile.academic.exam == "jelet"

    def test_exam_jexpo(self, engine):
        r = engine.understand("JEXPO")
        assert r.profile.academic.exam == "jexpo"

    def test_exam_cuet(self, engine):
        r = engine.understand("CUET")
        assert r.profile.academic.exam == "cuet"

    def test_exam_nata(self, engine):
        r = engine.understand("NATA")
        assert r.profile.academic.exam == "nata"


# ── Category extraction ───────────────────────────────────────────────

class TestCategoryExtraction:
    def test_category_general(self, engine):
        r = engine.understand("I am from general category")
        assert r.profile.personal.category == "general"

    def test_category_gen(self, engine):
        r = engine.understand("GEN category")
        assert r.profile.personal.category == "general"

    def test_category_ur(self, engine):
        r = engine.understand("UR category")
        assert r.profile.personal.category == "general"

    def test_category_obc(self, engine):
        r = engine.understand("OBC category")
        assert r.profile.personal.category == "obc"

    def test_category_obc_a(self, engine):
        r = engine.understand("OBC-A category")
        assert r.profile.personal.category == "obc"

    def test_category_obc_b(self, engine):
        r = engine.understand("OBC-B category")
        assert r.profile.personal.category == "obc"

    def test_category_obc_b_space(self, engine):
        r = engine.understand("obc b")
        assert r.profile.personal.category == "obc"

    def test_category_sc(self, engine):
        r = engine.understand("SC category")
        assert r.profile.personal.category == "sc"

    def test_category_st(self, engine):
        r = engine.understand("ST category")
        assert r.profile.personal.category == "st"

    def test_category_ews(self, engine):
        r = engine.understand("EWS category")
        assert r.profile.personal.category == "ews"

    def test_category_pwd(self, engine):
        r = engine.understand("PWD")
        assert r.profile.personal.category == "pwd"

    def test_category_management_not_extracted(self, engine):
        r = engine.understand("management quota")
        assert r.profile.personal.category == ""

    def test_category_nri(self, engine):
        r = engine.understand("NRI student")
        assert r.profile.personal.category == "nri"

    def test_category_tfw(self, engine):
        r = engine.understand("TFW category")
        assert r.profile.personal.category == "tfw"

    def test_category_hi_general(self, engine):
        r = engine.understand("general category se hoon")
        assert r.profile.personal.category == "general"

    def test_category_obc_normalized(self, engine):
        r = engine.understand("OBC-A")
        assert r.profile.personal.category == "obc"


# ── Interest extraction ───────────────────────────────────────────────

class TestInterestExtraction:
    def test_interest_cse(self, engine):
        r = engine.understand("I am interested in Computer Science")
        assert r.profile.career.interest == "CSE"

    def test_interest_ai(self, engine):
        r = engine.understand("I want to study AI")
        assert r.profile.career.interest == "AI"

    def test_interest_ai_ml(self, engine):
        r = engine.understand("my interest is AI ML")
        assert r.profile.career.interest == "AI"

    def test_interest_ece(self, engine):
        r = engine.understand("I want to pursue Electronics and Communication")
        assert r.profile.career.interest == "ECE"

    def test_interest_ee(self, engine):
        r = engine.understand("I want to take Electrical Engineering")
        assert r.profile.career.interest == "EE"

    def test_interest_me(self, engine):
        r = engine.understand("aim for Mechanical Engineering")
        assert r.profile.career.interest == "ME"

    def test_interest_ce(self, engine):
        r = engine.understand("target Civil Engineering")
        assert r.profile.career.interest == "CE"

    def test_interest_biotech(self, engine):
        r = engine.understand("interested in Biotechnology")
        assert r.profile.career.interest == "Biotechnology"

    def test_interest_data_science(self, engine):
        r = engine.understand("looking for Data Science")
        assert r.profile.career.interest == "Data Science"

    def test_interest_cyber(self, engine):
        r = engine.understand("interested in Cyber Security")
        assert r.profile.career.interest == "Cyber Security"

    def test_interest_iot(self, engine):
        r = engine.understand("want to do IoT")
        assert r.profile.career.interest == "IoT"

    def test_interest_robotics(self, engine):
        r = engine.understand("interested in Robotics")
        assert r.profile.career.interest == "Robotics"

    def test_interest_computer(self, engine):
        r = engine.understand("I like Computer")
        assert r.profile.career.interest == "CSE"

    def test_interest_computer_since(self, engine):
        r = engine.understand("Computer since")
        assert r.profile.career.interest == "CSE"

    def test_interest_electrical(self, engine):
        r = engine.understand("interested in electrical")
        assert r.profile.career.interest == "EE"

    def test_interest_machanical(self, engine):
        r = engine.understand("opt for machanical")
        assert r.profile.career.interest == "ME"

    def test_interest_ec(self, engine):
        r = engine.understand("prefer EC")
        assert r.profile.career.interest == "ECE"

    def test_interest_unsure_dont_know(self, engine):
        r = engine.understand("I don't know what to choose")
        assert r.profile.career.interest == ""

    def test_interest_unsure_not_sure(self, engine):
        r = engine.understand("I am not sure")
        assert r.profile.career.interest == ""

    def test_interest_unsure_confused(self, engine):
        r = engine.understand("I am confused")
        assert r.profile.career.interest == ""

    def test_interest_unsure_open(self, engine):
        r = engine.understand("I am open to anything")
        assert r.profile.career.interest == ""

    def test_interest_anthropology(self, engine):
        r = engine.understand("interested in Anthropology")
        assert r.profile.career.interest == "Anthropology"

    def test_interest_it(self, engine):
        r = engine.understand("want to study IT")
        assert r.profile.career.interest == "IT"

    def test_interest_cs(self, engine):
        r = engine.understand("prefer CS")
        assert r.profile.career.interest == "CSE"


# ── Budget extraction ─────────────────────────────────────────────────

class TestBudgetExtraction:
    def test_budget_3_lakh(self, engine):
        r = engine.understand("budget is 3 lakh")
        assert r.profile.personal.budget == 300000.0

    def test_budget_under_5_lakh(self, engine):
        r = engine.understand("budget under 5 lakh")
        assert r.profile.personal.budget == 500000.0

    def test_budget_below_3_lakh(self, engine):
        r = engine.understand("budget below 3 lakh")
        assert r.profile.personal.budget == 300000.0

    def test_budget_afford_2_lakh(self, engine):
        r = engine.understand("I can afford 2 lakh")
        assert r.profile.personal.budget == 200000.0

    def test_budget_rs_3_lakh(self, engine):
        r = engine.understand("my budget is Rs. 3 lakh")
        assert r.profile.personal.budget == 300000.0

    def test_budget_low_keyword(self, engine):
        r = engine.understand("I have low budget")
        assert r.profile.personal.budget == 0.0

    def test_budget_middle_class(self, engine):
        r = engine.understand("I am from middle class family")
        assert r.profile.personal.budget == 0.0

    def test_budget_cannot_afford(self, engine):
        r = engine.understand("My parents cannot afford")
        assert r.profile.personal.budget == 0.0

    def test_budget_expensive(self, engine):
        r = engine.understand("fees are expensive")
        assert r.profile.personal.budget == 0.0

    def test_budget_tight(self, engine):
        r = engine.understand("budget is tight")
        assert r.profile.personal.budget == 0.0

    def test_budget_education_loan(self, engine):
        r = engine.understand("I need education loan")
        assert r.profile.personal.budget == 0.0

    def test_budget_limited(self, engine):
        r = engine.understand("limited budget")
        assert r.profile.personal.budget == 0.0

    def test_budget_hi_afford_nahi(self, engine):
        r = engine.understand("parents afford korte parbe na")
        assert r.profile.personal.budget == 0.0

    def test_budget_hi_budget_kom(self, engine):
        r = engine.understand("budget kom hai")
        assert r.profile.personal.budget == 0.0

    def test_budget_scholarship_needed(self, engine):
        r = engine.understand("scholarship needed")
        assert r.profile.personal.budget == 0.0

    def test_budget_no_budget_mention(self, engine):
        r = engine.understand("my rank is 48000")
        assert r.profile.personal.budget is None

    def test_budget_around_2_lakh(self, engine):
        r = engine.understand("my budget is around 2 lakh")
        assert r.profile.personal.budget == 200000.0

    def test_budget_about_1_lakh(self, engine):
        r = engine.understand("budget about 1 lakh")
        assert r.profile.personal.budget == 100000.0

    def test_budget_under_50k(self, engine):
        r = engine.understand("budget under 50 thousand")
        assert r.profile.personal.budget == 50000.0


# ── Hostel extraction ─────────────────────────────────────────────────

class TestHostelExtraction:
    def test_hostel_need(self, engine):
        r = engine.understand("I need hostel")
        assert r.profile.personal.hostel_required is True

    def test_hostel_required(self, engine):
        r = engine.understand("hostel required")
        assert r.profile.personal.hostel_required is True

    def test_hostel_girls(self, engine):
        r = engine.understand("girls hostel required")
        assert r.profile.personal.hostel_required is True

    def test_hostel_boys(self, engine):
        r = engine.understand("boys hostel chahiye")
        assert r.profile.personal.hostel_required is True

    def test_hostel_day_scholar(self, engine):
        r = engine.understand("I am a day scholar")
        assert r.profile.personal.hostel_required is False

    def test_hostel_coming_from_bihar(self, engine):
        r = engine.understand("coming from Bihar")
        assert r.profile.personal.hostel_required is True

    def test_hostel_coming_from_assam(self, engine):
        r = engine.understand("coming from Assam")
        assert r.profile.personal.hostel_required is True

    def test_hostel_far_away(self, engine):
        r = engine.understand("I live far away")
        assert r.profile.personal.hostel_required is True

    def test_hostel_accommodation(self, engine):
        r = engine.understand("need accommodation")
        assert r.profile.personal.hostel_required is True

    def test_hostel_boarding(self, engine):
        r = engine.understand("boarding required")
        assert r.profile.personal.hostel_required is True

    def test_hostel_bn_lagbe(self, engine):
        r = engine.understand("hostel lagbe")
        assert r.profile.personal.hostel_required is True

    def test_hostel_hi_chahiye(self, engine):
        r = engine.understand("mujhe hostel chahiye")
        assert r.profile.personal.hostel_required is True

    def test_hostel_no_hostel(self, engine):
        r = engine.understand("I don't need hostel")
        assert r.profile.personal.hostel_required is False

    def test_hostel_no_mention(self, engine):
        r = engine.understand("my rank is 48000")
        assert r.profile.personal.hostel_required is None


# ── Current Education extraction ──────────────────────────────────────

class TestCurrentEducationExtraction:
    def test_current_year_1st(self, engine):
        r = engine.understand("I am in 1st year")
        assert r.profile.academic.current_year == 1

    def test_current_year_2nd(self, engine):
        r = engine.understand("currently in 2nd year")
        assert r.profile.academic.current_year == 2

    def test_current_year_3rd(self, engine):
        r = engine.understand("3rd year student")
        assert r.profile.academic.current_year == 3

    def test_current_year_4th(self, engine):
        r = engine.understand("4th year")
        assert r.profile.academic.current_year == 4

    def test_current_branch_ee(self, engine):
        r = engine.understand("currently studying EE")
        assert r.profile.academic.current_branch == "EE"

    def test_current_branch_cse(self, engine):
        r = engine.understand("pursuing Computer Science")
        assert r.profile.academic.current_branch == "CSE"

    def test_current_college_private(self, engine):
        r = engine.understand("private college")
        assert r.profile.academic.current_college == "private"

    def test_current_college_government(self, engine):
        r = engine.understand("government college")
        assert r.profile.academic.current_college == "government"


# ── Qualification extraction ──────────────────────────────────────────

class TestQualificationExtraction:
    def test_qual_diploma(self, engine):
        r = engine.understand("I have a diploma")
        assert r.profile.academic.qualification == "diploma"

    def test_qual_btech(self, engine):
        r = engine.understand("I am doing B.Tech")
        assert r.profile.academic.qualification == "bachelor"

    def test_qual_be(self, engine):
        r = engine.understand("BE completed")
        assert r.profile.academic.qualification == "bachelor"

    def test_qual_12th(self, engine):
        r = engine.understand("I passed 12th")
        assert r.profile.academic.qualification == "12th"

    def test_qual_hsc(self, engine):
        r = engine.understand("HSC completed")
        assert r.profile.academic.qualification == "12th"

    def test_qual_10th(self, engine):
        r = engine.understand("10th standard")
        assert r.profile.academic.qualification == "10th"


# ── Multi-language support ────────────────────────────────────────────

class TestMultiLanguageSupport:
    def test_hi_mera_rank(self, engine):
        r = engine.understand("mera rank 48k hai")
        assert r.profile.academic.rank == 48000

    def test_hi_interest_ai(self, engine):
        r = engine.understand("mera interest AI hai")
        assert r.profile.career.interest == "AI"

    def test_hi_general_category(self, engine):
        r = engine.understand("general category se hoon")
        assert r.profile.personal.category == "general"

    def test_hi_obc_category(self, engine):
        r = engine.understand("OBC category hai")
        assert r.profile.personal.category == "obc"

    def test_hi_pcm(self, engine):
        r = engine.understand("PCM 82 hai")
        assert r.profile.academic.pcm_percentage == 82.0

    def test_bn_amar_rank(self, engine):
        r = engine.understand("amar rank 48k")
        assert r.profile.academic.rank == 48000

    def test_bn_ai_chai(self, engine):
        r = engine.understand("ami AI porte chai")
        assert r.profile.career.interest == "AI"

    def test_bn_cse_chai(self, engine):
        r = engine.understand("ami CSE chai")
        assert r.profile.career.interest == "CSE"

    def test_bn_hostel_lagbe(self, engine):
        r = engine.understand("hostel lagbe")
        assert r.profile.personal.hostel_required is True

    def test_bn_scholarship_chai(self, engine):
        r = engine.understand("scholarship chai")
        assert r.profile.personal.budget == 0.0

    def test_mixed_hi_en_rank(self, engine):
        r = engine.understand("my rank 48k hai")
        assert r.profile.academic.rank == 48000

    def test_mixed_bn_en_interest(self, engine):
        r = engine.understand("ami CSE chai")
        assert r.profile.career.interest == "CSE"


# ── Typos and STT noise ──────────────────────────────────────────────

class TestTyposAndSTTNoise:
    def test_typo_a_i(self, engine):
        r = engine.understand("interested in A I")
        assert r.profile.career.interest == "AI"

    def test_typo_ai_and_ml(self, engine):
        r = engine.understand("AI and ML")
        assert r.profile.career.interest == "AI"

    def test_typo_computer_since(self, engine):
        r = engine.understand("Computer since")
        assert r.profile.career.interest == "CSE"

    def test_typo_electrical(self, engine):
        r = engine.understand("electrical engineering")
        assert r.profile.career.interest == "EE"

    def test_typo_machanical(self, engine):
        r = engine.understand("machanical engineering")
        assert r.profile.career.interest == "ME"

    def test_typo_civil_engg(self, engine):
        r = engine.understand("civil engg")
        assert r.profile.career.interest == "CE"

    def test_typo_obc_b(self, engine):
        r = engine.understand("obc b category")
        assert r.profile.personal.category == "obc"

    def test_typo_wb_jee(self, engine):
        r = engine.understand("wb jee")
        assert r.profile.academic.exam == "wbjee"

    def test_typo_jee_mains(self, engine):
        r = engine.understand("jee mains")
        assert r.profile.academic.exam == "jee_main"

    def test_typo_jee_advance(self, engine):
        r = engine.understand("jee advance")
        assert r.profile.academic.exam == "jee_advanced"


# ── Cross-turn profile merging ────────────────────────────────────────

class TestCrossTurnProfileMerging:
    def test_preserve_rank_across_turns(self, engine):
        state = ConversationState(session_id="test")
        r1 = engine.understand("my rank is 48000", state)
        state.profile = r1.profile.to_dict()
        r2 = engine.understand("I am from SC category", state)
        assert r2.profile.academic.rank == 48000
        assert r2.profile.personal.category == "sc"

    def test_preserve_multiple_across_turns(self, engine):
        state = ConversationState(session_id="test")
        r1 = engine.understand("my rank is 48000 and PCM 82", state)
        state.profile = r1.profile.to_dict()
        r2 = engine.understand("I am from OBC category", state)
        assert r2.profile.academic.rank == 48000
        assert r2.profile.academic.pcm_percentage == 82.0
        assert r2.profile.personal.category == "obc"

    def test_three_turns_full_profile(self, engine):
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
        assert r3.profile.career.interest == "AI"

    def test_no_overwrite_with_empty(self, engine):
        state = ConversationState(session_id="test")
        r1 = engine.understand("my rank is 48000", state)
        state.profile = r1.profile.to_dict()
        r2 = engine.understand("Hello", state)
        assert r2.profile.academic.rank == 48000

    def test_no_overwrite_pcm_with_greeting(self, engine):
        state = ConversationState(session_id="test")
        r1 = engine.understand("PCM 82", state)
        state.profile = r1.profile.to_dict()
        r2 = engine.understand("How are you?", state)
        assert r2.profile.academic.pcm_percentage == 82.0

    def test_overwrite_rank_with_new_rank(self, engine):
        state = ConversationState(session_id="test")
        r1 = engine.understand("my rank is 48000", state)
        state.profile = r1.profile.to_dict()
        r2 = engine.understand("actually my rank is 25000", state)
        assert r2.profile.academic.rank == 25000

    def test_missing_info_shrinks(self, engine):
        state = ConversationState(session_id="test")
        r1 = engine.understand("my rank is 48000", state)
        state.profile = r1.profile.to_dict()
        assert "academic.rank" not in r1.missing_info.items
        r2 = engine.understand("I have 85 PCM and am from general category", state)
        state.profile = r2.profile.to_dict()
        assert "academic.rank" not in r2.missing_info.items
        assert "academic.pcm_percentage" not in r2.missing_info.items
        assert "personal.category" not in r2.missing_info.items


# ── Normalization rules ───────────────────────────────────────────────

class TestNormalization:
    def test_ai_normalized(self, engine):
        r = engine.understand("interested in Artificial Intelligence")
        assert r.profile.career.interest == "AI"

    def test_ai_ml_normalized(self, engine):
        r = engine.understand("interested in AI ML")
        assert r.profile.career.interest == "AI"

    def test_cse_normalized(self, engine):
        r = engine.understand("interested in Computer Science")
        assert r.profile.career.interest == "CSE"

    def test_ee_normalized(self, engine):
        r = engine.understand("interested in Electrical Engineering")
        assert r.profile.career.interest == "EE"

    def test_me_normalized(self, engine):
        r = engine.understand("interested in Mechanical Engineering")
        assert r.profile.career.interest == "ME"

    def test_ce_normalized(self, engine):
        r = engine.understand("interested in Civil Engineering")
        assert r.profile.career.interest == "CE"

    def test_ece_normalized(self, engine):
        r = engine.understand("interested in Electronics and Communication")
        assert r.profile.career.interest == "ECE"

    def test_gen_to_general(self, engine):
        r = engine.understand("GEN category")
        assert r.profile.personal.category == "general"

    def test_ur_to_general(self, engine):
        r = engine.understand("UR category")
        assert r.profile.personal.category == "general"

    def test_obc_a_to_obc(self, engine):
        r = engine.understand("OBC-A")
        assert r.profile.personal.category == "obc"

    def test_obc_b_to_obc(self, engine):
        r = engine.understand("OBC-B")
        assert r.profile.personal.category == "obc"

    def test_management_not_category(self, engine):
        r = engine.understand("management")
        assert r.profile.personal.category == ""


# ── Diploma extraction ────────────────────────────────────────────────

class TestDiplomaExtraction:
    def test_diploma_pct(self, engine):
        r = engine.understand("diploma percentage 78")
        assert r.profile.academic.diploma_percentage == 78.0

    def test_diploma_branch_ee(self, engine):
        r = engine.understand("diploma in EE")
        assert r.profile.academic.diploma_branch == "EE"

    def test_diploma_branch_cse(self, engine):
        r = engine.understand("diploma in Computer Science")
        assert r.profile.academic.diploma_branch == "CSE"

    def test_diploma_78_pct(self, engine):
        r = engine.understand("I have a diploma with 78%")
        assert r.profile.academic.diploma_percentage == 78.0


# ── Location extraction ───────────────────────────────────────────────

class TestLocationExtraction:
    def test_location_west_bengal(self, engine):
        r = engine.understand("I am from West Bengal")
        assert r.profile.personal.location == "west bengal"

    def test_location_kolkata(self, engine):
        r = engine.understand("I live in Kolkata")
        assert r.profile.personal.location == "kolkata"

    def test_location_bihar(self, engine):
        r = engine.understand("coming from Bihar")
        assert r.profile.personal.location == "bihar"

    def test_location_assam(self, engine):
        r = engine.understand("I am from Assam")
        assert r.profile.personal.location == "assam"


# ── Edge Cases ────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_text(self, engine):
        r = engine.understand("")
        assert r.profile.academic.rank is None
        assert r.profile.academic.pcm_percentage is None
        assert r.profile.personal.category == ""

    def test_whitespace_text(self, engine):
        r = engine.understand("   ")
        assert r.profile.academic.rank is None

    def test_none_state(self, engine):
        r = engine.understand("my rank is 48000", None)
        assert r.profile.academic.rank == 48000

    def test_no_false_rank_from_numbers(self, engine):
        r = engine.understand("Hello, I am 25 years old")
        assert r.profile.academic.rank is None

    def test_no_false_budget_from_numbers(self, engine):
        r = engine.understand("I have 2 brothers")
        assert r.profile.personal.budget is None

    def test_no_false_pcm_from_numbers(self, engine):
        r = engine.understand("I am 82 years old")
        assert r.profile.academic.pcm_percentage is None
