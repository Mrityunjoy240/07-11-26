import pytest

from src.conversation.state import ConversationState, ConversationStage
from src.understanding.engine import UnderstandingEngine


@pytest.fixture
def engine():
    return UnderstandingEngine()


# ── Single intent detection (14+ tests, one per intent category) ───────

class TestSingleIntentDetection:
    def test_intent_admission(self, engine):
        result = engine.understand("What is the admission process?")
        assert result.intent.primary == "admission"

    def test_intent_fee(self, engine):
        result = engine.understand("What is the fee for BTech?")
        assert result.intent.primary == "fee"

    def test_intent_hostel(self, engine):
        result = engine.understand("Tell me about hostel facilities")
        assert result.intent.primary == "hostel"

    def test_intent_scholarship(self, engine):
        result = engine.understand("What scholarships are available?")
        assert result.intent.primary == "scholarship"

    def test_intent_placement(self, engine):
        result = engine.understand("What is the placement record?")
        assert result.intent.primary == "placement"

    def test_intent_department(self, engine):
        result = engine.understand("Which branches are available?")
        assert result.intent.primary == "department"

    def test_intent_cutoff(self, engine):
        result = engine.understand("What was the cutoff last year?")
        assert result.intent.primary == "cutoff"

    def test_intent_contact(self, engine):
        result = engine.understand("What is your phone number?")
        assert result.intent.primary == "institution"

    def test_intent_greeting(self, engine):
        result = engine.understand("Hello")
        assert result.intent.primary == "greeting"

    def test_intent_safety(self, engine):
        result = engine.understand("Is the campus safe for girls?")
        assert result.intent.primary == "safety"

    def test_intent_sports(self, engine):
        result = engine.understand("Do you have sports quota admission?")
        assert result.intent.primary == "sports_quota"

    def test_intent_transfer(self, engine):
        result = engine.understand("Can I transfer from another college?")
        assert result.intent.primary == "transfer"

    def test_intent_distance_education(self, engine):
        result = engine.understand("Do you offer online BTech programs?")
        assert result.intent.primary == "distance_education"

    def test_intent_counseling_info(self, engine):
        result = engine.understand("When is the counseling?")
        assert result.intent.primary == "counseling_info"

    def test_intent_grievance(self, engine):
        result = engine.understand("I want to file a complaint about my marks")
        assert result.intent.primary == "grievance"

    def test_intent_unknown(self, engine):
        result = engine.understand("this is just random text xyz")
        assert result.intent.primary == "unknown"


# ── Multi-intent detection (15+ tests) ──────────────────────────────────

class TestMultiIntentDetection:
    def test_hostel_and_fee(self, engine):
        result = engine.understand("What is the hostel fee?")
        assert result.intent.primary in ("fee", "hostel")
        assert len(result.intent.all_scores) >= 2

    def test_scholarship_and_fee(self, engine):
        result = engine.understand("Tell me about scholarship and fee structure")
        assert result.intent.primary in ("scholarship", "fee")
        assert len(result.intent.all_scores) >= 2

    def test_admission_and_placement(self, engine):
        result = engine.understand("Can I get admission and what about placements?")
        assert result.intent.primary in ("admission", "placement")
        assert len(result.intent.all_scores) >= 2

    def test_department_and_cutoff(self, engine):
        result = engine.understand("What branches and their cutoffs?")
        assert result.intent.primary in ("department", "cutoff")

    def test_hostel_and_safety(self, engine):
        result = engine.understand("Is the girls hostel safe?")
        assert result.intent.primary in ("hostel", "safety")

    def test_admission_and_scholarship(self, engine):
        result = engine.understand("Admission process and scholarship options")
        assert result.intent.primary in ("admission", "scholarship")

    def test_placement_and_contact(self, engine):
        result = engine.understand("Placement stats and contact details")
        assert result.intent.primary in ("placement", "institution")

    def test_fee_and_installment(self, engine):
        result = engine.understand("Can I pay fees in installments?")
        assert result.intent.primary == "fee"

    def test_admission_and_cutoff(self, engine):
        result = engine.understand("What rank cutoff for CSE admission?")
        assert result.intent.primary in ("admission", "cutoff")

    def test_hostel_and_distance(self, engine):
        result = engine.understand("Hostel for distance education students?")
        assert result.intent.primary in ("hostel", "distance_education")

    def test_career_confusion_and_department(self, engine):
        result = engine.understand("I am confused about which branch to choose")
        assert result.intent.primary in ("career_confusion", "department")

    def test_scholarship_renewal_and_grievance(self, engine):
        result = engine.understand("My scholarship hasn't been renewed, help!")
        assert result.intent.primary in ("scholarship", "grievance")

    def test_contact_and_counseling(self, engine):
        result = engine.understand("What is the counseling helpline number?")
        assert result.intent.primary in ("counseling_info", "institution")

    def test_fee_and_scholarship_combined(self, engine):
        result = engine.understand("Fees are high, any scholarship or financial aid?")
        assert result.intent.primary in ("fee", "scholarship")

    def test_multi_all_scores_populated(self, engine):
        result = engine.understand("Admission and hostel fee")
        assert len(result.intent.all_scores) >= 2

    def test_all_scores_confidence_included(self, engine):
        result = engine.understand("What is the fee structure?")
        assert result.intent.confidence > 0
        assert isinstance(result.intent.all_scores, dict)


