"""
Calendar Watcher — Personal Ops Agent
Polls Google Calendar for upcoming events and stores them in SQLite.
Read-only access — never creates, modifies, or deletes events.
"""

import json
from datetime import datetime, timedelta, timezone

from src.database import get_connection, log_activity
from src.google_auth import get_calendar_service


def poll(days_ahead=7):
    """
    Fetch events for the next `days_ahead` days from Google Calendar.
    Stores new events, updates changed ones, returns count of changes.
    """
    service = get_calendar_service()
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days_ahead)).isoformat()

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=100,
        )
        .execute()
    )

    events = result.get("items", [])
    conn = get_connection()
    new_count = 0
    updated_count = 0

    for event in events:
        event_id = event.get("id")
        if not event_id:
            continue

        start = event.get("start", {})
        end = event.get("end", {})
        all_day = 1 if "date" in start else 0
        start_time = start.get("dateTime", start.get("date", ""))
        end_time = end.get("dateTime", end.get("date", ""))

        # Check if event already exists
        existing = conn.execute(
            "SELECT id, raw_json FROM events WHERE id = ?", (event_id,)
        ).fetchone()

        raw = json.dumps(event)

        if existing:
            if existing["raw_json"] != raw:
                conn.execute(
                    """UPDATE events
                       SET summary=?, description=?, location=?,
                           start_time=?, end_time=?, all_day=?,
                           status=?, raw_json=?, last_synced=datetime('now')
                       WHERE id=?""",
                    (
                        event.get("summary", ""),
                        event.get("description", ""),
                        event.get("location", ""),
                        start_time,
                        end_time,
                        all_day,
                        event.get("status", "confirmed"),
                        raw,
                        event_id,
                    ),
                )
                updated_count += 1
        else:
            conn.execute(
                """INSERT INTO events
                   (id, summary, description, location, start_time, end_time,
                    all_day, status, calendar_id, raw_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'primary', ?)""",
                (
                    event_id,
                    event.get("summary", ""),
                    event.get("description", ""),
                    event.get("location", ""),
                    start_time,
                    end_time,
                    all_day,
                    event.get("status", "confirmed"),
                    raw,
                ),
            )
            new_count += 1

    conn.commit()
    conn.close()

    total = new_count + updated_count
    if total > 0:
        log_activity(
            "calendar_watcher",
            "poll",
            f"Fetched {len(events)} events: {new_count} new, {updated_count} updated",
        )

    return {"total": len(events), "new": new_count, "updated": updated_count}


def get_todays_events():
    """Get today's events from the database, sorted by start time."""
    conn = get_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    rows = conn.execute(
        """SELECT * FROM events
           WHERE start_time >= ? AND start_time < ?
           AND status != 'cancelled'
           ORDER BY start_time""",
        (today, tomorrow),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_upcoming_events(hours=48):
    """Get upcoming events within the next N hours."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()

    rows = conn.execute(
        """SELECT * FROM events
           WHERE start_time >= ? AND start_time <= ?
           AND status != 'cancelled'
           ORDER BY start_time""",
        (now, until),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    from src.database import init_db

    init_db()
    print("\n--- Calendar Watcher ---\n")
    result = poll()
    print(f"Poll complete: {result['total']} events fetched")
    print(f"  New: {result['new']}, Updated: {result['updated']}")

    print("\nToday's events:")
    for ev in get_todays_events():
        print(f"  • {ev['start_time']}: {ev['summary']}")
