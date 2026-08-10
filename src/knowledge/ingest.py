from __future__ import annotations

import hashlib
import re
from pathlib import Path

from src.knowledge.models import KnowledgeDocument

_PDF_READER = None


def _pdf_extractor() -> object | None:
    """Lazily import a PDF text extractor so the KB works without PDF tooling."""
    global _PDF_READER
    if _PDF_READER is None:
        try:
            from pypdf import PdfReader

            _PDF_READER = PdfReader
        except ImportError:
            _PDF_READER = False
    return _PDF_READER if _PDF_READER else None


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _doc_id_for(path: Path) -> str:
    raw = f"{path.name}:{path.stat().st_size}:{path.stat().st_mtime_ns}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def extract_text(path: Path) -> tuple[str, str]:
    """Return (title, text) for a .txt/.md/.pdf file.

    Plain text formats are read directly; PDFs are extracted with pypdf when
    available. The operator-facing CLI raises a clear error for PDFs when no
    extractor is installed so they can either install pypdf or upload the
    document as txt/md instead.
    """
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md", ".markdown", ".text"):
        text = path.read_text(encoding="utf-8", errors="replace")
    elif suffix == ".pdf":
        reader_cls = _pdf_extractor()
        if reader_cls is None:
            raise RuntimeError(
                f"Cannot read {path.name}: no PDF extractor installed. "
                "Install pypdf (pip install pypdf) or convert the document to txt."
            )
        reader = reader_cls(str(path))
        text = "\n".join(
            (page.extract_text() or "") for page in reader.pages
        )
    else:
        raise ValueError(
            f"Unsupported document type '{suffix}' for {path.name}. "
            "Supported: .txt, .md, .pdf"
        )
    title = re.sub(r"\.[A-Za-z0-9]+$", "", path.name)
    return title, text


def load_document(path: Path) -> KnowledgeDocument:
    """Extract a single file into a KnowledgeDocument keyed by content hash.

    The doc_id is derived from name+size+mtime so re-ingesting an *updated*
    document naturally replaces the old one (content changes -> new id) while
    an identical re-upload keeps the same id and is treated as a no-op update.
    """
    path = Path(path)
    title, text = extract_text(path)
    return KnowledgeDocument(
        doc_id=_doc_id_for(path),
        title=title,
        source=str(path.resolve()),
        text=text,
        metadata={"bytes": path.stat().st_size, "updated_ns": path.stat().st_mtime_ns},
    )


def load_documents(path: Path) -> list[KnowledgeDocument]:
    """Load every supported file under a path (single file or directory)."""
    path = Path(path)
    if path.is_file():
        return [load_document(path)]
    if path.is_dir():
        files = [
            p
            for p in sorted(path.iterdir())
            if p.is_file() and p.suffix.lower() in (".txt", ".md", ".markdown", ".text", ".pdf")
        ]
        return [load_document(p) for p in files]
    raise ValueError(f"Not a file or directory: {path}")
