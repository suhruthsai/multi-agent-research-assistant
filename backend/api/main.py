"""FastAPI app — REST + WebSocket for live agent streaming with graph API."""

import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.agents.orchestrator import research_graph
from backend.state import AgentState
from backend.memory.history import save_report, list_reports, get_report, delete_report

app = FastAPI(title="MARA — Multi-Agent Research Assistant", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    query: str


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


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


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
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Report not found"})
    return report


@app.delete("/history/{report_id}")
async def delete_history_item(report_id: str):
    """Delete a report by ID."""
    deleted = delete_report(report_id)
    if not deleted:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Report not found"})
    return {"status": "deleted"}


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
        "fact_check_results": result.get("fact_check_results", []),
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
        query = json.loads(data).get("query", "").strip()
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

                # Include extra data for specific nodes
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
            "fact_check_results": accumulated_state.get("fact_check_results", []),
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

        # Send final result
        final_data["node"] = "DONE"
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