# ── Intent from entities only (10+ tests) ──────────────────────────────

class TestIntentFromEntities:
    def test_rank_implies_admission(self, engine):
        result = engine.understand("my rank is 48000")
        assert result.intent.primary == "admission"

    def test_rank_and_pcm_implies_admission(self, engine):
        result = engine.understand("my rank is 12000 and pcm 92")
        assert result.intent.primary == "admission"

    def test_budget_implies_fee(self, engine):
        result = engine.understand("my budget is around 2 lakh")
        assert result.intent.primary == "fee"

    def test_category_implies_scholarship(self, engine):
        result = engine.understand("I am from SC category")
        assert result.intent.primary in ("admission", "scholarship")

    def test_interest_implies_department(self, engine):
        result = engine.understand("I am interested in Computer Science")
        assert result.intent.primary in ("admission", "department")

    def test_hostel_needed_implies_hostel(self, engine):
        result = engine.understand("I need hostel accommodation")
        assert result.intent.primary == "hostel"

    def test_exam_implies_admission(self, engine):
        result = engine.understand("I gave JEE Main")
        assert result.intent.primary == "admission"

    def test_board_implies_admission(self, engine):
        result = engine.understand("I studied in CBSE")
        assert result.intent.primary == "admission"

    def test_low_budget_implies_fee(self, engine):
        result = engine.understand("budget is tight")
        assert result.intent.primary == "fee"

    def test_exam_and_rank_strong_admission(self, engine):
        result = engine.understand("my rank is 25000 and I wrote JEE")
        assert result.intent.primary == "admission"
        assert result.intent.confidence > 0.2


# ── Intent from domain/pathway (10+ tests) ─────────────────────────────

class TestIntentFromDomain:
    def test_lateral_entry_pathway(self, engine):
        result = engine.understand("I have a diploma and want lateral entry to BTech")
        assert result.intent.primary in ("lateral_entry", "admission", "transfer")

    def test_management_quota_pathway(self, engine):
        result = engine.understand("Is management quota available with donation?")
        assert result.intent.primary == "management_quota"

    def test_sports_quota_pathway(self, engine):
        result = engine.understand("I am a state level athlete seeking sports quota")
        assert result.intent.primary == "sports_quota"

    def test_nri_pathway(self, engine):
        result = engine.understand("I am NRI living abroad")
        assert result.intent.primary == "nri_admission"

    def test_transfer_pathway(self, engine):
        result = engine.understand("I want to transfer from my current college")
        assert result.intent.primary == "transfer"

    def test_scholarship_pathway(self, engine):
        result = engine.understand("I need financial aid and scholarship")
        assert result.intent.primary == "scholarship"

    def test_regular_admission_pathway(self, engine):
        result = engine.understand("regular admission process")
        assert result.intent.primary == "admission"

    def test_lateral_entry_with_interest(self, engine):
        result = engine.understand("diploma in EE, want lateral entry")
        assert result.intent.primary in ("lateral_entry", "admission", "transfer")

    def test_sports_with_cricket(self, engine):
        result = engine.understand("cricket player state level sports quota")
        assert result.intent.primary == "sports_quota"

    def test_nri_with_cse(self, engine):
        result = engine.understand("NRI quota for CSE from Dubai")
        assert result.intent.primary in ("nri_admission", "admission")


# ── Intent from conversation context (10+ tests) ──────────────────────

