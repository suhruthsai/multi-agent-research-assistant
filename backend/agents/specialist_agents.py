import json
import asyncio
import logging
import os
from groq import AsyncGroq
from backend.state import AgentState
from backend.memory.vector_store import VectorStore
from backend.memory.knowledge_graph import KnowledgeGraph
from backend.tools.academic_tools import search_all_sources
from backend.tools.query_expansion import expand_query
from backend.tools.pdf_processor import process_papers_batch

logger = logging.getLogger(__name__)
_groq_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq_client

# Model fallback list
MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# Tuning
MIN_RELEVANCE_SCORE      = 0.30
TOP_N_FOR_CONFIDENCE     = 5
MIN_PAPERS_FOR_SYNTHESIS = 5
GROQ_TIMEOUT_SECONDS     = 60

vs = VectorStore()
kg = KnowledgeGraph()


def _papers_text(papers: list[dict], n: int = 5) -> str:
    """Shorter paper text — fewer tokens = faster + cheaper."""
    lines = []
    for i, p in enumerate(papers[:n], 1):
        lines.append(
            f"[{i}] {p['title']} ({p.get('year', 'N/A')})\n"
            f"    Authors: {', '.join(p.get('authors', [])[:3])}\n"
            f"    {p.get('abstract', '')[:300]}..."
        )
    return "\n\n".join(lines)


def _chunks_text(chunks: list[dict], n: int = 5) -> str:
    """Format chunks for LLM context."""
    lines = []
    for i, c in enumerate(chunks[:n], 1):
        lines.append(
            f"[Chunk {i}] From: {c.get('paper_title', 'Unknown')} (Section: {c.get('section', 'N/A')})\n"
            f"    {c['text'][:400]}..."
        )
    return "\n\n".join(lines)


async def _groq(system: str, user: str, max_tokens: int = 1500) -> str:
    """Call Groq with automatic model fallback, 60s timeout, retry on rate limit."""
    for model in MODELS:
        try:
            logger.info("[Groq] trying model: %s", model)
            response = await asyncio.wait_for(
                _get_groq_client().chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=0.2,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                ),
                timeout=GROQ_TIMEOUT_SECONDS,
            )
            logger.info("[Groq] ✅ success with model: %s", model)
            return response.choices[0].message.content or ""
        except asyncio.TimeoutError:
            logger.warning("[Groq] ⏱ timeout on model %s — trying next", model)
            continue
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["decommissioned", "rate_limit", "429", "529", "Rate limit"]):
                logger.warning("[Groq] ⚠️ rate limit on %s — waiting 15s then trying next", model)
                await asyncio.sleep(15)
                continue
            logger.error("[Groq] ❌ unexpected error on %s: %s", model, err)
            raise
    logger.error("[Groq] all models exhausted")
    return "Unable to generate response — all models exhausted. Please try again."


def _parse_json(raw: str) -> list:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        result = json.loads(cleaned)
        return result if isinstance(result, list) else [result]
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end   = cleaned.rfind("]") + 1
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except Exception:
                pass
    return []


