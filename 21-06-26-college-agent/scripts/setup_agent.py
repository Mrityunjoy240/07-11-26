"""Dograh Agent Setup Script

Creates a voice agent in Dograh that uses our RAG API for answers.

Usage:
    python scripts/setup_agent.py --dograh-url http://localhost:8001 --jwt <token>

    Or set DOGRAH_JWT environment variable and run:
    python scripts/setup_agent.py
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

DOGRAH_API = os.environ.get("DOGRAH_API", "http://localhost:8001")
BACKEND_API = os.environ.get("BACKEND_API", "http://backend:8080")


def api_call(method: str, path: str, jwt: str, body: dict = None) -> dict:
    url = f"{DOGRAH_API}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {jwt}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  ERROR {e.code}: {err[:300]}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Set up Dograh college agent")
    parser.add_argument("--dograh-url", default=DOGRAH_API, help="Dograh API URL")
    parser.add_argument("--backend-url", default=BACKEND_API, help="Backend API URL")
    parser.add_argument("--jwt", default=os.environ.get("DOGRAH_JWT", ""), help="Dograh JWT token")
    args = parser.parse_args()

    global DOGRAH_API, BACKEND_API
    DOGRAH_API = args.dograh_url
    BACKEND_API = args.backend_url
    jwt = args.jwt

    if not jwt:
        print("ERROR: Set DOGRAH_JWT env var or pass --jwt")
        print("Login to Dograh UI at http://localhost:3010, get JWT from browser dev tools.")
        sys.exit(1)

    # Step 1: Create HTTP API Tool
    print(">>> Creating college knowledge tool...")
    tool = api_call("POST", "/api/v1/tools", jwt, {
        "name": "query_college_knowledge_base",
        "description": "Query the college knowledge base for admissions info, fees, courses, faculty, placements. Use this when the caller asks about anything related to the college.",
        "type": "http_api",
        "config": {
            "method": "POST",
            "url": f"{BACKEND_API}/qa/query",
            "headers": {"Content-Type": "application/json"},
            "body": {"message": "{{input}}"},
            "response_mapping": {"result_path": "$.answer"},
        },
        "parameters": [
            {
                "name": "input",
                "type": "string",
                "description": "The caller's question about the college, exactly as spoken",
                "required": True,
            }
        ],
    })
    tool_id = tool.get("id")
    print(f"  Tool created: {tool_id}")

    # Step 2: Create Voice Agent
    print(">>> Creating voice agent...")
    agent = api_call("POST", "/api/v1/agents", jwt, {
        "name": "College Admissions Agent",
        "description": "Multilingual voice agent for college admissions inquiries. Handles English, Hindi, and Bengali.",
        "workflow_definition": {
            "nodes": [
                {
                    "id": "start",
                    "type": "start_call",
                    "config": {
                        "prompt": (
                            "Namaste! Welcome to Dr. B.C. Roy Engineering College. "
                            "I am your admissions assistant. I can answer your questions "
                            "about courses, fees, placements, and more. How can I help you today?"
                        ),
                        "allow_interruption": False,
                    },
                },
                {
                    "id": "agent",
                    "type": "agent",
                    "config": {
                        "prompt": (
                            "You are a friendly college admissions assistant for "
                            "Dr. B.C. Roy Engineering College. Answer callers' questions "
                            "clearly and concisely.\n\n"
                            "When you need information about courses, fees, placements, or admissions:\n"
                            "1. Use the query_college_knowledge_base tool to get accurate information\n"
                            "2. Always respond in the same language the caller used (Hindi/English/Bengali)\n"
                            "3. If you don't know something, use the tool to look it up\n"
                            "4. Keep answers brief and natural for a phone conversation\n"
                            "5. After answering, ask if there's anything else you can help with"
                        ),
                        "model": "gpt-4o-mini",
                        "tools": [tool_id],
                        "allow_interruption": True,
                        "max_duration_seconds": 600,
                    },
                },
                {
                    "id": "end",
                    "type": "end_call",
                    "config": {
                        "prompt": (
                            "Thank you for calling Dr. B.C. Roy Engineering College! "
                            "If you have more questions, feel free to call again. Have a great day!"
                        ),
                    },
                },
            ],
            "edges": [
                {"source": "start", "target": "agent"},
                {"source": "agent", "target": "end", "condition": "caller_says_goodbye"},
            ],
        },
    })
    agent_id = agent.get("id")
    print(f"  Agent created: {agent_id}")

    print(f"\n=== Agent setup complete! ===")
    print(f"  Agent ID: {agent_id}")
    print(f"  Tool ID:  {tool_id}")
    print(f"\nNext steps:")
    print(f"  1. Go to Dograh UI at http://localhost:3010")
    print(f"  2. Navigate to the agent to review/edit the workflow")
    print(f"  3. Configure telephony (Twilio/Vonage) in Settings")
    print(f"  4. Bind a phone number to this agent")
    print(f"  5. Test with a web call first")


if __name__ == "__main__":
    main()
