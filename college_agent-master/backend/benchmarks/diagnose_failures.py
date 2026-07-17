"""
Re-run each failing benchmark query with full diagnostics.
Captures handler, model, API response, latency, and classifies failure cause.
"""
import json, time, httpx, sys

BASE = "http://127.0.0.1:8000"

# The 23 failing queries from the benchmark
FAILURES = [
    (45, "EN", "unknown", "What is the stock price of Apple?"),
    (46, "EN", "campus", "Does BCREC have a library?"),
    (49, "EN", "placement", "Top recruiters at BCREC"),
    (56, "EN", "contact", "What is the college portal?"),
    (66, "EN", "online", "Does BCREC have online classes?"),
    (73, "HI", "placement", "बीसीआरईसी में प्लेसमेंट कितना है?"),
    (74, "HI", "admission", "मुझे एडमिशन लेना है। क्या प्रक्रिया है?"),
    (75, "HI", "admission", "बी.टेक में एडमिशन के लिए क्या योग्यता है?"),
    (79, "HI", "campus", "कैंपस में वाई-फाई उपलब्ध है?"),
    (80, "HI", "scholarship", "क्या छात्रवृत्ति मिलती है?"),
    (81, "HI", "why_bcrec", "बीसीआरईसी एनबीए मान्यता प्राप्त है?"),
    (82, "HI", "admission", "क्या लेटरल एंट्री मिलती है?"),
    (91, "BN", "placement", "বিসিআরইসি এর প্লেসমেন্ট রেট কত?"),
    (97, "BN", "campus", "ক্যাম্পাসে ওয়াই-ফাই আছে?"),
    (98, "BN", "scholarship", "স্কলারশিপ কী কী পাওয়া যায়?"),
    (99, "BN", "admission", "ল্যাটারাল এন্ট্রি কি পাওয়া যায়?"),
    (108, "HINGLISH", "admission", "Admission ke liye kya karna padta hai?"),
    (111, "HINGLISH", "campus", "WiFi available hai campus mein?"),
    (119, "BANGLISH", "placement", "Placement rate koto BCREC te?"),
    (120, "BANGLISH", "admission", "Vorti process ta ki?"),
    (128, "EN", "followup", "What about placements?"),
    (134, "EN", "multi_turn", "What about AIML?"),
    (136, "EN", "multi_turn", "Where can I track my application?"),
]

results = []

for num, lang, cat, query in FAILURES:
    session_id = f"diag-{num}"
    t0 = time.monotonic()
    
    diagnostic = {
        "num": num,
        "lang": lang,
        "category": cat,
        "query": query,
        "debug": {},
        "query_response": {},
        "latency_ms": 0,
        "is_error": False,
        "error_message": "",
    }
    
    try:
        # Step 1: Debug endpoint (shows handler classification, context, language)
        r1 = httpx.post(
            f"{BASE}/qa/debug",
            json={"message": query, "session_id": session_id},
            timeout=120,
        )
        diagnostic["debug"] = {
            "status": r1.status_code,
            "response": r1.json(),
        }
    except Exception as e:
        diagnostic["debug"] = {"status": "ERROR", "error": str(e)}
    
    try:
        # Step 2: Query endpoint (actual LLM call)
        r2 = httpx.post(
            f"{BASE}/qa/query",
            json={"message": query, "session_id": session_id},
            timeout=180,
        )
        diagnostic["query_response"] = {
            "status": r2.status_code,
            "response": r2.json(),
        }
    except httpx.TimeoutException:
        diagnostic["query_response"] = {"status": "TIMEOUT", "error": "HTTP request timed out (>180s)"}
    except Exception as e:
        diagnostic["query_response"] = {"status": "ERROR", "error": str(e)}
    
    diagnostic["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
    
    # Check for error indicators
    ans = ""
    source = ""
    model = ""
    if "response" in diagnostic["query_response"]:
        qr = diagnostic["query_response"]["response"]
        ans = str(qr.get("answer", ""))
        source = qr.get("source", "")
        model = qr.get("model", "")
    
    is_sorry = "i'm sorry" in ans.lower() or "having trouble" in ans.lower()
    diagnostic["is_error"] = is_sorry
    diagnostic["answer"] = ans[:300]
    diagnostic["source"] = source
    diagnostic["model"] = model
    
    # CLASSIFY
    if diagnostic["query_response"].get("status") == "TIMEOUT":
        classification = "Timeout"
    elif is_sorry:
        # Check if it's a rate limit or connection error
        if "rate limit" in ans.lower() or "429" in ans.lower():
            classification = "Rate limit"
        elif "timeout" in ans.lower():
            classification = "Timeout"
        else:
            classification = "Groq API failure"
    elif diagnostic["query_response"].get("status") not in (200, None):
        classification = "Network"
    else:
        classification = "OK"
    
    diagnostic["classification"] = classification
    
    results.append(diagnostic)
    print(f"#{num:3d} [{lang:8s}/{cat:12s}] src={source:25s} model={str(model)[:20]:20s} lat={diagnostic['latency_ms']:8.0f}ms cls={classification}")
    print(f"  Q: {query[:60]}")
    if is_sorry:
        print(f"  A: {ans[:120]}")
    print()

# Summary
print("=" * 80)
print("FAILURE CLASSIFICATION SUMMARY")
print("=" * 80)
from collections import Counter
classifications = Counter(r["classification"] for r in results)
for cls, count in classifications.most_common():
    print(f"  {cls}: {count}/{len(results)} ({count/len(results)*100:.1f}%)")

# Detailed per-query output for report
print()
print("=" * 80)
print("DETAILED PER-QUERY DIAGNOSTICS")
print("=" * 80)
for r in results:
    print(f"\n--- #{r['num']} [{r['lang']}/{r['category']}] ---")
    print(f"  Query: {r['query'][:80]}")
    print(f"  Source handler: {r['source']}")
    print(f"  Model: {r['model']}")
    print(f"  Latency: {r['latency_ms']:.0f}ms")
    print(f"  Classification: {r['classification']}")
    
    # Debug info
    dbg = r.get("debug", {})
    if "response" in dbg:
        dr = dbg["response"]
        print(f"  Debug/lang: {dr.get('lang', '?')}")
        print(f"  Debug/context_len: {dr.get('context_len', '?')}")
    
    # Query response details
    qr = r.get("query_response", {})
    if "response" in qr:
        qrj = qr["response"]
        print(f"  API status: {qr.get('status')}")
        print(f"  Source: {qrj.get('source', '?')}")
        print(f"  Answer: {str(qrj.get('answer', ''))[:200]}")
    
    # Error info
    if r.get("error_message"):
        print(f"  Error: {r['error_message'][:200]}")

# Save for report generation
json.dump(results, open("failure_diagnostics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("\nDiagnostics saved to failure_diagnostics.json")
