"""Tests for signal detection v2 — structured rule-based signal inference."""

import pytest

from src.conversation.state import ConversationState
from src.understanding.engine import UnderstandingEngine
from src.understanding.models import (
    ConversationSignals,
    UnderstandingIntent,
)
from src.understanding.profile import StudentProfile


@pytest.fixture
def engine():
    return UnderstandingEngine()


@pytest.fixture
def fresh_engine():
    return UnderstandingEngine()


# =========================================================================
# 1. English signals (20+ tests)
# =========================================================================

class TestEnglishSignals:
    def test_anxiety_worried(self, fresh_engine):
        s = fresh_engine._detect_signals("I am very worried about my admission", None, None)
        assert s.anxiety > 0

    def test_anxiety_nervous(self, fresh_engine):
        s = fresh_engine._detect_signals("I feel nervous about my results", None, None)
        assert s.anxiety > 0

    def test_anxiety_scared(self, fresh_engine):
        s = fresh_engine._detect_signals("I am scared I won't get admission", None, None)
        assert s.anxiety > 0

    def test_anxiety_panic(self, fresh_engine):
        s = fresh_engine._detect_signals("I am panicking about the deadline", None, None)
        assert s.anxiety > 0.4

    def test_anxiety_stressed(self, fresh_engine):
        s = fresh_engine._detect_signals("I am really stressed out about this", None, None)
        assert s.anxiety > 0

    def test_urgency_urgent(self, fresh_engine):
        s = fresh_engine._detect_signals("This is urgent, I need to know", None, None)
        assert s.urgency > 0

    def test_urgency_deadline(self, fresh_engine):
        s = fresh_engine._detect_signals("What is the deadline for application", None, None)
        assert s.urgency > 0

    def test_urgency_asap(self, fresh_engine):
        s = fresh_engine._detect_signals("Please reply ASAP", None, None)
        assert s.urgency > 0

    def test_urgency_last_date(self, fresh_engine):
        s = fresh_engine._detect_signals("When is the last date to apply", None, None)
        assert s.urgency > 0

    def test_urgency_running_out(self, fresh_engine):
        s = fresh_engine._detect_signals("I am running out of time for admission", None, None)
        assert s.urgency > 0.4

    def test_confusion_confused(self, fresh_engine):
        s = fresh_engine._detect_signals("I am confused about which branch to choose", None, None)
        assert s.confusion > 0

    def test_confusion_not_sure(self, fresh_engine):
        s = fresh_engine._detect_signals("I am not sure what to do", None, None)
        assert s.confusion > 0

    def test_confusion_dilemma(self, fresh_engine):
        s = fresh_engine._detect_signals("I am in a dilemma about my career", None, None)
        assert s.confusion > 0

    def test_confusion_cant_decide(self, fresh_engine):
        s = fresh_engine._detect_signals("I can't decide between CSE and ECE", None, None)
        assert s.confusion > 0

    def test_confusion_unsure(self, fresh_engine):
        s = fresh_engine._detect_signals("I am unsure which college is better", None, None)
        assert s.confusion > 0

    def test_hesitation_maybe(self, fresh_engine):
        s = fresh_engine._detect_signals("Maybe I should take computer science", None, None)
        assert s.hesitation > 0

    def test_hesitation_i_guess(self, fresh_engine):
        s = fresh_engine._detect_signals("I guess I could go for engineering", None, None)
        assert s.hesitation > 0

    def test_frustration_frustrated(self, fresh_engine):
        s = fresh_engine._detect_signals("I am so frustrated with this process", None, None)
        assert s.frustration > 0

    def test_frustration_fed_up(self, fresh_engine):
        s = fresh_engine._detect_signals("I am fed up with all this paperwork", None, None)
        assert s.frustration > 0

    def test_frustration_not_working(self, fresh_engine):
        s = fresh_engine._detect_signals("The website is not working again", None, None)
        assert s.frustration > 0

    def test_financial_expensive(self, fresh_engine):
        s = fresh_engine._detect_signals("The fees are too expensive", None, None)
        assert s.financial_concern > 0

    def test_financial_cannot_afford(self, fresh_engine):
        s = fresh_engine._detect_signals("I cannot afford the tuition fees", None, None)
        assert s.financial_concern > 0.3

    def test_financial_tight_budget(self, fresh_engine):
        s = fresh_engine._detect_signals("I have a tight budget for college", None, None)
        assert s.financial_concern > 0

    def test_financial_education_loan(self, fresh_engine):
        s = fresh_engine._detect_signals("I need an education loan for my studies", None, None)
        assert s.financial_concern > 0

    def test_parent_influence_my_father(self, fresh_engine):
        s = fresh_engine._detect_signals("My father wants me to be a doctor", None, None)
        assert s.parent_influence > 0

    def test_parent_influence_my_parents(self, fresh_engine):
        s = fresh_engine._detect_signals("My parents want me to study engineering", None, None)
        assert s.parent_influence > 0

    def test_parent_influence_mom_said(self, fresh_engine):
        s = fresh_engine._detect_signals("Mom said I should take the exam", None, None)
        assert s.parent_influence > 0


