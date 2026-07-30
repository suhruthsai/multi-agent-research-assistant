"""
Lightweight in-memory vector store using pure BM25 search.
No sentence-transformers or ChromaDB — works within 512MB free-tier limits.
"""

import logging
import re
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    return re.findall(r"\w+", text.lower())


class VectorStore:
    def __init__(self, persist_dir: str = "./chroma_db"):
        # persist_dir kept for API compatibility but unused (in-memory only)
        self._papers:       list[dict] = []   # raw paper dicts
        self._paper_tokens: list[list[str]] = []
        self._bm25_papers:  BM25Okapi | None = None

        self._chunks:       list[dict] = []   # raw chunk dicts
        self._chunk_tokens: list[list[str]] = []
        self._bm25_chunks:  BM25Okapi | None = None

        logger.info("[VectorStore] Lightweight BM25-only store initialised.")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _rebuild_paper_index(self) -> None:
        if self._paper_tokens:
            self._bm25_papers = BM25Okapi(self._paper_tokens)

    def _rebuild_chunk_index(self) -> None:
        if self._chunk_tokens:
            self._bm25_chunks = BM25Okapi(self._chunk_tokens)

    # ── Paper management ─────────────────────────────────────────────────────
    def add_papers(self, papers: list[dict]) -> None:
        if not papers:
            return

        seen_urls = {p.get("url", "") for p in self._papers}
        added = 0
        for p in papers:
            url = p.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            text = f"{p.get('title', '')} {p.get('abstract', '')}"
            self._papers.append(p)
            self._paper_tokens.append(_tokenize(text))
            added += 1

        if added:
            self._rebuild_paper_index()
            logger.info("[VectorStore] Added %d papers (total: %d)", added, len(self._papers))

    # ── BM25 keyword search ───────────────────────────────────────────────────
    def keyword_search(self, query: str, k: int = 15) -> list[dict]:
        if not self._bm25_papers or not self._papers:
            return []
        tokens = _tokenize(query)
        scores = self._bm25_papers.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
        results = []
        for idx, score in ranked:
            if score <= 0:
                continue
            paper = self._papers[idx].copy()
            paper["relevance_score"] = round(float(score), 4)
            results.append(paper)
        return results

    # ── Hybrid search (BM25 only — same API as before) ────────────────────────
    def hybrid_search(self, query: str, k: int = 20) -> list[dict]:
        """BM25 search (replaces BM25+semantic hybrid — same interface)."""
        return self.keyword_search(query, k=k)

    # ── Rerank (BM25 score-based — same API as cross-encoder) ────────────────
    def rerank(self, query: str, papers: list[dict], top_n: int = 10) -> list[dict]:
        """Re-rank using BM25 scores (replaces cross-encoder — same interface)."""
        if not papers:
            return []
        tokens = _tokenize(query)
        scored = []
        for p in papers:
            text = f"{p.get('title', '')} {p.get('abstract', '')}"
            doc_tokens = _tokenize(text)
            # Simple term-overlap score as lightweight reranker
            query_set = set(tokens)
            doc_set   = set(doc_tokens)
            overlap   = len(query_set & doc_set)
            score     = overlap / (len(query_set) + 1e-9)
            p = p.copy()
            p["relevance_score"] = round(
                0.7 * p.get("relevance_score", 0) + 0.3 * score, 4
            )
            scored.append(p)
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:top_n]

    # ── Chunk management ─────────────────────────────────────────────────────
    def add_chunks(self, chunks: list[dict]) -> None:
        if not chunks:
            return
        added = 0
        for chunk in chunks:
            text = chunk.get("text", "")
            if not text:
                continue
            self._chunks.append(chunk)
            self._chunk_tokens.append(_tokenize(text))
            added += 1
        if added:
            self._rebuild_chunk_index()
            logger.info("[VectorStore] Added %d chunks (total: %d)", added, len(self._chunks))

    def deep_search(self, query: str, k: int = 10) -> list[dict]:
        """BM25 search over full-text chunks."""
        if not self._bm25_chunks or not self._chunks:
            return []
        tokens = _tokenize(query)
        scores = self._bm25_chunks.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
        results = []
        for idx, score in ranked:
            if score <= 0:
                continue
            chunk = self._chunks[idx].copy()
            chunk["relevance_score"] = round(float(score), 4)
            results.append(chunk)
        return results

    # ── Clear ─────────────────────────────────────────────────────────────────
    def clear(self) -> None:
        self._papers       = []
        self._paper_tokens = []
        self._bm25_papers  = None
        self._chunks       = []
        self._chunk_tokens = []
        self._bm25_chunks  = None
        logger.info("[VectorStore] Cleared all in-memory data.")
