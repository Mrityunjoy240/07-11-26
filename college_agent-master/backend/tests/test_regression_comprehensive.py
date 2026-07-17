"""
Comprehensive Regression Test Suite for BCREC College Agent

Covers ALL previously discovered bugs to prevent regression.
Each bug has at least one automated test.

Run: cd backend && python3 tests/test_regression_comprehensive.py
"""

import json
import os
import sys
import time

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load canonical facts
FACTS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'college_facts.json')
with open(FACTS_PATH) as f:
    FACTS = json.load(f)

# API endpoint
API_URL = "http://localhost:8000/qa/query"


def make_query(query, session_id):
    """Make a query to the API and return the response."""
    import urllib.request
    import urllib.error
    
    data = json.dumps({"message": query, "session_id": session_id}).encode('utf-8')
    req = urllib.request.Request(API_URL, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {"error": str(e), "source": "error"}


def setup_session(session_id, language):
    """Set up a session with the specified language."""
    make_query("hello", session_id)
    make_query(language, session_id)


# ============================================================
# TEST CATEGORY 1: Bengali Greeting Aliases (BUG 1)
# ============================================================

def test_bengali_greeting_aliases():
    """Test that Bengali greeting aliases are recognized."""
    bugs = []
    
    greetings = ["nomoskar", "nomoshkar", "নমস্কার", "hello"]
    for greeting in greetings:
        session_id = f"test_greeting_{greeting[:5]}"
        result = make_query(greeting, session_id)
        source = result.get("source", "")
        
        # Should NOT be rejected as transcript_clarification
        if source == "transcript_clarification":
            bugs.append(f"FAIL: '{greeting}' rejected as transcript_clarification")
        elif "greeting" in source or "language" in source:
            pass  # Expected
        else:
            # Check if response is a valid greeting
            answer = result.get("answer", "")
            if "BCREC" in answer or "admission" in answer.lower():
                pass  # Valid response
            else:
                bugs.append(f"FAIL: '{greeting}' gave unexpected response: {answer[:50]}")
    
    return bugs


# ============================================================
# TEST CATEGORY 2: Farewell Detection (BUG 5)
# ============================================================

def test_farewell_detection():
    """Test that farewells are properly handled."""
    bugs = []
    
    session_id = "test_farewell"
    setup_session(session_id, "bengali")
    
    farewells = ["bye", "goodbye", "thank you", "thanks", "ধন্যবাদ"]
    for farewell in farewells:
        result = make_query(farewell, session_id)
        source = result.get("source", "")
        
        # Should NOT be rejected as transcript_clarification
        if source == "transcript_clarification":
            bugs.append(f"FAIL: '{farewell}' rejected as transcript_clarification")
        elif "farewell" in source or "thank" in result.get("answer", "").lower():
            pass  # Expected
        else:
            # Check if response acknowledges the farewell
            answer = result.get("answer", "")
            if "ধন্যবাদ" in answer or "thank" in answer.lower() or "help" in answer.lower():
                pass  # Valid response
            else:
                bugs.append(f"FAIL: '{farewell}' gave unexpected response: {answer[:50]}")
    
    return bugs


# ============================================================
# TEST CATEGORY 3: Typo Tolerance (BUG 2, 3, 4)
# ============================================================

def test_typo_tolerance():
    """Test that common typos are properly handled."""
    bugs = []
    
    session_id = "test_typo"
    setup_session(session_id, "bengali")
    
    typos = {
        "admisson": "admission",
        "scholership": "scholarship",
        "plcement": "placement",
        "hostle": "hostel",
        "cutofft": "cutoff",
    }
    
    for typo, expected in typos.items():
        result = make_query(typo, session_id)
        source = result.get("source", "")
        answer = result.get("answer", "")
        
        # Should NOT be rejected as transcript_clarification
        if source == "transcript_clarification":
            bugs.append(f"FAIL: '{typo}' rejected as transcript_clarification")
        elif expected.lower() in answer.lower():
            pass  # Expected - answer contains the expected keyword
        elif "ask" in answer.lower() or "question" in answer.lower():
            pass  # Valid - asking for clarification
        else:
            # Check if response is at least relevant
            if any(word in answer.lower() for word in ["fee", "placement", "hostel", "cutoff", "scholarship", "admission"]):
                pass  # Valid - response is about the topic
            else:
                bugs.append(f"FAIL: '{typo}' gave unexpected response: {answer[:50]}")
    
    return bugs


# ============================================================
# TEST CATEGORY 4: Profile Persistence
# ============================================================

def test_profile_persistence():
    """Test that profile information persists across turns."""
    bugs = []
    
    session_id = "test_profile"
    setup_session(session_id, "bengali")
    
    # Set rank
    result1 = make_query("amar rank 50000", session_id)
    answer1 = result1.get("answer", "")
    
    # Check if rank was acknowledged
    if "50000" not in answer1 and "50,000" not in answer1:
        bugs.append(f"FAIL: Rank not acknowledged in response: {answer1[:50]}")
    
    # Set PCM
    result2 = make_query("pcm 76%", session_id)
    answer2 = result2.get("answer", "")
    
    # Check if PCM was acknowledged
    if "76" not in answer2:
        bugs.append(f"FAIL: PCM not acknowledged in response: {answer2[:50]}")
    
    # Ask about profile
    result3 = make_query("tumi ki mone rekho?", session_id)
    answer3 = result3.get("answer", "")
    
    # Check if profile is remembered
    if "50000" not in answer3 and "50,000" not in answer3:
        bugs.append(f"FAIL: Profile not remembered - rank not in response: {answer3[:50]}")
    
    if "76" not in answer3:
        bugs.append(f"FAIL: Profile not remembered - PCM not in response: {answer3[:50]}")
    
    return bugs


# ============================================================
# TEST CATEGORY 5: Numeric Extraction (Percentages) (BUG 7)
# ============================================================

def test_numeric_extraction():
    """Test that numeric values are correctly extracted."""
    bugs = []
    
    session_id = "test_numeric"
    setup_session(session_id, "bengali")
    
    # Test percentage extraction
    result = make_query("pcm 76%", session_id)
    answer = result.get("answer", "")
    
    # Check if percentage is correctly extracted
    if "76" not in answer:
        bugs.append(f"FAIL: PCM percentage not extracted correctly: {answer[:50]}")
    
    # Check if percentage is not mangled
    if "6.0" in answer or "6,0" in answer:
        bugs.append(f"FAIL: PCM percentage mangled to 6.0%: {answer[:50]}")
    
    # Test rank extraction
    result2 = make_query("amar rank 50000", session_id)
    answer2 = result2.get("answer", "")
    
    if "50000" not in answer2 and "50,000" not in answer2:
        bugs.append(f"FAIL: Rank not extracted correctly: {answer2[:50]}")
    
    return bugs


# ============================================================
# TEST CATEGORY 6: Chain-of-Thought Suppression (BUG 6)
# ============================================================

def test_cot_suppression():
    """Test that chain-of-thought reasoning is suppressed."""
    bugs = []
    
    session_id = "test_cot"
    setup_session(session_id, "english")
    
    # Test with a query that might trigger CoT
    result = make_query("AI interest", session_id)
    answer = result.get("answer", "")
    
    # Check for CoT patterns
    cot_patterns = [
        "Okay, the user",
        "Let me think",
        "I need to",
        "First, I'll",
        "The user is asking",
        "My reasoning is",
        "I analyzed",
    ]
    
    for pattern in cot_patterns:
        if pattern.lower() in answer.lower():
            bugs.append(f"FAIL: CoT leakage detected: '{pattern}' found in response")
            break
    
    return bugs


# ============================================================
# TEST CATEGORY 7: Language Consistency
# ============================================================

def test_language_consistency():
    """Test that responses are in the correct language."""
    bugs = []
    
    # Test Bengali session
    session_id = "test_lang_bn"
    setup_session(session_id, "bengali")
    
    result = make_query("CSE er fee koto?", session_id)
    answer = result.get("answer", "")
    
    # Check if response contains Bengali words
    bengali_words = ["এর", "কত", "ফি", "টাকা", "হাজার", "লাখ"]
    has_bengali = any(word in answer for word in bengali_words)
    
    if not has_bengali:
        bugs.append(f"FAIL: Bengali session returned non-Bengali response: {answer[:50]}")
    
    # Test Hindi session
    session_id = "test_lang_hi"
    setup_session(session_id, "hindi")
    
    result = make_query("CSE ki fee hai?", session_id)
    answer = result.get("answer", "")
    
    # Check if response contains Hindi words
    hindi_words = ["का", "है", "फीस", "रुपये", "लाख"]
    has_hindi = any(word in answer for word in hindi_words)
    
    if not has_hindi:
        bugs.append(f"FAIL: Hindi session returned non-Hindi response: {answer[:50]}")
    
    return bugs


# ============================================================
# TEST CATEGORY 8: Fact Verification
# ============================================================

def test_fact_verification():
    """Test that facts match canonical college_facts.json."""
    bugs = []
    
    session_id = "test_facts"
    setup_session(session_id, "bengali")
    
    # Test fee
    result = make_query("CSE er total fee koto?", session_id)
    answer = result.get("answer", "")
    
    # CSE fee should be 6,17,700
    if "6,17,700" not in answer and "617700" not in answer:
        bugs.append(f"FAIL: CSE fee incorrect: {answer[:50]}")
    
    # Test cutoff
    session_id2 = "test_facts2"
    setup_session(session_id2, "bengali")
    result2 = make_query("CSE cutoff 2025 koto?", session_id2)
    answer2 = result2.get("answer", "")
    
    # CSE cutoff 2025 should be 67761
    if "67761" not in answer2:
        bugs.append(f"FAIL: CSE cutoff 2025 incorrect: {answer2[:50]}")
    
    # Test principal
    session_id3 = "test_facts3"
    setup_session(session_id3, "bengali")
    result3 = make_query("principal ke?", session_id3)
    answer3 = result3.get("answer", "")
    
    if "Dr. Sanjay S. Pawar" not in answer3:
        bugs.append(f"FAIL: Principal name incorrect: {answer3[:50]}")
    
    return bugs


# ============================================================
# TEST CATEGORY 9: Language Switching
# ============================================================

def test_language_switching():
    """Test that language switching works correctly."""
    bugs = []
    
    session_id = "test_switch"
    setup_session(session_id, "bengali")
    
    # Bengali query
    result1 = make_query("CSE er fee koto?", session_id)
    answer1 = result1.get("answer", "")
    
    if "এর" not in answer1 and "কত" not in answer1:
        bugs.append(f"FAIL: Bengali response expected: {answer1[:50]}")
    
    # Switch to Hindi
    result2 = make_query("in hindi", session_id)
    answer2 = result2.get("answer", "")
    
    if "का" not in answer2 and "है" not in answer2:
        bugs.append(f"FAIL: Hindi response expected after switch: {answer2[:50]}")
    
    # Hindi query
    result3 = make_query("placement kaisa hai?", session_id)
    answer3 = result3.get("answer", "")
    
    if "placement" not in answer3.lower() and "प्लेसमेंट" not in answer3:
        bugs.append(f"FAIL: Hindi response expected: {answer3[:50]}")
    
    return bugs


# ============================================================
# TEST CATEGORY 10: Out-of-Scope Handling
# ============================================================

def test_out_of_scope():
    """Test that out-of-scope queries are handled properly."""
    bugs = []
    
    session_id = "test_oos"
    setup_session(session_id, "bengali")
    
    oos_queries = ["weather", "IPL", "politics", "Python programming"]
    for query in oos_queries:
        result = make_query(query, session_id)
        source = result.get("source", "")
        answer = result.get("answer", "")
        
        # Should be handled as out-of-domain or redirect to college
        if source == "out_of_domain" or "college" in answer.lower():
            pass  # Expected
        elif "BCREC" in answer or "admission" in answer.lower():
            pass  # Redirect to college
        else:
            bugs.append(f"FAIL: '{query}' not handled as out-of-scope: {answer[:50]}")
    
    return bugs


# ============================================================
# TEST CATEGORY: College Identity (DEMO BLOCKER)
# ============================================================

FORBIDDEN_NAMES = ["Bengal College", "Bengal Engineering", "Bengal Institute"]

def test_college_identity():
    """Test that all identity queries return correct facts from college_facts.json.
    NEVER allow 'Bengal College of Engineering and Technology' or similar."""
    bugs = []

    identity_queries = [
        # English
        ("What is the college full name?", "Dr. Bidhan Chandra Roy Engineering College"),
        ("Which college is this?", "Dr. B.C. Roy Engineering College"),
        ("Where is the college?", "Durgapur"),
        ("What is the address?", "Jemua Road"),
        ("Who is the principal?", "Dr. Sanjay S. Pawar"),
        ("What is the website?", "bcrec.ac.in"),
        ("What is the phone number?", "0343-2501353"),
        ("What is the email?", "info@bcrec.ac.in"),
        ("When was the college established?", "August 2000"),
        ("Which university is BCREC affiliated to?", "MAKAUT"),
        ("What is the NAAC grade?", "B+"),
        # Hindi (Devanagari script)
        ("मुझे पूछना था इस कॉलेज का पूरा नाम क्या है", "Dr. B.C. Roy"),
        ("college ka naam kya hai", "Dr. B.C. Roy"),
        ("पूरा नाम क्या है", "Dr. B.C. Roy"),
        # Bengali
        ("পুরো নাম কি", "Dr. B.C. Roy"),
    ]

    for query, expected_fact in identity_queries:
        session_id = f"test_identity_{hash(query) % 10000}"
        result = make_query(query, session_id)
        answer = result.get("answer", "")

        # Check forbidden college names
        for forbidden in FORBIDDEN_NAMES:
            if forbidden.lower() in answer.lower():
                bugs.append(f"FAIL: '{query}' contains forbidden name '{forbidden}': {answer[:80]}")

        # Check expected fact is present
        if expected_fact.lower() not in answer.lower():
            bugs.append(f"FAIL: '{query}' missing expected fact '{expected_fact}': {answer[:80]}")

    return bugs


# ============================================================
# TEST CATEGORY: Backlog Handler (Institutional Policy)
# ============================================================

def test_backlog_handler():
    """Test that backlog queries return structured policy responses, not LLM guesses."""
    bugs = []

    backlog_queries = [
        ("mera ek subject me backlog hai", "supplementary"),
        ("backlog kaise clear hoga", "MAKAUT"),
        ("I have a backlog in one subject", "supplementary"),
        ("arrear exam kab hoga", "notification"),
    ]

    for query, expected_keyword in backlog_queries:
        session_id = f"test_backlog_{hash(query) % 10000}"
        result = make_query(query, session_id)
        answer = result.get("answer", "")

        if expected_keyword.lower() not in answer.lower():
            bugs.append(f"FAIL: '{query}' missing '{expected_keyword}': {answer[:80]}")

        # Should NOT mention scholarship, WBJEE, or admission in backlog response
        for forbidden in ["scholarship", "WBJEE", "admission process"]:
            if forbidden.lower() in answer.lower():
                bugs.append(f"FAIL: '{query}' mentions '{forbidden}' in backlog response")

    return bugs


# ============================================================
# MAIN TEST RUNNER
# ============================================================

def run_all_tests():
    """Run all regression tests and generate report."""
    print("=" * 70)
    print("COMPREHENSIVE REGRESSION TEST SUITE")
    print("BCREC College Admission Assistant")
    print("=" * 70)
    print()
    
    test_categories = [
        ("Bengali Greeting Aliases (BUG 1)", test_bengali_greeting_aliases),
        ("Farewell Detection (BUG 5)", test_farewell_detection),
        ("Typo Tolerance (BUG 2, 3, 4)", test_typo_tolerance),
        ("Profile Persistence", test_profile_persistence),
        ("Numeric Extraction (BUG 7)", test_numeric_extraction),
        ("Chain-of-Thought Suppression (BUG 6)", test_cot_suppression),
        ("Language Consistency", test_language_consistency),
        ("Fact Verification", test_fact_verification),
        ("Language Switching", test_language_switching),
        ("Out-of-Scope Handling", test_out_of_scope),
        ("College Identity (DEMO BLOCKER)", test_college_identity),
        ("Backlog Handler (Policy)", test_backlog_handler),
    ]
    
    total_bugs = 0
    passed_categories = 0
    failed_categories = 0
    
    for category_name, test_func in test_categories:
        print(f"\n{category_name}")
        print("-" * 50)
        
        try:
            bugs = test_func()
            
            if not bugs:
                print("  ✓ PASS - No bugs found")
                passed_categories += 1
            else:
                print(f"  ✗ FAIL - {len(bugs)} bug(s) found:")
                for bug in bugs:
                    print(f"    - {bug}")
                total_bugs += len(bugs)
                failed_categories += 1
        except Exception as e:
            print(f"  ✗ ERROR - {str(e)}")
            failed_categories += 1
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total Categories: {len(test_categories)}")
    print(f"  Passed: {passed_categories}")
    print(f"  Failed: {failed_categories}")
    print(f"  Total Bugs Found: {total_bugs}")
    print()
    
    if total_bugs == 0:
        print("  ✓ ALL TESTS PASSED")
    else:
        print(f"  ✗ {total_bugs} BUG(S) FOUND - NEEDS FIXING")
    
    print("=" * 70)
    
    return total_bugs == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
