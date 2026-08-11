"""Fixed-size overlapping chunks, splitting on paragraph boundaries where possible
(plan Section 8). Dependency-free; ~500 tokens ≈ ~2000 chars for English prose.
"""
import re

# ~4 chars/token is a reasonable heuristic for English; 500 tokens ≈ 2000 chars
CHUNK_SIZE_CHARS = 2000
CHUNK_OVERLAP_CHARS = 200
PARAGRAPH_SPLIT = re.compile(r"\n{2,}")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph boundaries."""
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in PARAGRAPH_SPLIT.split(text) if p.strip()]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # A single paragraph too long for one chunk → hard-split it.
        while len(para) > chunk_size:
            piece = para[:chunk_size]
            chunks.append(piece)
            para = para[chunk_size - overlap:]
        if not current:
            current = para
        elif len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}"
        else:
            chunks.append(current)
            # overlap: reuse the tail of the previous chunk
            current = current[-overlap:] + "\n\n" + para if overlap else para

    if current:
        chunks.append(current)

    return chunks
