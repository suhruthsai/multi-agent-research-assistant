"""
Academic sources — all free tier:
1. Semantic Scholar (200M+ papers)
2. arXiv (preprints)
3. OpenAlex (250M+ works, fully free)
4. CrossRef (metadata + DOI lookup)
"""

import asyncio
import logging
import httpx
import arxiv
from tenacity import retry, stop_after_attempt, wait_exponential

logger  = logging.getLogger(__name__)
SS_BASE  = "https://api.semanticscholar.org/graph/v1"
OA_BASE  = "https://api.openalex.org/works"
CR_BASE  = "https://api.crossref.org/works"


# ── Semantic Scholar ──────────────────────────────────────────────────────────
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=30))
async def search_semantic_scholar(query: str, limit: int = 15) -> list[dict]:
    fields = "paperId,title,abstract,authors,year,citationCount,url,referenceCount,references.paperId,references.title,references.url"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(
            f"{SS_BASE}/paper/search",
            params={"query": query, "limit": limit, "fields": fields},
            headers={"User-Agent": "MARA-ResearchAssistant/1.0"},
        )
        if r.status_code == 429:
            await asyncio.sleep(10)
            r.raise_for_status()
        r.raise_for_status()
        data = r.json()

    papers = []
    for p in data.get("data", []):
        abstract = p.get("abstract") or ""
        if len(abstract.split()) < 30:
            continue
        papers.append({
            "semantic_id":      p.get("paperId") or "",
            "title":           p.get("title", ""),
            "abstract":        abstract,
            "authors":         [a["name"] for a in p.get("authors", [])],
            "year":            p.get("year") or 0,
            "url":             p.get("url") or "",
            "source":          "semantic_scholar",
            "citation_count":  p.get("citationCount") or 0,
            "references":      [
                {
                    "semantic_id": ref.get("paperId") or "",
                    "title":       ref.get("title") or "",
                    "url":         ref.get("url") or "",
                }
                for ref in p.get("references", [])[:100]
            ],
            "relevance_score": 0.0,
        })
    return papers


# ── arXiv ─────────────────────────────────────────────────────────────────────
async def search_arxiv(query: str, max_results: int = 15) -> list[dict]:
    def _sync():
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = []
        for r in client.results(search):
            abstract = r.summary or ""
            if len(abstract.split()) < 30:
                continue
            results.append({
                "semantic_id":     "",
                "title":          r.title,
                "abstract":       abstract,
                "authors":        [str(a) for a in r.authors],
                "year":           r.published.year if r.published else 0,
                "url":            r.entry_id,
                "source":         "arxiv",
                "citation_count": 0,
                "references":     [],
                "relevance_score": 0.0,
            })
        return results
    return await asyncio.to_thread(_sync)


# ── OpenAlex (250M+ works, completely free) ───────────────────────────────────
async def search_openalex(query: str, limit: int = 15) -> list[dict]:
    """OpenAlex is fully free, no API key needed, 250M+ academic works."""
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(
                OA_BASE,
                params={
                    "search":      query,
                    "per-page":    limit,
                "select":      "title,abstract_inverted_index,authorships,publication_year,cited_by_count,doi",
                    "mailto":      "research@mara.ai",  # polite pool = faster responses
                },
            )
            r.raise_for_status()
            data = r.json()

        papers = []
        for w in data.get("results", []):
            title = w.get("title") or ""
            # OpenAlex stores abstracts as inverted index — reconstruct it
            inv = w.get("abstract_inverted_index") or {}
            if inv:
                words = [""] * (max(max(v) for v in inv.values()) + 1)
                for word, positions in inv.items():
                    for pos in positions:
                        words[pos] = word
                abstract = " ".join(words).strip()
            else:
                abstract = ""

            if not title or len(abstract.split()) < 30:
                continue

            authors = [
                a.get("author", {}).get("display_name", "")
                for a in w.get("authorships", [])[:3]
            ]
            doi = w.get("doi") or ""
            url = f"https://doi.org/{doi.replace('https://doi.org/', '')}" if doi else ""

            papers.append({
                "semantic_id":     "",
                "title":          title,
                "abstract":       abstract,
                "authors":        [a for a in authors if a],
                "year":           w.get("publication_year") or 0,
                "url":            url,
                "source":         "openalex",
                "citation_count": w.get("cited_by_count") or 0,
                "references":     [],
                "relevance_score": 0.0,
            })
        return papers
    except Exception as e:
        logger.warning("OpenAlex failed: %s", e)
        return []


# ── CrossRef (metadata + high citation papers) ────────────────────────────────
async def search_crossref(query: str, limit: int = 10) -> list[dict]:
    """CrossRef is free, great for finding highly cited papers with DOIs."""
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(
                CR_BASE,
                params={
                    "query":  query,
                    "rows":   limit,
                    "select": "title,abstract,author,published,is-referenced-by-count,DOI",
                },
                headers={"User-Agent": "MARA/1.0 (mailto:research@mara.ai)"},
            )
            r.raise_for_status()
            data = r.json()

        papers = []
        for item in data.get("message", {}).get("items", []):
            titles = item.get("title") or []
            title  = titles[0] if titles else ""
            abstract = item.get("abstract") or ""
            # Strip XML tags from CrossRef abstracts
            abstract = abstract.replace("<jats:p>", "").replace("</jats:p>", "").strip()

            if not title or len(abstract.split()) < 20:
                continue

            authors = [
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in item.get("author", [])[:3]
            ]
            pub = item.get("published", {}).get("date-parts", [[0]])[0]
            year = pub[0] if pub else 0
            doi  = item.get("DOI", "")

            papers.append({
                "semantic_id":     "",
                "title":          title,
                "abstract":       abstract,
                "authors":        [a for a in authors if a],
                "year":           year,
                "url":            f"https://doi.org/{doi}" if doi else "",
                "source":         "crossref",
                "citation_count": item.get("is-referenced-by-count") or 0,
                "references":     [],
                "relevance_score": 0.0,
            })
        return papers
    except Exception as e:
        logger.warning("CrossRef failed: %s", e)
        return []


# ── Combined search ───────────────────────────────────────────────────────────
async def search_all_sources(query: str, limit_each: int = 15) -> list[dict]:
    """Search all 4 free sources in parallel, deduplicate, sort by citations."""
    ss, ax, oa, cr = await asyncio.gather(
        search_semantic_scholar(query, limit_each),
        search_arxiv(query, limit_each),
        search_openalex(query, limit_each),
        search_crossref(query, 10),
        return_exceptions=True,
    )

    papers = []
    for source, name in [(ss, "Semantic Scholar"), (ax, "arXiv"),
                          (oa, "OpenAlex"), (cr, "CrossRef")]:
        if isinstance(source, list):
            papers.extend(source)
            logger.info("%s: %d papers", name, len(source))
        else:
            logger.warning("%s failed: %s", name, source)

    # Deduplicate by lowercase title
    seen, unique = set(), []
    for p in papers:
        k = p["title"].lower().strip()[:80]
        if k and k not in seen:
            seen.add(k)
            unique.append(p)

    # Pre-sort by citation count
    unique.sort(key=lambda x: x["citation_count"], reverse=True)
    logger.info("Total unique papers across all sources: %d", len(unique))
    return unique
