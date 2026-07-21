"""
SQLite-based persistent storage for research report history.
Stores full report data so users can revisit past research sessions.
"""

import json
import sqlite3
import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "history.db")


def _get_conn() -> sqlite3.Connection:
    """Get a database connection, creating the DB and table if needed."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS research_history (
            id            TEXT PRIMARY KEY,
            query         TEXT NOT NULL,
            report        TEXT,
            synthesis      TEXT,
            research_plan  TEXT,
            hypotheses     TEXT,   -- JSON
            papers         TEXT,   -- JSON
            graph_data     TEXT,   -- JSON
            topics         TEXT,   -- JSON
            confidence_score REAL DEFAULT 0.0,
            pdf_processed_count INTEGER DEFAULT 0,
            paper_count    INTEGER DEFAULT 0,
            created_at     TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_report(data: dict) -> str:
    """Save a completed research result. Returns the generated ID."""
    report_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO research_history
               (id, query, report, synthesis, research_plan,
                hypotheses, papers, graph_data,
                topics, confidence_score, pdf_processed_count, paper_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report_id,
                data.get("query", ""),
                data.get("report", ""),
                data.get("synthesis", ""),
                data.get("research_plan", ""),
                json.dumps(data.get("hypotheses", [])),
                json.dumps(data.get("papers", [])),
                json.dumps(data.get("graph_data")),
                json.dumps(data.get("topics", [])),
                data.get("confidence_score", 0.0),
                data.get("pdf_processed_count", 0),
                len(data.get("papers", [])),
                now,
            ),
        )
        conn.commit()
        logger.info("Saved report %s for query: %s", report_id, data.get("query", "")[:50])
        return report_id
    finally:
        conn.close()


def list_reports(limit: int = 50) -> list[dict]:
    """List recent reports (summary only — no full text)."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT id, query, confidence_score, paper_count,
                      pdf_processed_count, created_at
               FROM research_history
               ORDER BY created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_report(report_id: str) -> dict | None:
    """Get a full report by ID."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM research_history WHERE id = ?", (report_id,)
        ).fetchone()
        if not row:
            return None

        d = dict(row)
        # Parse JSON fields back
        for field in ("hypotheses", "papers", "topics"):
            try:
                d[field] = json.loads(d[field]) if d[field] else []
            except (json.JSONDecodeError, TypeError):
                d[field] = []
        try:
            d["graph_data"] = json.loads(d["graph_data"]) if d["graph_data"] else None
        except (json.JSONDecodeError, TypeError):
            d["graph_data"] = None

        return d
    finally:
        conn.close()


def delete_report(report_id: str) -> bool:
    """Delete a report by ID. Returns True if a row was deleted."""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "DELETE FROM research_history WHERE id = ?", (report_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
