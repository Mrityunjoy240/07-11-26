#!/usr/bin/env python3
"""Compare expected vs actual brain output for conversations where brain scores low."""
import os, json
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
from scripts.benchmark import _pipeline_to_dict

pipeline = PipelineOrchestrator()

convs = [
    "ADM_LOWRANK_001",
    "HOSTEL_GIRLS_001",
    "FEES_PARENT_001",
    "ADM_HIGHRANK_001",
    "MIXED_HINDI_001",
]

for cid in convs:
    for vd in Path("data/benchmark").glob("v*"):
        f = vd / f"{cid}.json"
        if not f.exists():
            continue
        data = json.loads(f.read_text())
        state = ConversationState(session_id=f"brain_{cid}")
        print(f"\n  {cid}:")
        for i, turn in enumerate(data.get("turns", [])):
            text = turn["student"]
            r = pipeline.run(text, state=state)
            rd = _pipeline_to_dict(r)
            brain = rd.get("brain", {})
            gold_brain = turn.get("expected", {}).get("brain", {})
            print(f"    T{i+1}: \"{text[:60]}\"")
            print(f"      gold:   applicable={gold_brain.get('applicable')} branches={gold_brain.get('eligible_branches', [])}")
            print(f"      actual: applicable={brain.get('applicable')} branches={brain.get('eligible_branches', [])}")
        break
