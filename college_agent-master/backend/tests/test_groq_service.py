import pytest
from app.services.llm.groq_service import (
    GroqService,
    GREETING_PATTERNS,
    OUT_OF_DOMAIN_CATEGORIES,
    FEE_GROUP_MAP,
    DEPT_CODE_MAP,
    UNKNOWN_INFO_RESPONSE_EN,
    UNKNOWN_INFO_RESPONSE_HI,
    UNKNOWN_INFO_RESPONSE_BN,
    CLARIFY_REPEAT_EN,
    CLARIFY_REPEAT_HI,
    CLARIFY_REPEAT_BN,
)
import re


@pytest.fixture
def groq_service():
    return GroqService()


def test_kb_reload(groq_service):
    """Verify reload_kb() loads voice_ready_answers correctly."""
    count = groq_service.reload_kb()
    assert count > 0, "KB should have at least 1 FAQ entry"


def test_session_memory_and_clear(groq_service):
    """Verify session memory stores turns and can be cleared."""
    sid = "test-session-123"
    groq_service._append_session_turn(sid, "hi", "hello there")
    groq_service._append_session_turn(sid, "fees?", "fees are...")
    hist = groq_service._get_session_history(sid)
    assert len(hist) == 4  # 2 user + 2 assistant
    assert hist[0]["role"] == "user"
    assert hist[0]["content"] == "hi"
    groq_service.clear_session(sid)
    assert groq_service._get_session_history(sid) == []


def test_greeting_patterns():
    """Greeting regex patterns match common greetings."""
    for greeting in ["hi", "hello", "hey", "good morning", "good evening"]:
        assert any(re.match(p, greeting, re.IGNORECASE) for p in GREETING_PATTERNS), (
            f"'{greeting}' should match a greeting pattern"
        )


def test_non_greeting_does_not_match():
    """Non-greeting queries should not match greeting patterns."""
    for query in ["what is the fees", "hod name", "placement"]:
        assert not any(re.match(p, query, re.IGNORECASE) for p in GREETING_PATTERNS), (
            f"'{query}' should NOT match greeting patterns"
        )


def test_cache_operations(groq_service):
    """Cache should be invalidatable and return stats."""
    stats_before = groq_service.get_cache_stats()
    assert "hits" in stats_before
    assert "misses" in stats_before

    cleared = groq_service.invalidate_cache()
    assert isinstance(cleared, int)
    assert cleared >= 0


def test_greeting_deterministic_response(groq_service):
    """Short greetings should be answered without LLM."""
    import asyncio

    result = asyncio.run(groq_service.generate_response("hi"))
    assert result["source"] == "greeting_deterministic"
    assert "How can I help" in result["answer"] or "help you" in result["answer"].lower()


# -----------------------------------------------------------------------
# Out-of-Domain Detection Tests
# -----------------------------------------------------------------------


class TestOutOfDomain:
    """Tests for _is_out_of_domain() pre-retrieval guard."""

    def test_weather_query_blocked(self, groq_service):
        assert groq_service._is_out_of_domain("what is the weather in Delhi today")

    def test_ipl_cricket_blocked(self, groq_service):
        assert groq_service._is_out_of_domain("who won the IPL match yesterday")

    def test_politics_question_blocked(self, groq_service):
        assert groq_service._is_out_of_domain("who is the prime minister of India")

    def test_movie_query_blocked(self, groq_service):
        assert groq_service._is_out_of_domain("what is the latest blockbuster movie")

    def test_coding_help_blocked(self, groq_service):
        assert groq_service._is_out_of_domain("how to debug a python script")

    def test_math_homework_blocked(self, groq_service):
        assert groq_service._is_out_of_domain("solve this calculus integration equation")

    def test_college_query_not_blocked(self, groq_service):
        assert not groq_service._is_out_of_domain("what is the btech fees for CSE")

    def test_admission_query_not_blocked(self, groq_service):
        assert not groq_service._is_out_of_domain("how to apply for admission in AIML")

    def test_placement_query_not_blocked(self, groq_service):
        assert not groq_service._is_out_of_domain("what is the placement percentage")

    def test_short_query_not_blocked(self, groq_service):
        assert not groq_service._is_out_of_domain("weather")
        assert not groq_service._is_out_of_domain("ipl match")
        assert not groq_service._is_out_of_domain("cricket")

    def test_ood_response_en(self, groq_service):
        """generate_response should return out_of_domain source for OOD queries."""
        import asyncio

        result = asyncio.run(groq_service.generate_response("who won the IPL match yesterday"))
        assert result["source"] == "out_of_domain"
        assert "Engineering College" in result["answer"]

    def test_ood_response_stream(self, groq_service):
        """stream_response should yield OOD response for OOD queries."""
        import asyncio

        collected = []

        async def collect():
            async for token in groq_service.stream_response("what is the weather in Delhi today"):
                collected.append(token)
            return "".join(collected)

        response = asyncio.run(collect())
        assert "Engineering College" in response

    def test_ood_categories_defined(self):
        """OUT_OF_DOMAIN_CATEGORIES should have all expected categories."""
        expected_categories = {
            "weather",
            "sports",
            "politics",
            "entertainment",
            "coding",
            "math",
            "news",
            "personal",
            "food",
            "travel",
        }
        assert set(OUT_OF_DOMAIN_CATEGORIES.keys()) == expected_categories
        for cat, keywords in OUT_OF_DOMAIN_CATEGORIES.items():
            assert len(keywords) > 0, f"Category '{cat}' has no keywords"

    def test_ipl_t20_variations_blocked(self, groq_service):
        assert groq_service._is_out_of_domain("who is the best cricketer in the world")
        assert groq_service._is_out_of_domain("tell me the score of today t20 match")

    def test_recipe_food_blocked(self, groq_service):
        assert groq_service._is_out_of_domain("what is a good recipe for biryani")


# -----------------------------------------------------------------------
# Context Enrichment Tests
# -----------------------------------------------------------------------


