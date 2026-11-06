"""Messy-language + latency probe for the brain.

Queries with typos, Banglish, Hinglish, villager phrasing, pure Hindi/Bengali,
and unexpected topics. Reports per-query latency + intent/action + confidence.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

env_path = os.path.join(ROOT, ".env")
if not os.getenv("GROQ_API_KEY") and os.path.exists(env_path):
    for line in open(env_path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("GROQ_API_KEY="):
            os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
            break

QUERIES = [
    # typos
    ("typo", "CSE admission fes koto?"),
    ("typo", "hostil fee kya hai?"),
    ("typo", "swiming pool ache ki?"),
    ("typo", "scholarsip list dao"),
    # Banglish villager style
    ("banglish", "dada, admission er jonyo koto taka lagbe?"),
    ("banglish", "fee koto porbe, bole dao na"),
    ("banglish", "college er hostel ache ki?"),
    ("banglish", "placement kemon? bhalo company ase naki?"),
    ("banglish", "kaka, scholarship ki pawa jai? amader barite obostha bhalo na"),
    ("banglish", "hostel er jonno alada taka dite hobe naki?"),
    # Hinglish
    ("hinglish", "bhaiya admission kaise hoga aur fees kitni hai?"),
    ("hinglish", "hostel ka kharcha alag hai kya?"),
    # pure languages
    ("hindi", "\u0939\u0949\u0938\u094d\u091f\u0932 \u092b\u0940\u0938 \u0915\u093f\u0924\u0928\u0940 \u0939\u0948?"),
    ("bengali", "\u0938\u093f.\u090f\u0938.\u0908 \u098f\u09b0 \u098f\u09a1\u09ae\u09bf\u09b6\u09a8 \u09ab\u09bf \u0995\u09a4?"),
    # unexpected
    ("unexpected", "chaikona helicopter course hai kya?"),
    ("unexpected", "college e cricket stadium ache?"),
    # broken
    ("broken", "fess 0 lakh koto bolo jaldi"),
]

def main() -> int:
    from src.conversation.state import ConversationState
    from src.knowledge.kb import KnowledgeBase
    from src.pipeline import PipelineOrchestrator

    kb = KnowledgeBase(root_dir="data/knowledge")
    try:
        from src.llm.groq import GroqLLM
        llm = GroqLLM(api_key=os.getenv("GROQ_API_KEY"))
    except Exception:
        llm = None

    pipeline = PipelineOrchestrator(knowledge=kb, llm=llm)
    state = ConversationState(session_id="messy-probe", profile={})

    print(f"{'kind':12} {'latency':>8} {'intent':20} {'action':32} conf   answer")
    print("-" * 130)
    lats = []
    for kind, q in QUERIES:
        t0 = time.perf_counter()
        try:
            result = pipeline.run(q, state=state)
        except Exception as e:
            print(f"{kind:12} {'ERR':>8} {q[:50]} -> {type(e).__name__}: {e}")
            continue
        ms = (time.perf_counter() - t0) * 1000
        lats.append(ms)
        intent = result.understanding.intent.primary if result.understanding else "?"
        action = result.decision.action if result.decision else "?"
        conf = result.knowledge.get("confidence", 0.0) if result.knowledge else 0.0
        answer = (result.response or "").replace("\n", " ")[:70]
        print(f"{kind:12} {ms:7.0f}ms {intent:20} {action:32} {conf:.2f}   {answer}")

    n = len(lats)
    if n:
        lats.sort()
        print("-" * 130)
        print(f"latency: min {lats[0]:.0f}ms | median {lats[n//2]:.0f}ms | "
              f"p90 {lats[int(n*0.9)]:.0f}ms | max {lats[-1]:.0f}ms | avg {sum(lats)/n:.0f}ms")

    # Backend existence guard on typo'd / villager existence forms
    print("\n--- backend existence guard (typo / villager forms) ---")
    try:
        sys.path.insert(0, os.path.join(ROOT, "college_agent-master", "backend"))
        from app.services.llm.groq_service import get_groq_service
        guard = get_groq_service()
        for q in ["swiming pool ache ki?", "swimming pool he kya",
                  "college e cricket stadium ache?", "marine course ache?",
                  "canteen ache ki?", "hostel ache ki?"]:
            r = guard._existence_refusal_guard(q, "en")
            print(f"{'REFUSED' if r else 'pass   '}  {q}")
    except Exception as e:
        print(f"guard probe failed: {e}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
