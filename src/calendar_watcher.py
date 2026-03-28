"""
Calendar Watcher — Personal Ops Agent (Klara)
Connects to Google Calendar API (read-only in v1), fetches events,
detects gaps, and provides schedule context to Klara.
"""

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

CREDENTIALS_DIR = Path(__file__).parent.parent / "config" / "credentials"
CREDENTIALS_PATH = CREDENTIALS_DIR / "credentials.json"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"


def _local_tz() -> datetime.timezone:
    """Return the local timezone as a datetime.timezone (or ZoneInfo if available)."""
    try:
        import time as _time
        local_name = _time.tzname[0]
        return ZoneInfo(local_name)
    except (ZoneInfoNotFoundError, Exception):
        return datetime.timezone(datetime.timedelta(seconds=-datetime.datetime.now().astimezone().utcoffset().total_seconds()))


def authenticate():
    """
    Handle the OAuth2 flow. Saves token.json after first auth so subsequent
    calls don't require browser interaction. Refreshes automatically on expiry.

    Returns a Google Calendar API service object, or raises RuntimeError
    if credentials.json is missing.
    """
    if not CREDENTIALS_PATH.exists():
        raise RuntimeError(
            f"Google credentials not found at {CREDENTIALS_PATH}.\n"
            "Follow the setup guide at docs/google_setup.md to create them."
        )

    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def get_upcoming_events(days: int = 7) -> list[dict]:
    """
    Fetch events from all calendars for the next `days` days.

    Returns a list of dicts with keys:
        summary, start, end, location, description, all_day
    All times are datetime objects in the local timezone.
    """
    service = authenticate()
    tz = datetime.datetime.now().astimezone().tzinfo

    now = datetime.datetime.now(tz=tz)
    time_min = now.isoformat()
    time_max = (now + datetime.timedelta(days=days)).isoformat()

    try:
        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except HttpError as e:
        raise RuntimeError(f"Google Calendar API error: {e}") from e

    events = []
    for item in result.get("items", []):
        start_raw = item.get("start", {})
        end_raw = item.get("end", {})

        all_day = "date" in start_raw and "dateTime" not in start_raw

        if all_day:
            start_dt = datetime.datetime.fromisoformat(start_raw["date"]).replace(
                hour=0, minute=0, tzinfo=tz
            )
            end_dt = datetime.datetime.fromisoformat(end_raw["date"]).replace(
                hour=23, minute=59, tzinfo=tz
            )
        else:
            start_dt = datetime.datetime.fromisoformat(start_raw["dateTime"]).astimezone(tz)
            end_dt = datetime.datetime.fromisoformat(end_raw["dateTime"]).astimezone(tz)

        events.append(
            {
                "summary": item.get("summary", "(No title)"),
                "start": start_dt,
                "end": end_dt,
                "location": item.get("location", ""),
                "description": item.get("description", ""),
                "all_day": all_day,
            }
        )

    events.sort(key=lambda e: e["start"])
    return events


def get_todays_events() -> list[dict]:
    """Return only events that fall (or start) today."""
    tz = datetime.datetime.now().astimezone().tzinfo
    today = datetime.datetime.now(tz=tz).date()

    all_events = get_upcoming_events(days=1)
    return [e for e in all_events if e["start"].date() == today]


def detect_gaps(events: list[dict], min_gap_minutes: int = 30) -> list[dict]:
    """
    Given a list of today's events, return free time windows of at least
    `min_gap_minutes` minutes.

    Returns a list of dicts with keys:
        start (datetime), end (datetime | None), duration_minutes (int | None)
    end is None when the gap extends to end-of-day (open-ended).
    """
    tz = datetime.datetime.now().astimezone().tzinfo
    today = datetime.datetime.now(tz=tz).date()
    now = datetime.datetime.now(tz=tz)

    # Work with today's timed events only (skip all-day events for gap detection)
    timed = [e for e in events if not e["all_day"] and e["start"].date() == today]
    timed.sort(key=lambda e: e["start"])

    gaps = []
    cursor = now  # Start looking from now, not midnight

    for event in timed:
        if event["start"] <= cursor:
            # Event already started or overlaps — advance cursor if needed
            cursor = max(cursor, event["end"])
            continue

        gap_minutes = int((event["start"] - cursor).total_seconds() / 60)
        if gap_minutes >= min_gap_minutes:
            gaps.append(
                {
                    "start": cursor,
                    "end": event["start"],
                    "duration_minutes": gap_minutes,
                }
            )
        cursor = max(cursor, event["end"])

    # Gap after the last event (open-ended, rest of day)
    gaps.append({"start": cursor, "end": None, "duration_minutes": None})

    return gaps


def _fmt_time(dt: datetime.datetime) -> str:
    """Format a datetime to '9:00 AM' style."""
    return dt.strftime("%-I:%M %p").lstrip("0") if hasattr(dt, "strftime") else str(dt)


def format_schedule_for_prompt(events: list[dict]) -> str:
    """
    Format a list of events into a clean text block for Klara's system prompt.
    Groups events by day.
    """
    if not events:
        return "No events found."

    from collections import defaultdict

    by_day: dict[datetime.date, list[dict]] = defaultdict(list)
    for e in events:
        by_day[e["start"].date()].append(e)

    lines = []
    for day in sorted(by_day.keys()):
        day_label = day.strftime("%A, %B %-d, %Y")
        lines.append(f"{day_label}:")
        for e in by_day[day]:
            if e["all_day"]:
                entry = f"  - All day: {e['summary']}"
            else:
                entry = f"  - {_fmt_time(e['start'])} - {_fmt_time(e['end'])}: {e['summary']}"
                if e["location"]:
                    entry += f" @ {e['location']}"
            lines.append(entry)
        lines.append("")

    return "\n".join(lines).rstrip()


def format_gaps_for_prompt(gaps: list[dict]) -> str:
    """
    Format detected free windows into text for Klara.
    """
    if not gaps:
        return "No free windows found today."

    lines = []
    for gap in gaps:
        if gap["end"] is None:
            lines.append(f"  - After {_fmt_time(gap['start'])} (rest of day)")
        else:
            mins = gap["duration_minutes"]
            hrs = mins // 60
            rem = mins % 60
            if hrs and rem:
                dur = f"{hrs}h {rem}m"
            elif hrs:
                dur = f"{hrs} hour{'s' if hrs > 1 else ''}"
            else:
                dur = f"{mins} minutes"
            lines.append(
                f"  - {_fmt_time(gap['start'])} - {_fmt_time(gap['end'])} ({dur})"
            )

    return "\n".join(lines)
