#!/usr/bin/env python3
"""
build.py — Single command to rebuild ALL runtime artifacts from knowledge_base.json

Usage:
    python scripts/build.py                # Full build
    python scripts/build.py --validate     # Validate only, don't write anything
    python scripts/build.py --skip-embeddings  # Skip expensive vector DB rebuild
"""

import sys
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCRIPTS = BASE / "scripts"
KB_FILE = BASE / "backend" / "data" / "knowledge_base.json"


def run_step(label, cmd):
    print(f"\n{'=' * 60}")
    print(f"STEP: {label}")
    print(f"{'=' * 60}")
    result = subprocess.run(cmd, cwd=BASE)
    if result.returncode != 0:
        print(f"FAILED: {label}")
        sys.exit(1)
    print(f"DONE: {label}")


def main():
    validate_only = "--validate" in sys.argv
    skip_embeddings = "--skip-embeddings" in sys.argv

    if not KB_FILE.exists():
        print(f"ERROR: {KB_FILE} not found")
        sys.exit(1)

    print(f"KB file: {KB_FILE} ({KB_FILE.stat().st_size} bytes)")

    # Step 1: Validate knowledge_base.json
    run_step("Validate knowledge_base.json", [sys.executable, str(SCRIPTS / "validate_kb.py")])

    if validate_only:
        print(f"\n{'=' * 60}")
        print("VALIDATE-ONLY: stopping after validation")
        print(f"{'=' * 60}")
        return

    # Step 2: Generate combined_kb.json (voice_ready_answers + quick_answers)
    run_step("Generate combined_kb.json", [sys.executable, str(SCRIPTS / "generate_kb.py")])

    # Step 3: Generate .md files from knowledge_base.json
    run_step(
        "Generate topic & department markdown files",
        [sys.executable, str(SCRIPTS / "generate_markdown.py")],
    )

    # Step 4: Generate admin_faq.json
    run_step("Generate admin_faq.json", [sys.executable, str(SCRIPTS / "generate_faq.py")])

    # Step 5: Generate embeddings (optional, skipped with --skip-embeddings)
    if not skip_embeddings:
        run_step(
            "Generate embeddings (vector DB rebuild)",
            [sys.executable, str(SCRIPTS / "generate_embeddings.py")],
        )
    else:
        print(f"\n{'=' * 60}")
        print("SKIPPED: embeddings generation (--skip-embeddings)")
        print(f"{'=' * 60}")

    print(f"\n{'=' * 60}")
    print("BUILD COMPLETE")
    print(f"{'=' * 60}")
    print("Generated artifacts:")
    print(f"  - backend/data/knowledge_base/combined_kb.json")
    print(f"  - backend/data/knowledge_base/topics/*.md")
    print(f"  - backend/data/knowledge_base/departments/*.md")
    print(f"  - backend/data/admin_faq.json")
    if not skip_embeddings:
        print(f"  - Vector DB (chroma_db/chroma_db_v2/)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
