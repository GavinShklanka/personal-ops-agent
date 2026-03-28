"""Tests for calendar_watcher utility functions."""

import datetime
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from calendar_watcher import (
    detect_gaps,
    format_gaps_for_prompt,
    format_schedule_for_prompt,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TZ = datetime.timezone.utc


def make_event(summary, start_hour, start_min, end_hour, end_min, all_day=False, day=None):
    if day is None:
        day = datetime.date.today()
    start = datetime.datetime(day.year, day.month, day.day, start_hour, start_min, tzinfo=TZ)
    end = datetime.datetime(day.year, day.month, day.day, end_hour, end_min, tzinfo=TZ)
    return {
        "summary": summary,
        "start": start,
        "end": end,
        "location": "",
        "description": "",
        "all_day": all_day,
    }


def make_all_day(summary, day=None):
    if day is None:
        day = datetime.date.today()
    start = datetime.datetime(day.year, day.month, day.day, 0, 0, tzinfo=TZ)
    end = datetime.datetime(day.year, day.month, day.day, 23, 59, tzinfo=TZ)
    return {
        "summary": summary,
        "start": start,
        "end": end,
        "location": "",
        "description": "",
        "all_day": True,
    }


# ---------------------------------------------------------------------------
# format_schedule_for_prompt
# ---------------------------------------------------------------------------


class TestFormatScheduleForPrompt:
    def test_empty_events(self):
        result = format_schedule_for_prompt([])
        assert result == "No events found."

    def test_single_event(self):
        events = [make_event("Team standup", 9, 0, 9, 30)]
        result = format_schedule_for_prompt(events)
        assert "Team standup" in result
        assert "9:00 AM" in result
        assert "9:30 AM" in result

    def test_multiple_events_sorted(self):
        events = [
            make_event("Lunch", 12, 0, 13, 0),
            make_event("Standup", 9, 0, 9, 30),
            make_event("Workshop", 15, 0, 16, 30),
        ]
        result = format_schedule_for_prompt(events)
        standup_pos = result.index("Standup")
        lunch_pos = result.index("Lunch")
        workshop_pos = result.index("Workshop")
        assert standup_pos < lunch_pos < workshop_pos

    def test_all_day_event(self):
        events = [make_all_day("Spring Break")]
        result = format_schedule_for_prompt(events)
        assert "All day" in result
        assert "Spring Break" in result

    def test_multi_day_events_grouped(self):
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)
        events = [
            make_event("Today meeting", 10, 0, 11, 0, day=today),
            make_event("Tomorrow meeting", 14, 0, 15, 0, day=tomorrow),
        ]
        result = format_schedule_for_prompt(events)
        today_pos = result.index(today.strftime("%A"))
        tomorrow_pos = result.index(tomorrow.strftime("%A"))
        assert today_pos < tomorrow_pos

    def test_event_with_location(self):
        today = datetime.date.today()
        event = make_event("Workshop", 10, 0, 11, 0, day=today)
        event["location"] = "Room 101"
        result = format_schedule_for_prompt([event])
        assert "Room 101" in result


# ---------------------------------------------------------------------------
# detect_gaps
# ---------------------------------------------------------------------------


class TestDetectGaps:
    def test_no_events_returns_open_gap(self):
        gaps = detect_gaps([])
        # Should return at least one open-ended gap (rest of day)
        assert len(gaps) >= 1
        open_gaps = [g for g in gaps if g["end"] is None]
        assert len(open_gaps) == 1

    def test_single_event_two_gaps(self):
        # One event in the middle of the day → gap before + gap after
        # We freeze "now" by using an event far in the future
        today = datetime.date.today()
        events = [make_event("Meeting", 14, 0, 15, 0, day=today)]
        gaps = detect_gaps(events, min_gap_minutes=1)
        # There should be a gap before the 2 PM meeting (if it's before 2 PM now)
        # and an open gap after. We can only assert the open-ended gap exists.
        open_gaps = [g for g in gaps if g["end"] is None]
        assert len(open_gaps) == 1

    def test_back_to_back_events_no_gap(self):
        today = datetime.date.today()
        events = [
            make_event("A", 9, 0, 10, 0, day=today),
            make_event("B", 10, 0, 11, 0, day=today),
        ]
        gaps = detect_gaps(events, min_gap_minutes=30)
        # No 30-minute gap between back-to-back events
        timed_gaps = [g for g in gaps if g["end"] is not None]
        assert all(g["duration_minutes"] >= 30 for g in timed_gaps)

    def test_overlapping_events(self):
        today = datetime.date.today()
        events = [
            make_event("A", 9, 0, 11, 0, day=today),
            make_event("B", 10, 0, 12, 0, day=today),  # overlaps with A
        ]
        # Should not crash; cursor advances past both events
        gaps = detect_gaps(events, min_gap_minutes=30)
        assert isinstance(gaps, list)

    def test_all_day_events_excluded_from_gap_detection(self):
        events = [make_all_day("Holiday")]
        gaps = detect_gaps(events, min_gap_minutes=30)
        # All-day events are skipped; the whole day should appear free
        open_gaps = [g for g in gaps if g["end"] is None]
        assert len(open_gaps) == 1

    def test_min_gap_filter(self):
        today = datetime.date.today()
        # Two events 15 minutes apart — shouldn't show up with 30-min threshold
        future = datetime.datetime.now(tz=TZ) + datetime.timedelta(hours=1)
        e1_start = future
        e1_end = future + datetime.timedelta(minutes=30)
        e2_start = e1_end + datetime.timedelta(minutes=15)
        e2_end = e2_start + datetime.timedelta(minutes=30)

        events = [
            {
                "summary": "Event 1",
                "start": e1_start,
                "end": e1_end,
                "location": "",
                "description": "",
                "all_day": False,
            },
            {
                "summary": "Event 2",
                "start": e2_start,
                "end": e2_end,
                "location": "",
                "description": "",
                "all_day": False,
            },
        ]
        gaps = detect_gaps(events, min_gap_minutes=30)
        # The 15-min window between the two events should NOT appear
        timed_gaps = [g for g in gaps if g["end"] is not None]
        assert all(g["duration_minutes"] >= 30 for g in timed_gaps)


# ---------------------------------------------------------------------------
# format_gaps_for_prompt
# ---------------------------------------------------------------------------


class TestFormatGapsForPrompt:
    def test_empty_gaps(self):
        result = format_gaps_for_prompt([])
        assert result == "No free windows found today."

    def test_open_ended_gap(self):
        now = datetime.datetime.now(tz=TZ).replace(hour=16, minute=30)
        gaps = [{"start": now, "end": None, "duration_minutes": None}]
        result = format_gaps_for_prompt(gaps)
        assert "After" in result or "rest of day" in result.lower()

    def test_timed_gap_shows_duration(self):
        now = datetime.datetime.now(tz=TZ).replace(hour=10, minute=0)
        later = now + datetime.timedelta(hours=2)
        gaps = [{"start": now, "end": later, "duration_minutes": 120}]
        result = format_gaps_for_prompt(gaps)
        assert "2 hour" in result or "120" in result

    def test_multiple_gaps(self):
        now = datetime.datetime.now(tz=TZ).replace(hour=10, minute=0)
        gap1_end = now + datetime.timedelta(minutes=90)
        gap2_start = gap1_end + datetime.timedelta(hours=1)
        gaps = [
            {"start": now, "end": gap1_end, "duration_minutes": 90},
            {"start": gap2_start, "end": None, "duration_minutes": None},
        ]
        result = format_gaps_for_prompt(gaps)
        assert result.count("-") >= 2  # At least two entries