# =========================================================================
# 2. Hindi signals (10+ tests) — Devanagari and Roman script
# =========================================================================

class TestHindiSignals:
    def test_anxiety_hindi_devanagari(self, fresh_engine):
        s = fresh_engine._detect_signals("मुझे डर लग रहा है एडमिशन को लेकर", None, None)
        assert s.anxiety > 0

    def test_anxiety_hindi_roman(self, fresh_engine):
        s = fresh_engine._detect_signals("mujhe bahut tension hai admission ki", None, None)
        assert s.anxiety > 0

    def test_anxiety_hindi_parshan(self, fresh_engine):
        s = fresh_engine._detect_signals("main bahut pareshan hoon", None, None)
        assert s.anxiety > 0

    def test_urgency_hindi_jaldi(self, fresh_engine):
        s = fresh_engine._detect_signals("jaldi batao kya hai last date", None, None)
        assert s.urgency > 0

    def test_urgency_hindi_time_nahi(self, fresh_engine):
        s = fresh_engine._detect_signals("mere paas time nahi hai", None, None)
        assert s.urgency > 0

    def test_confusion_hindi_samajh_nahi(self, fresh_engine):
        s = fresh_engine._detect_signals("samajh nahi aa raha kya karein", None, None)
        assert s.confusion > 0

    def test_confusion_hindi_devanagari(self, fresh_engine):
        s = fresh_engine._detect_signals("मुझे समझ नहीं आ रहा है", None, None)
        assert s.confusion > 0

    def test_confusion_hindi_kya_karein(self, fresh_engine):
        s = fresh_engine._detect_signals("kya karein ab, samajh mein nahi aa raha", None, None)
        assert s.confusion > 0

    def test_hesitation_hindi_shayad(self, fresh_engine):
        s = fresh_engine._detect_signals("shayad main CSE le loon", None, None)
        assert s.hesitation > 0

    def test_parent_influence_hindi(self, fresh_engine):
        s = fresh_engine._detect_signals("mere papa ne kaha hai engineering karo", None, None)
        assert s.parent_influence > 0

    def test_parent_influence_hindi_dev(self, fresh_engine):
        s = fresh_engine._detect_signals("पिता जी चाहते हैं कि मैं डॉक्टर बनूं", None, None)
        assert s.parent_influence > 0

    def test_financial_hindi_paise(self, fresh_engine):
        s = fresh_engine._detect_signals("fees bahut hai, paise nahi hai mere paas", None, None)
        assert s.financial_concern > 0

    def test_frustration_hindi_thak_gaya(self, fresh_engine):
        s = fresh_engine._detect_signals("bahut ho gaya, thak gaya main", None, None)
        assert s.frustration > 0

    def test_frustration_hindi_nirash(self, fresh_engine):
        s = fresh_engine._detect_signals("main nirash hoon is system se", None, None)
        assert s.frustration > 0


# =========================================================================
# 3. Bengali signals (10+ tests)
# =========================================================================

