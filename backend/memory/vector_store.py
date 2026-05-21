"""ChromaDB vector store for semantic paper retrieval."""

import logging
import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
_MODEL = "all-MiniLM-L6-v2"
_COL   = "research_papers"


class VectorStore:
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client     = chromadb.PersistentClient(path=persist_dir)
        self._embedder  = SentenceTransformer(_MODEL)
        self.collection = self.client.get_or_create_collection(
            name=_COL, metadata={"hnsw:space": "cosine"}
        )

    def add_papers(self, papers: list[dict]) -> None:
        if not papers:
            return
        docs, ids, metas = [], [], []
        for p in papers:
            pid  = p["url"].replace("https://", "").replace("/", "_")[:63]
            text = f"{p['title']}\n\n{p['abstract']}"
            docs.append(text)
            ids.append(pid)
            metas.append({
                "title": p["title"],
                "authors": ", ".join(p["authors"][:3]),
                "year": str(p.get("year", "")),
                "url": p["url"],
                "source": p["source"],
                "citation_count": str(p.get("citation_count", 0)),
            })
        embs = self._embedder.encode(docs, show_progress_bar=False).tolist()
        self.collection.upsert(documents=docs, ids=ids, embeddings=embs, metadatas=metas)

    def semantic_search(self, query: str, k: int = 8) -> list[dict]:
        if self.collection.count() == 0:
            return []
        q_emb = self._embedder.encode([query], show_progress_bar=False).tolist()
        res   = self.collection.query(query_embeddings=q_emb, n_results=min(k, self.collection.count()))
        papers = []
        for i, doc in enumerate(res["documents"][0]):
            meta = res["metadatas"][0][i]
            dist = res["distances"][0][i]
            papers.append({
                "title": meta["title"],
                "abstract": doc.split("\n\n", 1)[-1],
                "authors": meta["authors"].split(", "),
                "year": int(meta["year"]) if meta["year"] else 0,
                "url": meta["url"],
                "source": meta["source"],
                "citation_count": int(meta["citation_count"]),
                "relevance_score": round(1 - dist, 4),
            })
        return sorted(papers, key=lambda x: x["relevance_score"], reverse=True)

    def clear(self) -> None:
        self.client.delete_collection(_COL)
        self.collection = self.client.get_or_create_collection(_COL)