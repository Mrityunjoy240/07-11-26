"""Generate v2.1 baseline WITH per-turn detail for error analysis."""
import json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import PipelineOrchestrator
from src.conversation.state import ConversationState

CONVS_DIR = Path("data/benchmark/conversations")
MANIFEST = Path("data/benchmark/versions/v2.1.json")
BASELINE_PATH = Path("data/benchmark/evaluation/v2.1/pipeline_v1.json")

manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
conv_ids = manifest["conversations"]

pipe = PipelineOrchestrator()

results = {}
total_turns = 0
correct_intents = 0
correct_actions = 0
failed_convs = []
latencies = []

for conv_id in conv_ids:
    found = False
    for domain_dir in CONVS_DIR.iterdir():
        fp = domain_dir / f"{conv_id}.json"
        if fp.exists():
            conv = json.loads(fp.read_text(encoding="utf-8"))
            found = True
            break
    if not found:
        continue
    
    state = ConversationState(session_id=conv_id)
    turns = conv.get("turns", [])
    conv_correct_intent = 0
    conv_correct_action = 0
    conv_results = []
    
    for i, turn in enumerate(turns):
        text = turn.get("student", "")
        expected = turn.get("expected", {})
        
        t0 = time.time()
        result = pipe.run(text, state)
        latency_ms = (time.time() - t0) * 1000
        latencies.append(latency_ms)
        
        total_turns += 1
        
        expected_intent = expected.get("understanding", {}).get("intent", "")
        actual_intent = result.understanding.intent.primary if result.understanding else ""
        intent_match = expected_intent == actual_intent
        if intent_match:
            correct_intents += 1
            conv_correct_intent += 1
        
        expected_action = expected.get("decision", {}).get("action", "")
        actual_action = result.decision.action if result.decision else ""
        action_match = expected_action == actual_action
        if action_match:
            correct_actions += 1
            conv_correct_action += 1
        
        conv_results.append({
            "turn": i,
            "student": text[:80],
            "expected_intent": expected_intent,
            "actual_intent": actual_intent,
            "intent_match": intent_match,
            "expected_action": expected_action,
            "actual_action": actual_action,
            "action_match": action_match,
            "latency_ms": round(latency_ms, 1)
        })
    
    conv_pass = conv_correct_intent == len(turns) and conv_correct_action == len(turns)
    if not conv_pass:
        failed_convs.append(conv_id)
    
    results[conv_id] = {
        "turns": len(turns),
        "intent_correct": conv_correct_intent,
        "action_correct": conv_correct_action,
        "pass": conv_pass,
        "turns_detail": conv_results
    }
    
    status = "PASS" if conv_pass else "FAIL"
    print(f"  {conv_id}: {status} (intent={conv_correct_intent}/{len(turns)}, action={conv_correct_action}/{len(turns)})")

intent_accuracy = correct_intents / total_turns if total_turns else 0
action_accuracy = correct_actions / total_turns if total_turns else 0
turn_accuracy = sum(1 for r in results.values() if r["pass"]) / len(results) if results else 0
avg_latency = sum(latencies) / len(latencies) if latencies else 0

import subprocess
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()

baseline = {
    "version": "v2.1",
    "pipeline": "main",
    "pipeline_version": "v2.1",
    "model": "default",
    "temperature": 0.0,
    "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "pipeline_commit": commit,
    "benchmark_checksum": manifest.get("checksum", ""),
    "ontology_version": "2.1",
    "schema_version": "v2",
    "conversation_count": len(results),
    "turn_count": total_turns,
    "turn_accuracy": round(turn_accuracy, 4),
    "conversation_accuracy": round(turn_accuracy, 4),
    "intent_accuracy": round(intent_accuracy, 4),
    "action_accuracy": round(action_accuracy, 4),
    "retrieval_accuracy": None,
    "hallucination_rate": None,
    "avg_latency_ms": round(avg_latency, 1),
    "failed_conversations": failed_convs,
    "per_conversation": results,
    "status": "baseline",
    "notes": "Baseline with per-turn detail for error analysis."
}

BASELINE_PATH.write_text(json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(f"\nBaseline generated: {BASELINE_PATH}")
print(f"  Conversations: {len(results)}")
print(f"  Turns: {total_turns}")
print(f"  Intent accuracy: {intent_accuracy:.1%}")
print(f"  Action accuracy: {action_accuracy:.1%}")
print(f"  Turn accuracy: {turn_accuracy:.1%}")
print(f"  Failed: {len(failed_convs)}")
