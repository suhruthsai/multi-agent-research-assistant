"""
Advanced vector store with hybrid search (BM25 + semantic), re-ranking, and
separate collections for paper abstracts and full-text chunks.
"""

import logging
import re
from typing import Optional

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, CrossEncoder

logger = logging.getLogger(__name__)

_EMBED_MODEL  = "all-MiniLM-L6-v2"
_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_PAPERS_COL   = "research_papers"
_CHUNKS_COL   = "paper_chunks"


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    return re.findall(r"\w+", text.lower())


class VectorStore:
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client    = chromadb.PersistentClient(path=persist_dir)
        self._embedder = SentenceTransformer(_EMBED_MODEL)
        self._reranker: Optional[CrossEncoder] = None  # lazy load

        self.papers_col = self.client.get_or_create_collection(
            name=_PAPERS_COL, metadata={"hnsw:space": "cosine"}
        )
        self.chunks_col = self.client.get_or_create_collection(
            name=_CHUNKS_COL, metadata={"hnsw:space": "cosine"}
        )

        # BM25 index (in-memory, rebuilt from ChromaDB on startup)
        self._bm25_corpus: list[list[str]] = []
        self._bm25_meta: list[dict] = []
        self._bm25: Optional[BM25Okapi] = None

    # ── Lazy reranker loading ─────────────────────────────────────────────
    def _get_reranker(self) -> CrossEncoder:
        if self._reranker is None:
            logger.info("Loading cross-encoder reranker: %s", _RERANK_MODEL)
            self._reranker = CrossEncoder(_RERANK_MODEL)
        return self._reranker

    # ── Paper management ──────────────────────────────────────────────────
    def add_papers(self, papers: list[dict]) -> None:
        if not papers:
            return

        docs, ids, metas = [], [], []
        seen_ids: set[str] = set()
        for p in papers:
            url = p.get("url", "")
            if not url:
                continue
            pid  = url.replace("https://", "").replace("http://", "").replace("/", "_")[:63]
            # Skip duplicates within the same batch to avoid ChromaDB DuplicateIDError
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            text = f"{p['title']}\n\n{p.get('abstract', '')}"
            docs.append(text)
            ids.append(pid)
            metas.append({
                "title":          p["title"],
                "authors":        ", ".join(p.get("authors", [])[:3]),
                "year":           str(p.get("year", "")),
                "url":            url,
                "source":         p.get("source", "unknown"),
                "citation_count": str(p.get("citation_count", 0)),
            })

        if not docs:
            return

        embs = self._embedder.encode(docs, show_progress_bar=False).tolist()
        self.papers_col.upsert(documents=docs, ids=ids, embeddings=embs, metadatas=metas)

        # Update BM25 index
        for doc, meta in zip(docs, metas):
            tokens = _tokenize(doc)
            self._bm25_corpus.append(tokens)
            self._bm25_meta.append(meta)
        if self._bm25_corpus:
            self._bm25 = BM25Okapi(self._bm25_corpus)

        logger.info("Added %d papers to vector store (total: %d)", len(docs), self.papers_col.count())

    # ── Semantic search ───────────────────────────────────────────────────
    def semantic_search(self, query: str, k: int = 15) -> list[dict]:
        if self.papers_col.count() == 0:
            return []
        q_emb = self._embedder.encode([query], show_progress_bar=False).tolist()
        n     = min(k, self.papers_col.count())
        res   = self.papers_col.query(query_embeddings=q_emb, n_results=n)
        papers = []
        for i, doc in enumerate(res["documents"][0]):
            meta = res["metadatas"][0][i]
            dist = res["distances"][0][i]
            papers.append({
                "title":           meta["title"],
                "abstract":        doc.split("\n\n", 1)[-1],
                "authors":         meta["authors"].split(", "),
                "year":            int(meta["year"]) if meta["year"] else 0,
                "url":             meta["url"],
                "source":          meta["source"],
                "citation_count":  int(meta["citation_count"]),
                "relevance_score": round(1 - dist, 4),
            })
        return sorted(papers, key=lambda x: x["relevance_score"], reverse=True)

    # ── BM25 keyword search ───────────────────────────────────────────────
    def keyword_search(self, query: str, k: int = 15) -> list[dict]:
        if not self._bm25 or not self._bm25_corpus:
            return []
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
        papers = []
        for idx, score in ranked:
            if score <= 0:
                continue
            meta = self._bm25_meta[idx]
            papers.append({
                "title":           meta["title"],
                "abstract":        "",
                "authors":         meta["authors"].split(", "),
                "year":            int(meta["year"]) if meta["year"] else 0,
                "url":             meta["url"],
                "source":          meta["source"],
                "citation_count":  int(meta["citation_count"]),
                "relevance_score": round(score, 4),
                "_bm25_rank":      len(papers),
            })
        return papers

    # ── Hybrid search (RRF fusion) ────────────────────────────────────────
    def hybrid_search(self, query: str, k: int = 20) -> list[dict]:
        """Reciprocal Rank Fusion of semantic + BM25 results."""
        semantic = self.semantic_search(query, k=k)
        keyword  = self.keyword_search(query, k=k)

        # RRF: score = Σ 1/(rank + 60)
        rrf_scores: dict[str, float] = {}
        paper_map:  dict[str, dict]  = {}

        for rank, p in enumerate(semantic):
            url = p["url"]
            rrf_scores[url] = rrf_scores.get(url, 0) + 1.0 / (rank + 60)
            paper_map[url] = p

        for rank, p in enumerate(keyword):
            url = p["url"]
            rrf_scores[url] = rrf_scores.get(url, 0) + 1.0 / (rank + 60)
            if url not in paper_map:
                paper_map[url] = p

        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for url, score in ranked[:k]:
            paper = paper_map[url].copy()
            paper["relevance_score"] = round(score, 4)
            results.append(paper)

        return results

    # ── Re-rank with cross-encoder ────────────────────────────────────────
    def rerank(self, query: str, papers: list[dict], top_n: int = 10) -> list[dict]:
        """Re-rank papers using a cross-encoder model for higher precision."""
        if not papers:
            return []

        reranker = self._get_reranker()
        pairs    = [(query, f"{p['title']}. {p.get('abstract', '')[:300]}") for p in papers]
        scores   = reranker.predict(pairs)

        for i, paper in enumerate(papers):
            paper["relevance_score"] = round(float(scores[i]), 4)

        papers.sort(key=lambda x: x["relevance_score"], reverse=True)
        return papers[:top_n]

    # ── Chunk management (for full-text PDF) ──────────────────────────────
    def add_chunks(self, chunks: list[dict]) -> None:
        """Store full-text chunks with embeddings."""
        if not chunks:
            return

        docs, ids, metas = [], [], []
        seen_ids: set[str] = set()
        for i, chunk in enumerate(chunks):
            chunk_id = f"{chunk.get('paper_url', 'unknown')}__chunk_{i}".replace("https://", "").replace("/", "_")[:63]
            if chunk_id in seen_ids:
                continue
            seen_ids.add(chunk_id)
            docs.append(chunk["text"])
            ids.append(chunk_id)
            metas.append({
                "paper_title": chunk.get("paper_title", ""),
                "paper_url":   chunk.get("paper_url", ""),
                "section":     chunk.get("section", ""),
                "page":        str(chunk.get("page", 0)),
                "chunk_index": str(i),
            })

        if not docs:
            return

        embs = self._embedder.encode(docs, show_progress_bar=False).tolist()
        self.chunks_col.upsert(documents=docs, ids=ids, embeddings=embs, metadatas=metas)
        logger.info("Added %d chunks to vector store", len(docs))

    def deep_search(self, query: str, k: int = 10) -> list[dict]:
        """Search full-text chunks for fine-grained retrieval."""
        if self.chunks_col.count() == 0:
            return []
        q_emb = self._embedder.encode([query], show_progress_bar=False).tolist()
        n     = min(k, self.chunks_col.count())
        res   = self.chunks_col.query(query_embeddings=q_emb, n_results=n)

        results = []
        for i, doc in enumerate(res["documents"][0]):
            meta = res["metadatas"][0][i]
            dist = res["distances"][0][i]
            results.append({
                "text":            doc,
                "paper_title":     meta["paper_title"],
                "paper_url":       meta["paper_url"],
                "section":         meta["section"],
                "page":            int(meta["page"]),
                "relevance_score": round(1 - dist, 4),
            })
        return sorted(results, key=lambda x: x["relevance_score"], reverse=True)

    # ── Clear ─────────────────────────────────────────────────────────────
    def clear(self) -> None:
        self.client.delete_collection(_PAPERS_COL)
        self.client.delete_collection(_CHUNKS_COL)
        self.papers_col = self.client.get_or_create_collection(
            _PAPERS_COL, metadata={"hnsw:space": "cosine"}
        )
        self.chunks_col = self.client.get_or_create_collection(
            _CHUNKS_COL, metadata={"hnsw:space": "cosine"}
        )
        self._bm25_corpus = []
        self._bm25_meta   = []
        self._bm25        = None