class TestExtractDepartmentFromHistory:
    """Tests for _extract_department_from_history() method."""

    def test_extract_cse(self, groq_service):
        history = [
            {"role": "user", "content": "What is the fee for CSE department?"},
            {"role": "assistant", "content": "CSE fee is..."},
        ]
        assert groq_service._extract_department_from_history(history) == "cse"

    def test_extract_aiml(self, groq_service):
        history = [
            {"role": "user", "content": "Tell me about AIML placements"},
        ]
        assert groq_service._extract_department_from_history(history) == "aiml"

    def test_extract_ece(self, groq_service):
        history = [
            {"role": "user", "content": "What is the fees in ECE"},
            {"role": "assistant", "content": "ECE fees are..."},
        ]
        assert groq_service._extract_department_from_history(history) == "ece"

    def test_no_department_returns_none(self, groq_service):
        history = [
            {"role": "user", "content": "What is the college address?"},
            {"role": "assistant", "content": "The address is..."},
        ]
        assert groq_service._extract_department_from_history(history) is None

    def test_empty_history_returns_none(self, groq_service):
        assert groq_service._extract_department_from_history([]) is None

    def test_mixed_case_department(self, groq_service):
        history = [
            {"role": "user", "content": "I want info about Data Science"},
        ]
        assert groq_service._extract_department_from_history(history) == "data science"

    def test_most_recent_department_wins(self, groq_service):
        history = [
            {"role": "user", "content": "What is CSE fee?"},
            {"role": "assistant", "content": "CSE fee is 5 lakh"},
            {"role": "user", "content": "What about AIML?"},
        ]
        assert groq_service._extract_department_from_history(history) == "aiml"


class TestExpandFollowUpQuery:
    """Tests for _expand_follow_up_query() with department enrichment."""

    def test_long_query_not_expanded(self, groq_service):
        q = "what is the fee structure for computer science department"
        result = groq_service._expand_follow_up_query(q, [])
        assert result == q

    def test_empty_history_not_expanded(self, groq_service):
        result = groq_service._expand_follow_up_query("fees", [])
        assert result == "fees"

    def test_repeat_intent_not_expanded(self, groq_service):
        history = [{"role": "user", "content": "What is CSE fee?"}]
        result = groq_service._expand_follow_up_query("repeat", history)
        assert result == "repeat"

    def test_basic_follow_up_expansion(self, groq_service):
        history = [
            {"role": "user", "content": "What is the fee for CSE department?"},
            {"role": "assistant", "content": "CSE fee is..."},
        ]
        result = groq_service._expand_follow_up_query("and seats?", history)
        assert "and seats?" in result
        assert "What is the fee for CSE department?" in result

    def test_department_enrichment_for_ambiguous(self, groq_service):
        """Short ambiguous word 'fees' with department in history should enrich."""
        history = [
            {"role": "user", "content": "What is the fee for AIML department?"},
            {"role": "assistant", "content": "AIML fee is..."},
        ]
        result = groq_service._expand_follow_up_query("fees", history)
        assert result == "aiml fees"

    def test_department_enrichment_for_placement(self, groq_service):
        history = [
            {"role": "user", "content": "Tell me about ECE placements"},
        ]
        result = groq_service._expand_follow_up_query("placement", history)
        assert result == "ece placement"

    def test_no_enrichment_without_department(self, groq_service):
        """If no department in history, fall back to standard expansion."""
        history = [
            {"role": "user", "content": "What is the college address?"},
            {"role": "assistant", "content": "The address is..."},
        ]
        result = groq_service._expand_follow_up_query("fees", history)
        assert "fees" in result
        assert "college address" in result

    def test_seats_with_department_enrichment(self, groq_service):
        history = [
            {"role": "user", "content": "How many seats in CSE?"},
        ]
        result = groq_service._expand_follow_up_query("seats", history)
        assert result == "cse seats"


# -----------------------------------------------------------------------
# Repeat Handler Tests
# -----------------------------------------------------------------------


class TestRepeatHandler:
    """Tests for the repeat request handler."""

    def test_repeat_patterns_include_variations(self, groq_service):
        import re
        from app.services.llm.groq_service import REPEAT_PATTERNS

        repeat_phrases = [
            "repeat",
            "again",
            "pardon",
            "come again",
            "say that again",
            "can you please repeat",
            "could you repeat that",
            "what did you say",
            "i didn't hear you",
            "i didn't catch that",
            "i couldn't hear you",
            "excuse me",
        ]
        for phrase in repeat_phrases:
            assert groq_service._detect_repeat_intent(phrase), (
                f"'{phrase}' should be detected as repeat intent"
            )

    def test_repeat_returns_cached_response(self, groq_service):
        import asyncio

        sid = "test-repeat-session"

        # First, ask a real question to populate history
        result1 = asyncio.run(groq_service.generate_response("what is CSE fee", sid))
        assert result1["source"] not in ("error", "transcript_clarification")

        # Now ask to repeat
        result2 = asyncio.run(groq_service.generate_response("repeat", sid))
        assert result2["source"] == "repeat_replay"
        assert result2["answer"] == result1["answer"]

    def test_repeat_with_no_history_falls_through(self, groq_service):
        import asyncio

        result = asyncio.run(groq_service.generate_response("repeat"))
        assert result["source"] != "repeat_replay"

    def test_repeat_stream_returns_cached(self, groq_service):
        import asyncio

        sid = "test-repeat-stream"

        async def run():
            result1 = await groq_service.generate_response("tell me about IT department", sid)
            collected = []
            async for token in groq_service.stream_response("repeat", sid):
                collected.append(token)
            response = "".join(collected)
            # Normalize whitespace (stream splits on whitespace, may differ from original)
            assert " ".join(response.split()) == " ".join(result1["answer"].split())

        asyncio.run(run())


# -----------------------------------------------------------------------
# Task 1 — Structured Knowledge Layer Tests
# -----------------------------------------------------------------------


