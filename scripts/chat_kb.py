#!/usr/bin/env python3
"""Interactive chat against the college agent with KB grounding.

Type a question, see what the brain decides and what the KB says. Exit with
'quit' or Ctrl+C. Type '!kb <question>' to query the KB directly without the
brain, and '!src <file>' to ask about a specific source document.

Run:  python scripts/chat_kb.py [--root data/knowledge]
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
    if result.response and "mock LLM response" not in result.response:
        return result.response
    if result.plan and result.plan.turns:
        return " ".join(t.content for t in result.plan.turns)
    return result.response


def _print_answer(result) -> None:
    intent = result.understanding.intent.primary if result.understanding else "?"
    action = result.decision.action if result.decision else "?"
    print(f"\n  brain  -> intent: {intent}  |  action: {action}")
    print(f"  agent  -> {_answer(result)}")
    if result.knowledge and result.knowledge.get("sources"):
        print(f"  kb     -> retrieved: {result.knowledge.get('answer', '')[:220]}")
        print(f"  kb     -> sources: {', '.join(result.knowledge['sources'])} "
              f"| confidence: {result.knowledge.get('confidence', 0.0):.2f} "
              f"| kb_version: {result.knowledge.get('kb_version', '')[:8]}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/knowledge", help="KB root directory")
    parser.add_argument("--one-shot", nargs="+", metavar="QUESTION",
                        help="ask one or more questions and exit (no REPL)")
    args = parser.parse_args()

    _load_groq_key_from_env_file()

    from src.conversation.state import ConversationState
    from src.knowledge.kb import KnowledgeBase
    from src.pipeline import PipelineOrchestrator

    kb = KnowledgeBase(root_dir=args.root)
    status = kb.status()
    if status["documents"] == 0:
        print("KB is empty. Ingest documents first, e.g.:")
        print("  python -m src.knowledge.cli ingest --root data/knowledge "
              "college_agent_master_kb_full.txt")
        return 1
    print(f"KB: {status['documents']} document(s), {status['chunks']} chunk(s), "
          f"fingerprint {status['fingerprint'][:8]}")
    for source in kb.documents:
        print(f"  - {source}")

    # Pass an explicit LLM so the conversational-intent fallback is attached
    # (live demo). Without GROQ the pipeline still runs on MockLLM.
    try:
        from src.llm.groq import GroqLLM
        llm = GroqLLM(api_key=os.getenv("GROQ_API_KEY"))
    except Exception:
        llm = None

    pipeline = PipelineOrchestrator(knowledge=kb, llm=llm)
    state = ConversationState(session_id="interactive", profile={})

    if args.one_shot:
        for q in args.one_shot:
            print(f"\nYou> {q}")
            result = pipeline.run(q, state=state)
            _print_answer(result)
        return 0

    print("\n" + "=" * 78)
    print("Interactive test — ask anything about the college (type 'quit' to exit).")
    print("=" * 78)
    while True:
        try:
            question = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in ("quit", "exit"):
            break
        if question.startswith("!kb "):
            answer = kb.answer(question[4:].strip())
            if answer is None:
                print("  kb     -> no grounded answer (below threshold).")
            else:
                print(f"  kb     -> {answer.text}")
                print(f"  kb     -> sources: {', '.join(answer.sources)} "
                      f"| confidence: {answer.confidence:.2f}")
            continue
        if question.startswith("!src "):
            from pathlib import Path as _P
            path = _P(question[5:].strip())
            if not path.exists():
                print(f"  no such file: {path}")
                continue
            kb.ingest_paths([path])
            print(f"  ingested '{path}' -> {kb.fingerprint[:8]}")
            continue

        result = pipeline.run(question, state=state)
        _print_answer(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
