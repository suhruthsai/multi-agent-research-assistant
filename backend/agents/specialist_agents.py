"""
All 5 specialist agents — with async timeouts so no agent hangs forever.
Critic is faster: only evaluates top 5 papers instead of 10.
"""

import json
import asyncio
import logging
import os
from groq import AsyncGroq
from backend.state import AgentState
from backend.memory.vector_store import VectorStore
from backend.tools.academic_tools import search_all_sources

logger = logging.getLogger(__name__)
groq   = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

# ── Model fallback list ───────────────────────────────────────────────────────
MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# ── Tuning ────────────────────────────────────────────────────────────────────
MIN_RELEVANCE_SCORE      = 0.30
TOP_N_FOR_CONFIDENCE     = 5
MIN_PAPERS_FOR_SYNTHESIS = 5
GROQ_TIMEOUT_SECONDS     = 60   # max wait per LLM call

vs = VectorStore()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _papers_text(papers: list[dict], n: int = 5) -> str:
    """Shorter paper text — fewer tokens = faster + cheaper."""
    lines = []
    for i, p in enumerate(papers[:n], 1):
        lines.append(
            f"[{i}] {p['title']} ({p['year']})\n"
            f"    {p['abstract'][:250]}..."
        )
    return "\n\n".join(lines)


async def _groq(system: str, user: str, max_tokens: int = 1500) -> str:
    """
    Call Groq with:
    - automatic model fallback
    - 60 second timeout per call
    - retry on rate limit
    """
    for model in MODELS:
        try:
            logger.info("[Groq] trying model: %s", model)
            response = await asyncio.wait_for(
                groq.chat.completions.create(
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


# ── Search Agent ──────────────────────────────────────────────────────────────
async def search_agent(state: AgentState) -> dict:
    logger.info("[Search] query=%s", state["query"])
    query = state["query"]
    if state.get("iteration", 0) > 0:
        query = f"{query} recent advances systematic review"

    papers = await search_all_sources(query, limit_each=12)
    vs.add_papers(papers)
    ranked  = vs.semantic_search(query, k=15)
    quality = _filter_quality_papers(ranked)

    logger.info("[Search] %d → %d quality papers", len(ranked), len(quality))
    return {
        "papers":   quality,
        "status":   "search_complete",
        "messages": [{"role": "search_agent", "content": f"Retrieved {len(quality)} high-quality papers"}],
    }


# ── Critic Agent ──────────────────────────────────────────────────────────────
async def critic_agent(state: AgentState) -> dict:
    logger.info("[Critic] evaluating papers")

    # ── Only evaluate TOP 5 papers to save tokens and time ───────────────────
    top_papers = state["papers"][:5]

    system = """You are a peer reviewer. Evaluate each paper briefly.
Return ONLY a valid JSON array. Each object must have:
- paper_title: string
- score: float (0.0 to 1.0)
- strengths: list of 1-2 strings
- weaknesses: list of 1 string
- contradictions: list (empty if none)

Score guide: 0.9+=landmark, 0.75-0.9=solid, 0.6-0.75=adequate, below 0.6=weak"""

    user = f"Query: {state['query']}\n\nPapers:\n{_papers_text(top_papers, 5)}"

    raw      = await _groq(system, user, max_tokens=1500)
    critiques = _parse_json(raw)

    # Confidence from top scores
    scores     = sorted([c.get("score", 0.5) for c in critiques
                         if isinstance(c.get("score"), (int, float))], reverse=True)
    top_scores = scores[:TOP_N_FOR_CONFIDENCE]
    confidence = round(sum(top_scores) / len(top_scores), 2) if top_scores else 0.6

    logger.info("[Critic] confidence=%.2f scores=%s", confidence, top_scores)
    return {
        "critiques":        critiques,
        "confidence_score": confidence,
        "status":           "critique_complete",
        "messages":         [{"role": "critic_agent",
                              "content": f"Critiqued {len(critiques)} papers. Confidence: {confidence}"}],
    }


# ── Synthesis Agent ───────────────────────────────────────────────────────────
async def synthesis_agent(state: AgentState) -> dict:
    logger.info("[Synthesis] synthesising")

    scored = {c.get("paper_title", "").lower(): c.get("score", 0)
              for c in state["critiques"]}
    strong = [p for p in state["papers"]
              if scored.get(p["title"].lower(), 0.5) >= 0.55] or state["papers"][:6]

    system = """You are a research synthesizer. Reason ACROSS papers.
Use these exact headers:
## Key Agreements
## Contradictions
## Methodological Gaps
## Collective Conclusion
Be concise and specific."""

    user = (
        f"Query: {state['query']}\n\n"
        f"Papers:\n{_papers_text(strong, 6)}"
    )
    synthesis = await _groq(system, user, max_tokens=2000)
    return {
        "synthesis": synthesis,
        "status":    "synthesis_complete",
        "messages":  [{"role": "synthesis_agent",
                       "content": f"Synthesis done. Confidence: {state.get('confidence_score', 0)}"}],
    }


# ── Writer Agent ──────────────────────────────────────────────────────────────
async def writer_agent(state: AgentState) -> dict:
    logger.info("[Writer] generating report")

    system = """You are a scientific report writer.
Write a structured Markdown report with citations [Author et al., Year].
Structure:
# [Title]
## Executive Summary
## Background
## Key Findings
## Open Questions
## References"""

    user = (
        f"Query: {state['query']}\n\n"
        f"Synthesis:\n{state.get('synthesis', '')}\n\n"
        f"Papers:\n{_papers_text(state['papers'], 8)}"
    )
    report = await _groq(system, user, max_tokens=3000)
    return {
        "report":   report,
        "status":   "report_complete",
        "messages": [{"role": "writer_agent", "content": "Report generated"}],
    }


# ── Hypothesis Agent ──────────────────────────────────────────────────────────
async def hypothesis_agent(state: AgentState) -> dict:
    logger.info("[Hypothesis] generating hypotheses")

    system = """Generate 5 novel research hypotheses based on the synthesis.
Return ONLY a valid JSON array. Each object:
- hypothesis: string
- justification: string
- confidence: float (0.0–1.0)
- methodology_hint: string"""

    user = f"Query: {state['query']}\n\nSynthesis:\n{state.get('synthesis', '')}"

    raw        = await _groq(system, user, max_tokens=2000)
    hypotheses = _parse_json(raw)
    hypotheses.sort(key=lambda h: h.get("confidence", 0), reverse=True)

    return {
        "hypotheses": hypotheses,
        "status":     "hypotheses_complete",
        "messages":   [{"role": "hypothesis_agent",
                        "content": f"Generated {len(hypotheses)} hypotheses"}],
    }