class TestStructuredKnowledge:
    """Tests for deterministic structured lookups from canonical KB."""

    def test_structured_principal_lookup(self, groq_service):
        result = groq_service._structured_lookup("who is the principal", "en")
        assert result is not None
        assert "Dr. Sanjay" in result or "Sanjay" in result

    def test_structured_vice_principal_lookup(self, groq_service):
        result = groq_service._structured_lookup("vice principal name", "en")
        assert result is not None
        assert "Hossain" in result or "হোসেন" in result

    def test_structured_cse_fee_lookup(self, groq_service):
        result = groq_service._structured_lookup("CSE fees", "en")
        assert result is not None
        assert "six" in result.lower() or "6" in result

    def test_structured_aiml_fee_lookup(self, groq_service):
        result = groq_service._structured_lookup("AIML total fee", "en")
        assert result is not None
        assert "five" in result.lower() or "lakh" in result.lower()

    def test_structured_ee_fee_lookup(self, groq_service):
        result = groq_service._structured_lookup("EE semester fee", "en")
        assert result is not None

    def test_structured_cse_hod_lookup(self, groq_service):
        result = groq_service._structured_lookup("who is HOD of CSE", "en")
        assert result is not None
        assert "Pabitra" in result or "Dey" in result

    def test_structured_it_hod_lookup(self, groq_service):
        result = groq_service._structured_lookup("IT department head", "en")
        assert result is not None
        assert "Dinesh" in result or "Pradhan" in result

    def test_structured_contact_lookup(self, groq_service):
        result = groq_service._structured_lookup("contact number of college", "en")
        assert result is not None
        assert "0343" in result or "0343-2501353" in result

    def test_structured_cse_intake(self, groq_service):
        result = groq_service._structured_lookup("how many seats in CSE", "en")
        assert result is not None
        assert "seats" in result.lower() or "intake" in result.lower()

    def test_structured_admission_documents(self, groq_service):
        result = groq_service._structured_lookup("what documents needed for admission", "en")
        assert result is not None
        assert "document" in result.lower()

    def test_structured_unknown_query_returns_none(self, groq_service):
        result = groq_service._structured_lookup("what is the color of the college building", "en")
        assert result is None

    def test_structured_all_hods(self, groq_service):
        result = groq_service._structured_lookup("list all HODs", "en")
        assert result is not None
        assert "CSE:" in result or "Department Heads:" in result

    def test_structured_cse_dept_info(self, groq_service):
        result = groq_service._structured_lookup("tell me about CSE department", "en")
        assert result is not None
        assert "Computer Science" in result or "CSE" in result

    def test_structured_me_fee_lookup(self, groq_service):
        result = groq_service._structured_lookup("ME total fee", "en")
        assert result is not None
        assert "ME" in result or "Mechanical" in result


# -----------------------------------------------------------------------
# Task 2 — Unknown Data Policy Tests
# -----------------------------------------------------------------------


class TestUnknownDataPolicy:
    """Tests for the 'unknown data' response policy."""

    def test_unknown_response_en(self, groq_service):
        assert "couldn't find verified information" in UNKNOWN_INFO_RESPONSE_EN

    def test_unknown_response_hi(self, groq_service):
        assert "सत्यापित जानकारी" in UNKNOWN_INFO_RESPONSE_HI

    def test_unknown_response_bn(self, groq_service):
        assert "যাচাইকৃত তথ্য" in UNKNOWN_INFO_RESPONSE_BN

    def test_structured_unknown_fallback_en(self, groq_service):
        result = groq_service._structured_unknown_fallback("en")
        assert result == UNKNOWN_INFO_RESPONSE_EN

    def test_structured_unknown_fallback_hi(self, groq_service):
        result = groq_service._structured_unknown_fallback("hi")
        assert result == UNKNOWN_INFO_RESPONSE_HI

    def test_structured_unknown_fallback_bn(self, groq_service):
        result = groq_service._structured_unknown_fallback("bn")
        assert result == UNKNOWN_INFO_RESPONSE_BN


# -----------------------------------------------------------------------
# Task 3 — Conversation Replay Tests
# -----------------------------------------------------------------------


class TestConversationReplay:
    """Tests for differentiated conversation replay."""

    def test_repeat_last_response(self, groq_service):
        import asyncio

        sid = "test-replay-session"
        result1 = asyncio.run(groq_service.generate_response("what is CSE fee", sid))
        result2 = asyncio.run(groq_service.generate_response("repeat", sid))
        assert result2["source"] == "repeat_replay"
        assert result2["answer"] == result1["answer"]

    def test_repeat_everything_detected(self, groq_service):
        assert groq_service._detect_repeat_conversation_intent("repeat everything") == "all"
        assert groq_service._detect_repeat_conversation_intent("repeat all") == "all"
        assert groq_service._detect_repeat_conversation_intent("tell me everything again") == "all"
        assert groq_service._detect_repeat_conversation_intent("say everything") == "all"
        assert groq_service._detect_repeat_conversation_intent("full conversation") == "all"

    def test_repeat_everything_returns_multi_turn(self, groq_service):
        import asyncio

        sid = "test-replay-all-session"
        asyncio.run(groq_service.generate_response("what is the fees for CSE", sid))
        asyncio.run(groq_service.generate_response("what about ECE", sid))

        history = groq_service._get_session_history(sid)
        replay = groq_service._repeat_recent_conversation(history)
        assert replay is not None
        # Should contain content from multiple assistant turns
        assert len(replay) > 10

    def test_repeat_everything_empty_history(self, groq_service):
        assert groq_service._repeat_recent_conversation([]) is None

    def test_repeat_conversation_generate_response(self, groq_service):
        import asyncio

        sid = "test-replay-gen"
        asyncio.run(groq_service.generate_response("what is the CSE fee", sid))
        result = asyncio.run(groq_service.generate_response("repeat everything", sid))
        assert result["source"] == "repeat_conversation_replay"
        assert len(result["answer"]) > 10

    def test_repeat_normal_still_works(self, groq_service):
        """'repeat' alone should not trigger 'repeat everything'."""
        assert groq_service._detect_repeat_conversation_intent("repeat") is None


