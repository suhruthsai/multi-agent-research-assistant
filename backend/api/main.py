"""FastAPI app — REST + WebSocket for live agent streaming with graph API."""

import asyncio
import html
import io
import json
import logging
import os
import re
import zipfile
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.agents.orchestrator import research_graph, analyzer_graph
from backend.state import AgentState
from backend.memory.history import save_report, list_reports, get_report, delete_report

DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip()
]
API_KEY = os.getenv("MARA_API_KEY", "").strip()

app = FastAPI(title="MARA — Multi-Agent Research Assistant", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


class ResearchRequest(BaseModel):
    query: str


class ExportRequest(BaseModel):
    markdown: str
    title: str = "research-report"


def _is_authorized_key(key: str | None) -> bool:
    return not API_KEY or key == API_KEY


@app.middleware("http")
async def require_local_api_key(request: Request, call_next):
    """Optional local protection. Set MARA_API_KEY to require X-MARA-API-Key."""
    if request.method == "OPTIONS" or request.url.path in {"/health", "/docs", "/openapi.json"}:
        return await call_next(request)
    if not _is_authorized_key(request.headers.get("x-mara-api-key")):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    return await call_next(request)


def _initial_state(query: str) -> dict:
    """Create a fresh initial state for a research run."""
    return {
        "query":              query,
        "research_plan":      "",
        "papers":             [],
        "critiques":          [],
        "hypotheses":         [],
        "messages":           [],
        "chunks":             [],
        "topics":             [],
        "synthesis":          None,
        "report":             None,
        "graph_data":         None,
        "confidence_score":   0.0,
        "iteration":          0,
        "pdf_processed_count": 0,
        "status":             "starting",
    }


def _parse_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF."""
    try:
        import fitz
        doc  = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = []
        for page in doc:
            page_text = page.get_text("text")
            if page_text.strip():
                text.append(page_text)
        doc.close()
        return "\n\n".join(text)
    except Exception as e:
        logger.warning("PDF parse error: %s", e)
        return ""


def _safe_filename(title: str, ext: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()[:70]
    return f"{name or 'research-report'}.{ext}"


def _markdown_lines(markdown: str) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            lines.append(("blank", ""))
            continue
        if line.startswith("# "):
            lines.append(("h1", line[2:].strip()))
        elif line.startswith("## "):
            lines.append(("h2", line[3:].strip()))
        elif line.startswith("### "):
            lines.append(("h3", line[4:].strip()))
        elif line.startswith(("- ", "* ")):
            lines.append(("bullet", line[2:].strip()))
        else:
            lines.append(("p", re.sub(r"[*_`]+", "", line)))
    return lines


def _build_pdf(markdown: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    margin = 54
    y = margin

    def add_page_if_needed(height: float):
        nonlocal page, y
        if y + height > 790:
            page = doc.new_page(width=595, height=842)
            y = margin

    for kind, text in _markdown_lines(markdown):
        if kind == "blank":
            y += 8
            continue
        size = {"h1": 18, "h2": 15, "h3": 13, "bullet": 10, "p": 10}.get(kind, 10)
        font = "helv"
        prefix = "- " if kind == "bullet" else ""
        available_width = 487
        words = f"{prefix}{text}".split()
        current = ""
        wrapped = []
        for word in words:
            candidate = f"{current} {word}".strip()
            if fitz.get_text_length(candidate, fontname=font, fontsize=size) > available_width and current:
                wrapped.append(current)
                current = word
            else:
                current = candidate
        if current:
            wrapped.append(current)

        add_page_if_needed((len(wrapped) + 1) * (size + 5))
        for wrapped_line in wrapped:
            page.insert_text((margin, y), wrapped_line, fontsize=size, fontname=font, fill=(0.08, 0.09, 0.12))
            y += size + 5
        y += 6 if kind.startswith("h") else 3

    data = doc.tobytes()
    doc.close()
    return data


def _docx_para(text: str, style: str = "") -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    escaped = html.escape(text)
    return f"<w:p>{style_xml}<w:r><w:t xml:space=\"preserve\">{escaped}</w:t></w:r></w:p>"


def _build_docx(markdown: str) -> bytes:
    body = []
    for kind, text in _markdown_lines(markdown):
        if kind == "blank":
            body.append("<w:p/>")
        elif kind == "h1":
            body.append(_docx_para(text, "Title"))
        elif kind == "h2":
            body.append(_docx_para(text, "Heading1"))
        elif kind == "h3":
            body.append(_docx_para(text, "Heading2"))
        elif kind == "bullet":
            body.append(_docx_para(f"- {text}"))
        else:
            body.append(_docx_para(text))

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body)}<w:sectPr/></w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
    return out.getvalue()


@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0"}


@app.post("/export-report/{fmt}")
async def export_report(fmt: str, req: ExportRequest):
    """Export a markdown report as PDF or DOCX."""
    fmt = fmt.lower()
    title = req.title or "research-report"
    if fmt == "pdf":
        data = await asyncio.to_thread(_build_pdf, req.markdown)
        media_type = "application/pdf"
    elif fmt == "docx":
        data = await asyncio.to_thread(_build_docx, req.markdown)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        return JSONResponse(status_code=400, content={"error": "Format must be pdf or docx"})

    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(title, fmt)}"'},
    )


# ── History Endpoints ─────────────────────────────────────────────────────────
@app.get("/history")
async def get_history():
    """List recent research reports (summary only)."""
    return list_reports(limit=50)


@app.get("/history/{report_id}")
async def get_history_item(report_id: str):
    """Get a full report by ID."""
    report = get_report(report_id)
    if not report:
        return JSONResponse(status_code=404, content={"error": "Report not found"})
    return report


@app.delete("/history/{report_id}")
async def delete_history_item(report_id: str):
    """Delete a report by ID."""
    deleted = delete_report(report_id)
    if not deleted:
        return JSONResponse(status_code=404, content={"error": "Report not found"})
    return {"status": "deleted"}


# ── Query-Based Research (original) ──────────────────────────────────────────
@app.post("/research")
async def research(req: ResearchRequest):
    initial = _initial_state(req.query)
    result  = await research_graph.ainvoke(initial)
    return {
        "report":             result.get("report"),
        "synthesis":          result.get("synthesis"),
        "research_plan":      result.get("research_plan", ""),
        "hypotheses":         result.get("hypotheses", []),
        "papers":             result.get("papers", []),
        "graph_data":         result.get("graph_data"),
        "topics":             result.get("topics", []),
        "confidence_score":   result.get("confidence_score", 0.0),
        "pdf_processed_count": result.get("pdf_processed_count", 0),
        "messages":           result.get("messages", []),
    }


@app.websocket("/ws/research")
async def ws_research(websocket: WebSocket):
    await websocket.accept()
    try:
        data  = await websocket.receive_text()
        payload = json.loads(data)
        if not _is_authorized_key(payload.get("api_key") or websocket.query_params.get("api_key")):
            await websocket.send_text(json.dumps({"error": "Unauthorized"}))
            return
        query = payload.get("query", "").strip()
        if not query:
            await websocket.send_text(json.dumps({"error": "No query provided"}))
            return

        initial           = _initial_state(query)
        accumulated_state = dict(initial)

        async for event in research_graph.astream(initial, stream_mode="updates"):
            for node_name, node_output in event.items():
                if node_output is None:
                    continue

                # Accumulate state
                for k, v in node_output.items():
                    if isinstance(v, list) and isinstance(accumulated_state.get(k), list):
                        accumulated_state[k] = accumulated_state[k] + v
                    else:
                        accumulated_state[k] = v

                # Build the update message
                update = {
                    "node":        node_name,
                    "status":      node_output.get("status", node_name),
                    "paper_count": len(accumulated_state.get("papers", [])),
                    "confidence":  accumulated_state.get("confidence_score"),
                    "message":     (node_output.get("messages") or [{}])[-1],
                }

                if node_name == "planner":
                    update["research_plan"] = node_output.get("research_plan", "")
                if node_name == "search":
                    update["pdf_processed_count"] = node_output.get("pdf_processed_count", 0)
                    update["chunk_count"]         = len(node_output.get("chunks", []))
                    update["topics"]              = node_output.get("topics", [])

                try:
                    await websocket.send_text(json.dumps(update))
                except Exception as send_err:
                    logger.warning("Failed to send update: %s", send_err)

                await asyncio.sleep(0)

        # Save to history
        final_data = {
            "query":              query,
            "report":             accumulated_state.get("report"),
            "synthesis":          accumulated_state.get("synthesis"),
            "research_plan":      accumulated_state.get("research_plan", ""),
            "hypotheses":         accumulated_state.get("hypotheses", []),
            "papers":             accumulated_state.get("papers", []),
            "graph_data":         accumulated_state.get("graph_data"),
            "topics":             accumulated_state.get("topics", []),
            "confidence_score":   accumulated_state.get("confidence_score", 0.0),
            "pdf_processed_count": accumulated_state.get("pdf_processed_count", 0),
        }
        try:
            report_id = save_report(final_data)
            logger.info("Report saved to history: %s", report_id)
        except Exception as save_err:
            logger.warning("Failed to save to history: %s", save_err)
            report_id = None

        final_data["node"]       = "DONE"
        final_data["history_id"] = report_id
        await websocket.send_text(json.dumps(final_data))

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.exception("WebSocket error")
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── Paper Analyzer — REST ─────────────────────────────────────────────────────
@app.post("/analyze-papers")
async def analyze_papers_endpoint(
    files: List[UploadFile] = File(default=[]),
    texts: str = Form(default="[]"),   # JSON array of {title, text} objects
):
    """
    Accept:
      - Multiple PDF files (multipart upload)
      - Pasted texts/abstracts as a JSON array of {title, text} in the 'texts' field
    Returns per-paper analysis + comparative analysis.
    """
    uploaded_papers = []

    # Process PDFs
    for f in files:
        if not f.filename:
            continue
        pdf_bytes = await f.read()
        full_text = await asyncio.to_thread(_parse_pdf_bytes, pdf_bytes)
        if not full_text.strip():
            logger.warning("Could not extract text from %s", f.filename)
            continue
        # Use filename (without extension) as title fallback
        title = f.filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
        uploaded_papers.append({
            "title":       title,
            "full_text":   full_text,
            "source_type": "pdf",
            "filename":    f.filename,
        })

    # Process pasted texts
    try:
        text_inputs = json.loads(texts) if texts else []
    except Exception:
        text_inputs = []

    for item in text_inputs:
        if isinstance(item, dict) and item.get("text", "").strip():
            uploaded_papers.append({
                "title":       item.get("title", "Pasted Text").strip() or "Pasted Text",
                "full_text":   item["text"].strip(),
                "source_type": "text",
                "filename":    "manual_input",
            })

    if not uploaded_papers:
        return JSONResponse(status_code=400, content={"error": "No valid papers provided."})

    initial: AgentState = {
        "uploaded_papers":      uploaded_papers,
        "paper_analyses":       [],
        "comparative_analysis": None,
        "messages":             [],
        "status":               "analyzing",
    }
    result = await analyzer_graph.ainvoke(initial)

    return {
        "paper_analyses":       result.get("paper_analyses", []),
        "comparative_analysis": result.get("comparative_analysis", ""),
        "paper_count":          len(result.get("paper_analyses", [])),
    }


# ── Paper Analyzer — WebSocket (streaming) ────────────────────────────────────
@app.websocket("/ws/analyze-papers")
async def ws_analyze_papers(websocket: WebSocket):
    """
    WebSocket endpoint for streaming paper analysis.
    Client sends JSON: { papers: [{title, text, source_type, filename}], files_done: true }
    For PDFs, client must pre-read file bytes and send as base64 in text field.
    """
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        payload = json.loads(data)
        if not _is_authorized_key(payload.get("api_key") or websocket.query_params.get("api_key")):
            await websocket.send_text(json.dumps({"error": "Unauthorized"}))
            return

        # Accept pre-parsed paper list from frontend
        raw_papers  = payload.get("papers", [])
        uploaded_papers = []

        for item in raw_papers:
            source_type = item.get("source_type", "text")
            full_text   = item.get("full_text", item.get("text", "")).strip()

            # If PDF bytes were sent as base64, decode and parse
            if source_type == "pdf" and item.get("pdf_b64"):
                import base64
                pdf_bytes = base64.b64decode(item["pdf_b64"])
                full_text = await asyncio.to_thread(_parse_pdf_bytes, pdf_bytes)

            if not full_text:
                continue

            uploaded_papers.append({
                "title":       item.get("title", "Untitled"),
                "full_text":   full_text,
                "source_type": source_type,
                "filename":    item.get("filename", "manual_input"),
            })

        if not uploaded_papers:
            await websocket.send_text(json.dumps({"error": "No valid papers provided."}))
            return

        initial: AgentState = {
            "uploaded_papers":      uploaded_papers,
            "paper_analyses":       [],
            "comparative_analysis": None,
            "messages":             [],
            "status":               "analyzing",
        }

        accumulated: dict = dict(initial)

        async for event in analyzer_graph.astream(initial, stream_mode="updates"):
            for node_name, node_output in event.items():
                if node_output is None:
                    continue

                for k, v in node_output.items():
                    if isinstance(v, list) and isinstance(accumulated.get(k), list):
                        accumulated[k] = accumulated[k] + v
                    else:
                        accumulated[k] = v

                update = {
                    "node":    node_name,
                    "status":  node_output.get("status", node_name),
                    "message": (node_output.get("messages") or [{}])[-1],
                }

                if node_name == "paper_analyzer":
                    update["paper_analyses"] = node_output.get("paper_analyses", [])
                if node_name == "comparative_analyzer":
                    update["comparative_analysis"] = node_output.get("comparative_analysis", "")

                try:
                    await websocket.send_text(json.dumps(update))
                except Exception as send_err:
                    logger.warning("WS send error: %s", send_err)

                await asyncio.sleep(0)

        # Final message
        await websocket.send_text(json.dumps({
            "node":                 "DONE",
            "paper_analyses":       accumulated.get("paper_analyses", []),
            "comparative_analysis": accumulated.get("comparative_analysis", ""),
            "paper_count":          len(accumulated.get("paper_analyses", [])),
        }))

    except WebSocketDisconnect:
        logger.info("Analyzer client disconnected")
    except Exception as e:
        logger.exception("Analyzer WebSocket error")
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
