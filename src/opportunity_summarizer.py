"""
Opportunity Summarizer — Personal Ops Agent
Processes job-related email metadata and generates brief summaries.
Rule-based keyword extraction in v1 (no LLM required).
"""

import re
from datetime import datetime

from src.database import get_connection, log_activity


# Common job-related patterns
COMPANY_PATTERNS = [
    r"from\s+(.+?)\s+team",
    r"at\s+(.+?)[,\.\!]",
    r"join\s+(.+?)[,\.\!]",
    r"(.+?)\s+is\s+hiring",
    r"(.+?)\s+is\s+looking",
]

ROLE_PATTERNS = [
    r"((?:senior|junior|lead|staff|principal)?\s*(?:software|data|ml|ai|full.?stack|back.?end|front.?end|devops|cloud|platform)\s*(?:engineer|developer|scientist|analyst|architect))",
    r"((?:project|product|program)\s+manager)",
    r"((?:technical|engineering)\s+(?:lead|manager|director))",
]


def summarize_email(email):
    """
    Generate a summary for a single job-related email.

    Args:
        email: Dict with subject, snippet, sender, sender_email keys

    Returns:
        Dict with company, role, summary, and source fields
    """
    subject = email.get("subject", "")
    snippet = email.get("snippet", "")
    sender = email.get("sender", "")
    text = f"{subject} {snippet}".lower()

    # Extract company name
    company = _extract_company(text, sender)

    # Extract role
    role = _extract_role(text)

    # Build summary
    summary = f"{subject}"
    if company and company != "Unknown":
        summary = f"[{company}] {summary}"

    return {
        "email_id": email.get("id"),
        "company": company,
        "role": role,
        "summary": summary,
        "source": email.get("sender_email", ""),
    }


def summarize_new_opportunities():
    """
    Summarize all unsummarized job emails and store as job leads.

    Returns:
        Number of new leads created
    """
    conn = get_connection()

    # Find job emails that don't have corresponding job_leads
    rows = conn.execute(
        """SELECT e.* FROM emails e
           LEFT JOIN job_leads j ON e.id = j.email_id
           WHERE e.is_job_related = 1 AND j.id IS NULL
           ORDER BY e.created_at DESC"""
    ).fetchall()

    new_leads = 0
    for row in rows:
        email = dict(row)
        result = summarize_email(email)

        conn.execute(
            """INSERT INTO job_leads (email_id, company, role, summary)
               VALUES (?, ?, ?, ?)""",
            (result["email_id"], result["company"], result["role"], result["summary"]),
        )
        new_leads += 1

    conn.commit()
    conn.close()

    if new_leads > 0:
        log_activity(
            "opportunity_summarizer",
            "summarize",
            f"Created {new_leads} new job lead summaries",
        )

    return new_leads


def get_leads(status="new", limit=20):
    """Get job leads from the database."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT j.*, e.subject, e.sender_email, e.received_at
           FROM job_leads j
           LEFT JOIN emails e ON j.email_id = e.id
           WHERE j.status = ?
           ORDER BY j.created_at DESC
           LIMIT ?""",
        (status, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def format_digest(leads=None):
    """Format job leads into a readable digest."""
    if leads is None:
        leads = get_leads()

    if not leads:
        return "No new job opportunities to report."

    lines = ["💼 Job Opportunity Digest", ""]
    for lead in leads:
        company = lead.get("company", "?")
        role = lead.get("role", "")
        summary = lead.get("summary", "")
        lines.append(f"  🏢 {company}")
        if role:
            lines.append(f"     Role: {role}")
        lines.append(f"     {summary}")
        lines.append("")

    return "\n".join(lines)


def _extract_company(text, sender=""):
    """Try to extract a company name from email text or sender."""
    # Try sender domain first
    if "@" in sender:
        domain = sender.split("@")[-1].split(">")[0]
        # Skip common email providers
        generic = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "mail.com"}
        if domain not in generic:
            return domain.split(".")[0].title()

    # Try patterns
    for pattern in COMPANY_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()

    return "Unknown"


def _extract_role(text):
    """Try to extract a job role/title from text."""
    for pattern in ROLE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()
    return ""


if __name__ == "__main__":
    from src.database import init_db

    init_db()
    print("\n--- Opportunity Summarizer ---\n")
    new = summarize_new_opportunities()
    print(f"New leads created: {new}")
    print()
    print(format_digest())
