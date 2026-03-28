"""
Notifications — Personal Ops Agent
Sends push notifications to Gavin's phone via ntfy.sh.
Respects quiet hours defined in config/settings.yaml.
"""

import os
import yaml
import requests
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"
NTFY_BASE_URL = "https://ntfy.sh"


def _load_config():
    """Load notification config from settings.yaml."""
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    return config.get("notifications", {})


def _in_quiet_hours():
    """Check if current time falls within quiet hours."""
    config = _load_config()
    quiet_start = config.get("quiet_hours_start", "22:00")
    quiet_end = config.get("quiet_hours_end", "07:00")

    now = datetime.now()
    current_time = now.strftime("%H:%M")

    # Handle overnight quiet hours (e.g., 22:00 - 07:00)
    if quiet_start > quiet_end:
        return current_time >= quiet_start or current_time < quiet_end
    else:
        return quiet_start <= current_time < quiet_end


def send(title, body="", priority="default", tags=None, suppress_quiet=True):
    """
    Send a push notification via ntfy.

    Args:
        title: Notification title
        body: Notification body text
        priority: One of 'min', 'low', 'default', 'high', 'urgent'
        tags: List of emoji tags (e.g., ['calendar', 'warning'])
        suppress_quiet: If True, suppress during quiet hours (unless urgent)

    Returns:
        True if sent, False if suppressed or failed
    """
    topic = os.getenv("NTFY_TOPIC")
    if not topic:
        print("Warning: NTFY_TOPIC not set in .env — notification not sent")
        return False

    # Respect quiet hours (unless urgent)
    if suppress_quiet and priority != "urgent" and _in_quiet_hours():
        _log_notification(title, body, priority, "suppressed")
        return False

    headers = {
        "Title": title,
        "Priority": priority,
    }
    if tags:
        headers["Tags"] = ",".join(tags)

    try:
        response = requests.post(
            f"{NTFY_BASE_URL}/{topic}",
            data=body.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        _log_notification(title, body, priority, "sent")
        return True
    except Exception as e:
        _log_notification(title, body, priority, "failed", str(e))
        print(f"Notification failed: {e}")
        return False


def _log_notification(title, body, priority, status, error=None):
    """Log notification to database."""
    try:
        from src.database import get_connection

        conn = get_connection()
        conn.execute(
            """INSERT INTO notifications (type, title, body, priority, sent_at, status, error)
               VALUES ('push', ?, ?, ?, datetime('now'), ?, ?)""",
            (title, body, priority, status, error),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Don't crash if DB isn't ready


if __name__ == "__main__":
    print("\n--- Notification Test ---\n")
    topic = os.getenv("NTFY_TOPIC")
    if not topic or topic == "klara-ops-CHANGE-ME":
        print("Set NTFY_TOPIC in your .env file first!")
        print("Example: NTFY_TOPIC=gavin-ops-k8x2m9q")
    else:
        success = send(
            title="🤖 Personal Ops Agent",
            body="Hello from Klara! Your notification system is working.",
            priority="default",
            tags=["robot_face", "white_check_mark"],
            suppress_quiet=False,
        )
        if success:
            print("✓ Test notification sent! Check your phone.")
        else:
            print("✗ Notification failed. Check your NTFY_TOPIC.")
