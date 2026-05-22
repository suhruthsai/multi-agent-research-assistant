"""
PDF processor for downloading, parsing, and chunking research papers.
Uses PyMuPDF (fitz) for PDF text extraction.
"""

import asyncio
import logging
import re
from typing import Optional

import fitz  # PyMuPDF
import httpx

logger = logging.getLogger(__name__)

# Common section headers in academic papers
_SECTION_PATTERNS = re.compile(
    r"^(?:\d+\.?\s*)?"
    r"(Abstract|Introduction|Background|Related Work|Methods?|Methodology|"
    r"Approach|Experiment(?:s|al)?|Results?|Discussion|Conclusion(?:s)?|"
    r"References|Acknowledgment(?:s)?|Appendix|Supplementary)"
    r"(?:\s|$)",
    re.IGNORECASE,
)


async def download_pdf(url: str, timeout: int = 30) -> Optional[bytes]:
    """Download a PDF from a URL. Handles arXiv, DOI redirects, etc."""
    # Convert arXiv abstract URLs to PDF URLs
    if "arxiv.org/abs/" in url:
        url = url.replace("/abs/", "/pdf/") + ".pdf"
    elif "arxiv.org/html/" in url:
        url = url.replace("/html/", "/pdf/") + ".pdf"

    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True,
            headers={"User-Agent": "MARA-ResearchAssistant/1.0"}
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                content_type = resp.headers.get("content-type", "")
                if "pdf" in content_type or resp.content[:5] == b"%PDF-":
                    logger.info("Downloaded PDF: %s (%d bytes)", url, len(resp.content))
                    return resp.content
            logger.warning("PDF download failed for %s: status=%d", url, resp.status_code)
            return None
    except Exception as e:
        logger.warning("PDF download error for %s: %s", url, e)
        return None


def parse_pdf(pdf_bytes: bytes) -> str:
    """Extract full text from PDF bytes using PyMuPDF."""
    try:
        doc  = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = []
        for page in doc:
            page_text = page.get_text("text")
            if page_text.strip():
                text.append(page_text)
        doc.close()
        full_text = "\n\n".join(text)
        logger.info("Parsed PDF: %d pages, %d characters", len(text), len(full_text))
        return full_text
    except Exception as e:
        logger.warning("PDF parse error: %s", e)
        return ""


def _detect_section(line: str) -> Optional[str]:
    """Detect if a line is a section header."""
    stripped = line.strip()
    if len(stripped) > 80 or len(stripped) < 3:
        return None
    match = _SECTION_PATTERNS.match(stripped)
    if match:
        return match.group(1).title()
    return None


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
    paper_title: str = "",
    paper_url: str = "",
) -> list[dict]:
    """
    Split text into overlapping chunks with metadata.
    Tries to respect sentence boundaries.
    """
    if not text or len(text) < 100:
        return []

    # Clean up text
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current_chunk: list[str] = []
    current_len = 0
    current_section = "Unknown"

    for sentence in sentences:
        # Check if this is a section header
        section = _detect_section(sentence)
        if section:
            current_section = section

        words = sentence.split()
        sentence_len = len(words)

        if current_len + sentence_len > chunk_size and current_chunk:
            # Save current chunk
            chunk_text_str = " ".join(current_chunk)
            if len(chunk_text_str.split()) >= 20:  # minimum viable chunk
                chunks.append({
                    "text":        chunk_text_str,
                    "paper_title": paper_title,
                    "paper_url":   paper_url,
                    "section":     current_section,
                    "page":        0,
                    "chunk_index": len(chunks),
                })

            # Overlap: keep last few sentences
            overlap_words = 0
            overlap_start = len(current_chunk)
            for j in range(len(current_chunk) - 1, -1, -1):
                overlap_words += len(current_chunk[j].split())
                if overlap_words >= overlap:
                    overlap_start = j
                    break
            current_chunk = current_chunk[overlap_start:]
            current_len = sum(len(s.split()) for s in current_chunk)

        current_chunk.append(sentence)
        current_len += sentence_len

    # Don't forget the last chunk
    if current_chunk:
        chunk_text_str = " ".join(current_chunk)
        if len(chunk_text_str.split()) >= 20:
            chunks.append({
                "text":        chunk_text_str,
                "paper_title": paper_title,
                "paper_url":   paper_url,
                "section":     current_section,
                "page":        0,
                "chunk_index": len(chunks),
            })

    logger.info("Chunked into %d chunks from %d chars", len(chunks), len(text))
    return chunks


async def process_paper(paper: dict) -> list[dict]:
    """Full pipeline: download → parse → chunk a single paper."""
    url = paper.get("url", "")
    if not url:
        return []

    pdf_bytes = await download_pdf(url)
    if not pdf_bytes:
        return []

    text = await asyncio.to_thread(parse_pdf, pdf_bytes)
    if not text:
        return []

    chunks = chunk_text(
        text,
        paper_title=paper.get("title", ""),
        paper_url=url,
    )
    return chunks


async def process_papers_batch(papers: list[dict], max_papers: int = 5, timeout: int = 60) -> list[dict]:
    """Process multiple papers in parallel with a global timeout."""
    selected = papers[:max_papers]
    all_chunks = []
    processed  = 0

    try:
        tasks = [process_paper(p) for p in selected]
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=timeout,
        )
        for result in results:
            if isinstance(result, list) and result:
                all_chunks.extend(result)
                processed += 1
            elif isinstance(result, Exception):
                logger.warning("Paper processing error: %s", result)
    except asyncio.TimeoutError:
        logger.warning("PDF batch processing timed out after %ds", timeout)

    logger.info("Processed %d/%d papers → %d chunks", processed, len(selected), len(all_chunks))
    return all_chunks
