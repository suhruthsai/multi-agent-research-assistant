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


class AgentState(TypedDict):
    query: str
    papers: Annotated[list[Paper], operator.add]
    critiques: Annotated[list[Critique], operator.add]
    hypotheses: Annotated[list[Hypothesis], operator.add]
    messages: Annotated[list[dict], operator.add]
    synthesis: Optional[str]
    report: Optional[str]
    confidence_score: float
    iteration: int
    status: str