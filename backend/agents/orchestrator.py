"""
LangGraph orchestrator — 7-agent pipeline with confidence-based feedback loop.

Flow:
  START → planner → search → critic → synthesis → [loop?] → writer → fact_checker → hypothesis → END

- Threshold: 0.75 (realistic target)
- MAX_ITER: 2 (max 2 retries then ALWAYS proceeds)
- After max iterations reached → always goes to writer no matter what
"""

import logging
from langgraph.graph import StateGraph, START, END
from backend.state import AgentState
from backend.agents.specialist_agents import (
    planner_agent,
    search_agent,
    critic_agent,
    synthesis_agent,
    writer_agent,
    fact_checker_agent,
    hypothesis_agent,
)

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.75
MAX_ITER             = 2


def should_loop(state: AgentState) -> str:
    confidence = state.get("confidence_score", 1.0)
    iteration  = state.get("iteration", 0)

    if iteration >= MAX_ITER:
        logger.info(
            "[Orchestrator] Max iterations (%d) reached — proceeding to writer (confidence=%.2f)",
            MAX_ITER, confidence,
        )
        return "continue"

    if confidence < CONFIDENCE_THRESHOLD:
        logger.info(
            "[Orchestrator] confidence %.2f < %.2f → re-searching (iter %d/%d)",
            confidence, CONFIDENCE_THRESHOLD, iteration, MAX_ITER,
        )
        return "loop"

    logger.info("[Orchestrator] confidence %.2f ✅ → proceeding to writer", confidence)
    return "continue"


async def increment_iteration(state: AgentState) -> dict:
    return {"iteration": state.get("iteration", 0) + 1}


def build_graph():
    g = StateGraph(AgentState)

    # Add all 7 agent nodes + loop increment
    g.add_node("planner",        planner_agent)
    g.add_node("search",         search_agent)
    g.add_node("critic",         critic_agent)
    g.add_node("synthesis",      synthesis_agent)
    g.add_node("loop_increment", increment_iteration)
    g.add_node("writer",         writer_agent)
    g.add_node("fact_checker",   fact_checker_agent)
    g.add_node("hypothesis",     hypothesis_agent)

    # Define the flow
    g.add_edge(START, "planner")
    g.add_edge("planner", "search")
    g.add_edge("search", "critic")
    g.add_edge("critic", "synthesis")
    g.add_conditional_edges(
        "synthesis",
        should_loop,
        {"loop": "loop_increment", "continue": "writer"},
    )
    g.add_edge("loop_increment", "search")
    g.add_edge("writer", "fact_checker")
    g.add_edge("fact_checker", "hypothesis")
    g.add_edge("hypothesis", END)

    return g.compile()


research_graph = build_graph()


async def run_research(query: str) -> AgentState:
    initial: AgentState = {
        "query":              query,
        "research_plan":      "",
        "papers":             [],
        "critiques":          [],
        "hypotheses":         [],
        "messages":           [],
        "chunks":             [],
        "fact_check_results": [],
        "topics":             [],
        "synthesis":          None,
        "report":             None,
        "graph_data":         None,
        "confidence_score":   0.0,
        "iteration":          0,
        "pdf_processed_count": 0,
        "status":             "starting",
    }
    return await research_graph.ainvoke(initial)