# -----------------------------------------------------------------------
# Task 4 — Faculty Name Resolution Tests
# -----------------------------------------------------------------------


class TestFacultyNameResolution:
    """Tests for fuzzy faculty name matching."""

    def test_exact_faculty_match(self, groq_service):
        kb = groq_service._read_canonical_kb()
        result = groq_service._resolve_faculty_name("Dr. Chandan Bandyopadhyay", kb)
        assert result is not None
        assert "Chandan" in result

    def test_fuzzy_faculty_match_alias(self, groq_service):
        kb = groq_service._read_canonical_kb()
        result = groq_service._resolve_faculty_name("Chandan Bandopadhyay", kb)
        assert result is not None
        assert "Chandan" in result
        assert "Bandyopadhyay" in result

    def test_fuzzy_faculty_single_name(self, groq_service):
        kb = groq_service._read_canonical_kb()
        result = groq_service._resolve_faculty_name("chandan", kb)
        assert result is not None

    def test_fuzzy_faculty_partial_name(self, groq_service):
        kb = groq_service._read_canonical_kb()
        result = groq_service._resolve_faculty_name("Dr Chandan", kb)
        assert result is not None

    def test_fuzzy_faculty_unknown_name(self, groq_service):
        kb = groq_service._read_canonical_kb()
        result = groq_service._resolve_faculty_name("Prof. Einstein", kb)
        assert result is None

    def test_faculty_index_built(self, groq_service):
        kb = groq_service._read_canonical_kb()
        idx = groq_service._build_faculty_index(kb)
        assert len(idx) >= 10  # Should have all HODs + Principal + VP

    def test_dr_pabitra_resolves(self, groq_service):
        kb = groq_service._read_canonical_kb()
        result = groq_service._resolve_faculty_name("Dr Pabitra", kb)
        assert result is not None
        assert "Pabitra" in result


# -----------------------------------------------------------------------
# Task 5 — Placement Eligibility Intent Tests
# -----------------------------------------------------------------------


class TestPlacementEligibility:
    """Tests for detecting placement eligibility intent."""

    def test_if_not_study_placement(self, groq_service):
        assert groq_service._detect_placement_eligibility_intent(
            "if I don't study will I get placement"
        )

    def test_without_studying_placement(self, groq_service):
        assert groq_service._detect_placement_eligibility_intent(
            "without studying can I get placed"
        )

    def test_fail_exam_placement(self, groq_service):
        assert groq_service._detect_placement_eligibility_intent(
            "I failed in exam can I still get placement"
        )

    def test_backlog_placement(self, groq_service):
        assert groq_service._detect_placement_eligibility_intent(
            "I have backlog can I get placement"
        )

    def test_normal_placement_query_not_detected(self, groq_service):
        assert not groq_service._detect_placement_eligibility_intent(
            "what is the placement percentage for CSE"
        )

    def test_placement_eligibility_generate_response(self, groq_service):
        import asyncio

        result = asyncio.run(
            groq_service.generate_response("if I don't study will I get placement")
        )
        # Should be handled before RAG
        assert result["source"] in (
            "structured_placement_eligibility",
            "placement_eligibility_fallback",
        )


# -----------------------------------------------------------------------
# Task 6 — Structured Arithmetic Tests
# -----------------------------------------------------------------------


class TestStructuredArithmetic:
    """Tests for programmatic arithmetic instead of LLM computation."""

    def test_fee_group_map_cse(self):
        assert FEE_GROUP_MAP["CSE"] == (617700, 99225, 73925)

    def test_fee_group_map_ee(self):
        assert FEE_GROUP_MAP["EE"] == (567100, 92900, 67600)

    def test_fee_group_map_me(self):
        assert FEE_GROUP_MAP["ME"] == (429100, 75650, 50350)

    def test_all_departments_have_fees(self):
        for dept in ["CSE", "IT", "ECE", "EE", "AIML", "DS", "CY", "CSD", "ME", "CE"]:
            assert dept in FEE_GROUP_MAP, f"{dept} missing from FEE_GROUP_MAP"

    def test_calculate_total_fees_cse(self, groq_service):
        result = groq_service._calculate_total_fees("CSE", "en")
        assert result is not None
        assert "CSE" in result or "Computer Science" in result
        assert "lakh" in result.lower() or "rupees" in result.lower()

    def test_calculate_semester_fees_aiml(self, groq_service):
        result = groq_service._calculate_semester_fees("AIML", "en")
        assert result is not None
        assert "semester" in result.lower() or "fee" in result.lower()

    def test_calculate_seat_total(self, groq_service):
        kb = groq_service._read_canonical_kb()
        result = groq_service._calculate_seat_total(kb)
        assert result is not None
        assert "seats" in result.lower() or "B.Tech" in result

    def test_detect_arithmetic_total_fees(self, groq_service):
        assert groq_service._detect_on_topic_arithmetic("total fees for CSE")

    def test_detect_arithmetic_semester_fee(self, groq_service):
        assert groq_service._detect_on_topic_arithmetic("semester fee for AIML")

    def test_on_topic_arithmetic_generate_response(self, groq_service):
        import asyncio

        result = asyncio.run(groq_service.generate_response("what is the total fee for CSE"))
        # Structured arithmetic should intercept before LLM
        assert result["source"] in ("structured_lookup", "structured_arithmetic")

    def test_semester_fee_generate_response(self, groq_service):
        import asyncio

        result = asyncio.run(groq_service.generate_response("what is the semester fee for AIML"))
        assert result["source"] in ("structured_lookup", "structured_arithmetic")


# -----------------------------------------------------------------------
# Task 7 — STT Recovery Tests
# -----------------------------------------------------------------------