class TestBengaliSignals:
    def test_anxiety_bengali_chinta(self, fresh_engine):
        s = fresh_engine._detect_signals("আমার খুব চিন্তা হচ্ছে ভর্তি নিয়ে", None, None)
        assert s.anxiety > 0

    def test_anxiety_bengali_bhoy(self, fresh_engine):
        s = fresh_engine._detect_signals("আমি ভয় পেয়ে গেছি", None, None)
        assert s.anxiety > 0

    def test_anxiety_bengali_tension(self, fresh_engine):
        s = fresh_engine._detect_signals("আমার খুব টেনশন হচ্ছে", None, None)
        assert s.anxiety > 0

    def test_urgency_bengali_joldi(self, fresh_engine):
        s = fresh_engine._detect_signals("জলদি বলুন প্লিজ, সময় নেই", None, None)
        assert s.urgency > 0

    def test_confusion_bengali(self, fresh_engine):
        s = fresh_engine._detect_signals("বুঝতে পারছি না কী করব", None, None)
        assert s.confusion > 0

    def test_hesitation_bengali(self, fresh_engine):
        s = fresh_engine._detect_signals("হয়তো আমি ইঞ্জিনিয়ারিং নেব", None, None)
        assert s.hesitation > 0

    def test_frustration_bengali(self, fresh_engine):
        s = fresh_engine._detect_signals("বিরক্ত লাগছে, সহ্য হচ্ছে না", None, None)
        assert s.frustration > 0

    def test_financial_bengali(self, fresh_engine):
        s = fresh_engine._detect_signals("টাকার সমস্যা আছে, fees অনেক বেশি", None, None)
        assert s.financial_concern > 0

    def test_parent_influence_bengali(self, fresh_engine):
        s = fresh_engine._detect_signals("আমার বাবা চান আমি ডাক্তার হই", None, None)
        assert s.parent_influence > 0

    def test_financial_bengali_dam(self, fresh_engine):
        s = fresh_engine._detect_signals("বেশি দাম, সস্তা কিছু নেই", None, None)
        assert s.financial_concern > 0


# =========================================================================
# 4. Mixed language (10+ tests)
# =========================================================================

class TestMixedLanguageSignals:
    def test_mixed_hindi_english_anxiety(self, fresh_engine):
        s = fresh_engine._detect_signals("mera rank kam hai, bahut tension hai", None, None)
        assert s.anxiety > 0

    def test_mixed_hindi_english_urgency(self, fresh_engine):
        s = fresh_engine._detect_signals("jaldi batao, last date kab hai", None, None)
        assert s.urgency > 0

    def test_mixed_hindi_english_confusion(self, fresh_engine):
        s = fresh_engine._detect_signals("kuch samajh nahi aa raha, what should I do", None, None)
        assert s.confusion > 0

    def test_mixed_bengali_english_finance(self, fresh_engine):
        s = fresh_engine._detect_signals("fees bahut high, parents afford korte parbe na", None, None)
        assert s.financial_concern > 0

    def test_mixed_hindi_english_parent(self, fresh_engine):
        s = fresh_engine._detect_signals("ghar wale chahte hain main doctor banu", None, None)
        assert s.parent_influence > 0

    def test_mixed_hindi_english_frustration(self, fresh_engine):
        s = fresh_engine._detect_signals("bahut ho gaya, I am tired of this", None, None)
        assert s.frustration > 0

    def test_mixed_hindi_english_hesitation(self, fresh_engine):
        s = fresh_engine._detect_signals("shayad main computer science le loon, not sure", None, None)
        assert s.hesitation > 0
        assert s.confusion > 0

    def test_mixed_all_languages_anxiety(self, fresh_engine):
        s = fresh_engine._detect_signals("bahut tension hai, আমি worried", None, None)
        assert s.anxiety > 0

    def test_mixed_hindi_english_urgency_time(self, fresh_engine):
        s = fresh_engine._detect_signals("time kam hai, deadline close ho rahi hai", None, None)
        assert s.urgency > 0

    def test_mixed_budget_hindi(self, fresh_engine):
        s = fresh_engine._detect_signals("budget kam hai, parents afford kar payenge?", None, None)
        assert s.financial_concern > 0

    def test_mixed_confusion_bengali(self, fresh_engine):
        s = fresh_engine._detect_signals("confusion aache, idea nei ki korbo", None, None)
        assert s.confusion > 0


# =========================================================================
# 5. Composable signals (10+ tests)
# =========================================================================

