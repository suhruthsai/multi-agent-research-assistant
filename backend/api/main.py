"""FastAPI app — REST + WebSocket for live agent streaming. Fixed double-run bug."""

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

app = FastAPI(title="MARA — Multi-Agent Research Assistant", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    query: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/research")
async def research(req: ResearchRequest):
    initial: AgentState = {
        "query": req.query,
        "papers": [], "critiques": [], "hypotheses": [], "messages": [],
        "synthesis": None, "report": None,
        "confidence_score": 0.0, "iteration": 0, "status": "starting",
    }
    result = await research_graph.ainvoke(initial)
    return {
        "report":           result.get("report"),
        "synthesis":        result.get("synthesis"),
        "hypotheses":       result.get("hypotheses", []),
        "papers":           result.get("papers", []),
        "confidence_score": result.get("confidence_score", 0.0),
        "messages":         result.get("messages", []),
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

        initial: AgentState = {
            "query": query,
            "papers": [], "critiques": [], "hypotheses": [], "messages": [],
            "synthesis": None, "report": None,
            "confidence_score": 0.0, "iteration": 0, "status": "starting",
        }

        # ── Accumulate final state during streaming (no double run!) ──────────
        accumulated_state = dict(initial)

        async for event in research_graph.astream(initial, stream_mode="updates"):
            for node_name, node_output in event.items():
                if node_output is None:
                    continue

                # Merge node output into accumulated state
                for k, v in node_output.items():
                    if isinstance(v, list) and isinstance(accumulated_state.get(k), list):
                        accumulated_state[k] = accumulated_state[k] + v
                    else:
                        accumulated_state[k] = v

                try:
                    await websocket.send_text(json.dumps({
                        "node":        node_name,
                        "status":      node_output.get("status", node_name),
                        "paper_count": len(node_output.get("papers", [])),
                        "confidence":  node_output.get("confidence_score"),
                        "message":     (node_output.get("messages") or [{}])[-1],
                    }))
                except Exception as send_err:
                    logger.warning("Failed to send update: %s", send_err)
                await asyncio.sleep(0)

        # ── Send final result from accumulated state (no second ainvoke!) ─────
        await websocket.send_text(json.dumps({
            "node":             "DONE",
            "report":           accumulated_state.get("report"),
            "synthesis":        accumulated_state.get("synthesis"),
            "hypotheses":       accumulated_state.get("hypotheses", []),
            "papers":           accumulated_state.get("papers", []),
            "confidence_score": accumulated_state.get("confidence_score", 0.0),
        }))

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