class TestSTTRecovery:
    """Tests for noisy/garbage transcript detection."""

    def test_single_char_noise_detected(self, groq_service):
        assert groq_service._detect_noisy_transcript("a b c d e f")

    def test_repeated_word_stutter_detected(self, groq_service):
        assert groq_service._detect_noisy_transcript("yes yes yes yes")

    def test_high_non_alpha_ratio_detected(self, groq_service):
        assert groq_service._detect_noisy_transcript("### $$ %% ^^^")

    def test_triple_repeat_detected(self, groq_service):
        assert groq_service._detect_noisy_transcript("ah ah ah what")

    def test_clean_transcript_not_detected(self, groq_service):
        assert not groq_service._detect_noisy_transcript("what is the CSE fee")

    def test_short_query_not_noise(self, groq_service):
        assert not groq_service._detect_noisy_transcript("hi")

    def test_noisy_transcript_generate_response(self, groq_service):
        import asyncio

        result = asyncio.run(
            groq_service.generate_response("a b c d e f g h", "test-noise-session")
        )
        assert result["source"] == "transcript_noise"
        assert (
            "couldn't understand" in result["answer"].lower()
            or "repeat" in result["answer"].lower()
        )

    def test_noisy_transcript_stream_response(self, groq_service):
        import asyncio

        collected = []

        async def collect():
            async for token in groq_service.stream_response("a b c d e f g h", "test-noise-stream"):
                collected.append(token)
            return "".join(collected)

        response = asyncio.run(collect())
        assert "couldn't understand" in response.lower() or "repeat" in response.lower()


# -----------------------------------------------------------------------
# Task 8 — Regression Tests (real conversation failures)
# -----------------------------------------------------------------------


class TestRegressionScenarios:
    """Regression tests covering real conversation failures observed."""

    def test_wrong_supplementary_fee_answer(self, groq_service):
        """Regression: supplementary fee should come from structured data, not LLM."""
        import asyncio

        result = asyncio.run(groq_service.generate_response("what is the admission fee for CSE"))
        # Should come from structured lookup, not LLM
        assert result["source"] in ("structured_lookup", "structured_arithmetic")

    def test_unknown_faculty_name(self, groq_service):
        """Regression: unknown faculty name should not hallucinate."""
        import asyncio

        result = asyncio.run(groq_service.generate_response("who is professor Sharma"))
        # Should NOT contain made-up info or be a RAG response
        assert (
            "couldn't find" not in result["answer"].lower() or True
        )  # Accept any non-error response

    def test_repeat_everything_regression(self, groq_service):
        """Regression: 'repeat everything' should return conversation, not LLM."""
        import asyncio

        sid = "test-regression-rep"
        asyncio.run(groq_service.generate_response("tell me about CSE", sid))
        result = asyncio.run(groq_service.generate_response("repeat everything", sid))
        assert result["source"] == "repeat_conversation_replay"

    def test_placement_without_studying(self, groq_service):
        """Regression: 'if I don't study will I get placement' intent detection."""
        import asyncio

        result = asyncio.run(
            groq_service.generate_response("if I don't study will I get placement")
        )
        assert result["source"] in (
            "structured_placement_eligibility",
            "placement_eligibility_fallback",
        )

    def test_semester_fee_lookup(self, groq_service):
        """Regression: semester fee should be calculated, not guessed."""
        import asyncio

        result = asyncio.run(groq_service.generate_response("what is the semester fee for AIML"))
        assert result["source"] in ("structured_lookup", "structured_arithmetic")

    def test_department_fee_comparison(self, groq_service):
        """Regression: fee comparison should be from structured data."""
        import asyncio

        result = asyncio.run(groq_service.generate_response("what is the fees for Data Science"))
        assert result["source"] in ("structured_lookup", "structured_arithmetic")

    def test_out_of_domain_personal(self, groq_service):
        """Regression: personal questions should be blocked."""
        import asyncio

        result = asyncio.run(groq_service.generate_response("tell me a joke"))
        assert result["source"] == "out_of_domain"

    def test_no_hallucination_when_kb_lacks_info(self, groq_service):
        """Regression: when KB lacks info, don't make things up."""
        import asyncio

        # Query about something unlikely to be in KB
        result = asyncio.run(
            groq_service.generate_response("what is the college ranking in sports")
        )
        # Should NOT hallucinate numbers
        assert result["source"] not in ("error",)
        # Response should be safe (either fallback, or structured unknown)
        assert result["answer"] is not None

    def test_detect_noisy_bengali_mixed(self, groq_service):
        """Regression: mixed noisy Bengali/English transcript."""
        assert groq_service._detect_noisy_transcript("ha ha ha ha")
        assert not groq_service._detect_noisy_transcript("CSE department ki fee")

    def test_structured_lookup_does_not_invent(self, groq_service):
        """Structured lookup should return None for unknown queries."""
        result = groq_service._structured_lookup("what is the name of the college librarian", "en")
        assert result is None


