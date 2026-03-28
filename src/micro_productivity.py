"""
Micro Productivity — Personal Ops Agent
Finds gaps in the calendar and recommends focused tasks to fill them.
Matches available time blocks to active goals and task backlog.
"""

from datetime import datetime, timedelta

from src.database import log_activity


def find_gaps(events, min_gap_minutes=15):
    """
    Find gaps between calendar events.

    Args:
        events: List of event dicts with 'start_time' and 'end_time'
        min_gap_minutes: Minimum gap size to consider (default 15 min)

    Returns:
        List of gap dicts: [{"start": ..., "end": ..., "minutes": ...}]
    """
    if not events:
        return []

    # Parse and sort events by start time
    parsed = []
    for ev in events:
        if ev.get("all_day"):
            continue
        try:
            start = _parse_time(ev["start_time"])
            end = _parse_time(ev["end_time"])
            if start and end:
                parsed.append({"start": start, "end": end, "summary": ev.get("summary", "")})
        except (KeyError, ValueError):
            continue

    if not parsed:
        return []

    parsed.sort(key=lambda x: x["start"])
    gaps = []

    for i in range(len(parsed) - 1):
        gap_start = parsed[i]["end"]
        gap_end = parsed[i + 1]["start"]
        gap_minutes = int((gap_end - gap_start).total_seconds() / 60)

        if gap_minutes >= min_gap_minutes:
            gaps.append({
                "start": gap_start.isoformat(),
                "end": gap_end.isoformat(),
                "minutes": gap_minutes,
                "between": f"{parsed[i]['summary']} → {parsed[i+1]['summary']}",
            })

    return gaps


def suggest_tasks(gap_minutes, available_tasks=None):
    """
    Suggest tasks from the backlog that fit within a time gap.

    Args:
        gap_minutes: Available time in minutes
        available_tasks: Pre-fetched tasks list, or None to query DB

    Returns:
        List of task dicts sorted by priority and fit
    """
    if available_tasks is None:
        from src.goal_engine import get_available_tasks
        available_tasks = get_available_tasks(max_minutes=gap_minutes)

    # Filter tasks that fit, with some buffer (allow 10% over)
    fitting = [
        t for t in available_tasks
        if t.get("estimated_minutes", 30) <= gap_minutes * 1.1
    ]

    return fitting[:5]  # Return top 5 suggestions


def analyze_today():
    """
    Full analysis: find today's gaps and suggest tasks for each.

    Returns:
        List of dicts: [{"gap": {...}, "suggestions": [...]}]
    """
    from src.calendar_watcher import get_todays_events
    from src.goal_engine import get_available_tasks

    events = get_todays_events()
    gaps = find_gaps(events)
    all_tasks = get_available_tasks()

    results = []
    for gap in gaps:
        suggestions = suggest_tasks(gap["minutes"], all_tasks)
        results.append({
            "gap": gap,
            "suggestions": suggestions,
        })

    if results:
        total_free = sum(r["gap"]["minutes"] for r in results)
        log_activity(
            "micro_productivity",
            "analyze",
            f"Found {len(gaps)} gaps ({total_free} min free), {sum(len(r['suggestions']) for r in results)} task suggestions",
        )

    return results


def format_recommendations(results=None):
    """Format gap analysis results into readable text."""
    if results is None:
        results = analyze_today()

    if not results:
        return "No schedule gaps found today — fully booked or no events loaded."

    lines = ["⏰ Micro-Productivity Recommendations", ""]

    for r in results:
        gap = r["gap"]
        lines.append(f"📍 {gap['minutes']} min gap ({gap['between']})")

        if r["suggestions"]:
            for s in r["suggestions"][:3]:
                priority_icon = {"urgent": "🔴", "high": "🟡", "medium": "⚪", "low": "⬜"}.get(
                    s.get("goal_priority", "medium"), "⚪"
                )
                lines.append(
                    f"   {priority_icon} {s['title']} (~{s.get('estimated_minutes', '?')} min)"
                    f" — from: {s.get('goal_title', '?')}"
                )
        else:
            lines.append("   No matching tasks. Consider adding short tasks to your goals!")
        lines.append("")

    return "\n".join(lines)


def _parse_time(time_str):
    """Parse an ISO datetime string into a datetime object."""
    if not time_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.fromisoformat(time_str)
        except ValueError:
            continue
    return None


if __name__ == "__main__":
    from src.database import init_db

    init_db()
    print("\n--- Micro Productivity ---\n")
    print(format_recommendations())
