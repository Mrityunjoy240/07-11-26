#!/usr/bin/env python3
"""
RAG Test Suite Runner — 150 Questions (50 per language)
Tests BCREC AI Agent against English, Hindi, and Bengali queries
Generates comprehensive results and metrics
"""

import argparse
import asyncio
import json
import time
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

# Load .env for API keys
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

from app.services.llm.groq_service import get_groq_service


class RAGTestRunner:
    ENGLISH_QUESTIONS = {
        "fees": [
            "How much are the fees for CSE?",
            "What is the total cost of studying at BCREC?",
            "Are there any scholarship options available?",
            "What's the fee structure for IT branch?",
            "Can I pay fees in installments?",
            "How much does ECE cost per year?",
            "Is there a fee for hostel accommodation?",
            "What are the charges for the library?",
            "Do engineering students have to pay lab fees separately?",
            "What's the cost difference between CSE and other branches?",
        ],
        "admissions": [
            "What are the admission criteria for B.Tech?",
            "How do I apply for admission to BCREC?",
            "What's the cutoff rank for CSE?",
            "Do you accept applications throughout the year?",
            "Is GATE score required for admission?",
            "What documents do I need for admission?",
            "When is the next admission cycle?",
            "Can I transfer from another college?",
            "What's the acceptance rate for BCREC?",
            "Do you offer lateral entry for diploma holders?",
        ],
        "faculty": [
            "Who is the Principal of BCREC?",
            "Who is the Vice Principal?",
            "Who is the HOD of CSE department?",
            "How many faculty members are in the ECE department?",
            "What are the qualifications of the CSE HOD?",
            "Who handles student affairs?",
            "Can I meet the Vice Principal?",
            "Who is responsible for placements?",
            "What's the contact number of the Principal's office?",
            "Who is the HOD of Mechanical Engineering?",
        ],
        "placements": [
            "What's the placement rate at BCREC?",
            "Which companies recruit from BCREC?",
            "What's the average package offered?",
            "How many students got placed last year?",
            "Which branch has the best placements?",
            "Do you have pre-placement training?",
            "When does the placement season start?",
            "What's the highest package offered?",
            "How many companies visited for placements?",
            "Do final year students get guaranteed placements?",
        ],
        "campus": [
            "Do you have a hostel on campus?",
            "What sports facilities are available?",
            "Is there a library with good resources?",
            "Do you have computer labs?",
            "Is WiFi available on campus?",
            "What's the college address?",
            "How do I contact the college?",
            "What are the college timings?",
            "Is there a student canteen?",
            "What transportation is available?",
        ],
    }

    HINDI_QUESTIONS = {
        "fees": [
            "CSE ki fees kitni hai?",
            "BCREC mein padhai ka total kharcha kitna hai?",
            "Kya koi scholarship option uplabdh hai?",
            "IT branch ki fees sanrachna kya hai?",
            "Kya main kiston mein fees de sakta hoon?",
            "ECE saal mein kitne rupaye ka kharch hai?",
            "Hostel rehne ke liye kitna paisa lagta hai?",
            "Library ke liye kitna charge hai?",
            "Kya engineering chhatron ko alag se lab fees deni padti hai?",
            "CSE aur anya shakhon mein fees mein kitna antar hai?",
        ],
        "admissions": [
            "B.Tech mein pravesh ke manadand kya hain?",
            "Main BCREC mein aavedan kaise de sakta hoon?",
            "CSE ke liye cutoff rank kya hai?",
            "Kya saal bhar aavedan svikar kiye jaate hain?",
            "Kya GATE score ki aavashyakta hai?",
            "Pravesh ke liye kaun se dastaavez chahiye?",
            "Agla pravesh chakra kab hai?",
            "Kya main doosre college se transfer kar sakta hoon?",
            "BCREC mein svikriti dar kya hai?",
            "Kya diploma dhaarakon ke liye lateral entry hai?",
        ],
        "faculty": [
            "BCREC ka principal kaun hai?",
            "Vice Principal kaun hai?",
            "CSE vibhag ka HOD kaun hai?",
            "ECE vibhag mein kitne shikshak hain?",
            "CSE ke HOD ki yogyataen kya hain?",
            "Chhatra mamlon ka prabhari kaun hai?",
            "Kya main Vice Principal se mil sakta hoon?",
            "Placement ke liye kaun zimmedar hai?",
            "Principal karyalaya ka phone number kya hai?",
            "Mechanical Engineering ka HOD kaun hai?",
        ],
        "placements": [
            "BCREC mein placement rate kya hai?",
            "BCREC se kaun si companies bharti karti hain?",
            "Average package kitna hai?",
            "Pichhle saal kitne chhatron ko jagah mili?",
            "Kis shakha ke paas sabse achhi placement hai?",
            "Kya pre-placement training hai?",
            "Placement season kab shuru hota hai?",
            "Sabse zyada package kitna hai?",
            "Placement ke liye kitni companies aayin?",
            "Kya antim varsh ke chhatron ko guaranteed placement milta hai?",
        ],
        "campus": [
            "Kya campus mein hostel hai?",
            "Kaun si khel suvidhaen uplabdh hain?",
            "Kya achhe sansadhanon ke saath library hai?",
            "Kya computer labs hain?",
            "Kya campus par WiFi uplabdh hai?",
            "College ka pata kya hai?",
            "Main college se kaise sampark kar sakta hoon?",
            "College ka samay kya hai?",
            "Kya canteen hai?",
            "Kya parivahan uplabdh hai?",
        ],
    }

    BENGALI_QUESTIONS = {
        "fees": [
            "CSE er fee koto?",
            "BCREC te porashonar mot kharch koto?",
            "Kono britir bikolpo ache ki?",
            "IT vibhager fee kathamo ki?",
            "Ami kistite fee dite pari ki?",
            "ECE bochore koto taka kharch?",
            "Hostel thakar jonno koto taka lage?",
            "Libraryr jonno koto charge?",
            "Engineering shiksharthider alada lab fee dite hoy ki?",
            "CSE ebong anyo vibhager modhye fee parthokko koto?",
        ],
        "admissions": [
            "B.Tech e bhortir mondondo ki?",
            "Ami BCREC te abedon korte pari kibhabe?",
            "CSE er jonno cutoff rank koto?",
            "Shara bochhor abedon grohito hoy ki?",
            "GATE score proyojon ache ki?",
            "Bhortir jonno ki ki dolil lage?",
            "Poroborti bhirti chokro kokhon?",
            "Ami onno college theke sthanantorito hote pari ki?",
            "BCREC er grohonযোগ্যতার har koto?",
            "Diploma dharakder jonno pashyoprabesh ache ki?",
        ],
        "faculty": [
            "BCREC er prodhan ke?",
            "Upo-pradhan ke?",
            "CSE vibhager prodhan ke?",
            "ECE vibhage kotjon shikkhok ache?",
            "CSE prodhaner joggyota ki?",
            "Shikkharthi bishoyok dayittwe ke ache?",
            "Ami upo-pradhaner sathe dekha korte pari ki?",
            "Placement er jonno ke dayee?",
            "Prodhaner office er phone number koto?",
            "Yantrik prokoushol vibhager prodhan ke?",
        ],
        "placements": [
            "BCREC te placement har koto?",
            "BCREC theke kon kon company niyog dey?",
            "Gor package koto?",
            "Goto bochhor kotjon shikkharthi placed hoyeche?",
            "Kon vibhager shrestho placement ache?",
            "Placement purbo probhshon ache ki?",
            "Placement season kokhon shuru hoy?",
            "Sorboccho package koto?",
            "Placement er jonno koti company eshechilo?",
            "Shesh bochorer shikkharthira guaranteed placement pay ki?",
        ],
        "campus": [
            "Campus e hostel ache ki?",
            "Ki ki khelar subidha ache?",
            "Bhalo sansthan shoho library ache ki?",
            "Computer lab ache ki?",
            "Campus e WiFi ache ki?",
            "College er thikana ki?",
            "Ami college er sathe jogajog korte pari kibhabe?",
            "College er shomoy ki?",
            "Canteen ache ki?",
            "Poribohon upolobdh ache ki?",
        ],
    }

    def __init__(self, lang_filter=None):
        self.groq = get_groq_service()
        self.results = []
        self.start_time = 0.0
        self.lang_filter = lang_filter

    async def run_test(self, qnum: int, lang: str, cat: str, question: str):
        t0 = time.time()
        try:
            resp = await self.groq.generate_response(question, session_id=f"150test_{lang}_{qnum}")
            latency = time.time() - t0
            answer = resp.get("answer", "")
            status = self._determine_status(question, answer, lang)
            self.results.append(
                {
                    "num": qnum,
                    "lang": lang,
                    "cat": cat,
                    "q": question,
                    "answer": answer[:200],
                    "latency": round(latency, 2),
                    "status": status,
                }
            )
            return status, latency
        except Exception as e:
            latency = time.time() - t0
            self.results.append(
                {
                    "num": qnum,
                    "lang": lang,
                    "cat": cat,
                    "q": question,
                    "answer": f"ERROR: {str(e)[:100]}",
                    "latency": round(latency, 2),
                    "status": "ERROR",
                }
            )
            return "ERROR", latency

    def _determine_status(self, question: str, answer: str, lang: str) -> str:
        a = answer.lower()
        deflections = [
            "don't have information",
            "don't know",
            "not aware",
            "please call",
            "मुझे जानकारी नहीं",
            "मेरे पास",
            "আমার কাছে",
            "আমি জানি না",
        ]
        if any(d in a for d in deflections):
            return "PARTIAL"
        if len(answer) > 30:
            return "PASS"
        return "PARTIAL"

    async def run_all(self, limit=None):
        self.start_time = time.time()
        qnum = 0
        all_langs = [
            ("en", self.ENGLISH_QUESTIONS),
            ("hi", self.HINDI_QUESTIONS),
            ("bn", self.BENGALI_QUESTIONS),
        ]
        if self.lang_filter:
            all_langs = [(l, q) for l, q in all_langs if l == self.lang_filter]
            if not all_langs:
                print(f"  Unknown language: {self.lang_filter}. Use en, hi, or bn.")
                return
        for lang, questions in all_langs:
            total = sum(len(qs) for qs in questions.values())
            print(f"\n{'=' * 60}\n  {lang.upper()} — {total} questions\n{'=' * 60}")
            for cat, qs in questions.items():
                for q in qs:
                    qnum += 1
                    safe_q = (
                        q[:55]
                        .encode(sys.stdout.encoding, errors="replace")
                        .decode(sys.stdout.encoding, errors="replace")
                    )
                    print(f"  [{qnum:3d}] {safe_q:55s}", end=" ", flush=True)
                    status, lat = await self.run_test(qnum, lang, cat, q)
                    tag = {"PASS": "OK", "PARTIAL": "~", "FAIL": "XX", "ERROR": "ERR"}.get(
                        status, "?"
                    )
                    tag = tag.encode(sys.stdout.encoding, errors="replace").decode(
                        sys.stdout.encoding, errors="replace"
                    )
                    print(f" {tag} ({lat:.1f}s)")
                    if limit and qnum >= limit:
                        return
                    await asyncio.sleep(0.3)

    def report(self):
        elapsed = time.time() - self.start_time
        total = len(self.results)
        by_status = {
            s: sum(1 for r in self.results if r["status"] == s)
            for s in ["PASS", "PARTIAL", "FAIL", "ERROR"]
        }
        pass_rate = (by_status["PASS"] / total * 100) if total else 0

        by_lang = {}
        for lang in ["en", "hi", "bn"]:
            rl = [r for r in self.results if r["lang"] == lang]
            if rl:
                lp = sum(1 for r in rl if r["status"] == "PASS")
                by_lang[lang] = (
                    lp,
                    len(rl),
                    lp / len(rl) * 100,
                    sum(r["latency"] for r in rl) / len(rl),
                )

        by_cat = {}
        for cat in set(r["cat"] for r in self.results):
            rc = [r for r in self.results if r["cat"] == cat]
            cp = sum(1 for r in rc if r["status"] == "PASS")
            by_cat[cat] = (cp, len(rc), cp / len(rc) * 100)

        print(f"\n{'=' * 60}")
        print("  TEST REPORT SUMMARY")
        print(f"{'=' * 60}")
        print(f"\n  Total: {total} | Elapsed: {elapsed:.0f}s")
        print(
            f"  PASS: {by_status['PASS']} | PARTIAL: {by_status['PARTIAL']} | FAIL: {by_status['FAIL']} | ERROR: {by_status['ERROR']}"
        )
        print(f"\n   OVERALL: {pass_rate:.1f}%")
        print(f"\n  By Language:")
        for lang, (p, t, r, lat) in by_lang.items():
            print(f"    {lang.upper()}: {p}/{t} ({r:.1f}%) — avg {lat:.1f}s")
        print(f"\n  By Category:")
        for cat, (p, t, r) in sorted(by_cat.items()):
            print(f"    {cat:12s}: {p}/{t} ({r:.1f}%)")

        out = Path(__file__).resolve().parent.parent / "reports" / "phase2_results.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.parent.mkdir(exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "total": total,
                    "elapsed": elapsed,
                    "by_status": by_status,
                    "pass_rate": pass_rate,
                    "by_language": {
                        k: {"pass": v[0], "total": v[1], "rate": v[2], "avg_latency": v[3]}
                        for k, v in by_lang.items()
                    },
                    "by_category": {
                        k: {"pass": v[0], "total": v[1], "rate": v[2]} for k, v in by_cat.items()
                    },
                    "results": self.results,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        print(f"\n   reports/phase2_results.json saved")
        print(f"\n{'=' * 60}")
        if pass_rate >= 80:
            print("   PRODUCTION READY (80%+)")
        elif pass_rate >= 60:
            print("   ACCEPTABLE (60-80%) - debug and retest")
        else:
            print("   NEEDS WORK (<60%)")
        print(f"{'=' * 60}")


async def main():
    parser = argparse.ArgumentParser(description="RAG 150-Question Test Suite")
    parser.add_argument("--lang", choices=["en", "hi", "bn"], help="Run only this language")
    parser.add_argument("--model", default=None, help="Override Groq model (e.g. qwen/qwen3-32b)")
    args = parser.parse_args()

    runner = RAGTestRunner(lang_filter=args.lang)
    label = f" ({args.lang.upper()})" if args.lang else ""
    if args.model:
        runner.groq.model = args.model
        label += f" [{args.model}]"
    print(f"RAG 150-Question Test Suite{label}")
    print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await runner.run_all()
    runner.report()


if __name__ == "__main__":
    asyncio.run(main())
