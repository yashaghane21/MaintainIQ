"""Document text extraction, cleaning and chunking."""

import io
import re
from dataclasses import dataclass

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass
class Page:
    page_number: int | None   # 1-based for PDFs; None for plain text
    text: str


@dataclass
class Chunk:
    chunk_index: int
    page_number: int | None
    text: str


def extract_pages(filename: str, data: bytes) -> list[Page]:
    """Extract text per page. Raises ValueError for unsupported/unreadable files."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        try:
            reader = PdfReader(io.BytesIO(data))
            pages = [Page(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
        except (PdfReadError, ValueError, KeyError) as exc:
            raise ValueError(f"Could not read PDF: {exc}") from exc
    elif lower.endswith(".txt"):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        pages = [Page(None, text)]
    else:
        raise ValueError("Unsupported file type. Upload a .pdf or .txt file.")

    pages = [Page(p.page_number, clean_text(p.text)) for p in pages]
    if not any(p.text for p in pages):
        raise ValueError("No extractable text found (scanned PDFs without a text layer are not supported).")
    return pages


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS.sub("", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # join hyphenated line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_long(paragraph: str, size: int) -> list[str]:
    """Split an oversized paragraph on sentence boundaries, falling back to hard cuts."""
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    parts, current = [], ""
    for sentence in sentences:
        while len(sentence) > size:
            if current:
                parts.append(current)
                current = ""
            parts.append(sentence[:size])
            sentence = sentence[size:]
        if len(current) + len(sentence) + 1 > size and current:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts


def _tail(text: str, overlap: int) -> str:
    if overlap <= 0 or len(text) <= overlap:
        return ""
    tail = text[-overlap:]
    # Prefer starting the overlap at a sentence boundary so excerpts read cleanly.
    sentence = re.search(r"[.!?]\s+", tail)
    if sentence:
        return tail[sentence.end():]
    space = tail.find(" ")
    return tail[space + 1:] if space != -1 else tail


def chunk_pages(pages: list[Page], size: int = 900, overlap: int = 150) -> list[Chunk]:
    """Paragraph-aware chunking that never crosses page boundaries (keeps page citations exact)."""
    chunks: list[Chunk] = []
    for page in pages:
        paragraphs = [p.strip() for p in page.text.split("\n\n") if p.strip()]
        current = ""
        for para in paragraphs:
            pieces = _split_long(para, size) if len(para) > size else [para]
            for piece in pieces:
                if current and len(current) + len(piece) + 2 > size:
                    chunks.append(Chunk(len(chunks), page.page_number, current))
                    carry = _tail(current, overlap)
                    current = f"{carry}\n\n{piece}" if carry else piece
                else:
                    current = f"{current}\n\n{piece}" if current else piece
        if current:
            chunks.append(Chunk(len(chunks), page.page_number, current))
    return chunks
