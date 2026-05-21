from typing import TypedDict, List, Dict, Any


class AgentState(TypedDict, total=False):
    query: str
    papers: List[Dict[str, Any]]
    critiques: List[Dict[str, Any]]
    synthesis: str
    report: str
    hypotheses: List[Dict[str, Any]]
    confidence_score: float
    status: str
    messages: List[Dict[str, str]]