#!/usr/bin/env python3
"""Check what decision actions the engine produces for edge cases."""
import os, sys
from pathlib import Path

if not os.getenv("GROQ_API_KEY"):
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("GROQ_API_KEY="):
                os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip()
                break

from src.pipeline import PipelineOrchestrator
from src.conversation.state import ConversationState

pipeline = PipelineOrchestrator()

tests = [
    ("lateral_1", "I am in 1st year EE at a private college. Can I transfer to your college?"),
    ("lateral_2", "Can I get lateral entry into 2nd year CS?"),
    ("fee_install", "Can I pay fees in installments?"),
    ("sports_1", "I have a sports quota certificate. How do I apply?"),
    ("sports_2", "How to apply for sports quota admission?"),
    ("schol_renew", "My scholarship needs renewal. What is the process?"),
]

for sid, text in tests:
    state = ConversationState(session_id=sid)
    r = pipeline.run(text, state=state)
    action = r.decision.action if r.decision else "N/A"
    print(f"  \"{text[:60]}\" -> action=\"{action}\"")
