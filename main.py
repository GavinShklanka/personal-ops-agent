"""
Personal Ops Agent — Entry Point
Starts Klara's systems: scheduler, dashboard, or chat interface.

Usage:
  python main.py                    Start full agent (scheduler + dashboard)
  python main.py --chat             Start Klara chat interface
  python main.py --status           Show system status
  python main.py --briefing-now     Generate and print a morning briefing
  python main.py --dashboard-only   Start just the dashboard
"""

import sys
import os
import argparse
import threading
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent))


def cmd_status():
    """Show system connection status."""
    from src.database import get_connection, DB_PATH, init_db

    init_db()

    print("\n--- Personal Ops Agent Status ---\n")

    # Database
    print(f"Database: {DB_PATH}")
    conn = get_connection()
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    print(f"  Schema version: {version}")

    event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    goal_count = conn.execute("SELECT COUNT(*) FROM goals WHERE status='active'").fetchone()[0]
    email_count = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
    pending_count = conn.execute("SELECT COUNT(*) FROM approvals WHERE status='pending'").fetchone()[0]
    conn.close()

    print(f"  Events stored: {event_count}")
    print(f"  Active goals: {goal_count}")
    print(f"  Emails tracked: {email_count}")
    print(f"  Pending approvals: {pending_count}")

    # Google OAuth
    token_path = Path(__file__).parent / "config" / "credentials" / "token.json"
    if token_path.exists():
        print("\nGoogle OAuth: Connected ✓")
    else:
        print("\nGoogle OAuth: Not connected")
        print("  Run: python -m src.google_auth")

    # ntfy
    from dotenv import load_dotenv
    load_dotenv()
    topic = os.getenv("NTFY_TOPIC")
    if topic and topic != "klara-ops-CHANGE-ME":
        print(f"\nntfy: Configured ✓ (topic: {topic[:8]}...)")
    else:
        print("\nntfy: Not configured")
        print("  Set NTFY_TOPIC in .env")

    # Anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key and api_key != "your-key-here":
        print(f"\nAnthropic API: Configured ✓")
    else:
        print("\nAnthropic API: Not configured")

    print()


def cmd_chat():
    """Start Klara chat interface."""
    from src.klara import chat
    chat()


def cmd_briefing():
    """Generate and print a morning briefing now."""
    from src.database import init_db
    init_db()

    from src.daily_anchor import generate_briefing
    print("\n--- Generating Morning Briefing ---\n")
    briefing = generate_briefing(use_llm=True)
    print(briefing)
    print()


def cmd_dashboard_only():
    """Start just the Flask dashboard."""
    from src.database import init_db
    init_db()

    from src.dashboard import run_dashboard
    run_dashboard()


def cmd_full_agent():
    """Start the full agent: scheduler + dashboard."""
    from src.database import init_db
    init_db()

    print("\n" + "=" * 50)
    print("  Klara — Personal Ops Agent")
    print("=" * 50)

    # Start scheduler in background
    from src.scheduler import start as start_scheduler
    start_scheduler()

    # Start dashboard (blocks — runs Flask server)
    from src.dashboard import run_dashboard
    print()
    run_dashboard()


def main():
    parser = argparse.ArgumentParser(
        description="Personal Ops Agent — Klara",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                 Start full agent (scheduler + dashboard)
  python main.py --chat          Start Klara chat
  python main.py --status        Show connection status
  python main.py --briefing-now  Generate morning briefing
  python main.py --dashboard-only Start just the web dashboard
        """,
    )
    parser.add_argument("--chat", action="store_true", help="Start Klara chat interface")
    parser.add_argument("--status", action="store_true", help="Show system status")
    parser.add_argument("--briefing-now", action="store_true", help="Generate briefing now")
    parser.add_argument("--dashboard-only", action="store_true", help="Start just the dashboard")

    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.chat:
        cmd_chat()
    elif args.briefing_now:
        cmd_briefing()
    elif args.dashboard_only:
        cmd_dashboard_only()
    else:
        cmd_full_agent()


if __name__ == "__main__":
    main()