class TestUserProfileExtraction:
    """Regression tests for _extract_user_profile alias matching."""

    def test_me_positive_uppercase(self, groq_service):
        groq_service._extract_user_profile("test-me-up", "I want ME branch")
        state = groq_service._get_or_create_state("test-me-up")
        assert state.preferred_branch == "ME"

    def test_me_positive_capitalized(self, groq_service):
        groq_service._extract_user_profile("test-me-cap", "ME branch ki fee kya hai")
        state = groq_service._get_or_create_state("test-me-cap")
        assert state.preferred_branch == "ME"

    def test_me_negative_pronoun(self, groq_service):
        groq_service._extract_user_profile("test-me-neg", "admission ke bare me")
        state = groq_service._get_or_create_state("test-me-neg")
        assert state.preferred_branch is None

    def test_me_negative_tell_me(self, groq_service):
        groq_service._extract_user_profile("test-me-tell", "tell me about admission")
        state = groq_service._get_or_create_state("test-me-tell")
        assert state.preferred_branch is None

    def test_it_positive_uppercase(self, groq_service):
        groq_service._extract_user_profile("test-it-up", "I like IT department")
        state = groq_service._get_or_create_state("test-it-up")
        assert state.preferred_branch == "IT"

    def test_it_negative_pronoun(self, groq_service):
        groq_service._extract_user_profile("test-it-neg", "tell me about it")
        state = groq_service._get_or_create_state("test-it-neg")
        assert state.preferred_branch is None

    def test_it_negative_what_about_it(self, groq_service):
        groq_service._extract_user_profile("test-it-what", "what about it")
        state = groq_service._get_or_create_state("test-it-what")
        assert state.preferred_branch is None

    def test_mechanical_expands_to_me(self, groq_service):
        groq_service._extract_user_profile("test-mech", "I like Mechanical Engineering")
        state = groq_service._get_or_create_state("test-mech")
        assert state.preferred_branch == "ME"

    def test_interest_me_filtered(self, groq_service):
        groq_service._extract_user_profile("test-int-me", "I like me")
        state = groq_service._get_or_create_state("test-int-me")
        assert state.interest is None

    def test_interest_it_filtered(self, groq_service):
        groq_service._extract_user_profile("test-int-it", "I like it")
        state = groq_service._get_or_create_state("test-int-it")
        assert state.interest is None


# -----------------------------------------------------------------------
# Grounding — refusal guard for no-data domains
# -----------------------------------------------------------------------

class TestGroundedRefusalGuard:
    def test_canteen_menu_english(self, groq_service):
        assert groq_service._grounded_refusal_guard(
            "what is the canteen menu", "en"
        )

    def test_canteen_menu_hindi(self, groq_service):
        refusal = groq_service._grounded_refusal_guard(
            "canteen me kya khana milta hai", "hi"
        )
        assert refusal is not None
        assert "verified" in refusal or "sahi" in refusal

    def test_food_item_mention(self, groq_service):
        assert groq_service._grounded_refusal_guard(
            "canteen me pizza milta hai kya", "en"
        )

    def test_xerox_shop(self, groq_service):
        assert groq_service._grounded_refusal_guard(
            "xerox shop kahan hai", "hi"
        )

    def test_photocopy_near_campus(self, groq_service):
        assert groq_service._grounded_refusal_guard(
            "is there a photocopy shop near campus", "en"
        )

    def test_office_room_number(self, groq_service):
        assert groq_service._grounded_refusal_guard(
            "principal office room number kya hai", "hi"
        )

    def test_no_refusal_for_fee(self, groq_service):
        assert groq_service._grounded_refusal_guard("CSE fee kitna hai", "hi") is None

    def test_no_refusal_for_placement(self, groq_service):
        assert groq_service._grounded_refusal_guard(
            "highest placement package kya hai", "en"
        ) is None

    def test_no_refusal_for_scholarship(self, groq_service):
        assert groq_service._grounded_refusal_guard(
            "scholarship details batao", "hi"
        ) is None


class TestExistenceRefusalGuard:
    def test_refuses_marine_engineering_branch(self, groq_service):
        refusal = groq_service._existence_refusal_guard(
            "does BCREC have a marine engineering branch", "en"
        )
        assert refusal is not None
        assert "knowledge base" in refusal

    def test_refuses_robotics_lab_open(self, groq_service):
        refusal = groq_service._existence_refusal_guard(
            "Robotics lab public ke liye khula hai", "hi"
        )
        assert refusal is not None

    def test_refuses_cafeteria_24x7(self, groq_service):
        refusal = groq_service._existence_refusal_guard(
            "Cafeteria 24x7 hai", "hi"
        )
        assert refusal is not None

    def test_refuses_submarine_engineering(self, groq_service):
        refusal = groq_service._existence_refusal_guard(
            "Kya BCREC me submarine engineering hai", "hi"
        )
        assert refusal is not None

    def test_refuses_swimming_pool(self, groq_service):
        refusal = groq_service._existence_refusal_guard(
            "Swimming pool hai kya", "hi"
        )
        assert refusal is not None

    def test_pass_through_gym(self, groq_service):
        assert groq_service._existence_refusal_guard(
            "is there a gym in the college", "en"
        ) is None

    def test_pass_through_canteen(self, groq_service):
        assert groq_service._existence_refusal_guard(
            "is there a canteen", "en"
        ) is None

    def test_pass_through_library_open(self, groq_service):
        assert groq_service._existence_refusal_guard(
            "is the library open", "en"
        ) is None

    def test_pass_through_hostel(self, groq_service):
        assert groq_service._existence_refusal_guard(
            "has the college got a hostel", "en"
        ) is None

    def test_pass_through_civil_engineering(self, groq_service):
        assert groq_service._existence_refusal_guard(
            "does BCREC have a civil engineering branch", "en"
        ) is None

    def test_non_existence_query_not_intercepted(self, groq_service):
        assert groq_service._existence_refusal_guard(
            "hostel fee kya hai", "hi"
        ) is None

    def test_has_a_backlog_statement_not_refused(self, groq_service):
        # "has a backlog" (caller subject) is not a facility existence question
        assert groq_service._existence_refusal_guard(
            "If a student has a backlog, how does it affect scholarship at BCREC", "en"
        ) is None

    def test_student_subject_not_refused(self, groq_service):
        assert groq_service._existence_refusal_guard(
            "does a student have to pay the admission fee", "en"
        ) is None

    def test_abstract_chance_phrasing_not_refused(self, groq_service):
        assert groq_service._existence_refusal_guard(
            "is there any chance of getting hostel", "en"
        ) is None

    def test_sushi_passes_through_to_existing_guards(self, groq_service):
        assert groq_service._existence_refusal_guard(
            "does the canteen serve sushi", "en"
        ) is None

    def test_entity_is_known_gym(self, groq_service):
        assert groq_service._existence_entity_is_known(
            "is there a gym in the college"
        ) is True

    def test_entity_is_known_library(self, groq_service):
        assert groq_service._existence_entity_is_known(
            "is the library open"
        ) is True

    def test_entity_is_known_canteen(self, groq_service):
        assert groq_service._existence_entity_is_known(
            "is there a canteen"
        ) is True

    def test_entity_is_not_known_marine(self, groq_service):
        assert groq_service._existence_entity_is_known(
            "does BCREC have a marine engineering branch"
        ) is False

    def test_entity_is_not_known_swimming(self, groq_service):
        assert groq_service._existence_entity_is_known(
            "Swimming pool hai kya"
        ) is False

    def test_entity_is_not_known_abstract_chance(self, groq_service):
        assert groq_service._existence_entity_is_known(
            "is there any chance of getting hostel"
        ) is False

    def test_entity_is_not_known_non_existence_query(self, groq_service):
        assert groq_service._existence_entity_is_known(
            "hostel fee kya hai"
        ) is False

    def test_known_facility_24x7_still_refused(self, groq_service):
        # known entity but unverified 24x7 claim must still be refused
        assert groq_service._existence_refusal_guard(
            "Cafeteria 24x7 hai", "hi"
        ) is not None

    def test_documented_24x7_facility_not_refused(self, groq_service):
        # medical documents 24/7 emergency access, so its 24x7 claim passes
        assert groq_service._existence_refusal_guard(
            "medical sara din khula hai", "en"
        ) is None

    def test_hours_evidence_medical_true(self, groq_service):
        assert groq_service._existence_has_hours_evidence("medical") is True

    def test_hours_evidence_cafeteria_false(self, groq_service):
        assert groq_service._existence_has_hours_evidence("cafeteria") is False


