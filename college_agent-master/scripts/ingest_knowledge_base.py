import os
import sys
import logging
import asyncio
from pathlib import Path

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from langchain_core.documents import Document
from app.services.vector_store import get_vector_store
from app.services.document_processor import DocumentProcessor

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ingest-kb")


async def ingest_kb():
    vector_store = get_vector_store()
    doc_processor = DocumentProcessor()

    # Clear existing to ensure fresh index
    logger.info("Clearing existing vector store...")
    vector_store.clear_collection()

    # Resolve paths relative to project root
    project_root = Path(__file__).resolve().parent.parent
    kb_dir = project_root / "backend" / "data" / "knowledge_base"
    uploads_dir = project_root / "uploads"

    all_docs = []

    # 1. Process Markdown Files from departments/ and topics/
    # Markdown contains prose descriptions (fees breakdowns, college info, etc.)
    markdown_dirs = [kb_dir / "departments", kb_dir / "topics"]
    for mdir in markdown_dirs:
        if not mdir.exists():
            continue

        logger.info(f"Processing markdown files in {mdir}...")
        for md_file in mdir.glob("*.md"):
            chunks = await doc_processor.process_file(str(md_file))
            for chunk in chunks:
                all_docs.append(
                    Document(
                        page_content=chunk["text"],
                        metadata={"source": chunk["source"], **chunk.get("metadata", {})},
                    )
                )

    # 2. Ingest voice_ready_answers from combined_kb.json (pre-written multilingual answers)
    kb_json_path = kb_dir / "combined_kb.json"
    json_doc_count = 0
    if kb_json_path.exists():
        import json

        logger.info("Processing voice_ready_answers from combined_kb.json...")
        with open(kb_json_path, "r", encoding="utf-8") as f:
            kb_data = json.load(f)
        vra = kb_data.get("voice_ready_answers", {})
        for section_name, section_data in vra.items():
            if not isinstance(section_data, dict):
                continue

            def _anchor_text(text, anchor):
                return text  # anchor in metadata only; don't pollute multilingual embeddings

            # Pattern A: section has answers.{en,hi,bn} (principal, vice_principal, placement, hostel, ...)
            if "answers" in section_data and isinstance(section_data["answers"], dict):
                anchor = section_data.get("semantic_anchor", "")
                for lang in ("en", "hi", "bn"):
                    text = section_data["answers"].get(lang, "")
                    if text:
                        all_docs.append(
                            Document(
                                page_content=_anchor_text(text.strip(), anchor),
                                metadata={
                                    "source": "combined_kb_json",
                                    "section": section_name,
                                    "language": lang,
                                    "semantic_anchor": anchor,
                                },
                            )
                        )
                        json_doc_count += 1
            # Pattern B: section has sub_answers.X.answers.{en,hi,bn} (hod)
            elif "sub_answers" in section_data and isinstance(section_data["sub_answers"], dict):
                for sub_key, sub_data in section_data["sub_answers"].items():
                    if isinstance(sub_data, dict) and "answers" in sub_data:
                        anchor = sub_data.get("semantic_anchor", "")
                        for lang in ("en", "hi", "bn"):
                            text = sub_data["answers"].get(lang, "")
                            if text:
                                all_docs.append(
                                    Document(
                                        page_content=_anchor_text(text.strip(), anchor),
                                        metadata={
                                            "source": "combined_kb_json",
                                            "section": section_name,
                                            "subsection": sub_key,
                                            "language": lang,
                                            "semantic_anchor": anchor,
                                        },
                                    )
                                )
                                json_doc_count += 1
            # Pattern C: section has direct sub-entries like fees.cse_it_ece.{en,hi,bn}
            else:
                for sub_key, sub_data in section_data.items():
                    if sub_key in ("keywords", "semantic_anchor") or not isinstance(sub_data, dict):
                        continue
                    anchor = sub_data.get("semantic_anchor", "")
                    if "en" in sub_data and "hi" in sub_data and "bn" in sub_data:
                        for lang in ("en", "hi", "bn"):
                            text = sub_data.get(lang, "")
                            if text:
                                all_docs.append(
                                    Document(
                                        page_content=_anchor_text(text.strip(), anchor),
                                        metadata={
                                            "source": "combined_kb_json",
                                            "section": section_name,
                                            "subsection": sub_key,
                                            "language": lang,
                                            "semantic_anchor": anchor,
                                        },
                                    )
                                )
                                json_doc_count += 1

        # 2b. Also ingest quick_answers as English-only docs
        quick = kb_data.get("quick_answers", {})
        for qkey, qtext in quick.items():
            if isinstance(qtext, str) and qtext.strip():
                all_docs.append(
                    Document(
                        page_content=qtext.strip(),
                        metadata={
                            "source": "combined_kb_json",
                            "section": "quick_answers",
                            "subsection": qkey,
                            "language": "en",
                            "semantic_anchor": qkey,
                        },
                    )
                )
                json_doc_count += 1

        # 2c. Ingest key data sections from the FLAT knowledge_base.json (college, admission, placements, etc.)
        flat_kb_path = project_root / "backend" / "data" / "knowledge_base.json"
        if flat_kb_path.exists():
            logger.info("Processing data sections from knowledge_base.json...")
            with open(flat_kb_path, "r", encoding="utf-8") as f:
                flat_data = json.load(f)
            data_sections = [
                "college",
                "admission",
                "placements",
                "hostel",
                "infrastructure",
                "scholarships",
                "student_life",
                "academics",
                "fees_summary",
            ]
            for section in data_sections:
                section_data = flat_data.get(section, {})
                if not isinstance(section_data, dict):
                    continue
                parts = []

                def _collect(obj, depth=0):
                    if depth > 3:
                        return
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if isinstance(v, (str, int, float, bool)):
                                parts.append(f"{k}: {v}")
                            elif isinstance(v, dict):
                                _collect(v, depth + 1)
                            elif isinstance(v, list):
                                items = [str(x)[:100] for x in v[:5]]
                                if items:
                                    parts.append(f"{k}: {', '.join(items)}")
                    elif isinstance(obj, list):
                        for item in obj[:3]:
                            _collect(item, depth + 1)

                _collect(section_data)
                if parts:
                    text = ". ".join(parts)
                    all_docs.append(
                        Document(
                            page_content=text,
                            metadata={
                                "source": "knowledge_base_json",
                                "section": section,
                                "language": "en",
                                "semantic_anchor": section,
                            },
                        )
                    )
                    json_doc_count += 1

        logger.info(f"Added {json_doc_count} JSON documents")

    # 3. Re-ingest any admin-uploaded files from uploads/ directory
    # (so they aren't silently lost after a reindex)
    if uploads_dir.exists():
        logger.info(f"Processing uploaded files in {uploads_dir}...")
        for upload_file in uploads_dir.iterdir():
            if upload_file.is_file() and upload_file.suffix.lower() in {
                ".pdf",
                ".txt",
                ".csv",
                ".xlsx",
                ".xls",
                ".md",
            }:
                try:
                    chunks = await doc_processor.process_file(str(upload_file))
                    for chunk in chunks:
                        all_docs.append(
                            Document(
                                page_content=chunk["text"],
                                metadata={"source": chunk["source"], **chunk.get("metadata", {})},
                            )
                        )
                except Exception as e:
                    logger.error(f"Error processing upload {upload_file.name}: {e}")

    # 4. Add to Vector Store
    md_doc_count = len(all_docs) - json_doc_count
    if all_docs:
        logger.info(
            f"Adding {len(all_docs)} documents ({md_doc_count} markdown + {json_doc_count} JSON) to Vector Store..."
        )
        # Add in batches to avoid overwhelming the system
        batch_size = 50
        for i in range(0, len(all_docs), batch_size):
            batch = all_docs[i : i + batch_size]
            vector_store.add_documents(batch)
            logger.info(
                f"Ingested batch {i // batch_size + 1}/{(len(all_docs) - 1) // batch_size + 1}"
            )

        logger.info("Knowledge Base ingestion COMPLETE.")
    else:
        logger.warning("No documents found to ingest!")


if __name__ == "__main__":
    asyncio.run(ingest_kb())
