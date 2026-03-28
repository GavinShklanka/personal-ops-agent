# Klara — Permissions & Scope

This document describes what Klara can and cannot access at each stage of development.

## v1 Scopes

### Google Calendar
- **Scope:** `https://www.googleapis.com/auth/calendar.readonly`
- **Access:** Read-only. Klara can see events, titles, times, and attendees.
- **Cannot:** Create, edit, or delete any calendar events.

### Gmail
- **Scope:** `https://www.googleapis.com/auth/gmail.metadata`
- **Access:** Metadata only — subject lines, sender addresses, timestamps, labels.
- **Cannot:** Read email body content, send emails, modify or delete messages.

## What Klara Will Never Do Automatically

- Send emails on your behalf
- Auto-apply to job listings
- Accept or decline calendar invites
- Make any commitment that involves another person

## Future Scopes (Planned, Not Yet Active)

| Scope | When | Gate |
|---|---|---|
| `calendar.events` (write) | WP11 | Approval queue — explicit confirmation required per action |
| `gmail.send` | TBD | Out of scope for now |

## Credential Storage

All OAuth tokens are stored locally in `config/credentials/` and are gitignored. They never leave your machine. No credentials are logged or transmitted to any service other than Google's OAuth endpoints.
