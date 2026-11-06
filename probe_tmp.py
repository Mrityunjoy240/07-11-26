import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.pipeline import PipelineOrchestrator
from src.conversation.state import ConversationState

CASES = [
    ("greeting", ["hi"]),
    ("help", ["i need help"]),
    ("who-are-you", ["who are you?"]),
    ("ece-curriculum", ["what do we study in ECE?"]),
    ("admission-enter", ["I'm looking for admission in ECE"]),
    ("admission-rank-supplied", ["I want admission in ECE, my WBJEE rank is 80000"]),
]

pipeline = PipelineOrchestrator(knowledge=None)

for label, texts in CASES:
    state = ConversationState(session_id=f"s-{label}", profile={})
    print(f"\n=== {label} ===")
    for text in texts:
        result = pipeline.run(text, state=state)
        intent = result.understanding.intent.primary if result.understanding else "?"
        problem = result.reasoning.current_problem if result.reasoning else "?"
        action = result.decision.action if result.decision else "?"
        content = " ".join(t.content for t in result.plan.turns) if result.plan and result.plan.turns else (result.response or "")
        print(f"  {text!r}")
        print(f"    intent={intent} problem={problem} action={action}")
        print(f"    -> {content}")
