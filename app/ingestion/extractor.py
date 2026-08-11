"""Extract raw text from uploaded files (plan Section 8)."""
from pathlib import Path


def extract_text(path: str | Path) -> str:
    """PDF → pypdf; .txt/.md → plain read. Raises ValueError on unsupported types."""
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(p))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)

    if suffix in (".txt", ".md"):
        return p.read_text(encoding="utf-8", errors="replace")

    raise ValueError(f"Unsupported file type: {suffix} (supported: .pdf, .txt, .md)")
