import json
o = json.load(open('data/benchmark/coverage/ontology_v2.1.json', encoding='utf-8'))
print(f"Intents: {o['intents']['count']} (items: {len(o['intents']['items'])})")
print(f"Actions: {o['actions']['count']} (items: {len(o['actions']['items'])})")
print(f"Behaviors: {o['behaviors']['count']} (items: {len(o['behaviors']['items'])})")
print(f"Operators: {o['reasoning_operators']['count']} (items: {len(o['reasoning_operators']['items'])})")
print(f"Merged from v2.0: {len(o['intents']['merged_from_v2_0'])} intents")
print(f"Removed from v2.0: {len(o['actions']['removed_from_v2_0'])} actions")
