# Personal Ops Agent — Klara

> *"I had always been aware of the Low Momentum — the risk of allowing one's curiosity to slow…"*
> — Klara, *Klara and the Sun* by Kazuo Ishiguro

Klara is an active AI personal assistant that helps you manage your schedule, track goals, stay on top of job opportunities, and make the most of your time.

She's named after the AF (Artificial Friend) in Kazuo Ishiguro's novel — observant, caring, and always looking out for her person.

---

## What Klara Does

- **Conversational interface** — Talk to Klara naturally. She remembers your conversation context within a session.
- **Morning briefings** — A daily summary of your calendar, active goals, and anything that needs your attention. *(WP4)*
- **Calendar awareness** — Polls Google Calendar to keep Klara informed of your schedule. *(WP3)*
- **Gmail triage** — Surfaces important emails by scanning metadata (subject/sender), without reading body content. *(WP3)*
- **Goal tracking** — Maintain weekly and monthly goals that Klara references when recommending how to spend your time. *(WP6)*
- **Micro-productivity** — Finds gaps in your calendar and suggests focused tasks to fill them. *(WP5)*
- **Opportunity radar** — Detects and summarizes job opportunity emails. *(WP7)*
- **Phone alerts** — Push notifications via ntfy.sh for time-sensitive items. *(WP8)*
- **World briefing** — Top RSS headlines relevant to your context. *(WP9)*
- **Approval gates** — Any action that modifies your calendar or sends a message requires your explicit sign-off. *(WP11)*

---

## Quickstart

See [docs/runbook.md](docs/runbook.md) for full setup instructions.

**Short version:**

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env        # Add your ANTHROPIC_API_KEY
python main.py
```

---

## Project Structure

```
personal-ops-agent/
├── config/           # settings.yaml + gitignored credentials/
├── src/              # All modules (klara.py is the working core; others are stubs)
├── db/               # SQLite databases (gitignored *.db)
├── docs/             # permissions.md, runbook.md
├── tests/            # pytest suite
├── main.py           # Entry point
└── requirements.txt
```

---

## Privacy & Permissions

Klara only has read-only access to Google Calendar and Gmail metadata in v1. No emails are sent, no calendar events are created, and all credentials are stored locally. See [docs/permissions.md](docs/permissions.md) for details.

---

## Status

v0.1 — Klara's conversational core is live. Background integrations (Google, ntfy, ChromaDB) are stubbed and will be implemented in subsequent work packages.
