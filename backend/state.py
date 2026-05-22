"""Shared AgentState TypedDict passed through the LangGraph graph."""

import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict


class Paper(TypedDict):
    title: str
    abstract: str
    authors: list[str]
    year: int
    url: str
    source: str
    citation_count: int
    relevance_score: float


class Critique(TypedDict):
    paper_title: str
    score: float
    strengths: list[str]
    weaknesses: list[str]
    contradictions: list[str]


class Hypothesis(TypedDict):
    hypothesis: str
    justification: str
    confidence: float


class FactCheck(TypedDict):
    claim: str
    status: str          # "verified", "unverified", "contradicted"
    evidence: str
    source_paper: str


class AgentState(TypedDict, total=False):
    query: str
    research_plan: str
    papers: Annotated[list[Paper], operator.add]
    critiques: Annotated[list[Critique], operator.add]
    hypotheses: Annotated[list[Hypothesis], operator.add]
    messages: Annotated[list[dict], operator.add]
    chunks: Annotated[list[dict], operator.add]
    fact_check_results: Annotated[list[FactCheck], operator.add]
    topics: Annotated[list[str], operator.add]
    synthesis: Optional[str]
    report: Optional[str]
    graph_data: Optional[dict]
    confidence_score: float
    iteration: int
    pdf_processed_count: int
    status: str