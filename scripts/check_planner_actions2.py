#!/usr/bin/env python3
"""Check what planner actions the pipeline produces for specific conversations."""
import os
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
    ("ANTHRO_001", "I want to study Anthropology. Do you have that course?"),
    ("LEGACY_001", "My father studied CSE at this college in 1990. I want to follow his footsteps."),
]

for sid, text in tests:
    state = ConversationState(session_id=sid)
    r = pipeline.run(text, state=state)
    if r.plan:
        for i, turn in enumerate(r.plan.turns):
            print(f"  {sid} turn {i}: action=\"{turn.action}\" content=\"{turn.content[:60]}\"")
    else:
        print(f"  {sid}: no plan produced")
