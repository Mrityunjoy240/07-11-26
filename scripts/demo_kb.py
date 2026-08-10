#!/usr/bin/env python3
"""End-to-end demo: operator uploads college documents -> KB -> student asks.

Run:  python scripts/demo_kb.py

What it shows:
  1. Operator upload:  college documents (txt/pdf) are ingested into the
     knowledge base via the KB layer (no Python edits required — the CLI
     does the same job:  python -m src.knowledge.cli ingest <path>).
  2. Student asks questions; the pipeline retrieves the *current* document
     content (RAG) and the brain still decides intent/action independently.
  3. Provenance: every answer prints its KB sources + confidence.
  4. Update: re-ingesting an updated document bumps the KB fingerprint and
     instantly serves the new content (cache is invalidated).

The demo works fully offline: if no GROQ_API_KEY is available the assistant
message falls back to the deterministic plan text, which already contains the
grounded KB answer.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_groq_key_from_env_file() -> None:
    env_path = ROOT / ".env"
    if os.getenv("GROQ_API_KEY"):
        return
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("GROQ_API_KEY="):
                os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                return


def _answer(result) -> str:
    """Best-effort final answer: real LLM, else the deterministic plan text."""
    if result.response and "mock LLM response" not in result.response:
        return result.response
    if result.plan and result.plan.turns:
        return " ".join(t.content for t in result.plan.turns)
    return result.response


def _print_turn(i: int, question: str, result) -> None:
    intent = result.understanding.intent.primary if result.understanding else "?"
    action = result.decision.action if result.decision else "?"
    print(f"\n[Turn {i}] STUDENT: {question}")
    print(f"  brain  -> intent: {intent}  |  action: {action}")
    print(f"  agent  -> {_answer(result)}")
    if result.knowledge and result.knowledge.get("sources"):
        print(f"  kb     -> retrieved: {result.knowledge.get('answer', '')[:180]}")
        print(f"  kb     -> sources: {', '.join(result.knowledge['sources'])} "
              f"| confidence: {result.knowledge.get('confidence', 0.0):.2f} "
              f"| kb_version: {result.knowledge.get('kb_version', '')[:8]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/knowledge", help="KB root directory")
    parser.add_argument(
        "--source",
        default="college_agent_master_kb_full.txt",
        help="document(s) to ingest when the KB is empty (file or directory)",
    )
    args = parser.parse_args()

    _load_groq_key_from_env_file()

    from src.knowledge.kb import KnowledgeBase
    from src.pipeline import PipelineOrchestrator
    from src.conversation.state import ConversationState

    kb = KnowledgeBase(root_dir=args.root)

    print("=" * 78)
    print("OPERATOR UPLOAD: college documents -> knowledge base")
    print("=" * 78)
    if kb.document_count == 0:
        added = kb.ingest_paths([args.source])
        print(f"  ingested {added} document(s) from '{args.source}'")
    else:
        print(f"  reusing existing KB ({kb.document_count} document(s), "
              f"{kb.chunk_count} chunks)")
    status = kb.status()
    print(f"  KB status -> docs: {status['documents']}, chunks: {status['chunks']}, "
          f"fingerprint: {status['fingerprint'][:12]}..., "
          f"embedder: {status['embedder']['name']}")

    print("\n" + "=" * 78)
    print("STUDENT QUESTIONS: brain decides intent/action, KB grounds the answer")
    print("=" * 78)

    pipeline = PipelineOrchestrator(knowledge=kb)
    state = ConversationState(session_id="demo", profile={})

    conversation = [
        "What do we study in ECE?",
        "What are the college timings?",
        "What is the ECE fee?",
        "Which companies visit for placement?",
        "What are the hostel facilities?",
        "My rank is 80000. Can I get ECE?",
    ]

    for i, question in enumerate(conversation, 1):
        result = pipeline.run(question, state=state)
        _print_turn(i, question, result)

    print("\n" + "=" * 78)
    print("OPERATOR UPDATE: edit a college document and re-upload (no code changes)")
    print("=" * 78)
    import tempfile

    docs_dir = Path(tempfile.mkdtemp())
    doc_path = docs_dir / "college_info.txt"
    doc_path.write_text(
        "DR. B.C. ROY ENGINEERING COLLEGE\n"
        "College Timings: Monday to Friday from 10:00 AM to 5:30 PM. "
        "Closed on Saturdays and Sundays.\n",
        encoding="utf-8",
    )
    kb.ingest_paths([doc_path])
    before = kb.fingerprint
    before_answer = kb.answer("What are the college timings?")
    doc_path.write_text(
        "DR. B.C. ROY ENGINEERING COLLEGE\n"
        "College Timings: Monday to Saturday from 9:00 AM to 6:00 PM. "
        "Closed on Sundays.\n",
        encoding="utf-8",
    )
    added = kb.ingest_paths([doc_path])
    state2 = ConversationState(session_id="demo-update", profile={})
    result = pipeline.run("What are the college timings?", state=state2)
    print(f"  edited 'college_info.txt' and re-uploaded ({added} change); fingerprint "
          f"{before[:8]} -> {kb.fingerprint[:8]}")
    print(f"  before: {before_answer.text if before_answer else '(none)'}")
    print(f"  STUDENT: What are the college timings?")
    print(f"  brain  -> intent: {result.understanding.intent.primary}  |  "
          f"action: {result.decision.action}")
    print(f"  agent  -> {_answer(result)}")
    if result.knowledge and result.knowledge.get("sources"):
        print(f"  kb     -> retrieved: {result.knowledge.get('answer', '')[:180]}")
        print(f"  kb     -> sources: {', '.join(result.knowledge['sources'])}")
    print("\nDemo complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
