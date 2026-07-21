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
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
]

# Tuning
MIN_RELEVANCE_SCORE      = 0.30
TOP_N_FOR_CONFIDENCE     = 5
MIN_PAPERS_FOR_SYNTHESIS = 5
GROQ_TIMEOUT_SECONDS     = 60

vs = VectorStore()


def clear_vector_memory() -> None:
    """Clear stored abstracts/chunks so a new run cannot reuse unrelated papers."""
    vs.clear()


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


async def _groq(system: str, user: str, max_tokens: int = 1500, temperature: float = 0.2) -> str:
    """Call Groq with automatic model fallback, 60s timeout, retry on rate limit."""
    for model in MODELS:
        try:
            logger.info("[Groq] trying model: %s", model)
            response = await asyncio.wait_for(
                _get_groq_client().chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
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
            if any(x in err for x in ["404", "model_not_found", "does not exist", "NotFoundError"]):
                logger.warning("[Groq] ⚠️ model not found %s — trying next", model)
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

    if state.get("iteration", 0) == 0:
        clear_vector_memory()

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

    # Step 3: Add to vector store; graph is scoped to this research run
    vs.add_papers(unique)
    run_kg = KnowledgeGraph()

    # Step 4: Hybrid search (BM25 + semantic with RRF)
    hybrid_results = vs.hybrid_search(query, k=20)

    # Step 5: Re-rank with cross-encoder
    reranked = vs.rerank(query, hybrid_results, top_n=12)
    quality  = _filter_quality_papers(reranked)

    # Step 6: Build a per-query knowledge graph
    run_kg.add_papers(quality)
    topic_texts = []
    for i, p in enumerate(quality[:10], 1):
        topic_texts.append(f"[{i}] {p['title']}\nAbstract: {p.get('abstract', '')[:350]}")

    try:
        topic_raw = await _groq(
            "Extract paper-specific research topics. Return ONLY a JSON array. "
            "Each item must be an object with keys paper_index and topics. "
            "topics must contain 2-4 short topic strings for that paper.",
            "\n".join(topic_texts),
            max_tokens=700,
        )
        topic_items = _parse_json(topic_raw)
        flat_topics = []
        for item in topic_items:
            if not isinstance(item, dict):
                continue
            idx = item.get("paper_index")
            if not isinstance(idx, int) or idx < 1 or idx > len(quality):
                continue
            paper_topics = [str(t) for t in item.get("topics", []) if str(t).strip()]
            flat_topics.extend(paper_topics)
            run_kg.add_topics(quality[idx - 1].get("url", ""), paper_topics)
        flat_topics = sorted(set(flat_topics))
    except Exception as e:
        logger.warning("Topic extraction failed: %s", e)
        flat_topics = []

    run_kg.add_citation_links_from_metadata(quality)
    run_kg.add_similarity_links(quality)

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
        "graph_data":          run_kg.to_json(),
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
# 6. HYPOTHESIS AGENT — Generates novel research hypotheses
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

    graph_data = state.get("graph_data") or {"nodes": [], "links": [], "stats": {}}

    return {
        "hypotheses": hypotheses,
        "graph_data": graph_data,
        "status":     "hypotheses_complete",
        "messages":   [{"role": "hypothesis_agent",
                        "content": f"Generated {len(hypotheses)} hypotheses. "
                                   f"Knowledge graph: {graph_data.get('stats', {}).get('total_nodes', 0)} nodes"}],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 7. PAPER ANALYZER AGENT — Deep per-paper analysis (no hallucination)
#    Works with uploaded PDFs and pasted text/abstracts.
#    Uses temperature=0.1 and strictly grounds output in provided text.
# ═══════════════════════════════════════════════════════════════════════════════

# How many characters of full_text to send to the LLM per paper.
# ~8000 chars ≈ ~2000 tokens — enough for a dense paper abstract+body.
_MAX_PAPER_CHARS = 8000

ANALYZER_SYSTEM = """You are a precise academic paper analyst. You will be given the FULL TEXT of a research paper.

Your task: analyze ONLY what is written in the paper. Do NOT add outside knowledge, do NOT invent claims, do NOT hallucinate.

Return a valid JSON object with these exact keys:
{
  "title": "<inferred or given title>",
  "summary": "<3 to 5 solid paragraphs summarizing the paper accurately, covering: problem statement, proposed approach, experiments, results, and conclusions>",
  "advantages": ["<specific strength 1>", "<specific strength 2>", ...],
  "disadvantages": ["<specific limitation 1>", "<specific limitation 2>", ...],
  "key_findings": ["<finding 1>", "<finding 2>", "<finding 3>", ...],
  "methodology": "<1-2 sentences describing the methodology or approach used>"
}

Rules you MUST follow:
- Every claim must come directly from the paper text provided.
- If the paper does not clearly state something, do NOT include it.
- advantages = real contributions/strengths explicitly mentioned in the paper.
- disadvantages = explicit limitations, future work, weaknesses, or gaps acknowledged in the paper.
- key_findings = 3-6 specific, concrete findings with numbers/results if available.
- Do NOT wrap in markdown code blocks. Return pure JSON only."""


async def _analyze_single_paper(paper: dict) -> dict:
    """Analyze one paper and return a PaperAnalysis dict."""
    title     = paper.get("title", "Untitled Paper")
    full_text = paper.get("full_text", "")
    filename  = paper.get("filename", "manual_input")
    source_type = paper.get("source_type", "text")

    # Truncate to avoid token overflow — keep intro + conclusion area
    text_for_llm = full_text[:_MAX_PAPER_CHARS]
    if len(full_text) > _MAX_PAPER_CHARS:
        # Also append the last 1000 chars (often conclusion/references area)
        text_for_llm += "\n\n...[middle sections omitted]...\n\n" + full_text[-1000:]

    user = f"""Title (if known): {title}

--- PAPER TEXT START ---
{text_for_llm}
--- PAPER TEXT END ---

Analyze this paper strictly based on the text above."""

    raw = await _groq(ANALYZER_SYSTEM, user, max_tokens=2500, temperature=0.1)

    # Parse JSON response
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts   = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        start = cleaned.find("{")
        end   = cleaned.rfind("}") + 1
        if start != -1 and end > start:
            try:
                result = json.loads(cleaned[start:end])
            except Exception:
                result = {}
        else:
            result = {}

    # Ensure all fields present with fallbacks
    return {
        "title":          result.get("title", title),
        "summary":        result.get("summary", "Analysis could not be generated."),
        "advantages":     result.get("advantages", []),
        "disadvantages":  result.get("disadvantages", []),
        "key_findings":   result.get("key_findings", []),
        "methodology":    result.get("methodology", ""),
        "source_type":    source_type,
        "filename":       filename,
    }


async def paper_analyzer_agent(state: AgentState) -> dict:
    """
    Analyze each uploaded paper one by one.
    Produces a list of PaperAnalysis objects — one per paper.
    Uses strict grounding prompts to prevent hallucination.
    """
    uploaded = state.get("uploaded_papers", [])
    if not uploaded:
        return {
            "paper_analyses": [],
            "status":         "analysis_complete",
            "messages":       [{"role": "paper_analyzer_agent",
                                "content": "No papers provided for analysis."}],
        }

    logger.info("[PaperAnalyzer] Analyzing %d papers sequentially", len(uploaded))

    analyses = []
    for i, paper in enumerate(uploaded):
        logger.info("[PaperAnalyzer] Analyzing paper %d/%d: %s", i + 1, len(uploaded), paper.get("title", "?"))
        try:
            analysis = await _analyze_single_paper(paper)
            analyses.append(analysis)
        except Exception as e:
            logger.error("[PaperAnalyzer] Failed to analyze paper %d: %s", i + 1, e)
            analyses.append({
                "title":         paper.get("title", f"Paper {i+1}"),
                "summary":       f"Analysis failed: {str(e)}",
                "advantages":    [],
                "disadvantages": [],
                "key_findings":  [],
                "methodology":   "",
                "source_type":   paper.get("source_type", "text"),
                "filename":      paper.get("filename", "unknown"),
            })

    return {
        "paper_analyses": analyses,
        "status":         "analysis_complete",
        "messages":       [{"role": "paper_analyzer_agent",
                            "content": f"Analyzed {len(analyses)} papers successfully."}],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 8. COMPARATIVE ANALYZER AGENT — Cross-paper comparison
#    Only runs after all papers are analyzed individually.
# ═══════════════════════════════════════════════════════════════════════════════
async def comparative_analyzer_agent(state: AgentState) -> dict:
    """
    Generate a comparative analysis across all analyzed papers.
    Identifies agreements, contradictions, best contributions, and overall conclusion.
    """
    analyses = state.get("paper_analyses", [])
    if not analyses:
        return {
            "comparative_analysis": "No papers were analyzed.",
            "status":               "comparison_complete",
            "messages":             [{"role": "comparative_analyzer_agent",
                                      "content": "No analyses to compare."}],
        }

    if len(analyses) == 1:
        # Only one paper — no cross-comparison needed
        return {
            "comparative_analysis": (
                f"Only one paper was provided. See the individual analysis above for "
                f"a complete breakdown of **{analyses[0]['title']}**."
            ),
            "status":   "comparison_complete",
            "messages": [{"role": "comparative_analyzer_agent",
                          "content": "Single paper — no cross-paper comparison needed."}],
        }

    # Build a structured summary of each paper for the LLM
    summaries = []
    for i, a in enumerate(analyses, 1):
        adv  = "\n    - ".join(a.get("advantages", [])[:4]) or "None listed"
        dis  = "\n    - ".join(a.get("disadvantages", [])[:4]) or "None listed"
        find = "\n    - ".join(a.get("key_findings", [])[:4]) or "None listed"
        summaries.append(
            f"**Paper {i}: {a['title']}**\n"
            f"  Methodology: {a.get('methodology', 'N/A')}\n"
            f"  Key Findings:\n    - {find}\n"
            f"  Advantages:\n    - {adv}\n"
            f"  Disadvantages:\n    - {dis}"
        )

    system = """You are an expert academic reviewer performing a comparative analysis of multiple research papers.

Based ONLY on the paper summaries provided, write a structured Markdown comparative analysis with these exact sections:

## Overview
Brief overview of all papers and their common theme/domain.

## Key Agreements
What findings, methods, or conclusions do the papers agree on?

## Contradictions & Debates
Where do the papers disagree or present conflicting evidence?

## Comparative Strengths
How do the papers compare in terms of methodology, rigor, and contribution?

## Comparative Weaknesses
Common limitations or gaps shared across the papers.

## Overall Conclusion
Which paper(s) make the strongest contribution and why? What does the collection of papers tell us together?

Be precise, cite paper titles directly, and do NOT add external knowledge."""

    user = (
        f"Number of papers: {len(analyses)}\n\n"
        + "\n\n---\n\n".join(summaries)
    )

    comparison = await _groq(system, user, max_tokens=3000, temperature=0.1)

    return {
        "comparative_analysis": comparison,
        "status":               "comparison_complete",
        "messages":             [{"role": "comparative_analyzer_agent",
                                  "content": f"Comparative analysis complete across {len(analyses)} papers."}],
    }