def _filter_quality_papers(papers: list[dict]) -> list[dict]:
    filtered = [p for p in papers if p.get("relevance_score", 0) >= MIN_RELEVANCE_SCORE]
    if len(filtered) < MIN_PAPERS_FOR_SYNTHESIS:
        filtered = sorted(papers, key=lambda x: x.get("relevance_score", 0), reverse=True)[:8]
    def score(p):
        return p.get("relevance_score", 0) + min(p.get("citation_count", 0) / 500, 1.0) * 0.15
    return sorted(filtered, key=score, reverse=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. PLANNER AGENT — Creates a structured research plan
# ═══════════════════════════════════════════════════════════════════════════════
async def planner_agent(state: AgentState) -> dict:
    """Analyze the query and create a structured research plan."""
    system = """You are a research planning specialist. Given a research query, create a 
structured research plan. Be concise and actionable.

Use these exact headers and provide 2-3 bullet points under each:
## Key Subtopics
## Search Strategy
## Evidence Types Needed
## Expected Challenges"""

    user = f"Research query: {state['query']}"
    plan = await _groq(system, user, max_tokens=800)

    return {
        "research_plan": plan,
        "status":        "plan_complete",
        "messages":      [{"role": "planner_agent",
                           "content": f"Research plan created for: {state['query'][:50]}..."}],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SEARCH AGENT — Hybrid search with query expansion + PDF processing
# ═══════════════════════════════════════════════════════════════════════════════
async def search_agent(state: AgentState) -> dict:
    """Search with query expansion, hybrid retrieval, re-ranking, and PDF processing."""
    query = state["query"]

    # On retry iterations, augment the query
    if state.get("iteration", 0) > 0:
        query = f"{query} recent advances systematic review"

    # Step 1: Query expansion — get alternative search queries
    try:
        alt_queries = await expand_query(query)
    except Exception as e:
        logger.warning("Query expansion failed: %s", e)
        alt_queries = []

    all_queries = [query] + alt_queries
    logger.info("Searching with %d queries: %s", len(all_queries), all_queries)

    # Step 2: Search all sources with all queries in parallel
    search_tasks = [search_all_sources(q, limit_each=10) for q in all_queries]
    results = await asyncio.gather(*search_tasks, return_exceptions=True)

    all_papers = []
    for r in results:
        if isinstance(r, list):
            all_papers.extend(r)
        else:
            logger.warning("Search batch failed: %s", r)

    # Deduplicate by title
    seen, unique = set(), []
    for p in all_papers:
        k = p["title"].lower().strip()[:80]
        if k and k not in seen:
            seen.add(k)
            unique.append(p)

    # Step 3: Add to vector store and build knowledge graph
    vs.add_papers(unique)
    kg.add_papers(unique)

    # Step 4: Hybrid search (BM25 + semantic with RRF)
    hybrid_results = vs.hybrid_search(query, k=20)

    # Step 5: Re-rank with cross-encoder
    reranked = vs.rerank(query, hybrid_results, top_n=12)
    quality  = _filter_quality_papers(reranked)

    # Step 6: Extract topics for knowledge graph
    topic_texts = []
    for p in quality[:5]:
        topic_texts.append(f"- {p['title']}")

    try:
        topic_raw = await _groq(
            "Extract 5-8 key research topics/themes from these paper titles. "
            "Return ONLY a JSON array of short topic strings.",
            "\n".join(topic_texts),
            max_tokens=200,
        )
        topics = _parse_json(topic_raw)
        if isinstance(topics, list):
            flat_topics = [str(t) for t in topics if isinstance(t, str)]
            for p in quality:
                kg.add_topics(p.get("url", ""), flat_topics)
        else:
            flat_topics = []
    except Exception as e:
        logger.warning("Topic extraction failed: %s", e)
        flat_topics = []

    # Step 7: Process PDFs for full-text chunks (top 3 papers, async with timeout)
    pdf_chunks = []
    pdf_count  = 0
    try:
        pdf_chunks = await process_papers_batch(quality, max_papers=3, timeout=45)
        if pdf_chunks:
            vs.add_chunks(pdf_chunks)
            pdf_count = len(set(c.get("paper_url", "") for c in pdf_chunks))
    except Exception as e:
        logger.warning("PDF processing failed: %s", e)

    return {
        "papers":              quality,
        "chunks":              pdf_chunks,
        "topics":              flat_topics,
        "pdf_processed_count": pdf_count,
        "status":              "search_complete",
        "messages":            [{"role": "search_agent",
                                 "content": f"Retrieved {len(quality)} papers (hybrid search), "
                                            f"processed {pdf_count} PDFs → {len(pdf_chunks)} chunks"}],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CRITIC AGENT — Evaluates paper quality
# ═══════════════════════════════════════════════════════════════════════════════
async def critic_agent(state: AgentState) -> dict:
    top_papers = state.get("papers", [])[:5]
    system = """You are a peer reviewer. Evaluate each paper briefly.
Return ONLY a valid JSON array. Each object must have:
- paper_title: string
- score: float (0.0 to 1.0)
- strengths: list of 1-2 strings
- weaknesses: list of 1 string
- contradictions: list (empty if none)

Score guide: 0.9+=landmark, 0.75-0.9=solid, 0.6-0.75=adequate, below 0.6=weak"""

    user = f"Query: {state['query']}\n\nPapers:\n{_papers_text(top_papers, 5)}"
    raw       = await _groq(system, user, max_tokens=1500)
    critiques = _parse_json(raw)
    scores    = sorted([c.get("score", 0.5) for c in critiques
                        if isinstance(c.get("score"), (int, float))], reverse=True)
    top_scores = scores[:TOP_N_FOR_CONFIDENCE]
    confidence = round(sum(top_scores) / len(top_scores), 2) if top_scores else 0.6

    return {
        "critiques":        critiques,
        "confidence_score": confidence,
        "status":           "critique_complete",
        "messages":         [{"role": "critic_agent",
                              "content": f"Critiqued {len(critiques)} papers. Confidence: {confidence}"}],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SYNTHESIS AGENT — Cross-paper analysis with deep search support
# ═══════════════════════════════════════════════════════════════════════════════
async def synthesis_agent(state: AgentState) -> dict:
    scored = {c.get("paper_title", "").lower(): c.get("score", 0) for c in state.get("critiques", [])}
    strong = [p for p in state.get("papers", [])
              if scored.get(p["title"].lower(), 0.5) >= 0.55] or state.get("papers", [])[:6]

    # Get deep search results from full-text chunks
    deep_context = ""
    try:
        deep_results = vs.deep_search(state["query"], k=5)
        if deep_results:
            deep_context = f"\n\n## Detailed Excerpts from Full Papers:\n{_chunks_text(deep_results, 5)}"
    except Exception as e:
        logger.warning("Deep search failed: %s", e)

    system = """You are a research synthesizer. Reason ACROSS papers and evidence.
Use these exact headers:
## Key Agreements
## Contradictions  
## Methodological Gaps
## Emerging Trends
## Collective Conclusion
Be concise, specific, and cite papers by [Author et al., Year] format."""

    user = (
        f"Query: {state['query']}\n\n"
        f"Papers:\n{_papers_text(strong, 6)}"
        f"{deep_context}"
    )
    synthesis = await _groq(system, user, max_tokens=2500)

    return {
        "synthesis": synthesis,
        "status":    "synthesis_complete",
        "messages":  [{"role": "synthesis_agent",
                       "content": f"Synthesis done with {len(strong)} papers + deep search. "
                                  f"Confidence: {state.get('confidence_score', 0)}"}],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 5. WRITER AGENT — Generates the final research report
# ═══════════════════════════════════════════════════════════════════════════════
async def writer_agent(state: AgentState) -> dict:
    # Get deep search results for more detailed writing
    deep_context = ""
    try:
        deep_results = vs.deep_search(state["query"], k=5)
        if deep_results:
            deep_context = f"\n\nDetailed excerpts:\n{_chunks_text(deep_results, 5)}"
    except Exception:
        pass

    system = """You are a scientific report writer. Write a comprehensive, well-structured
Markdown report with inline citations [Author et al., Year].

Structure your report with these exact sections:
# [Descriptive Title for the Research Topic]
## Executive Summary
## Background & Context
## Key Findings
## Methodological Analysis
## Emerging Trends & Future Directions
## Open Questions
## References

Guidelines:
- Use [Author et al., Year] citation format throughout
- Be specific — cite actual findings, numbers, and methods
- Each section should have 2-4 substantive paragraphs
- The report should be thorough and publication-quality"""

    user = (
        f"Query: {state['query']}\n\n"
        f"Research Plan:\n{state.get('research_plan', 'N/A')}\n\n"
        f"Synthesis:\n{state.get('synthesis', '')}\n\n"
        f"Papers:\n{_papers_text(state.get('papers', []), 8)}"
        f"{deep_context}"
    )
    report = await _groq(system, user, max_tokens=4000)

    return {
        "report":   report,
        "status":   "report_complete",
        "messages": [{"role": "writer_agent", "content": "Report generated"}],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 6. FACT-CHECKER AGENT — Verifies claims against source papers
# ═══════════════════════════════════════════════════════════════════════════════
async def fact_checker_agent(state: AgentState) -> dict:
    """Verify claims in the report against source papers."""
    report = state.get("report", "")
    papers = state.get("papers", [])

    if not report or not papers:
        return {
            "fact_check_results": [],
            "status":             "fact_check_complete",
            "messages":           [{"role": "fact_checker_agent",
                                    "content": "No report to fact-check"}],
        }

    system = """You are a scientific fact-checker. Given a research report and source papers,
identify the key factual claims in the report and verify whether each claim is 
supported by the source papers.

Return ONLY a valid JSON array. Each object must have:
- claim: string (the specific claim from the report)
- status: string (one of: "verified", "unverified", "contradicted")
- evidence: string (brief explanation of supporting/contradicting evidence)
- source_paper: string (title of the supporting paper, or "None" if unverified)

Check 5-8 key claims. Focus on:
- Specific factual assertions
- Statistical claims or numbers
- Attribution of findings to specific papers
- Methodological claims"""

    user = (
        f"Report:\n{report[:2000]}\n\n"
        f"Source Papers:\n{_papers_text(papers, 6)}"
    )

    raw     = await _groq(system, user, max_tokens=2000)
    results = _parse_json(raw)

    # Ensure proper structure
    checked = []
    for r in results:
        if isinstance(r, dict) and "claim" in r:
            checked.append({
                "claim":        r.get("claim", ""),
                "status":       r.get("status", "unverified"),
                "evidence":     r.get("evidence", ""),
                "source_paper": r.get("source_paper", "None"),
            })

    verified_count = sum(1 for c in checked if c["status"] == "verified")
    total          = len(checked)

    return {
        "fact_check_results": checked,
        "status":             "fact_check_complete",
        "messages":           [{"role": "fact_checker_agent",
                                "content": f"Verified {verified_count}/{total} claims"}],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 7. HYPOTHESIS AGENT — Generates novel research hypotheses
# ═══════════════════════════════════════════════════════════════════════════════
async def hypothesis_agent(state: AgentState) -> dict:
    system = """Generate 5 novel research hypotheses based on the synthesis and findings.
Return ONLY a valid JSON array. Each object must have:
- hypothesis: string (clear, testable hypothesis)
- justification: string (why this hypothesis is promising)
- confidence: float (0.0–1.0, how confident you are)
- methodology_hint: string (brief suggestion for how to test it)"""

    user = (
        f"Query: {state['query']}\n\n"
        f"Synthesis:\n{state.get('synthesis', '')}\n\n"
        f"Key topics: {', '.join(state.get('topics', []))}"
    )
    raw        = await _groq(system, user, max_tokens=2000)
    hypotheses = _parse_json(raw)
    hypotheses.sort(key=lambda h: h.get("confidence", 0), reverse=True)

    # Finalize knowledge graph data
    graph_data = kg.to_json()

    return {
        "hypotheses": hypotheses,
        "graph_data": graph_data,
        "status":     "hypotheses_complete",
        "messages":   [{"role": "hypothesis_agent",
                        "content": f"Generated {len(hypotheses)} hypotheses. "
                                   f"Knowledge graph: {graph_data.get('stats', {}).get('total_nodes', 0)} nodes"}],
    }