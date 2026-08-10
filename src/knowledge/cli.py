from __future__ import annotations

import argparse
import sys

from src.knowledge.kb import KnowledgeBase


def _print_status(kb: KnowledgeBase) -> None:
    status = kb.status()
    print(f"Knowledge base root: {status['root']}")
    print(f"Documents: {status['documents']}")
    print(f"Chunks:    {status['chunks']}")
    print(f"Embedder:  {status['embedder']['name']} (dim={status['embedder']['dim']})")
    print(f"Fingerprint: {status['fingerprint'] or '(empty)'}")
    print(f"Cache entries: {status['cache_entries']}")
    for doc in kb.documents:
        print(f"  - {doc.title} ({doc.source})")


def _cmd_ingest(args: argparse.Namespace) -> int:
    kb = KnowledgeBase(root_dir=args.root)
    added = kb.ingest_paths(args.paths)
    print(f"Ingested: {added} document(s) added or updated.")
    _print_status(kb)
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    kb = KnowledgeBase(root_dir=args.root)
    _print_status(kb)
    return 0


def _cmd_clear(args: argparse.Namespace) -> int:
    kb = KnowledgeBase(root_dir=args.root)
    kb.clear()
    print("Knowledge base cleared.")
    _print_status(kb)
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    kb = KnowledgeBase(root_dir=args.root)
    answer = kb.answer(args.query, top_k=args.top_k)
    if answer is None:
        print("No relevant document found for this query.")
        return 1
    print(answer.text)
    print()
    print(f"Sources: {', '.join(answer.sources) or '(none)'}")
    print(f"Confidence: {answer.confidence:.2f} | KB version: {answer.kb_version}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.knowledge.cli",
        description=(
            "Operator CLI for the college knowledge base. Upload/replace "
            "college documents without touching any Python code: ingest them, "
            "then the agent answers student questions from the current index."
        ),
    )
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--root", default="data/knowledge", help="KB root directory")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser(
        "ingest", parents=[parent], help="ingest a file or directory of documents"
    )
    p_ingest.add_argument("paths", nargs="+", help="file(s) or directory(ies) to ingest")
    p_ingest.set_defaults(func=_cmd_ingest)

    p_status = sub.add_parser("status", parents=[parent], help="show KB status")
    p_status.set_defaults(func=_cmd_status)

    p_clear = sub.add_parser("clear", parents=[parent], help="clear the KB index")
    p_clear.set_defaults(func=_cmd_clear)

    p_ask = sub.add_parser(
        "ask", parents=[parent], help="ask the KB a question and show the grounded answer"
    )
    p_ask.add_argument("query", help="question to ask")
    p_ask.add_argument("--top-k", type=int, default=4, help="number of chunks to retrieve")
    p_ask.set_defaults(func=_cmd_ask)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
