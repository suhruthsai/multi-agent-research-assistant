"""
Query expansion using LLM to generate alternative search queries.
This improves recall by searching from multiple angles.
"""

import asyncio
import json
import logging
import os
from groq import AsyncGroq

logger = logging.getLogger(__name__)
_groq_client = None


def _get_groq():
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq_client

MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]


async def expand_query(original_query: str) -> list[str]:
    """
    Generate 3 alternative search queries from the original query.
    Each variant targets a different angle:
    1. Broader / more general terms
    2. Specific techniques or methods
    3. Related domains or applications
    """
    system = """You are a research query expansion specialist. Given a research query, 
generate exactly 3 alternative search queries that will help find more relevant papers.

Each query should target a different angle:
1. Broader terms (generalize the topic)
2. Specific techniques or methods mentioned or implied
3. Related domains or applications

Return ONLY a valid JSON array of 3 strings. No explanation."""

    user = f"Original query: {original_query}"

    for model in MODELS:
        try:
            response = await asyncio.wait_for(
                _get_groq().chat.completions.create(
                    model=model,
                    max_tokens=300,
                    temperature=0.4,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                ),
                timeout=30,
            )
            raw = response.choices[0].message.content or "[]"
            # Parse JSON
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()

            queries = json.loads(cleaned)
            if isinstance(queries, list) and len(queries) >= 1:
                logger.info("Query expansion: %d alternatives generated", len(queries))
                return [str(q) for q in queries[:3]]
        except asyncio.TimeoutError:
            logger.warning("Query expansion timeout on %s", model)
            continue
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["decommissioned", "rate_limit", "429", "529"]):
                await asyncio.sleep(5)
                continue
            logger.warning("Query expansion failed on %s: %s", model, e)
            continue

    # Fallback: return simple variations
    logger.warning("Query expansion: all models failed, using fallback")
    return [
        f"{original_query} survey review",
        f"{original_query} methods techniques",
    ]
