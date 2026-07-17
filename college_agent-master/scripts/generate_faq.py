#!/usr/bin/env python3
"""Generate admin_faq.json from combined_kb.json for legacy admin API."""

import json
import sys
from pathlib import Path

KB_PATH = Path("backend/data/knowledge_base/combined_kb.json")
OUTPUT_PATH = Path("backend/data/admin_faq.json")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_faq_entries(vra):
    entries = []
    for key, entry in vra.items():
        if not isinstance(entry, dict):
            continue
        keywords = entry.get("keywords", [])
        languages = list(entry.get("answers", {}).keys()) if "answers" in entry else []
        if "sub_answers" in entry and isinstance(entry["sub_answers"], dict):
            for sub_key, sub_data in entry["sub_answers"].items():
                if isinstance(sub_data, dict) and "answers" in sub_data:
                    sub_langs = list(sub_data["answers"].keys())
                    entries.append(
                        {
                            "key": f"{key}.{sub_key}",
                            "keywords": sub_data.get("keywords", keywords),
                            "languages": sub_langs,
                            "has_sub_answers": False,
                        }
                    )
        entries.append(
            {
                "key": key,
                "keywords": keywords,
                "languages": languages,
                "has_sub_answers": "sub_answers" in entry,
            }
        )
    return entries


def main():
    validate_only = "--validate" in sys.argv
    print("=" * 60)
    print("BCREC FAQ Generator")
    print("=" * 60)

    kb = load_json(KB_PATH)
    vra = kb.get("voice_ready_answers", {})
    entries = build_faq_entries(vra)

    output = {"entries": entries, "total": len(entries)}

    output_json = json.dumps(output, indent=2, ensure_ascii=False)
    json.loads(output_json)

    print(f"  Entries: {len(entries)}")
    print(f"  Size: {len(output_json)} bytes")

    if validate_only:
        print("\nValidation passed. Output NOT written (--validate mode).")
        return

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(output_json)
    print(f"\nWritten: {OUTPUT_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()
