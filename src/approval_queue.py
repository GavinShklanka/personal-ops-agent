"""
Approval Queue — Personal Ops Agent
Human-in-the-loop safety gate for actions that modify external state.
No action that touches an external service (beyond read-only polling)
can execute without explicit approval from Gavin.
"""

import json
from datetime import datetime

from src.database import get_connection, log_activity


def queue_action(action_type, description, payload=None):
    """
    Queue an action for approval.

    Args:
        action_type: Category like 'send_notification', 'create_event', etc.
        description: Human-readable description of what this action will do
        payload: Dict of action parameters (stored as JSON)

    Returns:
        Approval queue item ID
    """
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO approvals (action_type, description, payload)
           VALUES (?, ?, ?)""",
        (action_type, description, json.dumps(payload) if payload else None),
    )
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()

    log_activity(
        "approval_queue",
        "queued",
        f"#{item_id}: [{action_type}] {description}",
    )

    return item_id


def approve(item_id):
    """Approve a queued action."""
    conn = get_connection()
    conn.execute(
        """UPDATE approvals
           SET status='approved', decided_at=datetime('now')
           WHERE id=? AND status='pending'""",
        (item_id,),
    )
    conn.commit()

    # Get the approved action
    row = conn.execute("SELECT * FROM approvals WHERE id=?", (item_id,)).fetchone()
    conn.close()

    if row:
        log_activity("approval_queue", "approved", f"#{item_id}: {row['description']}")
        return dict(row)
    return None


def reject(item_id):
    """Reject a queued action."""
    conn = get_connection()
    conn.execute(
        """UPDATE approvals
           SET status='rejected', decided_at=datetime('now')
           WHERE id=? AND status='pending'""",
        (item_id,),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM approvals WHERE id=?", (item_id,)).fetchone()
    conn.close()

    if row:
        log_activity("approval_queue", "rejected", f"#{item_id}: {row['description']}")
        return dict(row)
    return None


def list_pending():
    """Get all pending approval items."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM approvals
           WHERE status='pending'
           ORDER BY created_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_all(limit=50):
    """Get all approval items (any status)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_counts():
    """Get counts by status."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT status, COUNT(*) as count FROM approvals GROUP BY status"
    ).fetchall()
    conn.close()
    return {r["status"]: r["count"] for r in rows}


if __name__ == "__main__":
    from src.database import init_db

    init_db()
    print("\n--- Approval Queue ---\n")
    pending = list_pending()
    if pending:
        print(f"{len(pending)} pending approvals:")
        for item in pending:
            print(f"  #{item['id']}: [{item['action_type']}] {item['description']}")
    else:
        print("No pending approvals.")