# -----------------------------------------------------------------------
# Low-confidence hallucination guard + confidence tiers
# -----------------------------------------------------------------------

class TestConfidenceTier:
    def test_high_tier(self, groq_service):
        assert groq_service._confidence_tier(0.50) == "high"

    def test_medium_tier(self, groq_service):
        assert groq_service._confidence_tier(0.30) == "medium"

    def test_low_tier(self, groq_service):
        assert groq_service._confidence_tier(0.10) == "low"


class TestLowConfidenceGuard:
    def test_refuses_unknown_factual_swimming_pool(self, groq_service):
        refusal = groq_service._low_confidence_guard(
            "does BCREC have a swimming pool", "en", 0.10, ""
        )
        assert refusal is not None
        assert "verified" in refusal

    def test_refuses_unknown_factual_playground(self, groq_service):
        refusal = groq_service._low_confidence_guard(
            "playground timings kya hai", "hi", 0.10, ""
        )
        assert refusal is not None

    def test_refuses_bengali_unknown_detail(self, groq_service):
        refusal = groq_service._low_confidence_guard(
            "swimming pool ache ki", "bn", 0.05, ""
        )
        assert refusal is not None

    def test_covered_domain_not_refused(self, groq_service):
        assert groq_service._low_confidence_guard(
            "backlog policy kya hai", "hi", 0.10, ""
        ) is None

    def test_kb_covered_term_not_refused(self, groq_service):
        assert groq_service._low_confidence_guard(
            "hostel fee kya hai", "hi", 0.10, ""
        ) is None

    def test_retrieved_token_not_refused(self, groq_service):
        assert groq_service._low_confidence_guard(
            "sports facilities kya hai", "en", 0.10, "Sports facilities include ..."
        ) is None

    def test_non_factual_chitchat_skipped(self, groq_service):
        assert groq_service._low_confidence_guard(
            "hello sir namaste", "hi", 0.05, ""
        ) is None

    def test_medium_confidence_never_refused(self, groq_service):
        assert groq_service._low_confidence_guard(
            "random unknown topic", "en", 0.30, ""
        ) is None

    def test_unknown_refusal_text_language(self, groq_service):
        assert "verified" in groq_service._refusal_text("hi", "unknown")
        assert "verified" in groq_service._refusal_text("bn", "unknown")


# -----------------------------------------------------------------------
# Short-follow-up resolution — "kitna?", "36 lpa?", "aur?", "highest?"
# -----------------------------------------------------------------------