class TestComposableSignals:
    def test_anxiety_and_financial(self, fresh_engine):
        s = fresh_engine._detect_signals("I am very worried about the expensive fees", None, None)
        assert s.anxiety > 0
        assert s.financial_concern > 0

    def test_anxiety_and_confusion(self, fresh_engine):
        s = fresh_engine._detect_signals("I am confused and worried about my career", None, None)
        assert s.anxiety > 0
        assert s.confusion > 0

    def test_urgency_and_anxiety(self, fresh_engine):
        s = fresh_engine._detect_signals("I am panicking because the deadline is tomorrow", None, None)
        assert s.anxiety > 0
        assert s.urgency > 0

    def test_financial_and_parent(self, fresh_engine):
        s = fresh_engine._detect_signals("My parents cannot afford the expensive fees", None, None)
        assert s.parent_influence > 0
        assert s.financial_concern > 0

    def test_confusion_and_hesitation(self, fresh_engine):
        s = fresh_engine._detect_signals("I am confused, maybe I should take CSE", None, None)
        assert s.confusion > 0
        assert s.hesitation > 0

    def test_anxiety_urgency_confusion(self, fresh_engine):
        s = fresh_engine._detect_signals("I am worried and confused about the urgent deadline", None, None)
        assert s.anxiety > 0
        assert s.confusion > 0
        assert s.urgency > 0

    def test_frustration_anxiety(self, fresh_engine):
        s = fresh_engine._detect_signals("I am so frustrated and worried about all this", None, None)
        assert s.frustration > 0
        assert s.anxiety > 0

    def test_financial_anxiety_frustration(self, fresh_engine):
        s = fresh_engine._detect_signals("I am frustrated that I can't afford the fees and worried", None, None)
        assert s.frustration > 0
        assert s.financial_concern > 0
        assert s.anxiety > 0

    def test_parent_and_confusion(self, fresh_engine):
        s = fresh_engine._detect_signals("My father wants me to do engineering but I am confused", None, None)
        assert s.parent_influence > 0
        assert s.confusion > 0

    def test_all_signals_high(self, fresh_engine):
        s = fresh_engine._detect_signals(
            "I am worried, confused, and frustrated. The expensive fees are urgent and maybe I need to ask my parents",
            None, None,
        )
        assert s.anxiety > 0
        assert s.confusion > 0
        assert s.frustration > 0
        assert s.financial_concern > 0
        assert s.urgency > 0
        assert s.hesitation > 0
        assert s.parent_influence > 0


# =========================================================================
# 6. Contradictory wording / Negation (10+ tests)
# =========================================================================

class TestNegationSignals:
    def test_not_worried(self, fresh_engine):
        s = fresh_engine._detect_signals("I am not worried about my admission", None, None)
        assert s.anxiety == 0.0

    def test_no_tension(self, fresh_engine):
        s = fresh_engine._detect_signals("there is no tension at all", None, None)
        assert s.anxiety == 0.0

    def test_not_confused(self, fresh_engine):
        s = fresh_engine._detect_signals("I am not confused about my career", None, None)
        assert s.confusion == 0.0

    def test_not_urgent(self, fresh_engine):
        s = fresh_engine._detect_signals("It is not urgent, take your time", None, None)
        assert s.urgency == 0.0

    def test_not_scared(self, fresh_engine):
        s = fresh_engine._detect_signals("I am not scared about the exam", None, None)
        assert s.anxiety == 0.0

    def test_no_confusion(self, fresh_engine):
        s = fresh_engine._detect_signals("There is no confusion, I know what I want", None, None)
        assert s.confusion == 0.0

    def test_not_afford_negated(self, fresh_engine):
        s = fresh_engine._detect_signals("it is not expensive at all", None, None)
        assert s.financial_concern == 0.0

    def test_parents_supportive(self, fresh_engine):
        s = fresh_engine._detect_signals("My family is supportive of my decision", None, None)
        assert s.parent_influence == 0.0

    def test_not_stressed(self, fresh_engine):
        s = fresh_engine._detect_signals("I am not stressed about the results", None, None)
        assert s.anxiety == 0.0

    def test_budget_fine(self, fresh_engine):
        s = fresh_engine._detect_signals("Everything is fine, no issues with the cost", None, None)
        assert s.financial_concern == 0.0

    def test_no_hesitation(self, fresh_engine):
        s = fresh_engine._detect_signals("I am not unsure, I have decided", None, None)
        assert s.hesitation == 0.0

    def test_not_frustrated(self, fresh_engine):
        s = fresh_engine._detect_signals("I am not frustrated, everything is fine", None, None)
        assert s.frustration == 0.0

    def test_dont_worry_complex(self, fresh_engine):
        s = fresh_engine._detect_signals("I am not really that worried about it", None, None)
        assert s.anxiety == 0.0


# =========================================================================
# 7. Cross-turn persistence (8+ tests)
# =========================================================================

