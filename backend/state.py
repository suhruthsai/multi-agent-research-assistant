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


class UploadedPaper(TypedDict):
    """A paper provided directly by the user (PDF bytes decoded or pasted text)."""
    title: str
    full_text: str       # Full extracted text from PDF or pasted content
    source_type: str     # "pdf" | "text"
    filename: str        # Original filename or "manual_input"


class PaperAnalysis(TypedDict):
    """Per-paper analysis result from the paper_analyzer_agent."""
    title: str
    summary: str                  # Detailed 3-5 paragraph summary
    advantages: list[str]         # Key contributions / strengths
    disadvantages: list[str]      # Limitations / weaknesses / gaps
    key_findings: list[str]       # Bullet-point key findings
    methodology: str              # Brief methodology description
    source_type: str              # "pdf" | "text"
    filename: str


class AgentState(TypedDict, total=False):
    # ── Query-based research fields ──────────────────────────────────────
    query: str
    research_plan: str
    papers: Annotated[list[Paper], operator.add]
    critiques: Annotated[list[Critique], operator.add]
    hypotheses: Annotated[list[Hypothesis], operator.add]
    messages: Annotated[list[dict], operator.add]
    chunks: Annotated[list[dict], operator.add]
    topics: Annotated[list[str], operator.add]
    synthesis: Optional[str]
    report: Optional[str]
    graph_data: Optional[dict]
    confidence_score: float
    iteration: int
    pdf_processed_count: int
    status: str

    # ── Paper analyzer mode fields ────────────────────────────────────────
    uploaded_papers: list[UploadedPaper]          # Raw inputs from user
    paper_analyses: list[PaperAnalysis]           # Per-paper LLM analysis
    comparative_analysis: Optional[str]           # Final cross-paper comparison