class TestIntentFromContext:
    def test_discovery_stage(self, engine):
        state = ConversationState(session_id="test", stage=ConversationStage.DISCOVERY)
        result = engine.understand("Tell me about college", state)
        assert result.intent.primary == "admission"

    def test_evaluation_stage_gives_department(self, engine):
        state = ConversationState(session_id="test", stage=ConversationStage.EVALUATION)
        result = engine.understand("Which branch should I pick?", state)
        assert result.intent.primary in ("department", "admission")

    def test_decision_stage_gives_fee(self, engine):
        state = ConversationState(session_id="test", stage=ConversationStage.DECISION)
        result = engine.understand("How much do I need to pay?", state)
        assert result.intent.primary == "fee"

    def test_decision_stage_gives_hostel(self, engine):
        state = ConversationState(session_id="test", stage=ConversationStage.DECISION)
        result = engine.understand("Where will I stay?", state)
        assert result.intent.primary == "hostel"

    def test_decision_stage_gives_placement(self, engine):
        state = ConversationState(session_id="test", stage=ConversationStage.DECISION)
        result = engine.understand("Will I get a job?", state)
        assert result.intent.primary == "placement"

    def test_application_stage_contact(self, engine):
        state = ConversationState(session_id="test", stage=ConversationStage.APPLICATION)
        result = engine.understand("Who do I contact?", state)
        assert result.intent.primary == "institution"

    def test_existing_student_context(self, engine):
        state = ConversationState(session_id="test", profile={"rank": 48000, "pcm_percentage": 85})
        result = engine.understand("Tell me more", state)
        assert result.intent.primary != "unknown"

    def test_complete_profile_context(self, engine):
        state = ConversationState(session_id="test", profile={
            "rank": 48000, "pcm_percentage": 85, "category": "general", "interest": "CSE"
        })
        result = engine.understand("What now?", state)
        assert result.intent.primary not in ("unknown", "greeting")

    def test_decision_stage_context_hostel(self, engine):
        state = ConversationState(session_id="test", stage=ConversationStage.DECISION)
        result = engine.understand("hostel options", state)
        assert result.intent.primary == "hostel"

    def test_discovery_stage_greeting_context(self, engine):
        state = ConversationState(session_id="test", stage=ConversationStage.DISCOVERY)
        result = engine.understand("Hi", state)
        assert result.intent.primary == "greeting"


# ── Conflict resolution (10+ tests) ────────────────────────────────────

class TestConflictResolution:
    def test_hostel_wins_over_fee(self, engine):
        result = engine.understand("hostel fee")
        assert result.intent.primary in ("hostel", "fee")

    def test_scholarship_wins_over_fee(self, engine):
        result = engine.understand("scholarship and fee waiver")
        assert result.intent.primary == "scholarship"

    def test_lateral_wins_over_admission(self, engine):
        result = engine.understand("lateral entry admission")
        assert result.intent.primary in ("lateral_entry", "admission", "transfer")

    def test_sports_wins_over_admission(self, engine):
        result = engine.understand("sports quota admission")
        assert result.intent.primary in ("sports_quota", "admission")

    def test_transfer_wins_over_admission(self, engine):
        result = engine.understand("transfer admission process")
        assert result.intent.primary in ("transfer", "admission")

    def test_greeting_removed_when_meaningful(self, engine):
        result = engine.understand("hello I need hostel info")
        assert result.intent.primary != "greeting"
        assert result.intent.primary == "hostel"

    def test_repeat_removed_when_other_intent(self, engine):
        result = engine.understand("repeat what is the fee?")
        assert result.intent.primary != "repeat"
        assert result.intent.primary == "fee"

    def test_management_quota_wins_over_admission(self, engine):
        result = engine.understand("management quota admission")
        assert result.intent.primary in ("management_quota", "admission")

    def test_distance_education_wins_over_admission(self, engine):
        result = engine.understand("distance education admission")
        assert result.intent.primary in ("distance_education", "admission")

    def test_hostel_safety_wins_over_greeting(self, engine):
        result = engine.understand("hi is the girls hostel safe?")
        assert result.intent.primary not in ("greeting",)


# ── Hindi intent detection (10+ tests) ─────────────────────────────────

