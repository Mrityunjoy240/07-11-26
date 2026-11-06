"""Village-style Hindi + Bengali full-conversation probes.

Each language runs as ONE continuous conversation (shared ConversationState),
measuring per-query latency, intent, action, and grounding confidence.
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

HINDI = [
    "हेलो, कॉलेज में कौन है? मैं गाँव से बोल रहा हूँ।",
    "भाई साहब, इंजीनियरिंग में एडमिशन कैसे होता है?",
    "फीस कितना लगेगा पूरा कोर्स का?",
    "हॉस्टल मिलेगा क्या? कितना किराया है?",
    "प्लेसमेंट होता है ना? कंपनी आती है क्या?",
    "गाँव से कैसे पहुँचे कॉलेज? बस कितनी लगती है?",
    "12वीं में कितने नंबर चाहिए एडमिशन के लिए?",
    "जेईई चाहिए या डायरेक्ट एडमिशन मिल जाता है?",
    "डॉक्यूमेंट क्या-क्या लेके आना पड़ेगा?",
    "लड़के-लड़कियों का अलग हॉस्टल है क्या?",
    "खाना मिलेगा हॉस्टल में? कैसा खाना है?",
    "कॉलेज शहर से कितना दूर है?",
    "स्कॉलरशिप मिलती है गरीब लड़कों को?",
    "सिविल और मैकेनिकल दोनों चलता है क्या?",
    "एडमिशन कब शुरू होगा? फॉर्म कब आएगा?",
    "गाँव वाला लड़का पढ़ पाएगा या बहुत कठिन है?",
    "टीचर लोग अच्छे हैं ना? पढ़ाते हैं ठीक से?",
    "रात को बाहर घूमने की अनुमति है क्या?",
    "मोबाइल रख सकते हैं हॉस्टल में?",
    "बैंक लोन के लिए कॉलेज मदद करता है क्या?",
    "फर्स्ट ईयर में कितना खर्च आ जाएगा कुल?",
    "कॉलेज में मंदिर या मस्जिद है क्या?",
    "लड़की है मेरी, सेफ्टी कैसी है?",
    "एग्जाम कितनी बार होता है साल में?",
    "पास हो जाने के बाद जॉब लग जाती है ना?",
]

BENGALI = [
    "হ্যালো, কলেজে কে আছেন? আমি গাঁও থেকে ফোন করছি।",
    "দাদা, ইঞ্জিনিয়ারিং-এ অ্যাডমিশন কীভাবে হয়?",
    "ফি কত লাগবে পুরো কোর্সের?",
    "হোস্টেল পাওয়া যাবে তো? ভাড়া কত?",
    "প্লেসমেন্ট হয় তো? কোম্পানি আসে?",
    "গাঁও থেকে কলেজে কীভাবে যাব? বাস কত লাগে?",
    "দ্বাদশে কত নম্বর থাকলে অ্যাডমিশন পাব?",
    "জেইই লাগবে নাকি সরাসরি অ্যাডমিশন হয়?",
    "কাগজপত্র কী কী নিয়ে যেতে হবে?",
    "ছেলেমেয়ের আলাদা হোস্টেল আছে তো?",
    "হোস্টেলে খাওয়া পাওয়া যায়? খাবার কেমন?",
    "কলেজ শহর থেকে কত দূরে?",
    "গরিব ছেলেদের স্কলারশিপ পাওয়া যায়?",
    "সিভিল আর মেকানিক্যাল দুটোই চলে তো?",
    "অ্যাডমিশন কবে শুরু হবে? ফর্ম কবে আসবে?",
    "গাঁওয়ের ছেলে পড়তে পারবে নাকি খুব কঠিন?",
    "স্যার-ম্যাডামরা ভালো পড়ান তো?",
    "রাতে বাইরে যাওয়ার অনুমতি আছে?",
    "হোস্টেলে মোবাইল রাখা যায়?",
    "ব্যাংক লোনের জন্য কলেজ সাহায্য করে?",
    "প্রথম বছরে মোট খরচ কত পড়বে?",
    "কলেজে মন্দির বা মসজিদ আছে?",
    "মেয়েকে পাঠাব, সেফটি কেমন?",
    "পরীক্ষা বছরে কতবার হয়?",
    "পাস হলে চাকরি পেয়ে যায় তো?",
]


def run_set(name, queries):
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
    state = ConversationState(session_id=f"village-{name.lower()}", profile={})

    print(f"\n{'='*120}\n=== {name.upper()} ({len(queries)} queries, one conversation) ===\n{'='*120}")
    print(f"{'#':>2} {'latency':>8} {'intent':18} {'action':30} {'conf':>5}  answer")
    print("-" * 120)
    lats = []
    for i, q in enumerate(queries, 1):
        t0 = time.perf_counter()
        try:
            result = pipeline.run(q, state=state)
        except Exception as e:
            print(f"{i:>2} {'ERR':>8} {q[:40]} -> {type(e).__name__}: {e}")
            continue
        ms = (time.perf_counter() - t0) * 1000
        lats.append(ms)
        intent = result.understanding.intent.primary if result.understanding else "?"
        action = result.decision.action if result.decision else "?"
        conf = result.knowledge.get("confidence", 0.0) if result.knowledge else 0.0
        answer = (result.response or "").replace("\n", " ")[:80]
        print(f"{i:>2} {ms:7.0f}ms {intent:18} {action:30} {conf:5.2f}  {answer}")
    n = len(lats)
    if n:
        lats.sort()
        print("-" * 120)
        print(f"{name}: min {lats[0]:.0f}ms | median {lats[n//2]:.0f}ms | "
              f"p90 {lats[int(n*0.9)]:.0f}ms | max {lats[-1]:.0f}ms | avg {sum(lats)/n:.0f}ms | "
              f"total {(sum(lats)/1000):.1f}s")


if __name__ == "__main__":
    run_set("Hindi", HINDI)
    run_set("Bengali", BENGALI)