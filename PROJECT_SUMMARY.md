# MARA - Multi-Agent Research Assistant

## Project Summary
MARA is an AI-powered research assistant that helps users search, analyze, organize, and export academic research. The system uses a multi-agent workflow to plan a research query, retrieve relevant papers, analyze paper content, extract themes, build hypotheses, synthesize findings, and generate a final research report. It also supports uploaded paper analysis, research history, knowledge graph visualization, and PDF/DOCX report export.

## Problem Statement
Academic research is time-consuming because users must search multiple sources, compare papers manually, track citations/topics, and convert findings into a structured report. MARA reduces this workload by automating the research pipeline while keeping results inspectable through papers, citations, topics, and graph relationships.

## Key Features
- Multi-agent research pipeline for planning, search, critique, hypothesis generation, synthesis, and report writing.
- Hybrid retrieval using academic search, BM25-style ranking, semantic/vector memory, and re-ranking.
- Knowledge graph showing papers, authors, topics, clusters, citation links, and similarity relationships.
- Paper analyzer for uploaded PDFs or pasted paper text with individual and comparative analysis.
- Live WebSocket progress updates showing agent activity during research.
- Report history for saving, loading, and deleting previous research outputs.
- PDF and DOCX export for final research reports.
- Optional local API-key protection and restricted frontend CORS origins.
- Docker-ready project structure with Dockerfile, entrypoint, and environment template.

## Technology Stack
- Frontend: Next.js, React, TypeScript, Tailwind CSS, lucide-react.
- Backend: FastAPI, WebSockets, Pydantic, PyMuPDF.
- AI/Agents: LangGraph, Groq API, LangSmith tracing support.
- Retrieval/Memory: ChromaDB, sentence-transformers, rank-bm25.
- Graph: NetworkX-based knowledge graph.
- Storage: Local history database and local vector memory.

## System Workflow
1. User enters a research query or uploads papers.
2. Planner agent creates a research direction.
3. Search/retrieval tools collect relevant academic papers and full-text PDF content when available.
4. Specialist agents critique, compare, extract topics, generate hypotheses, and synthesize findings.
5. Knowledge graph connects papers to authors, topics, clusters, citations, and similar papers.
6. Final report is generated, saved to history, and can be exported as PDF or DOCX.

## Knowledge Graph Usage
The knowledge graph improves explainability by showing how research papers are connected. It represents papers, authors, topics, and clusters as nodes, with edges for authorship, topic coverage, cluster membership, citations, and paper similarity. This makes the system more effective because users can inspect relationships instead of only reading a static report.

## Project Impact
MARA is useful for students, researchers, and academic reviewers who need a faster way to understand a research area. It turns scattered papers into a structured research report, provides visual relationship mapping, supports uploaded paper comparison, and preserves past research sessions.

## Future Enhancements
- Add user accounts and cloud storage for multi-user deployment.
- Improve citation extraction with stronger external citation APIs.
- Add collaborative report editing and annotation.
- Support more export formats and citation styles such as IEEE, APA, and BibTeX.
- Add deployment-ready Docker Compose and production database support.
