"""Impact analysis: removing 'help' and 'take' from BANGLA_ROMAN_WORDS."""
import re, os

from app.utils.language_detect import BANGLA_ROMAN_WORDS, HINDI_ROMAN_WORDS

BANGLA_ROMAN_MOD = frozenset(w for w in BANGLA_ROMAN_WORDS if w not in ("help", "take"))

def detect_lang(text, use_help_take=True):
    word_set = BANGLA_ROMAN_WORDS if use_help_take else BANGLA_ROMAN_MOD
    text_lower = text.lower()
    text_words = set(re.sub(r"[^\w\s]", " ", text_lower).split())
    bn_count = len(text_words & word_set)
    hi_count = len(text_words & HINDI_ROMAN_WORDS)
    if bn_count >= 1 and bn_count > hi_count:
        return "bn"
    if hi_count >= 1 and hi_count > bn_count:
        return "hi"
    if bn_count >= 2 and bn_count == hi_count:
        return "bn"
    if hi_count >= 2 and hi_count == bn_count:
        return "hi"
    return "en"

# --- Find all test queries that might be affected ---
test_dir = "tests"
affected_tests = []
for f in sorted(os.listdir(test_dir)):
    if f.endswith(".py"):
        path = os.path.join(test_dir, f)
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            lower = line.lower()
            if "help" in lower or "take" in lower:
                # Check if this is a test assertion/language-related
                if any(kw in lower for kw in ["detect_language", "resolve_language",
                                               "bangla_roman", "language", "lang",
                                               "assert", "expected", "=="]):
                    affected_tests.append((f, i, line.strip()))

print("=== Test files with HELP/TAKE in language-related context ===")
for f, line_no, content in affected_tests:
    print(f"  {f}:{line_no}: {content[:120]}")

# --- Simulate all scenarios ---
print("\n\n=== BEFORE/AFTER classification table ===")
queries = [
    # User's exact examples
    ("1", "help"),
    ("2", "i need help"),
    ("3", "i need healp"),
    ("4", "help koro"),
    ("5", "akta help lagbe"),
    ("6", "take koro"),
    ("7", "amar help lagbe"),
    # Additional edge cases
    ("8", "help me"),
    ("9", "help please"),
    ("10", "take"),
    ("11", "take this"),
    ("12", "take korte hobe"),
    ("13", "help lagbe"),
    ("14", "take koro na"),
    ("15", "help korun"),
    ("16", "take care"),
    ("17", "helpful"),
    ("18", "taken"),
    ("19", "healp"),
    ("20", "healp koro"),
    ("21", "help korben"),
    ("22", "help korbo"),
    ("23", "help chai"),
    ("24", "take kore dao"),
    ("25", "help korchi"),
    ("26", "help lomba"),
    ("27", "I want to take admission in AIML"),
    ("28", "take admission"),
]

print(f"{'#':3s} {'Query':35s} {'BEFORE':8s} {'AFTER':8s} {'CHANGE'}")
print("-" * 65)
changes = []
for num, q in queries:
    before = detect_lang(q, use_help_take=True)
    after = detect_lang(q, use_help_take=False)
    c = "YES" if before != after else ""
    print(f"{num:3s} {q:35s} {before:8s} {after:8s} {c}")
    if before != after:
        changes.append((num, q, before, after))

print(f"\n\n=== QUIERIES THAT CHANGE ({len(changes)}) ===")
for num, q, b, a in changes:
    print(f"  #{num} {q!r:35s} {b} -> {a}")

# --- Analyze each change ---
print("\n\n=== IMPACT ANALYSIS ===")
for num, q, b, a in changes:
    words = set(re.sub(r"[^\w\s]", " ", q.lower()).split())
    bn_kw_before = len(words & BANGLA_ROMAN_WORDS)
    bn_kw_after = len(words & BANGLA_ROMAN_MOD)
    hi_kw = len(words & HINDI_ROMAN_WORDS)
    verdict = ""
    if a == "en":
        if any(w in BANGLA_ROMAN_MOD for w in words):
            verdict = "CORRECT? Has other Bangla words but goes to en (FastText might fix)"
        elif hi_kw > 0:
            verdict = "REGRESSION? Other words match Hindi set"
        else:
            verdict = "LIKELY CORRECT - pure English query"
    elif a == "bn":
        verdict = "STAYS BN (has other Bangla keywords)"
    elif a == "hi":
        verdict = "REGRESSION? Should be en - 'me' triggers Hindi"
    print(f"  #{num} {q!r:35s} {b}->{a}  bn_kw:{bn_kw_before}->{bn_kw_after}  hi_kw:{hi_kw}  {verdict}")

# --- Check resolve_language impact (with kw_count >= 2 guard) ---
print("\n\n=== resolve_language() impact (kw_count >= 2 guard) ===")
print("Queries where detect_language changes but resolve_language would still pass:")
for num, q, b, a in changes:
    words = set(re.sub(r"[^\w\s]", " ", q.lower()).split())
    bn_kw = len(words & BANGLA_ROMAN_MOD)
    hi_kw = len(words & HINDI_ROMAN_WORDS)
    # resolve_language: switch only if kw_count >= 2
    if a == "bn" and bn_kw >= 2:
        print(f"  #{num} {q!r:35s} {b}->{a}  bn_kw={bn_kw} -> would switch to BN (>=2)")
    elif a == "bn" and bn_kw < 2:
        print(f"  #{num} {q!r:35s} {b}->{a}  bn_kw={bn_kw} -> would stay current (guard)")
    elif a == "hi" and hi_kw >= 2:
        print(f"  #{num} {q!r:35s} {b}->{a}  hi_kw={hi_kw} -> would switch to HI (>=2)")
    elif a == "hi" and hi_kw < 2:
        print(f"  #{num} {q!r:35s} {b}->{a}  hi_kw={hi_kw} -> would stay current (guard)")
    else:
        print(f"  #{num} {q!r:35s} {b}->{a}  -> no switch risk")
