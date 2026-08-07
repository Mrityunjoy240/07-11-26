"""Interactive chat with the BCREC Voice Brain over the Sarvam SDK bridge.

Opens an SDK session (dev/test channel) and lets you talk to the agent the
same way a caller would, then hangs up when you quit.

Usage:
    python scripts/sdk_chat.py                # defaults below
    python scripts/sdk_chat.py --topic admissions --lang Hindi
    python scripts/sdk_chat.py --base http://127.0.0.1:8000 --phone +919876543210
"""

import argparse
import json
import sys
import urllib.request

DEFAULT_BASE = "http://127.0.0.1:8000"


def _request(base: str, method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Talk to the BCREC Voice Brain over the SDK bridge"
    )
    parser.add_argument("--base", default=DEFAULT_BASE,
                        help=f"backend base URL (default: {DEFAULT_BASE})")
    parser.add_argument("--phone", default="+919876543210",
                        help="user identifier for the session")
    parser.add_argument("--lang", default="English",
                        help="language (e.g. English, Hindi, Bengali)")
    parser.add_argument("--topic", default="general",
                        help="query topic (e.g. admissions, fees, placement)")
    parser.add_argument("--caller-type", default="PSTN",
                        help="caller type (e.g. PSTN, web, mobile)")
    args = parser.parse_args()

    print("Connecting to voice brain...")
    try:
        created = _request(
            args.base,
            "POST",
            "/sdk/sessions",
            {
                "user_identifier": args.phone,
                "language": args.lang,
                "query_topic": args.topic,
                "caller_type": args.caller_type,
            },
        )
    except Exception as e:
        print(f"Failed to create session: {e}")
        print("Is the backend running with SARVAM_SDK_ENABLED=true?")
        return 1

    session = created["session"]
    sid = session["session_id"]
    print(f"Connected. Session {sid} ({session['status']})")
    print(f"Tip: {args.phone} | lang={args.lang} | topic={args.topic}")
    print("Type your question, or 'exit'/'quit' to hang up.\n")

    try:
        while True:
            try:
                question = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not question:
                continue
            if question.lower() in {"exit", "quit", "bye"}:
                break
            try:
                result = _request(
                    args.base,
                    "POST",
                    f"/sdk/sessions/{sid}/message",
                    {"message": question},
                )
            except Exception as e:
                print(f"Error: {e}")
                continue
            print(f"Brain: {result.get('answer') or '(no answer)'}\n")
    finally:
        try:
            _request(args.base, "POST", f"/sdk/sessions/{sid}/stop", {"reason": "user_request"})
            print("Hung up.")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