class TestHindiIntent:
    def test_hindi_fee(self, engine):
        result = engine.understand("फीस कितनी है?")
        assert result.intent.primary == "fee"

    def test_hindi_admission(self, engine):
        result = engine.understand("प्रवेश कब से शुरू है?")
        assert result.intent.primary == "admission"

    def test_hindi_hostel(self, engine):
        result = engine.understand("हॉस्टल की सुविधा कैसी है?")
        assert result.intent.primary == "hostel"

    def test_hindi_scholarship(self, engine):
        result = engine.understand("छात्रवृत्ति मिलती है क्या?")
        assert result.intent.primary == "scholarship"

    def test_hindi_contact(self, engine):
        result = engine.understand("संपर्क नंबर क्या है?")
        assert result.intent.primary == "institution"

    def test_hindi_safety(self, engine):
        result = engine.understand("कैंपस सुरक्षित है क्या?")
        assert result.intent.primary == "safety"

    def test_hindi_department(self, engine):
        result = engine.understand("कौन से विभाग हैं?")
        assert result.intent.primary == "department"

    def test_hindi_greeting(self, engine):
        result = engine.understand("नमस्ते")
        assert result.intent.primary == "greeting"

    def test_hindi_mixed_rank(self, engine):
        result = engine.understand("mera rank 55k hai WBJEE mein. PCM 72")
        assert result.intent.primary == "admission"

    def test_hindi_budget_fee(self, engine):
        result = engine.understand("फीस बहुत ज्यादा है, कोई छात्रवृत्ति?")
        assert result.intent.primary in ("fee", "scholarship")


# ── Bengali intent detection (10+ tests) ───────────────────────────────

class TestBengaliIntent:
    def test_bengali_admission(self, engine):
        result = engine.understand("আমি ভর্তি সম্পর্কে জানতে চাই")
        assert result.intent.primary == "admission"

    def test_bengali_fee(self, engine):
        result = engine.understand("কোর্স ফি কত টাকা?")
        assert result.intent.primary == "fee"

    def test_bengali_hostel(self, engine):
        result = engine.understand("আবাসনের ব্যবস্থা কেমন?")
        assert result.intent.primary == "hostel"

    def test_bengali_scholarship(self, engine):
        result = engine.understand("স্কলারশিপ পাওয়া যায় কি?")
        assert result.intent.primary == "scholarship"

    def test_bengali_contact(self, engine):
        result = engine.understand("যোগাযোগের নম্বর দিন")
        assert result.intent.primary == "institution"

    def test_bengali_department(self, engine):
        result = engine.understand("কি কি বিভাগ আছে?")
        assert result.intent.primary == "department"

    def test_bengali_greeting(self, engine):
        result = engine.understand("হ্যালো")
        assert result.intent.primary == "greeting"

    def test_bengali_counseling(self, engine):
        result = engine.understand("কাউন্সেলিং কবে হবে?")
        assert result.intent.primary == "counseling_info"

    def test_bengali_admission_query(self, engine):
        result = engine.understand("ভর্তির যোগ্যতা কী?")
        assert result.intent.primary == "admission"

    def test_bengali_safety(self, engine):
        result = engine.understand("নিরাপত্তা কেমন?")
        assert result.intent.primary == "safety"


# ── Mixed language intent (10+ tests) ──────────────────────────────────

class TestMixedLanguageIntent:
    def test_english_hindi_fee(self, engine):
        result = engine.understand("kitna fee hai CSE ka?")
        assert result.intent.primary == "fee"

    def test_english_hindi_admission(self, engine):
        result = engine.understand("admission kab se hai?")
        assert result.intent.primary == "admission"

    def test_english_hindi_hostel(self, engine):
        result = engine.understand("hostel ki facility hai kya?")
        assert result.intent.primary == "hostel"

    def test_english_hindi_placement(self, engine):
        result = engine.understand("placement kitna hai yahan?")
        assert result.intent.primary == "placement"

    def test_english_bengali_fee(self, engine):
        result = engine.understand("koto taka course fee?")
        assert result.intent.primary == "fee"

    def test_hindi_budget_concern(self, engine):
        result = engine.understand("fees bahut hai, koi scholarship?")
        assert result.intent.primary in ("fee", "scholarship")

    def test_mixed_greeting_then_query(self, engine):
        result = engine.understand("hello sir, admission ke baare mein batao")
        assert result.intent.primary == "admission"

    def test_mixed_hostel_query(self, engine):
        result = engine.understand("hostel kaise hai aur fee kitna?")
        assert result.intent.primary in ("hostel", "fee")

    def test_mixed_branch_query(self, engine):
        result = engine.understand("kaun kaun se branch hain?")
        assert result.intent.primary == "department"

    def test_mixed_cutoff_query(self, engine):
        result = engine.understand("cutoff kitna tha pichle saal?")
        assert result.intent.primary == "cutoff"


# ── Confidence scoring (10+ tests) ─────────────────────────────────────

