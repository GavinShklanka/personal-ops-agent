"""
Approval Queue — Personal Ops Agent
Human-in-the-loop gate for any LLM-proposed action that touches an external
service (calendar writes, email drafts). Klara queues proposals here;
Gavin approves or rejects them via the Flask dashboard.
"""

import json
from src.db import get_conn, init_db, now_iso

DASHBOARD_URL = "http://localhost:5000/approvals"


def queue_action(action_type: str, payload: dict) -> dict:
    """
    Insert a proposed action into the approvals table with status='pending'.
    Returns a summary dict including the new row id.
    """
    init_db()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO approvals (action_type, payload, status, created_at) VALUES (?, ?, 'pending', ?)",
            (action_type, json.dumps(payload), now_iso()),
        )
        return {
            "id": cur.lastrowid,
            "action_type": action_type,
            "status": "pending",
            "dashboard_url": DASHBOARD_URL,
        }


def get_pending_approvals() -> list[dict]:
    """Return all pending approvals, newest first."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM approvals WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()
        return [_deserialize(r) for r in rows]


def get_all_approvals(limit: int = 50) -> list[dict]:
    """Return recent approvals of any status."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_deserialize(r) for r in rows]


def approve_action(approval_id: int) -> bool:
    """Mark a pending approval as approved. Returns True if a row was updated."""
    init_db()
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE approvals SET status = 'approved', decided_at = ? WHERE id = ? AND status = 'pending'",
            (now_iso(), approval_id),
        )
        return cur.rowcount > 0


def reject_action(approval_id: int) -> bool:
    """Mark a pending approval as rejected. Returns True if a row was updated."""
    init_db()
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE approvals SET status = 'rejected', decided_at = ? WHERE id = ? AND status = 'pending'",
            (now_iso(), approval_id),
        )
        return cur.rowcount > 0


def pending_count() -> int:
    init_db()
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM approvals WHERE status = 'pending'"
        ).fetchone()[0]


def _deserialize(row) -> dict:
    d = dict(row)
    try:
        d["payload"] = json.loads(d["payload"])
    except (json.JSONDecodeError, KeyError):
        pass
    return d
