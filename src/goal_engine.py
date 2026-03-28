"""
Goal Engine — Personal Ops Agent
CRUD for weekly and monthly goals stored in SQLite.
Klara can add goals, read active goals, and update progress via tool-use.
"""

from src.db import get_conn, init_db, now_iso


def add_goal(
    title: str,
    description: str = "",
    period: str = "weekly",
    due_date: str = "",
) -> dict:
    """Insert a new active goal. Returns the created row as a dict."""
    init_db()
    ts = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO goals (title, description, period, status, progress, due_date, created_at, updated_at)
               VALUES (?, ?, ?, 'active', 0, ?, ?, ?)""",
            (title, description, period, due_date or None, ts, ts),
        )
        return {"id": cur.lastrowid, "title": title, "period": period, "status": "active"}


def get_active_goals() -> list[dict]:
    """Return all goals with status='active', newest first."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM goals WHERE status = 'active' ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_goals(limit: int = 100) -> list[dict]:
    """Return all goals regardless of status."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM goals ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_goal_by_id(goal_id: int) -> dict | None:
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return dict(row) if row else None


def update_goal_progress(goal_id: int, progress: int, note: str = "") -> dict:
    """
    Update progress (0-100). Automatically marks goal 'completed' at 100.
    Returns a summary dict.
    """
    init_db()
    progress = max(0, min(100, progress))
    new_status = "completed" if progress >= 100 else "active"
    with get_conn() as conn:
        conn.execute(
            "UPDATE goals SET progress = ?, status = ?, updated_at = ? WHERE id = ?",
            (progress, new_status, now_iso(), goal_id),
        )
    return {"goal_id": goal_id, "progress": progress, "status": new_status, "note": note}


def complete_goal(goal_id: int) -> dict:
    """Convenience: mark a goal as 100% complete."""
    return update_goal_progress(goal_id, 100)


def abandon_goal(goal_id: int) -> bool:
    init_db()
    with get_conn() as conn:
        conn.execute(
            "UPDATE goals SET status = 'abandoned', updated_at = ? WHERE id = ?",
            (now_iso(), goal_id),
        )
    return True