class TestCrossTurnPersistence:
    def test_high_anxiety_carries_forward(self):
        """Anxiety >= 0.6 in prev turn should carry 50% forward."""
        eng = UnderstandingEngine()
        eng._prev_signals_by_session["s"] = ConversationSignals(anxiety=0.8)
        s = eng._detect_signals("Hello, just checking in", None, None, session_id="s")
        assert s.anxiety > 0.3
        assert s.anxiety <= 0.5

    def test_moderate_anxiety_carries_less(self):
        """Anxiety 0.4-0.6 in prev turn carries 35%."""
        eng = UnderstandingEngine()
        eng._prev_signals_by_session["s"] = ConversationSignals(anxiety=0.5)
        s = eng._detect_signals("Hello", None, None, session_id="s")
        assert s.anxiety > 0.0
        assert s.anxiety <= 0.25

    def test_low_anxiety_minimal_carry(self):
        """Anxiety < 0.4 in prev turn carries only 15%."""
        eng = UnderstandingEngine()
        eng._prev_signals_by_session["s"] = ConversationSignals(anxiety=0.3)
        s = eng._detect_signals("Hello", None, None, session_id="s")
        assert s.anxiety <= 0.1

    def test_urgency_persists(self):
        eng = UnderstandingEngine()
        eng._prev_signals_by_session["s"] = ConversationSignals(urgency=0.7)
        s = eng._detect_signals("Hello", None, None, session_id="s")
        assert s.urgency > 0.3

    def test_confusion_persists(self):
        eng = UnderstandingEngine()
        eng._prev_signals_by_session["s"] = ConversationSignals(confusion=0.9)
        s = eng._detect_signals("Hello", None, None, session_id="s")
        assert s.confusion > 0.3

    def test_multiple_signals_persist(self):
        eng = UnderstandingEngine()
        eng._prev_signals_by_session["s"] = ConversationSignals(anxiety=0.7, financial_concern=0.6)
        s = eng._detect_signals("Hello", None, None, session_id="s")
        assert s.anxiety > 0.3
        assert s.financial_concern > 0.2

    def test_new_text_adds_to_persisted(self):
        eng = UnderstandingEngine()
        eng._prev_signals_by_session["s"] = ConversationSignals(anxiety=0.6)
        s = eng._detect_signals("I am worried", None, None, session_id="s")
        assert s.anxiety > 0.6

    def test_persisted_signal_decays_without_reinforcement(self):
        eng = UnderstandingEngine()
        eng._prev_signals_by_session["s"] = ConversationSignals(anxiety=0.9, confusion=0.5, urgency=0.8)
        s1 = eng._detect_signals("Hello", None, None, session_id="s")
        s2 = eng._detect_signals("Hello again", None, None, session_id="s")
        s3 = eng._detect_signals("Hello third time", None, None, session_id="s")
        assert s1.anxiety >= s2.anxiety >= s3.anxiety

    def test_sessions_do_not_leak(self):
        """Persistence is scoped per session: a shared engine running two
        sessions must not carry signals across them."""
        eng = UnderstandingEngine()
        eng._prev_signals_by_session["a"] = ConversationSignals(anxiety=0.9)
        sa = eng._detect_signals("Hello", None, None, session_id="a")
        sb = eng._detect_signals("Hello", None, None, session_id="b")
        assert sa.anxiety > 0.3
        assert sb.anxiety == 0.0

    def test_zero_initial_prev(self, fresh_engine):
        """No previous signals means no carryover."""
        s = fresh_engine._detect_signals("Hello", None, None)
        assert s.anxiety == 0.0
        assert s.urgency == 0.0

    def test_financial_concern_also_persists(self):
        eng = UnderstandingEngine()
        eng._prev_signals_by_session["s"] = ConversationSignals(financial_concern=0.8)
        s = eng._detect_signals("I need to check the weather", None, None, session_id="s")
        assert s.financial_concern > 0.3


# =========================================================================
# 8. False-positive prevention (10+ tests)
# =========================================================================

