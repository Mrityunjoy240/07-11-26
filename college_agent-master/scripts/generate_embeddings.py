#!/usr/bin/env python3
"""
generate_embeddings.py — Rebuild vector store from scratch.

Usage:
    python scripts/generate_embeddings.py            # Full rebuild
    python scripts/generate_embeddings.py --dry-run  # Show what would be ingested
"""

import sys
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("generate-embeddings")

from ingest_knowledge_base import ingest_kb


async def main():
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("BCREC Embeddings Generator")
    print("=" * 60)

    if dry_run:
        print("\nDRY RUN MODE — no ingestion will occur.")
        print("Would rebuild vector store from:")
        print("  1. backend/data/knowledge_base/topics/*.md")
        print("  2. backend/data/knowledge_base/departments/*.md")
        print(
            "  3. backend/data/knowledge_base/combined_kb.json (voice_ready_answers + quick_answers)"
        )
        print("  4. backend/data/knowledge_base.json (data sections)")
        print("  5. uploads/ (any admin-uploaded files)")
        print("\nDone.")
        return

    print("\nStarting full vector store rebuild...")
    await ingest_kb()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
