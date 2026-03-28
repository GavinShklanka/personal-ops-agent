"""
Klara — Personal Ops Agent
A thoughtful AI assistant that helps manage schedule, goals, and opportunities.

Phase 2 — True Agent Architecture:
  - Anthropic tool-use agentic loop (read + approval-gated write tools)
  - ChromaDB long-term memory (past conversation recall)
  - Live calendar context injected at startup
  - SQLite-backed goals and approval queue
"""

import datetime
import os
import uuid
import yaml
import anthropic
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"

# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool-use format)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_todays_schedule",
        "description": (
            "Get Gavin's Google Calendar events for today. "
            "Returns a formatted list of events with times, titles, and locations."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_upcoming_events",
        "description": "Get Gavin's calendar events for the next N days (default 7).",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look ahead (1–14). Default 7.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_free_windows",
        "description": (
            "Get Gavin's free time windows today — gaps between events "
            "with at least min_minutes of available time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_minutes": {
                    "type": "integer",
                    "description": "Minimum gap size in minutes. Default 30.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_active_goals",
        "description": (
            "Retrieve all of Gavin's currently active goals from the local database, "
            "including titles, descriptions, progress, and periods."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_goal",
        "description": (
            "Add a new goal to Gavin's goal tracker. "
            "This writes directly to the local database — no approval required."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title for the goal."},
                "description": {"type": "string", "description": "Longer description (optional)."},
                "period": {
                    "type": "string",
                    "enum": ["weekly", "monthly"],
                    "description": "Time period for the goal.",
                },
                "due_date": {
                    "type": "string",
                    "description": "Optional due date as YYYY-MM-DD.",
                },
            },
            "required": ["title", "period"],
        },
    },
    {
        "name": "update_goal_progress",
        "description": (
            "Update the progress percentage on one of Gavin's goals. "
            "Setting progress to 100 automatically marks the goal as completed. "
            "No approval required — this only updates the local database."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer", "description": "ID of the goal to update."},
                "progress": {
                    "type": "integer",
                    "description": "New progress from 0 to 100.",
                },
                "note": {
                    "type": "string",
                    "description": "Optional note about this progress update.",
                },
            },
            "required": ["goal_id", "progress"],
        },
    },
    {
        "name": "block_calendar_time",
        "description": (
            "Propose blocking time on Gavin's Google Calendar. "
            "IMPORTANT: This does NOT execute immediately. "
            "It sends the proposal to the approval queue for Gavin's review at "
            "http://localhost:5000/approvals. Always tell Gavin to check the dashboard."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event title for the calendar block."},
                "date": {"type": "string", "description": "Date as YYYY-MM-DD."},
                "start_time": {
                    "type": "string",
                    "description": "Start time in 24-hour HH:MM format.",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration of the block in minutes.",
                },
            },
            "required": ["title", "date", "start_time", "duration_minutes"],
        },
    },
    {
        "name": "draft_email_reply",
        "description": (
            "Draft an email reply for Gavin to review. "
            "IMPORTANT: This does NOT send anything. "
            "It queues the draft in the approval queue at http://localhost:5000/approvals "
            "where Gavin can review and approve before it goes anywhere."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address."},
                "subject": {"type": "string", "description": "Email subject line."},
                "body": {"type": "string", "description": "Full email body text."},
            },
            "required": ["to", "subject", "body"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

def _execute_tool(name: str, tool_input: dict) -> str:
    """Dispatch a tool call and return a plain-text result string."""
    try:
        if name == "get_todays_schedule":
            from src.calendar_watcher import get_todays_events, format_schedule_for_prompt
            events = get_todays_events()
            return format_schedule_for_prompt(events) if events else "No events scheduled today."

        elif name == "get_upcoming_events":
            from src.calendar_watcher import get_upcoming_events, format_schedule_for_prompt
            days = int(tool_input.get("days", 7))
            events = get_upcoming_events(days=days)
            return format_schedule_for_prompt(events) if events else f"No events in the next {days} days."

        elif name == "get_free_windows":
            from src.calendar_watcher import get_todays_events, detect_gaps, format_gaps_for_prompt
            min_min = int(tool_input.get("min_minutes", 30))
            events = get_todays_events()
            gaps = detect_gaps(events, min_gap_minutes=min_min)
            return format_gaps_for_prompt(gaps)

        elif name == "get_active_goals":
            from src.goal_engine import get_active_goals
            goals = get_active_goals()
            if not goals:
                return "No active goals. Use add_goal to set some."
            lines = []
            for g in goals:
                line = f"[ID {g['id']}] {g['title']} ({g['period']}) — {g['progress']}% complete"
                if g.get("due_date"):
                    line += f", due {g['due_date']}"
                if g.get("description"):
                    line += f"\n    {g['description']}"
                lines.append(line)
            return "\n".join(lines)

        elif name == "add_goal":
            from src.goal_engine import add_goal
            result = add_goal(
                title=tool_input["title"],
                description=tool_input.get("description", ""),
                period=tool_input.get("period", "weekly"),
                due_date=tool_input.get("due_date", ""),
            )
            return f"Goal added (ID {result['id']}): \"{result['title']}\" [{result['period']}]"

        elif name == "update_goal_progress":
            from src.goal_engine import update_goal_progress
            result = update_goal_progress(
                goal_id=int(tool_input["goal_id"]),
                progress=int(tool_input["progress"]),
                note=tool_input.get("note", ""),
            )
            if result["status"] == "completed":
                return f"Goal {result['goal_id']} marked complete. Well done!"
            return f"Goal {result['goal_id']} progress updated to {result['progress']}%."

        elif name == "block_calendar_time":
            from src.approval_queue import queue_action
            result = queue_action(
                "block_calendar_time",
                {
                    "title": tool_input["title"],
                    "date": tool_input["date"],
                    "start_time": tool_input["start_time"],
                    "duration_minutes": tool_input["duration_minutes"],
                },
            )
            return (
                f"Calendar block proposal queued (approval #{result['id']}). "
                "Gavin can approve or reject it at http://localhost:5000/approvals — "
                "nothing has been added to the calendar yet."
            )

        elif name == "draft_email_reply":
            from src.approval_queue import queue_action
            result = queue_action(
                "draft_email_reply",
                {
                    "to": tool_input["to"],
                    "subject": tool_input["subject"],
                    "body": tool_input["body"],
                },
            )
            return (
                f"Email draft queued for review (approval #{result['id']}). "
                "Gavin can read and approve it at http://localhost:5000/approvals — "
                "nothing has been sent yet."
            )

        else:
            return f"[Unknown tool: {name}]"

    except RuntimeError as e:
        # calendar not connected, etc.
        return f"[Tool unavailable: {e}]"
    except Exception as e:
        return f"[Tool error in {name}: {e}]"


# ---------------------------------------------------------------------------
# Calendar context (injected once at startup)
# ---------------------------------------------------------------------------

def _build_calendar_context() -> str:
    try:
        from src.calendar_watcher import (
            get_upcoming_events,
            get_todays_events,
            detect_gaps,
            format_schedule_for_prompt,
            format_gaps_for_prompt,
        )
    except ImportError:
        return ""

    try:
        today_events = get_todays_events()
        week_events = get_upcoming_events(days=7)
    except RuntimeError as e:
        return (
            "\n\n[CALENDAR: Not connected. "
            f"Reason: {e} "
            "Mention this to Gavin if he asks about his schedule and point him "
            "to docs/google_setup.md.]"
        )
    except Exception as e:
        return f"\n\n[CALENDAR: Error — {e}. Mention this if Gavin asks about his schedule.]"

    tz = datetime.datetime.now().astimezone().tzinfo
    today_label = datetime.datetime.now(tz=tz).strftime("%A, %B %-d, %Y")
    today_date = datetime.datetime.now(tz=tz).date()

    if today_events:
        today_section = (
            f"Today ({today_label}):\n"
            + format_schedule_for_prompt(today_events)
            + "\n\nFree windows today:\n"
            + format_gaps_for_prompt(detect_gaps(today_events))
        )
    else:
        today_section = f"Today ({today_label}): no scheduled events."

    rest = [e for e in week_events if e["start"].date() != today_date]
    week_section = (
        "This week's upcoming events:\n" + format_schedule_for_prompt(rest)
        if rest
        else "No further events this week."
    )

    return f"\n\n---\n{today_section}\n\n{week_section}\n---"


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

def _run_agentic_turn(
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    messages: list,
) -> tuple[str, list]:
    """
    Run the tool-use loop for a single user turn.
    Returns (final_text_response, updated_messages).
    Caps at 10 tool-call rounds to prevent infinite loops.
    """
    for _ in range(10):
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        # Append assistant's response (may contain tool_use blocks)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text = block.text
                    break
            return text, messages

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result_text = _execute_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                        }
                    )
            messages.append({"role": "user", "content": tool_results})
            continue  # Let Klara process the results

        # Unexpected stop_reason
        break

    return "[Klara hit the tool-call limit — please try rephrasing.]", messages