class TestFalsePositivePrevention:
    def test_normal_greeting(self, fresh_engine):
        s = fresh_engine._detect_signals("Hello, how are you?", None, None)
        assert s.anxiety == 0.0
        assert s.urgency == 0.0
        assert s.confusion == 0.0
        assert s.frustration == 0.0
        assert s.financial_concern == 0.0

    def test_normal_introduction(self, fresh_engine):
        s = fresh_engine._detect_signals("My name is John and I am from WBCHSE board", None, None)
        assert s.anxiety == 0.0
        assert s.financial_concern == 0.0
        assert s.parent_influence == 0.0

    def test_normal_academic_question(self, fresh_engine):
        s = fresh_engine._detect_signals("What is the cutoff for CSE this year", None, None)
        assert s.anxiety == 0.0
        assert s.confusion == 0.0

    def test_normal_ranking(self, fresh_engine):
        s = fresh_engine._detect_signals("My rank is 48000 and I have 85 percent", None, None)
        assert s.anxiety == 0.0
        assert s.frustration == 0.0

    def test_fee_inquiry_not_financial_concern(self, fresh_engine):
        s = fresh_engine._detect_signals("What is the CSE department cutoff", None, None)
        assert s.financial_concern == 0.0

    def test_normal_location_query(self, fresh_engine):
        s = fresh_engine._detect_signals("I am from Kolkata, West Bengal", None, None)
        assert s.anxiety == 0.0
        assert s.urgency == 0.0

    def test_normal_interest_statement(self, fresh_engine):
        s = fresh_engine._detect_signals("I am interested in Computer Science and AI", None, None)
        assert s.anxiety == 0.0
        assert s.hesitation == 0.0

    def test_normal_boarding_info(self, fresh_engine):
        s = fresh_engine._detect_signals("I studied in CBSE board", None, None)
        assert s.parent_influence == 0.0
        assert s.anxiety == 0.0

    def test_normal_time_query(self, fresh_engine):
        s = fresh_engine._detect_signals("What time does the office open", None, None)
        assert s.urgency == 0.0

    def test_normal_thanks(self, fresh_engine):
        s = fresh_engine._detect_signals("Thank you for your help", None, None)
        assert s.anxiety == 0.0
        assert s.confusion == 0.0
        assert s.frustration == 0.0

    def test_no_overlap_with_intent(self, fresh_engine):
        """Simple informational queries should not trigger emotional signals."""
        s = fresh_engine._detect_signals("What is the cutoff rank for CSE this year", None, None)
        assert s.anxiety == 0.0
        assert s.frustration == 0.0


# =========================================================================
# 9. Intent-based signal boosting (5+ tests)
# =========================================================================

class TestIntentBoosting:
    def test_fee_intent_boosts_financial(self, fresh_engine):
        """Fee intent with the word 'expensive' should boost financial_concern."""
        intent = UnderstandingIntent(primary="fee", confidence=0.8)
        s = fresh_engine._detect_signals("The fees are expensive", intent, None)
        assert s.financial_concern > 0.3  # 0.3 (keyword) + 0.15 (intent boost) > 0.3

    def test_safety_intent_boosts_anxiety(self, fresh_engine):
        intent = UnderstandingIntent(primary="safety", confidence=0.7)
        s = fresh_engine._detect_signals("I am worried about safety on campus", intent, None)
        assert s.anxiety > 0.3  # 0.35 (worried) + 0.15 (safety intent boost)

    def test_department_intent_boosts_confusion(self, fresh_engine):
        intent = UnderstandingIntent(primary="department", confidence=0.7)
        s = fresh_engine._detect_signals("I am confused about which department to choose", intent, None)
        assert s.confusion > 0.35  # 0.35 (confused) + 0.1 (department boost) > 0.35

    def test_scholarship_intent_boosts_financial(self, fresh_engine):
        intent = UnderstandingIntent(primary="scholarship", confidence=0.8)
        s = fresh_engine._detect_signals("I need scholarship, the fees are expensive", intent, None)
        assert s.financial_concern > 0.3  # 0.3 (expensive) + 0.2 (intent boost) > 0.3

    def test_admission_intent_boosts_urgency(self, fresh_engine):
        intent = UnderstandingIntent(primary="admission", confidence=0.7)
        s = fresh_engine._detect_signals("This is urgent, I need to know about admission", intent, None)
        assert s.urgency > 0.45  # 0.45 (urgent) + 0.1 (admission boost) > 0.45

    def test_intent_boost_not_applied_without_base(self, fresh_engine):
        """Intent boost should NOT create signals from nothing."""
        intent = UnderstandingIntent(primary="fee", confidence=0.8)
        s = fresh_engine._detect_signals("What documents do I need for admission", intent, None)
        assert s.financial_concern == 0.0

    def test_multiple_intent_boosts(self, fresh_engine):
        intent = UnderstandingIntent(primary="hostel", confidence=0.7)
        s = fresh_engine._detect_signals("I am worried about hostel accommodation", intent, None)
        assert s.anxiety > 0.35  # 0.35 (worried) + 0.1 (hostel boost) > 0.35


