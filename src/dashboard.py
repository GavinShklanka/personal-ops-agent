"""
Dashboard — Personal Ops Agent
Local Flask web UI. Shows today's schedule, active goals, and the approval
queue so Gavin can approve or reject Klara's proposed actions.

Run standalone:  python -m src.dashboard
Or import and call run() from the scheduler.
"""

from flask import Flask, redirect, render_template_string, request, url_for

from src.approval_queue import approve_action, get_all_approvals, get_pending_approvals, reject_action
from src.goal_engine import abandon_goal, complete_goal, get_all_goals, add_goal

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Shared base template
# ---------------------------------------------------------------------------
_BASE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Klara — Personal Ops</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <style>
    body { background: #0d1117; color: #c9d1d9; }
    .navbar { background: #161b22 !important; border-bottom: 1px solid #30363d; }
    .navbar-brand { color: #58a6ff !important; font-weight: 600; }
    .nav-link { color: #8b949e !important; }
    .nav-link:hover, .nav-link.active { color: #c9d1d9 !important; }
    .card { background: #161b22; border: 1px solid #30363d; }
    .card-header { background: #21262d; border-bottom: 1px solid #30363d; font-weight: 600; }
    .badge-pending   { background: #d29922; }
    .badge-approved  { background: #238636; }
    .badge-rejected  { background: #b62324; }
    .badge-active    { background: #1f6feb; }
    .badge-completed { background: #238636; }
    .progress { background: #21262d; }
    table { color: #c9d1d9; }
    th { color: #8b949e; font-size: .85rem; text-transform: uppercase; }
    .payload-cell { font-family: monospace; font-size: .82rem; color: #8b949e; }
    .btn-approve { background: #238636; border: none; }
    .btn-reject  { background: #b62324; border: none; }
    hr { border-color: #30363d; }
  </style>
</head>
<body>
<nav class="navbar navbar-expand-lg">
  <div class="container-fluid">
    <a class="navbar-brand" href="/">&#10024; Klara</a>
    <div class="collapse navbar-collapse">
      <ul class="navbar-nav me-auto">
        <li class="nav-item"><a class="nav-link {% if page=='home' %}active{% endif %}" href="/">Dashboard</a></li>
        <li class="nav-item"><a class="nav-link {% if page=='approvals' %}active{% endif %}" href="/approvals">Approvals</a></li>
        <li class="nav-item"><a class="nav-link {% if page=='goals' %}active{% endif %}" href="/goals">Goals</a></li>
      </ul>
    </div>
  </div>
</nav>
<div class="container-fluid py-4">
  {% block content %}{% endblock %}
</div>
</body>
</html>
"""

_HOME = (
    _BASE.replace("{% block content %}{% endblock %}", """
{% block content %}
<div class="row g-4">

  <!-- Pending Approvals Summary -->
  <div class="col-12">
    {% if pending %}
    <div class="alert" style="background:#3d2b00;border:1px solid #d29922;color:#ffa657;">
      &#9888; {{ pending|length }} action{{ 's' if pending|length != 1 }} waiting for your approval &mdash;
      <a href="/approvals" style="color:#ffa657;font-weight:600;">Review now</a>
    </div>
    {% else %}
    <div class="alert" style="background:#0d2c0f;border:1px solid #238636;color:#56d364;">
      &#10003; No pending approvals
    </div>
    {% endif %}
  </div>

  <!-- Active Goals -->
  <div class="col-md-6">
    <div class="card h-100">
      <div class="card-header">Active Goals</div>
      <div class="card-body">
        {% if goals %}
          {% for g in goals %}
          <div class="mb-3">
            <div class="d-flex justify-content-between align-items-start mb-1">
              <span>{{ g.title }}
                <span class="badge badge-active ms-1">{{ g.period }}</span>
              </span>
              <span class="text-muted small">{{ g.progress }}%</span>
            </div>
            <div class="progress" style="height:6px;">
              <div class="progress-bar" style="width:{{ g.progress }}%;background:#1f6feb;"></div>
            </div>
            {% if g.description %}<div class="text-muted small mt-1">{{ g.description }}</div>{% endif %}
          </div>
          {% endfor %}
        {% else %}
          <p class="text-muted">No active goals. <a href="/goals">Add one</a>.</p>
        {% endif %}
      </div>
    </div>
  </div>

  <!-- Recent Approvals -->
  <div class="col-md-6">
    <div class="card h-100">
      <div class="card-header">Recent Approvals</div>
      <div class="card-body p-0">
        <table class="table table-sm mb-0" style="background:transparent;">
          <thead><tr><th>Action</th><th>Status</th><th>When</th></tr></thead>
          <tbody>
          {% for a in recent %}
          <tr>
            <td>{{ a.action_type }}</td>
            <td><span class="badge badge-{{ a.status }}">{{ a.status }}</span></td>
            <td class="text-muted small">{{ a.created_at[:16].replace('T',' ') }}</td>
          </tr>
          {% else %}
          <tr><td colspan="3" class="text-muted p-3">No actions yet.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

</div>
{% endblock %}""")
)

_APPROVALS = (
    _BASE.replace("{% block content %}{% endblock %}", """
{% block content %}
<h5 class="mb-4">Approval Queue</h5>

{% if pending %}
<div class="card mb-4">
  <div class="card-header">&#9888; Pending ({{ pending|length }})</div>
  <div class="card-body p-0">
    <table class="table table-sm mb-0" style="background:transparent;">
      <thead><tr><th>#</th><th>Action</th><th>Details</th><th>Requested</th><th></th></tr></thead>
      <tbody>
      {% for a in pending %}
      <tr>
        <td class="text-muted">{{ a.id }}</td>
        <td><strong>{{ a.action_type }}</strong></td>
        <td class="payload-cell">
          {% for k, v in a.payload.items() %}
            <div><span style="color:#58a6ff">{{ k }}</span>: {{ v }}</div>
          {% endfor %}
        </td>
        <td class="text-muted small">{{ a.created_at[:16].replace('T',' ') }}</td>
        <td class="text-nowrap">
          <form method="post" action="/approvals/{{ a.id }}/approve" class="d-inline">
            <button class="btn btn-approve btn-sm text-white me-1">&#10003; Approve</button>
          </form>
          <form method="post" action="/approvals/{{ a.id }}/reject" class="d-inline">
            <button class="btn btn-reject btn-sm text-white">&#10007; Reject</button>
          </form>
        </td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% else %}
<p class="text-muted">No pending approvals.</p>
{% endif %}

{% if decided %}
<div class="card">
  <div class="card-header text-muted">History</div>
  <div class="card-body p-0">
    <table class="table table-sm mb-0" style="background:transparent;">
      <thead><tr><th>#</th><th>Action</th><th>Status</th><th>Decided</th></tr></thead>
      <tbody>
      {% for a in decided %}
      <tr>
        <td class="text-muted">{{ a.id }}</td>
        <td>{{ a.action_type }}</td>
        <td><span class="badge badge-{{ a.status }}">{{ a.status }}</span></td>
        <td class="text-muted small">{{ (a.decided_at or '')[:16].replace('T',' ') }}</td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endif %}
{% endblock %}""")
)

_GOALS = (
    _BASE.replace("{% block content %}{% endblock %}", """
{% block content %}
<div class="row g-4">
  <div class="col-md-8">
    <h5 class="mb-3">All Goals</h5>
    <div class="card">
      <div class="card-body p-0">
        <table class="table table-sm mb-0" style="background:transparent;">
          <thead><tr><th>#</th><th>Goal</th><th>Period</th><th>Progress</th><th>Status</th><th></th></tr></thead>
          <tbody>
          {% for g in goals %}
          <tr>
            <td class="text-muted">{{ g.id }}</td>
            <td>
              {{ g.title }}
              {% if g.description %}<div class="text-muted small">{{ g.description }}</div>{% endif %}
            </td>
            <td><span class="badge badge-active">{{ g.period }}</span></td>
            <td style="min-width:100px;">
              <div class="progress" style="height:6px;">
                <div class="progress-bar" style="width:{{ g.progress }}%;background:#1f6feb;"></div>
              </div>
              <div class="text-muted small">{{ g.progress }}%</div>
            </td>
            <td><span class="badge badge-{{ g.status }}">{{ g.status }}</span></td>
            <td class="text-nowrap">
              {% if g.status == 'active' %}
              <form method="post" action="/goals/{{ g.id }}/complete" class="d-inline">
                <button class="btn btn-approve btn-sm text-white me-1">Done</button>
              </form>
              <form method="post" action="/goals/{{ g.id }}/abandon" class="d-inline">
                <button class="btn btn-reject btn-sm text-white">Drop</button>
              </form>
              {% endif %}
            </td>
          </tr>
          {% else %}
          <tr><td colspan="6" class="text-muted p-3">No goals yet.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="col-md-4">
    <h5 class="mb-3">Add Goal</h5>
    <div class="card">
      <div class="card-body">
        <form method="post" action="/goals/add">
          <div class="mb-3">
            <label class="form-label small">Title</label>
            <input name="title" class="form-control form-control-sm" style="background:#0d1117;color:#c9d1d9;border-color:#30363d;" required>
          </div>
          <div class="mb-3">
            <label class="form-label small">Description (optional)</label>
            <textarea name="description" rows="2" class="form-control form-control-sm" style="background:#0d1117;color:#c9d1d9;border-color:#30363d;"></textarea>
          </div>
          <div class="mb-3">
            <label class="form-label small">Period</label>
            <select name="period" class="form-select form-select-sm" style="background:#0d1117;color:#c9d1d9;border-color:#30363d;">
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div class="mb-3">
            <label class="form-label small">Due Date (optional)</label>
            <input name="due_date" type="date" class="form-control form-control-sm" style="background:#0d1117;color:#c9d1d9;border-color:#30363d;">
          </div>
          <button type="submit" class="btn btn-primary btn-sm w-100">Add Goal</button>
        </form>
      </div>
    </div>
  </div>
</div>
{% endblock %}""")
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    from src.approval_queue import get_pending_approvals, get_all_approvals
    from src.goal_engine import get_active_goals
    return render_template_string(
        _HOME,
        page="home",
        pending=get_pending_approvals(),
        goals=get_active_goals(),
        recent=get_all_approvals(limit=10),
    )


@app.route("/approvals")
def approvals():
    all_approvals = get_all_approvals(limit=100)
    pending = [a for a in all_approvals if a["status"] == "pending"]
    decided = [a for a in all_approvals if a["status"] != "pending"]
    return render_template_string(_APPROVALS, page="approvals", pending=pending, decided=decided)


@app.route("/approvals/<int:approval_id>/approve", methods=["POST"])
def approve(approval_id):
    approve_action(approval_id)
    return redirect(url_for("approvals"))


@app.route("/approvals/<int:approval_id>/reject", methods=["POST"])
def reject(approval_id):
    reject_action(approval_id)
    return redirect(url_for("approvals"))


@app.route("/goals")
def goals():
    return render_template_string(_GOALS, page="goals", goals=get_all_goals())


@app.route("/goals/add", methods=["POST"])
def goals_add():
    title = request.form.get("title", "").strip()
    if title:
        add_goal(
            title=title,
            description=request.form.get("description", "").strip(),
            period=request.form.get("period", "weekly"),
            due_date=request.form.get("due_date", "").strip(),
        )
    return redirect(url_for("goals"))


@app.route("/goals/<int:goal_id>/complete", methods=["POST"])
def goals_complete(goal_id):
    complete_goal(goal_id)
    return redirect(url_for("goals"))


@app.route("/goals/<int:goal_id>/abandon", methods=["POST"])
def goals_abandon(goal_id):
    abandon_goal(goal_id)
    return redirect(url_for("goals"))


def run(host: str = "127.0.0.1", port: int = 5000, debug: bool = False):
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run(debug=True)