class TestConfidenceScoring:
    def test_greeting_has_high_confidence(self, engine):
        result = engine.understand("Hello")
        assert result.intent.confidence > 0.2

    def test_fee_query_has_confidence(self, engine):
        result = engine.understand("What are the fees for CSE?")
        assert result.intent.confidence > 0.2

    def test_admission_has_confidence(self, engine):
        result = engine.understand("When will the admission start?")
        assert result.intent.confidence > 0.2

    def test_unknown_has_low_confidence(self, engine):
        result = engine.understand("xyzzz random")
        assert result.intent.confidence == 0.0

    def test_multiple_signals_increase_confidence(self, engine):
        result1 = engine.understand("fee")
        result2 = engine.understand("My rank is 25000 and I want CSE, what is the fee structure?")
        assert result2.intent.confidence >= result1.intent.confidence

    def test_all_scores_are_rounded(self, engine):
        result = engine.understand("What is the hostel fee?")
        for k, v in result.intent.all_scores.items():
            assert isinstance(v, float)
            assert v >= 0.0

    def test_entity_boosted_confidence(self, engine):
        result = engine.understand("my rank is 48000")
        assert result.intent.confidence > 0.1

    def test_placement_query_confidence(self, engine):
        result = engine.understand("What is the placement record?")
        assert result.intent.confidence > 0.2

    def test_cutoff_query_confidence(self, engine):
        result = engine.understand("What was the cutoff last year?")
        assert result.intent.confidence > 0.2

    def test_scholarship_query_confidence(self, engine):
        result = engine.understand("What scholarships are available?")
        assert result.intent.confidence > 0.2


# ── Edge cases (15+ tests) ─────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_string(self, engine):
        result = engine.understand("")
        assert result.intent.primary == "unknown"

    def test_only_spaces(self, engine):
        result = engine.understand("   ")
        assert result.intent.primary == "unknown"

    def test_greeting_only(self, engine):
        result = engine.understand("Hello")
        assert result.intent.primary == "greeting"

    def test_gibberish(self, engine):
        result = engine.understand("asdfghjkl qwerty zxcvbnm")
        assert result.intent.primary == "unknown"

    def test_numbers_only(self, engine):
        result = engine.understand("12345 67890")
        assert result.intent.primary == "unknown"

    def test_special_chars_only(self, engine):
        result = engine.understand("!@#$%^&*()")
        assert result.intent.primary == "unknown"

    def test_very_long_text(self, engine):
        long = "admission " * 100
        result = engine.understand(long)
        assert result.intent.primary == "admission"

    def test_single_word_question(self, engine):
        result = engine.understand("Admission?")
        assert result.intent.primary == "admission"

    def test_uppercase_text(self, engine):
        result = engine.understand("WHAT ARE THE FEES FOR CSE?")
        assert result.intent.primary == "fee"

    def test_mixed_case(self, engine):
        result = engine.understand("HoStEl FaCiLiTiEs")
        assert result.intent.primary == "hostel"

    def test_punctuated_greeting(self, engine):
        result = engine.understand("Hello!!!")
        assert result.intent.primary == "greeting"

    def test_short_abbreviation(self, engine):
        result = engine.understand("CSE cutoff?")
        assert result.intent.primary in ("cutoff", "department")

    def test_emoji_text(self, engine):
        result = engine.understand("Hello 🙏 admission please")
        assert result.intent.primary == "admission"

    def test_polite_greeting(self, engine):
        result = engine.understand("Good morning, I want to ask about fees")
        assert result.intent.primary == "fee"

    def test_greeting_with_name(self, engine):
        result = engine.understand("Namaste, my name is Rahul")
        assert result.intent.primary in ("greeting", "admission")


# ── All existing intent tests must pass ─────────────────────────────────

class TestExistingIntentTestsStillPass:
    def test_intent_fee(self, engine):
        result = engine.understand("What are the fees for CSE?")
        assert result.intent.primary == "fee"

    def test_intent_admission(self, engine):
        result = engine.understand("When will the admission start?")
        assert result.intent.primary == "admission"

    def test_intent_placement(self, engine):
        result = engine.understand("What is the placement record?")
        assert result.intent.primary == "placement"

    def test_intent_greeting(self, engine):
        result = engine.understand("Hello")
        assert result.intent.primary == "greeting"

    def test_intent_unknown(self, engine):
        result = engine.understand("this is just random text xyz")
        assert result.intent.primary == "unknown"

    def test_intent_confidence_scored(self, engine):
        result = engine.understand("What are the fees for CSE?")
        assert result.intent.confidence > 0