# =========================================================================
# 10. Edge cases (7+ tests)
# =========================================================================

class TestEdgeCases:
    def test_empty_text(self, fresh_engine):
        s = fresh_engine._detect_signals("", None, None)
        assert s.anxiety == 0.0
        assert s.urgency == 0.0
        assert s.confusion == 0.0

    def test_whitespace_only(self, fresh_engine):
        s = fresh_engine._detect_signals("   ", None, None)
        assert s.anxiety == 0.0

    def test_numbers_only(self, fresh_engine):
        s = fresh_engine._detect_signals("48000 85 2024", None, None)
        assert s.anxiety == 0.0
        assert s.confusion == 0.0

    def test_special_characters(self, fresh_engine):
        s = fresh_engine._detect_signals("!!! ### $$$ %%%", None, None)
        assert s.anxiety == 0.0

    def test_very_long_text(self, fresh_engine):
        long_text = "I am " + "very " * 200 + "worried"
        s = fresh_engine._detect_signals(long_text, None, None)
        assert s.anxiety > 0  # worried is detected even in long text

    def test_mixed_numbers_and_words(self, fresh_engine):
        s = fresh_engine._detect_signals("I got 85.5% in 12th standard", None, None)
        assert s.anxiety == 0.0

    def test_unicode_mixed(self, fresh_engine):
        s = fresh_engine._detect_signals("Hello नमस्तে হ্যালো world", None, None)
        assert s.anxiety == 0.0

    def test_single_word(self, fresh_engine):
        s = fresh_engine._detect_signals("worried", None, None)
        assert s.anxiety > 0

    def test_case_insensitive(self, fresh_engine):
        s = fresh_engine._detect_signals("I AM WORRIED AND CONFUSED", None, None)
        assert s.anxiety > 0
        assert s.confusion > 0

    def test_punctuation_handling(self, fresh_engine):
        s = fresh_engine._detect_signals("I'm worried, confused, and frustrated!", None, None)
        assert s.anxiety > 0
        assert s.confusion > 0
        assert s.frustration > 0


# =========================================================================
# Extra: full pipeline integration tests
# =========================================================================

class TestPipelineIntegration:
    def test_anxiety_in_pipeline(self, engine):
        result = engine.understand("I am very worried about my admission")
        assert result.signals.anxiety > 0

    def test_urgency_in_pipeline(self, engine):
        result = engine.understand("This is urgent, when is the deadline?")
        assert result.signals.urgency > 0

    def test_confusion_in_pipeline(self, engine):
        result = engine.understand("I am confused about which branch to choose")
        assert result.signals.confusion > 0

    def test_financial_in_pipeline(self, engine):
        result = engine.understand("The fees are too expensive for me")
        assert result.signals.financial_concern > 0

    def test_multiple_signals_in_pipeline(self, engine):
        result = engine.understand("I am confused and worried about the fees")
        assert result.signals.confusion > 0
        assert result.signals.anxiety > 0
        assert result.signals.financial_concern > 0

    def test_no_false_positives_in_pipeline(self, engine):
        result = engine.understand("I got 85 percent in class 12")
        assert result.signals.anxiety == 0.0
        assert result.signals.urgency == 0.0
        assert result.signals.confusion == 0.0

    def test_profile_based_boost_confusion(self, fresh_engine):
        profile = StudentProfile()
        profile.academic.rank = None
        s = fresh_engine._detect_signals("kya karein, samajh nahi aa raha", None, profile)
        assert s.confusion > 0.25

    def test_profile_based_boost_financial(self, fresh_engine):
        profile = StudentProfile()
        profile.personal.budget = 20000.0
        s = fresh_engine._detect_signals("college ki fees ke baare mein batao", None, profile)
        assert s.financial_concern > 0.2

    def test_profile_low_budget_boost(self, fresh_engine):
        profile = StudentProfile()
        profile.personal.budget = 100000.0
        s = fresh_engine._detect_signals("Tell me about college options", None, profile)
        assert s.financial_concern >= 0.1
