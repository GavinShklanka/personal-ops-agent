"""
Gmail Watcher — Personal Ops Agent
Polls Gmail for new email metadata and flags job-related messages.
Read-only access — never sends, modifies, or deletes messages.
"""

import re
import yaml
from pathlib import Path
from datetime import datetime, timezone

from src.database import get_connection, log_activity
from src.google_auth import get_gmail_service

CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def _load_job_config():
    """Load job keyword configuration from settings.yaml."""
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    gmail_config = config.get("gmail", {})
    return {
        "keywords": [k.lower() for k in gmail_config.get("job_keywords", [])],
        "senders": [s.lower() for s in gmail_config.get("job_senders", [])],
    }


def _calculate_job_score(subject, sender, snippet, config):
    """
    Score how likely an email is job-related (0.0 to 1.0).
    Based on keyword matches in subject, sender, and snippet.
    """
    score = 0.0
    text = f"{subject} {snippet}".lower()
    sender_lower = sender.lower() if sender else ""

    # Check sender whitelist (high signal)
    for s in config["senders"]:
        if s in sender_lower:
            score += 0.5
            break

    # Check keywords in subject + snippet
    matches = sum(1 for kw in config["keywords"] if kw in text)
    if matches > 0:
        score += min(0.5, matches * 0.15)

    return min(1.0, score)


def poll(max_results=25):
    """
    Fetch recent emails from Gmail and store metadata in SQLite.
    Flags job-related emails based on configured keywords.
    Returns count of new and job-related emails.
    """
    service = get_gmail_service()
    job_config = _load_job_config()

    result = (
        service.users().messages().list(userId="me", maxResults=max_results).execute()
    )
    messages = result.get("messages", [])

    conn = get_connection()
    new_count = 0
    job_count = 0

    for msg_stub in messages:
        msg_id = msg_stub["id"]

        # Skip if already stored
        existing = conn.execute(
            "SELECT id FROM emails WHERE id = ?", (msg_id,)
        ).fetchone()
        if existing:
            continue

        # Fetch metadata
        detail = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            )
            .execute()
        )

        headers = {
            h["name"]: h["value"]
            for h in detail.get("payload", {}).get("headers", [])
        }

        subject = headers.get("Subject", "")
        sender = headers.get("From", "")
        snippet = detail.get("snippet", "")
        thread_id = detail.get("threadId", "")
        labels = ",".join(detail.get("labelIds", []))

        # Extract sender email
        email_match = re.search(r"<(.+?)>", sender)
        sender_email = email_match.group(1) if email_match else sender

        # Score for job relevance
        job_score = _calculate_job_score(subject, sender, snippet, job_config)
        is_job = 1 if job_score >= 0.3 else 0

        # Parse date
        received_at = headers.get("Date", "")

        conn.execute(
            """INSERT INTO emails
               (id, thread_id, sender, sender_email, subject, snippet,
                labels, received_at, is_job_related, job_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                msg_id,
                thread_id,
                sender,
                sender_email,
                subject,
                snippet,
                labels,
                received_at,
                is_job,
                job_score,
            ),
        )
        new_count += 1
        if is_job:
            job_count += 1

    conn.commit()
    conn.close()

    if new_count > 0:
        log_activity(
            "gmail_watcher",
            "poll",
            f"{new_count} new emails, {job_count} job-related",
        )

    return {"new": new_count, "job_related": job_count}


def get_job_emails(limit=20):
    """Get recent job-related emails from the database."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM emails
           WHERE is_job_related = 1
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_emails(limit=20):
    """Get the most recent emails from the database."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM emails ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    from src.database import init_db

    init_db()
    print("\n--- Gmail Watcher ---\n")
    result = poll()
    print(f"Poll complete: {result['new']} new emails, {result['job_related']} job-related")

    job_emails = get_job_emails(5)
    if job_emails:
        print("\nJob-related emails:")
        for e in job_emails:
            print(f"  • {e['subject']} (from: {e['sender_email']}, score: {e['job_score']:.2f})")
    else:
        print("\nNo job-related emails found yet.")
