"""
Goal Engine — Personal Ops Agent
CRUD interface for weekly and monthly goals stored in SQLite.
Tracks progress, surfaces stalled goals, and feeds context into Klara.
"""

from datetime import datetime

from src.database import get_connection, log_activity


# --------------- Goal CRUD ---------------


def add_goal(title, description="", deadline=None, estimated_minutes=None, priority="medium"):
    """Add a new goal. Returns the new goal's ID."""
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO goals (title, description, deadline, estimated_minutes, priority)
           VALUES (?, ?, ?, ?, ?)""",
        (title, description, deadline, estimated_minutes, priority),
    )
    goal_id = cursor.lastrowid
    conn.commit()
    conn.close()
    log_activity("goal_engine", "add_goal", f"#{goal_id}: {title}")
    return goal_id


def list_goals(status="active", limit=50):
    """List goals filtered by status."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM goals WHERE status = ?
           ORDER BY
             CASE priority
               WHEN 'urgent' THEN 1
               WHEN 'high' THEN 2
               WHEN 'medium' THEN 3
               WHEN 'low' THEN 4
             END,
             deadline ASC NULLS LAST
           LIMIT ?""",
        (status, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_goal(goal_id):
    """Get a single goal by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_goal(goal_id, **kwargs):
    """Update goal fields. Pass any column name as kwarg."""
    allowed = {"title", "description", "deadline", "estimated_minutes", "priority", "status", "progress_pct"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    if updates.get("status") == "completed":
        updates["completed_at"] = datetime.now().isoformat()

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [goal_id]

    conn = get_connection()
    conn.execute(f"UPDATE goals SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    log_activity("goal_engine", "update_goal", f"#{goal_id}: {updates}")
    return True


def complete_goal(goal_id):
    """Mark a goal as completed."""
    return update_goal(goal_id, status="completed", progress_pct=100)


def delete_goal(goal_id):
    """Archive a goal (soft delete)."""
    return update_goal(goal_id, status="archived")


# --------------- Task CRUD ---------------


def add_task(goal_id, title, estimated_minutes=30):
    """Add a task under a goal. Returns task ID."""
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO tasks (goal_id, title, estimated_minutes)
           VALUES (?, ?, ?)""",
        (goal_id, title, estimated_minutes),
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


def list_tasks(goal_id=None, status=None):
    """List tasks, optionally filtered by goal and/or status."""
    conn = get_connection()
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []

    if goal_id is not None:
        query += " AND goal_id = ?"
        params.append(goal_id)
    if status is not None:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def complete_task(task_id):
    """Mark a task as done."""
    conn = get_connection()
    conn.execute(
        "UPDATE tasks SET status='done', completed_at=datetime('now') WHERE id=?",
        (task_id,),
    )
    conn.commit()
    conn.close()


def get_available_tasks(max_minutes=None):
    """
    Get all incomplete tasks, optionally filtered by time estimate.
    Useful for micro-productivity recommendations.
    """
    conn = get_connection()
    query = """
        SELECT t.*, g.title as goal_title, g.priority as goal_priority, g.deadline
        FROM tasks t
        JOIN goals g ON t.goal_id = g.id
        WHERE t.status IN ('todo', 'in_progress')
        AND g.status = 'active'
    """
    params = []

    if max_minutes is not None:
        query += " AND t.estimated_minutes <= ?"
        params.append(max_minutes)

    query += """
        ORDER BY
          CASE g.priority
            WHEN 'urgent' THEN 1 WHEN 'high' THEN 2
            WHEN 'medium' THEN 3 WHEN 'low' THEN 4
          END,
          g.deadline ASC NULLS LAST
    """

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --------------- CLI ---------------


def _interactive_cli():
    """Simple interactive CLI for goal management."""
    from src.database import init_db

    init_db()

    print("\n" + "=" * 40)
    print("  Goal Engine — Interactive Mode")
    print("=" * 40)

    while True:
        print("\n[1] List goals  [2] Add goal  [3] Add task")
        print("[4] Complete goal  [5] Complete task  [6] Quit")
        choice = input("\n> ").strip()

        if choice == "1":
            goals = list_goals()
            if not goals:
                print("No active goals.")
            for g in goals:
                tasks = list_tasks(goal_id=g["id"])
                done = sum(1 for t in tasks if t["status"] == "done")
                total = len(tasks)
                print(f"\n  [{g['priority'][0].upper()}] #{g['id']}: {g['title']}")
                if g["deadline"]:
                    print(f"      Deadline: {g['deadline']}")
                if total > 0:
                    print(f"      Tasks: {done}/{total} done")

        elif choice == "2":
            title = input("  Title: ").strip()
            if not title:
                continue
            desc = input("  Description (optional): ").strip()
            deadline = input("  Deadline YYYY-MM-DD (optional): ").strip() or None
            mins = input("  Estimated minutes (optional): ").strip()
            priority = input("  Priority (low/medium/high/urgent) [medium]: ").strip() or "medium"
            gid = add_goal(title, desc, deadline, int(mins) if mins else None, priority)
            print(f"  ✓ Goal #{gid} created")

        elif choice == "3":
            gid = input("  Goal ID: ").strip()
            if not gid.isdigit():
                continue
            title = input("  Task title: ").strip()
            if not title:
                continue
            mins = input("  Estimated minutes [30]: ").strip() or "30"
            tid = add_task(int(gid), title, int(mins))
            print(f"  ✓ Task #{tid} created under goal #{gid}")

        elif choice == "4":
            gid = input("  Goal ID to complete: ").strip()
            if gid.isdigit():
                complete_goal(int(gid))
                print(f"  ✓ Goal #{gid} completed")

        elif choice == "5":
            tid = input("  Task ID to complete: ").strip()
            if tid.isdigit():
                complete_task(int(tid))
                print(f"  ✓ Task #{tid} completed")

        elif choice == "6":
            print("  Bye!")
            break


if __name__ == "__main__":
    _interactive_cli()
