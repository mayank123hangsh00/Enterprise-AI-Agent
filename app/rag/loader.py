"""Document loader — reads .txt and .pdf files from the documents directory."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

DOCUMENTS_DIR = Path(__file__).resolve().parents[2] / "documents"


@dataclass
class Document:
    content: str
    source: str          # original filename, e.g. "company_leave_policy.txt"
    metadata: dict = field(default_factory=dict)


def load_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def load_pdf(path: Path) -> str:
    try:
        import PyPDF2  # noqa: PLC0415

        text_parts: list[str] = []
        with path.open("rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except ImportError:
        logger.warning("PyPDF2 not installed. Skipping %s", path.name)
        return ""
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to read PDF %s: %s", path.name, exc)
        return ""


def load_documents(directory: Path = DOCUMENTS_DIR) -> List[Document]:
    """Load all supported documents from *directory*."""
    documents: List[Document] = []

    if not directory.exists():
        logger.warning("Documents directory not found: %s", directory)
        return documents

    for path in sorted(directory.iterdir()):
        if path.suffix.lower() == ".txt":
            content = load_txt(path)
        elif path.suffix.lower() == ".pdf":
            content = load_pdf(path)
        else:
            continue  # skip unsupported formats

        if not content.strip():
            logger.warning("Empty content in %s — skipping.", path.name)
            continue

        documents.append(
            Document(
                content=content,
                source=path.name,
                metadata={"file_type": path.suffix.lstrip(".")},
            )
        )
        logger.info("Loaded document: %s (%d chars)", path.name, len(content))

    logger.info("Total documents loaded: %d", len(documents))
    return documents
