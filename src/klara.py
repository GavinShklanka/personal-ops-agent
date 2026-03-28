"""
Klara — Personal Ops Agent
A thoughtful AI assistant that helps manage schedule, goals, and opportunities.
"""

import os
import datetime
import yaml
import anthropic
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Load settings
CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def create_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env file.")
        print("Copy .env.example to .env and add your key.")
        raise SystemExit(1)
    return anthropic.Anthropic(api_key=api_key)


def _build_calendar_context() -> str:
    """
    Try to fetch today's and this week's calendar events.
    Returns a formatted string to inject into the system prompt,
    or a fallback message if the calendar is not connected.
    """
    try:
        from calendar_watcher import (
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
        # credentials.json missing or API error
        return (
            "\n\n[CALENDAR STATUS: Not connected. "
            f"Reason: {e} "
            "Tell Gavin you don't have calendar access yet and point him to docs/google_setup.md.]"
        )
    except Exception as e:
        return (
            f"\n\n[CALENDAR STATUS: Error fetching calendar data ({e}). "
            "Mention this to Gavin if he asks about his schedule.]"
        )

    tz = datetime.datetime.now().astimezone().tzinfo
    today_label = datetime.datetime.now(tz=tz).strftime("%A, %B %-d, %Y")

    # Build today's section
    if today_events:
        today_schedule = format_schedule_for_prompt(today_events)
        gaps = detect_gaps(today_events)
        gaps_text = format_gaps_for_prompt(gaps)
        today_section = (
            f"Here is Gavin's schedule for today ({today_label}):\n"
            f"{today_schedule}\n\n"
            f"Free windows today:\n{gaps_text}"
        )
    else:
        today_section = f"Gavin has no scheduled events today ({today_label})."

    # Build this week's section (exclude today to avoid repetition)
    today_date = datetime.datetime.now(tz=tz).date()
    rest_of_week = [e for e in week_events if e["start"].date() != today_date]

    if rest_of_week:
        week_schedule = format_schedule_for_prompt(rest_of_week)
        week_section = f"This week's upcoming events:\n{week_schedule}"
    else:
        week_section = "No further events scheduled this week."

    return f"\n\n---\n{today_section}\n\n{week_section}\n---"


def _build_system_prompt(base_prompt: str, calendar_context: str) -> str:
    """Combine the base system prompt with live calendar context."""
    calendar_instructions = """

When answering questions about Gavin's schedule, time, or availability:
- Reference the actual calendar events listed above — never fabricate events.
- Proactively notice free windows and suggest productive uses when relevant.
- When proposing a scheduling action (blocking time, rescheduling, etc.), frame it
  as a suggestion that needs Gavin's approval before any action is taken.
- If asked about calendar data you don't have (other people's calendars, past events
  beyond what's listed), say so clearly rather than guessing."""

    if "[CALENDAR STATUS: Not connected" in calendar_context or "[CALENDAR STATUS: Error" in calendar_context:
        return base_prompt + calendar_context
    elif calendar_context:
        return base_prompt + calendar_instructions + calendar_context
    else:
        return base_prompt


def chat():
    """Main conversational loop with Klara."""
    config = load_config()
    client = create_client()
    klara_config = config["klara"]

    base_system_prompt = klara_config["system_prompt"]
    model = klara_config["model"]

    # Fetch calendar context once at startup
    calendar_context = _build_calendar_context()
    system_prompt = _build_system_prompt(base_system_prompt, calendar_context)

    messages = []

    print()
    print("=" * 50)
    print("  Klara — Personal Ops Agent")
    print("  Type 'quit' or 'exit' to end the conversation")
    print("=" * 50)
    print()

    # Klara's greeting
    greeting_response = client.messages.create(
        model=model,
        max_tokens=300,
        system=system_prompt,
        messages=[{"role": "user", "content": "Say hello and briefly introduce yourself. Keep it warm and concise — 2-3 sentences max."}]
    )
    greeting = greeting_response.content[0].text
    print(f"Klara: {greeting}")
    print()

    # Don't add greeting to conversation history — start fresh

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

        try:
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages
            )

            assistant_message = response.content[0].text
            messages.append({"role": "assistant", "content": assistant_message})

            print(f"\nKlara: {assistant_message}\n")

        except anthropic.APIError as e:
            print(f"\n[Connection issue: {e}. Try again.]\n")
            messages.pop()  # Remove the failed user message


if __name__ == "__main__":
    chat()
