#!/usr/bin/env python3
"""Test fact extraction for specific student texts."""
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
    ("fees_parent", "I am a parent. My son got 22k rank, PCM 85. What is the total fee for IT?"),
    ("transfer", "I am in 1st year EE at a private college in Bengal. I had 32k WBJEE rank. Can I transfer?"),
    ("foreign_t2", "I have 92% in CBSE PCM. Budget is not a constraint. I want CSE only."),
]

for sid, text in tests:
    state = ConversationState(session_id=sid)
    r = pipeline.run(text, state=state)
    facts = {}
    if r.understanding:
        p = r.understanding.profile
        facts = {
            "rank": p.academic.rank,
            "pcm": p.academic.pcm_percentage,
            "exam": p.academic.exam,
            "interest": p.career.interest,
        }
    print(f"  {sid}: {facts}")
    print(f"    state.profile = {state.profile}")