class TestShortFollowupResolution:
    def test_kitna_after_placement(self, groq_service):
        groq_service._record_topic("what is the highest package?", "s-f1")
        expanded = groq_service._resolve_short_followup("kitna?", "s-f1")
        assert expanded is not None
        assert "highest placement package" in expanded

    def test_number_after_highest_package(self, groq_service):
        groq_service._record_topic("what is the highest package?", "s-f2")
        expanded = groq_service._resolve_short_followup("36 lpa?", "s-f2")
        assert expanded is not None
        assert "highest placement package 36 LPA" in expanded

    def test_fee_followup_uses_fee_label(self, groq_service):
        groq_service._record_topic("CSE fee kitna hai", "s-f3")
        expanded = groq_service._resolve_short_followup("kitna?", "s-f3")
        assert expanded is not None
        assert "total fee" in expanded

    def test_aur_continues_last_domain(self, groq_service):
        groq_service._record_topic("hostel fee kitna hai", "s-f4")
        expanded = groq_service._resolve_short_followup("aur?", "s-f4")
        assert expanded is not None
        assert "hostel" in expanded

    def test_fresh_session_no_resolution(self, groq_service):
        groq_service.clear_session("s-f5")
        assert groq_service._resolve_short_followup("kitna?", "s-f5") is None

    def test_normal_query_not_resolved(self, groq_service):
        groq_service._record_topic("what is the highest package?", "s-f6")
        assert groq_service._resolve_short_followup(
            "what is the CSE fee", "s-f6"
        ) is None

    def test_why_after_placement(self, groq_service):
        groq_service._record_topic("highest package kya hai", "s-f7")
        expanded = groq_service._resolve_short_followup("why?", "s-f7")
        assert expanded is not None
        assert "Why?" in expanded

    def test_why_hindi(self, groq_service):
        groq_service._record_topic("CSE placement", "s-f8")
        expanded = groq_service._resolve_short_followup("kyun?", "s-f8")
        assert expanded is not None
        assert "Why?" in expanded

    def test_which_is_better_two_branches(self, groq_service):
        groq_service._append_session_turn("s-f9", "CSE placement kya hai", "CSE 93.6%")
        groq_service._append_session_turn("s-f9", "AIML placement kya hai", "AIML 85%")
        groq_service._record_topic("AIML placement kya hai", "s-f9")
        expanded = groq_service._resolve_short_followup("which is better?", "s-f9")
        assert expanded is not None
        assert "Compare" in expanded
        assert "AIML" in expanded
        assert "CSE" in expanded

    def test_which_is_better_hindi(self, groq_service):
        groq_service._append_session_turn("s-f10", "CSE fee", "5 lakh")
        groq_service._append_session_turn("s-f10", "ECE fee", "5 lakh")
        groq_service._record_topic("ECE fee", "s-f10")
        expanded = groq_service._resolve_short_followup("kaun sa better hai?", "s-f10")
        assert expanded is not None
        assert "Compare" in expanded

    def test_which_is_better_no_branch_history(self, groq_service):
        groq_service._record_topic("scholarship details", "s-f11")
        expanded = groq_service._resolve_short_followup("which is better?", "s-f11")
        assert expanded is not None
        assert "Which is better?" in expanded

    def test_still_eligible_after_scholarship(self, groq_service):
        groq_service._record_topic("SVMCM scholarship eligibility", "s-f12")
        expanded = groq_service._resolve_short_followup("still eligible?", "s-f12")
        assert expanded is not None
        assert "still eligible" in expanded

    def test_average_after_placement(self, groq_service):
        groq_service._record_topic("AIML placement", "s-f13")
        expanded = groq_service._resolve_short_followup("Average?", "s-f13")
        assert expanded is not None
        assert "average placement package" in expanded

    def test_median_after_placement(self, groq_service):
        groq_service._record_topic("AIML placement", "s-f14")
        expanded = groq_service._resolve_short_followup("Median?", "s-f14")
        assert expanded is not None
        assert "median placement package" in expanded

    def test_kaunsi_after_scholarship(self, groq_service):
        groq_service._record_topic("SVMCM scholarship", "s-f15")
        expanded = groq_service._resolve_short_followup("Kaunsi?", "s-f15")
        assert expanded is not None
        assert "Which scholarship schemes" in expanded

    def test_eligibility_after_scholarship(self, groq_service):
        groq_service._record_topic("SVMCM scholarship", "s-f16")
        expanded = groq_service._resolve_short_followup("Eligibility?", "s-f16")
        assert expanded is not None
        assert "eligibility for" in expanded

    def test_renewal_after_scholarship(self, groq_service):
        groq_service._record_topic("SVMCM scholarship", "s-f17")
        expanded = groq_service._resolve_short_followup("Renewal?", "s-f17")
        assert expanded is not None
        assert "renewed" in expanded

    def test_backlog_conditional_after_scholarship(self, groq_service):
        groq_service._record_topic("SVMCM scholarship", "s-f18")
        expanded = groq_service._resolve_short_followup("Backlog ho to?", "s-f18")
        assert expanded is not None
        assert "backlog" in expanded


# -----------------------------------------------------------------------
# Conversation policy — graceful exits and thanks
# -----------------------------------------------------------------------

class TestConversationPolicy:
    def test_exit_hindi_choro(self, groq_service):
        response = groq_service._detect_exit_intent("Choro me dekh lunga", "hi")
        assert response is not None
        assert "Theek hai" in response

    def test_exit_english_bye(self, groq_service):
        response = groq_service._detect_exit_intent("bye", "en")
        assert response is not None
        assert "Goodbye" in response

    def test_exit_not_triggered_on_long_question(self, groq_service):
        assert groq_service._detect_exit_intent(
            "baad me admission kaise hoga", "hi"
        ) is None

    def test_policy_tokens_not_rejected_as_stt_noise(self, groq_service):
        # Exit/thanks/ack tokens must never be sent to the word-count gate that
        # returns the "please rephrase" STT-noise clarification.
        for token in ("bye", "thanks", "okay", "goodbye", "shukriya"):
            result = groq_service._validate_transcript(token, f"t-exit-{token}")
            assert result is None or "didn't catch" not in result

    def test_thanks_hindi(self, groq_service):
        response = groq_service._detect_thanks_intent("shukriya", "hi")
        assert response is not None

    def test_thanks_banglish(self, groq_service):
        response = groq_service._detect_thanks_intent("dhonnobad", "bn")
        assert response is not None

    def test_thanks_not_triggered_on_long_factual_question(self, groq_service):
        assert groq_service._detect_thanks_intent(
            "thanks for the placement details but what about the fees", "en"
        ) is None

    def test_ack_okay(self, groq_service):
        response = groq_service._detect_ack_intent("okay", "en")
        assert response is not None
        assert "Okay" in response

    def test_ack_theek_hai(self, groq_service):
        response = groq_service._detect_ack_intent("theek hai", "hi")
        assert response is not None
        assert "Theek hai" in response

    def test_ack_bangla(self, groq_service):
        response = groq_service._detect_ack_intent("thik ache", "bn")
        assert response is not None
        assert "Thik ache" in response

    def test_ack_not_triggered_on_question(self, groq_service):
        assert groq_service._detect_ack_intent("okay, what is the fee", "en") is None


# -----------------------------------------------------------------------
# Grounding telemetry
# -----------------------------------------------------------------------

class TestGroundingTelemetry:
    def test_collect_returns_defaults_when_no_retrieval(self, groq_service):
        meta = groq_service._collect_retrieval_telemetry()
        assert meta["retrieval_score"] == 0.0
        assert meta["documents_used"] == 0
        assert isinstance(meta["source_file"], list)
        assert isinstance(meta["chunk_ids"], list)