# ---------------------------------------------------------------------------
# Config + client
# ---------------------------------------------------------------------------

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def create_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env file.")
        print("Copy .env.example to .env and add your key.")
        raise SystemExit(1)
    return anthropic.Anthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Main chat loop
# ---------------------------------------------------------------------------

def chat():
    config = load_config()
    client = create_client()
    klara_cfg = config["klara"]
    model = klara_cfg["model"]
    base_prompt = klara_cfg["system_prompt"]

    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]

    # --- Build system prompt with calendar context + tool instructions ---
    calendar_ctx = _build_calendar_context()

    tool_instructions = """

You have tools to query live data and take actions on Gavin's behalf:

READ tools (call freely):
  • get_todays_schedule / get_upcoming_events / get_free_windows — live calendar data
  • get_active_goals — Gavin's current goals from the local database

WRITE tools — local database (no approval needed):
  • add_goal, update_goal_progress — these write directly to the local db

WRITE tools — external services (ALWAYS require approval):
  • block_calendar_time, draft_email_reply — these queue a proposal in the
    approval queue. Always tell Gavin to check http://localhost:5000/approvals
    and remind him that nothing has actually been sent or changed yet.

Rules:
  - Never fabricate calendar events or emails. Only reference what tools return.
  - When you don't know Gavin's schedule, call get_todays_schedule first.
  - Proactively notice free windows and suggest productive uses when relevant.
  - Frame write proposals as "I've queued X for your approval" — never "I've done X"."""

    system_prompt = base_prompt + tool_instructions + calendar_ctx

    # --- Load relevant memory from past sessions ---
    try:
        from src.memory import query_relevant, format_memories_for_prompt, is_available
        if is_available():
            memories = query_relevant(
                "Gavin's goals, schedule, preferences, and recent context",
                n_results=4,
                exclude_session=session_id,
            )
            if memories:
                memory_block = "\n\n" + format_memories_for_prompt(memories)
                system_prompt += memory_block
    except Exception:
        pass

    messages = []

    print()
    print("=" * 52)
    print("  Klara — Personal Ops Agent")
    print("  Dashboard: http://localhost:5000")
    print("  Type 'quit' or 'exit' to end")
    print("=" * 52)
    print()

    # Greeting (not added to history)
    try:
        greeting_resp = client.messages.create(
            model=model,
            max_tokens=300,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Say hello and briefly introduce yourself. "
                        "If you have calendar data, mention what today looks like in one sentence. "
                        "Keep it warm and concise — 2-3 sentences max."
                    ),
                }
            ],
        )
        print(f"Klara: {greeting_resp.content[0].text}")
    except Exception as e:
        print(f"Klara: Hello Gavin. I'm here and ready. ({e})")
    print()

    # --- Conversation loop ---
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKlara: Take care, Gavin. I'll be here when you need me.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "bye"):
            print("\nKlara: Take care, Gavin. I'll be here when you need me.")
            break

        messages.append({"role": "user", "content": user_input})

        # Store user turn in memory
        try:
            from src.memory import store_turn
            store_turn(session_id, "user", user_input)
        except Exception:
            pass

        # Store in SQLite conversation log
        try:
            from src.db import get_conn, init_db, now_iso
            init_db()
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO conversation_log (session_id, role, content, created_at) VALUES (?,?,?,?)",
                    (session_id, "user", user_input, now_iso()),
                )
        except Exception:
            pass

        try:
            response_text, messages = _run_agentic_turn(client, model, system_prompt, messages)
            print(f"\nKlara: {response_text}\n")

            # Store assistant turn in memory + SQLite
            try:
                from src.memory import store_turn
                store_turn(session_id, "assistant", response_text)
            except Exception:
                pass
            try:
                from src.db import get_conn, init_db, now_iso
                init_db()
                with get_conn() as conn:
                    conn.execute(
                        "INSERT INTO conversation_log (session_id, role, content, created_at) VALUES (?,?,?,?)",
                        (session_id, "assistant", response_text, now_iso()),
                    )
            except Exception:
                pass

        except anthropic.APIError as e:
            print(f"\n[Connection issue: {e}. Try again.]\n")
            # Roll back the last user message so history stays valid
            if messages and messages[-1]["role"] == "user":
                messages.pop()


if __name__ == "__main__":
    chat()
