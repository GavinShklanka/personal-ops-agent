"""
Dashboard — Personal Ops Agent
Local Flask web UI at localhost:5000 for viewing schedule, goals,
job leads, world briefing, and approval queue.
Dark mode, premium design. Read-only in v1.
"""

import yaml
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template_string, request, redirect, url_for, jsonify

from src.database import get_connection, init_db

CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"

app = Flask(__name__)

# ──────────────────────────────────────────────
#  HTML TEMPLATE — Dark Mode Dashboard
# ──────────────────────────────────────────────

BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Klara — Personal Ops Agent</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg-primary: #0a0e17;
    --bg-secondary: #111827;
    --bg-card: #1a2235;
    --bg-card-hover: #1f2a40;
    --border: #2a3650;
    --text-primary: #e8ecf4;
    --text-secondary: #8892a6;
    --text-dim: #5a6478;
    --accent-cyan: #06d6a0;
    --accent-blue: #4ea8de;
    --accent-amber: #f4a261;
    --accent-red: #ef476f;
    --accent-purple: #9b5de5;
    --shadow: 0 4px 24px rgba(0,0,0,0.3);
    --radius: 12px;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: 'Inter', system-ui, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    line-height: 1.6;
  }

  .top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 32px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(10px);
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 600;
    color: var(--accent-cyan);
  }

  .logo span { color: var(--text-secondary); font-weight: 400; font-size: 14px; }

  .nav-links { display: flex; gap: 24px; }
  .nav-links a {
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
    transition: color 0.2s;
  }
  .nav-links a:hover, .nav-links a.active { color: var(--accent-cyan); }

  .status-badge {
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 20px;
    background: rgba(6, 214, 160, 0.15);
    color: var(--accent-cyan);
    border: 1px solid rgba(6, 214, 160, 0.3);
  }

  .container {
    max-width: 1280px;
    margin: 0 auto;
    padding: 24px 32px;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
    gap: 20px;
  }

  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    transition: background 0.2s, transform 0.2s;
  }
  .card:hover {
    background: var(--bg-card-hover);
    transform: translateY(-1px);
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .card-title {
    font-size: 14px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-secondary);
  }

  .card-icon { font-size: 20px; }

  .card-content { font-size: 14px; }

  .event-item, .goal-item, .email-item, .headline-item, .approval-item {
    padding: 10px 0;
    border-bottom: 1px solid rgba(42, 54, 80, 0.5);
  }
  .event-item:last-child, .goal-item:last-child, .email-item:last-child,
  .headline-item:last-child, .approval-item:last-child {
    border-bottom: none;
  }

  .event-time {
    font-size: 12px;
    color: var(--accent-blue);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .event-title { font-size: 14px; margin-top: 2px; }

  .priority-urgent { color: var(--accent-red); }
  .priority-high { color: var(--accent-amber); }
  .priority-medium { color: var(--text-primary); }
  .priority-low { color: var(--text-dim); }

  .badge {
    display: inline-block;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 500;
  }
  .badge-pending { background: rgba(244,162,97,0.2); color: var(--accent-amber); }
  .badge-approved { background: rgba(6,214,160,0.2); color: var(--accent-cyan); }
  .badge-rejected { background: rgba(239,71,111,0.2); color: var(--accent-red); }
  .badge-new { background: rgba(78,168,222,0.2); color: var(--accent-blue); }

  .empty-state {
    color: var(--text-dim);
    font-style: italic;
    font-size: 13px;
    padding: 16px 0;
  }

  .btn {
    display: inline-block;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    text-decoration: none;
    transition: opacity 0.2s;
    margin-right: 6px;
  }
  .btn:hover { opacity: 0.85; }
  .btn-approve { background: var(--accent-cyan); color: var(--bg-primary); }
  .btn-reject { background: var(--accent-red); color: white; }

  .full-width { grid-column: 1 / -1; }

  .hero-date {
    font-size: 28px;
    font-weight: 300;
    color: var(--text-primary);
    margin-bottom: 4px;
  }
  .hero-sub {
    font-size: 14px;
    color: var(--text-dim);
    margin-bottom: 24px;
  }

  @media (max-width: 768px) {
    .container { padding: 16px; }
    .grid { grid-template-columns: 1fr; }
    .top-bar { padding: 12px 16px; }
  }
</style>
</head>
<body>
  <div class="top-bar">
    <div class="logo">
      🤖 Klara <span>Personal Ops Agent</span>
    </div>
    <div class="nav-links">
      <a href="/" class="{{ 'active' if page == 'home' }}">Dashboard</a>
      <a href="/goals" class="{{ 'active' if page == 'goals' }}">Goals</a>
      <a href="/approvals" class="{{ 'active' if page == 'approvals' }}">Approvals</a>
    </div>
    <div class="status-badge">● Online</div>
  </div>

  <div class="container">
    {% block content %}{% endblock %}
  </div>
</body>
</html>
"""

DASHBOARD_HTML = """
{% extends "base" %}
{% block content %}
<div class="hero-date">{{ today_formatted }}</div>
<div class="hero-sub">{{ greeting }}</div>

<div class="grid">
  <!-- Today's Schedule -->
  <div class="card">
    <div class="card-header">
      <span class="card-title">📅 Today's Schedule</span>
      <span class="card-icon">{{ events|length }}</span>
    </div>
    <div class="card-content">
      {% if events %}
        {% for ev in events %}
        <div class="event-item">
          <div class="event-time">{{ ev.start_display }}</div>
          <div class="event-title">{{ ev.summary or 'Untitled' }}</div>
        </div>
        {% endfor %}
      {% else %}
        <div class="empty-state">No events today — open canvas!</div>
      {% endif %}
    </div>
  </div>

  <!-- Active Goals -->
  <div class="card">
    <div class="card-header">
      <span class="card-title">🎯 Active Goals</span>
      <span class="card-icon">{{ goals|length }}</span>
    </div>
    <div class="card-content">
      {% if goals %}
        {% for g in goals[:6] %}
        <div class="goal-item">
          <span class="priority-{{ g.priority }}">●</span>
          {{ g.title }}
          {% if g.deadline %}
            <span style="float:right; font-size:12px; color:var(--text-dim)">
              due {{ g.deadline }}
            </span>
          {% endif %}
        </div>
        {% endfor %}
      {% else %}
        <div class="empty-state">No active goals. Add some to get started!</div>
      {% endif %}
    </div>
  </div>

  <!-- Job Opportunities -->
  <div class="card">
    <div class="card-header">
      <span class="card-title">💼 Job Opportunities</span>
      <span class="card-icon">{{ leads|length }}</span>
    </div>
    <div class="card-content">
      {% if leads %}
        {% for l in leads[:5] %}
        <div class="email-item">
          <div style="display:flex; justify-content:space-between; align-items:center">
            <strong>{{ l.company or 'Unknown' }}</strong>
            <span class="badge badge-{{ l.status }}">{{ l.status }}</span>
          </div>
          <div style="font-size:13px; color:var(--text-secondary); margin-top:2px">
            {{ l.summary[:80] }}{{ '...' if l.summary|length > 80 }}
          </div>
        </div>
        {% endfor %}
      {% else %}
        <div class="empty-state">No job leads yet. Connect Gmail to start tracking.</div>
      {% endif %}
    </div>
  </div>

  <!-- World Headlines -->
  <div class="card">
    <div class="card-header">
      <span class="card-title">📰 World Headlines</span>
    </div>
    <div class="card-content">
      {% if headlines %}
        {% for h in headlines[:5] %}
        <div class="headline-item">
          <span style="font-size:11px; color:var(--accent-blue)">{{ h.source }}</span>
          <div>
            {% if h.url %}<a href="{{ h.url }}" target="_blank" style="color:var(--text-primary); text-decoration:none">{{ h.title }}</a>
            {% else %}{{ h.title }}{% endif %}
          </div>
        </div>
        {% endfor %}
      {% else %}
        <div class="empty-state">No headlines loaded. They refresh automatically.</div>
      {% endif %}
    </div>
  </div>

  <!-- Pending Approvals -->
  {% if pending_approvals %}
  <div class="card full-width">
    <div class="card-header">
      <span class="card-title">⚠️ Pending Approvals</span>
      <span class="card-icon">{{ pending_approvals|length }}</span>
    </div>
    <div class="card-content">
      {% for a in pending_approvals %}
      <div class="approval-item" style="display:flex; justify-content:space-between; align-items:center">
        <div>
          <span class="badge badge-pending">{{ a.action_type }}</span>
          {{ a.description }}
        </div>
        <div>
          <a href="/approvals/{{ a.id }}/approve" class="btn btn-approve">Approve</a>
          <a href="/approvals/{{ a.id }}/reject" class="btn btn-reject">Reject</a>
        </div>
      </div>
      {% endfor %}
    </div>
  </div>
  {% endif %}
</div>
{% endblock %}
"""

GOALS_HTML = """
{% extends "base" %}
{% block content %}
<div class="hero-date">Goals</div>
<div class="hero-sub">Track what matters</div>

<div class="grid">
  <div class="card full-width">
    <div class="card-header">
      <span class="card-title">🎯 Active Goals ({{ goals|length }})</span>
    </div>
    <div class="card-content">
      {% if goals %}
        {% for g in goals %}
        <div class="goal-item">
          <div style="display:flex; justify-content:space-between; align-items:center">
            <div>
              <span class="priority-{{ g.priority }}">●</span>
              <strong>{{ g.title }}</strong>
              {% if g.description %}
                <div style="font-size:13px; color:var(--text-secondary); margin-top:2px; padding-left:16px">
                  {{ g.description[:100] }}
                </div>
              {% endif %}
            </div>
            <div style="text-align:right">
              {% if g.deadline %}
                <div style="font-size:12px; color:var(--text-dim)">Due: {{ g.deadline }}</div>
              {% endif %}
              <span class="badge badge-{{ g.priority }}">{{ g.priority }}</span>
            </div>
          </div>
        </div>
        {% endfor %}
      {% else %}
        <div class="empty-state">No active goals. Use the Goal Engine CLI to add some.</div>
      {% endif %}
    </div>
  </div>
</div>
{% endblock %}
"""

APPROVALS_HTML = """
{% extends "base" %}
{% block content %}
<div class="hero-date">Approval Queue</div>
<div class="hero-sub">Human-in-the-loop safety gate</div>

<div class="grid">
  <div class="card full-width">
    <div class="card-header">
      <span class="card-title">Pending ({{ pending|length }})</span>
    </div>
    <div class="card-content">
      {% if pending %}
        {% for a in pending %}
        <div class="approval-item" style="display:flex; justify-content:space-between; align-items:center">
          <div>
            <span class="badge badge-pending">{{ a.action_type }}</span>
            {{ a.description }}
            <div style="font-size:11px; color:var(--text-dim)">Created: {{ a.created_at }}</div>
          </div>
          <div>
            <a href="/approvals/{{ a.id }}/approve" class="btn btn-approve">Approve</a>
            <a href="/approvals/{{ a.id }}/reject" class="btn btn-reject">Reject</a>
          </div>
        </div>
        {% endfor %}
      {% else %}
        <div class="empty-state">No pending approvals. All clear! ✓</div>
      {% endif %}
    </div>
  </div>

  <div class="card full-width">
    <div class="card-header">
      <span class="card-title">History</span>
    </div>
    <div class="card-content">
      {% if history %}
        {% for a in history %}
        <div class="approval-item">
          <span class="badge badge-{{ a.status }}">{{ a.status }}</span>
          {{ a.description }}
          <span style="font-size:11px; color:var(--text-dim); float:right">{{ a.decided_at or a.created_at }}</span>
        </div>
        {% endfor %}
      {% else %}
        <div class="empty-state">No approval history yet.</div>
      {% endif %}
    </div>
  </div>
</div>
{% endblock %}
"""


# ──────────────────────────────────────────────
#  TEMPLATE ENGINE (uses render_template_string with inheritance)
# ──────────────────────────────────────────────

from jinja2 import BaseLoader, TemplateNotFound, Environment

class DictLoader(BaseLoader):
    """Load templates from a dictionary for self-contained deployment."""
    def __init__(self, templates):
        self.templates = templates

    def get_source(self, environment, template):
        if template in self.templates:
            source = self.templates[template]
            return source, None, lambda: True
        raise TemplateNotFound(template)


_templates = {
    "base": BASE_HTML,
    "dashboard": DASHBOARD_HTML,
    "goals": GOALS_HTML,
    "approvals": APPROVALS_HTML,
}

_jinja_env = Environment(loader=DictLoader(_templates))


def _render(template_name, **context):
    """Render a template with the given context."""
    tmpl = _jinja_env.get_template(template_name)
    return tmpl.render(**context)


# ──────────────────────────────────────────────
#  ROUTES
# ──────────────────────────────────────────────

@app.route("/")
def index():
    now = datetime.now()
    conn = get_connection()

    # Today's events
    today = now.strftime("%Y-%m-%d")
    events_raw = conn.execute(
        """SELECT * FROM events
           WHERE start_time LIKE ? AND status != 'cancelled'
           ORDER BY start_time""",
        (f"{today}%",),
    ).fetchall()

    events = []
    for ev in events_raw:
        d = dict(ev)
        st = d.get("start_time", "")
        if "T" in st:
            d["start_display"] = st.split("T")[1][:5]
        else:
            d["start_display"] = "All day"
        events.append(d)

    # Goals
    goals = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM goals WHERE status='active' ORDER BY priority, deadline"
        ).fetchall()
    ]

    # Job leads
    leads = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM job_leads ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
    ]

    # Headlines
    headlines = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM world_headlines ORDER BY fetched_at DESC LIMIT 5"
        ).fetchall()
    ]

    # Pending approvals
    pending = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM approvals WHERE status='pending' ORDER BY created_at DESC"
        ).fetchall()
    ]

    conn.close()

    # Greeting
    hour = now.hour
    if hour < 12:
        greeting = "Good morning, Gavin."
    elif hour < 17:
        greeting = "Good afternoon, Gavin."
    else:
        greeting = "Good evening, Gavin."

    return _render(
        "dashboard",
        page="home",
        today_formatted=now.strftime("%A, %B %d, %Y"),
        greeting=greeting,
        events=events,
        goals=goals,
        leads=leads,
        headlines=headlines,
        pending_approvals=pending,
    )


@app.route("/goals")
def goals_page():
    conn = get_connection()
    goals = [
        dict(r)
        for r in conn.execute(
            """SELECT * FROM goals WHERE status='active'
               ORDER BY
                 CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2
                   WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END,
                 deadline ASC"""
        ).fetchall()
    ]
    conn.close()
    return _render("goals", page="goals", goals=goals)


@app.route("/approvals")
def approvals_page():
    conn = get_connection()
    pending = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM approvals WHERE status='pending' ORDER BY created_at DESC"
        ).fetchall()
    ]
    history = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM approvals WHERE status!='pending' ORDER BY decided_at DESC LIMIT 20"
        ).fetchall()
    ]
    conn.close()
    return _render("approvals", page="approvals", pending=pending, history=history)


@app.route("/approvals/<int:item_id>/approve")
def approve_action(item_id):
    from src.approval_queue import approve
    approve(item_id)
    return redirect(url_for("approvals_page"))


@app.route("/approvals/<int:item_id>/reject")
def reject_action(item_id):
    from src.approval_queue import reject
    reject(item_id)
    return redirect(url_for("approvals_page"))


# ──────────────────────────────────────────────
#  API ENDPOINTS (for future use)
# ──────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    conn = get_connection()

    event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    goal_count = conn.execute(
        "SELECT COUNT(*) FROM goals WHERE status='active'"
    ).fetchone()[0]
    email_count = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
    pending_count = conn.execute(
        "SELECT COUNT(*) FROM approvals WHERE status='pending'"
    ).fetchone()[0]

    conn.close()

    return jsonify({
        "status": "online",
        "counts": {
            "events": event_count,
            "goals": goal_count,
            "emails": email_count,
            "pending_approvals": pending_count,
        },
    })


def run_dashboard():
    """Start the Flask dashboard server."""
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    dash_config = config.get("dashboard", {})

    host = dash_config.get("host", "127.0.0.1")
    port = dash_config.get("port", 5000)
    debug = dash_config.get("debug", False)

    print(f"\n  [dashboard] Starting at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    init_db()
    run_dashboard()
