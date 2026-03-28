"""
Daily Anchor — Personal Ops Agent
Morning briefing engine that combines calendar events, active goals,
job email updates, and world headlines into a concise daily summary.
"""

import os
import yaml
import anthropic
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

from src.database import get_connection, log_activity

load_dotenv()
CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def _load_config():
    """Load daily anchor config."""
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    return config.get("daily_anchor", {})


def generate_briefing(use_llm=True):
    """
    Generate a morning briefing combining all available data.

    Args:
        use_llm: If True, use Klara (Anthropic) to compose the briefing.
                 If False, use a simple template.

    Returns:
        Formatted briefing string.
    """
    # Gather data
    events = _get_todays_events()
    goals = _get_active_goals()
    job_emails = _get_recent_job_emails()
    headlines = _get_headlines()

    if use_llm and os.getenv("ANTHROPIC_API_KEY"):
        briefing = _generate_with_klara(events, goals, job_emails, headlines)
    else:
        briefing = _generate_template(events, goals, job_emails, headlines)

    # Store the briefing
    _store_briefing(briefing)

    return briefing


def _get_todays_events():
    """Get today's calendar events from DB."""
    try:
        from src.calendar_watcher import get_todays_events
        return get_todays_events()
    except Exception:
        return []


def _get_active_goals():
    """Get active goals from DB."""
    try:
        from src.goal_engine import list_goals
        return list_goals(status="active")
    except Exception:
        return []


def _get_recent_job_emails():
    """Get recent job-related emails."""
    try:
        from src.gmail_watcher import get_job_emails
        return get_job_emails(limit=5)
    except Exception:
        return []


def _get_headlines():
    """Get stored world headlines."""
    try:
        from src.world_briefing import get_stored_headlines
        return get_stored_headlines(limit=5)
    except Exception:
        return []


def _generate_with_klara(events, goals, job_emails, headlines):
    """Use Anthropic API to compose a warm, concise briefing."""
    config = yaml.safe_load(open(CONFIG_PATH))
    model = config.get("klara", {}).get("model", "claude-sonnet-4-20250514")

    # Build context for Klara
    context_parts = []

    context_parts.append(f"Today is {datetime.now().strftime('%A, %B %d, %Y')}.")

    if events:
        context_parts.append("\nToday's schedule:")
        for ev in events:
            context_parts.append(f"  • {ev.get('start_time', '?')}: {ev.get('summary', 'Untitled')}")
    else:
        context_parts.append("\nNo calendar events today.")

    if goals:
        context_parts.append(f"\nActive goals ({len(goals)}):")
        for g in goals[:5]:
            deadline = f" (due: {g['deadline']})" if g.get("deadline") else ""
            context_parts.append(f"  • [{g['priority']}] {g['title']}{deadline}")

    if job_emails:
        context_parts.append(f"\nRecent job-related emails ({len(job_emails)}):")
        for e in job_emails[:3]:
            context_parts.append(f"  • {e.get('subject', 'No subject')} (from: {e.get('sender_email', '?')})")

    if headlines:
        context_parts.append("\nWorld headlines:")
        for h in headlines[:5]:
            context_parts.append(f"  • [{h.get('source', '?')}] {h.get('title', '')}")

    context = "\n".join(context_parts)

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=model,
            max_tokens=500,
            system=(
                "You are Klara, a warm and observant personal assistant. "
                "Generate a concise morning briefing for Gavin. Be warm but brief. "
                "Highlight the most important things for today. "
                "Format it cleanly with sections. Keep it under 200 words."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Here's today's data. Generate my morning briefing:\n\n{context}",
                }
            ],
        )
        return response.content[0].text
    except Exception as e:
        print(f"LLM briefing failed ({e}), falling back to template")
        return _generate_template(events, goals, job_emails, headlines)


def _generate_template(events, goals, job_emails, headlines):
    """Generate a simple template-based briefing (no LLM needed)."""
    lines = []
    lines.append(f"☀️ Good morning, Gavin!")
    lines.append(f"📅 {datetime.now().strftime('%A, %B %d, %Y')}")
    lines.append("")

    # Schedule
    lines.append("— Schedule —")
    if events:
        for ev in events:
            time_str = ev.get("start_time", "?")
            if "T" in time_str:
                time_str = time_str.split("T")[1][:5]
            lines.append(f"  {time_str}  {ev.get('summary', 'Untitled')}")
    else:
        lines.append("  No events today — open canvas!")
    lines.append("")

    # Goals
    if goals:
        lines.append(f"— Goals ({len(goals)} active) —")
        for g in goals[:3]:
            marker = "🔴" if g["priority"] == "urgent" else "🟡" if g["priority"] == "high" else "⚪"
            lines.append(f"  {marker} {g['title']}")
        lines.append("")

    # Job leads
    if job_emails:
        lines.append(f"— Job Updates ({len(job_emails)}) —")
        for e in job_emails[:2]:
            lines.append(f"  📧 {e.get('subject', 'No subject')}")
        lines.append("")

    # Headlines
    if headlines:
        lines.append("— Headlines —")
        for h in headlines[:3]:
            lines.append(f"  • {h.get('title', '')}")
        lines.append("")

    lines.append("Have a great day! — Klara")
    return "\n".join(lines)


def _store_briefing(content):
    """Store briefing in database."""
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO briefings (type, content) VALUES ('morning', ?)",
            (content,),
        )
        conn.commit()
        conn.close()
        log_activity("daily_anchor", "generate", f"Morning briefing ({len(content)} chars)")
    except Exception:
        pass


def send_briefing():
    """Generate and send the morning briefing via ntfy."""
    briefing = generate_briefing()

    try:
        from src.notifications import send
        send(
            title="☀️ Morning Briefing",
            body=briefing,
            priority="default",
            tags=["sunrise"],
            suppress_quiet=False,  # Morning briefing should always send
        )
    except Exception as e:
        print(f"Failed to send briefing notification: {e}")

    return briefing


if __name__ == "__main__":
    from src.database import init_db

    init_db()
    print("\n--- Daily Anchor — Morning Briefing ---\n")
    briefing = generate_briefing(use_llm=False)
    print(briefing)
