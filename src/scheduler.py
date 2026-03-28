"""
Scheduler — Personal Ops Agent
APScheduler heartbeat that coordinates all background polling tasks.
Triggers calendar and gmail watchers, daily briefings, and productivity analysis.
"""

import yaml
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from src.database import log_activity

CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"

_scheduler = None


def _load_config():
    """Load scheduler config from settings.yaml."""
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    return config


def _safe_run(name, func):
    """Wrapper that catches and logs errors without crashing the scheduler."""
    def wrapper():
        try:
            result = func()
            print(f"  [scheduler] {name}: OK")
            return result
        except Exception as e:
            print(f"  [scheduler] {name}: ERROR — {e}")
            log_activity("scheduler", f"{name}_error", str(e))
    return wrapper


def create_scheduler():
    """Create and configure the APScheduler with all polling jobs."""
    global _scheduler
    config = _load_config()
    sched_config = config.get("scheduler", {})
    anchor_config = config.get("daily_anchor", {})

    tz = sched_config.get("timezone", "America/Halifax")
    cal_minutes = sched_config.get("calendar_poll_minutes", 5)
    gmail_minutes = sched_config.get("gmail_poll_minutes", 10)
    briefing_time = anchor_config.get("briefing_time", "07:00")
    briefing_hour, briefing_minute = briefing_time.split(":")

    _scheduler = BackgroundScheduler(timezone=tz)

    # Calendar polling
    try:
        from src.calendar_watcher import poll as cal_poll
        _scheduler.add_job(
            _safe_run("calendar_poll", cal_poll),
            IntervalTrigger(minutes=cal_minutes),
            id="calendar_poll",
            name="Calendar Watcher",
            replace_existing=True,
        )
    except ImportError:
        print("  [scheduler] Calendar watcher not available")

    # Gmail polling
    try:
        from src.gmail_watcher import poll as gmail_poll
        _scheduler.add_job(
            _safe_run("gmail_poll", gmail_poll),
            IntervalTrigger(minutes=gmail_minutes),
            id="gmail_poll",
            name="Gmail Watcher",
            replace_existing=True,
        )
    except ImportError:
        print("  [scheduler] Gmail watcher not available")

    # Job opportunity summarization (runs after gmail poll)
    try:
        from src.opportunity_summarizer import summarize_new_opportunities
        _scheduler.add_job(
            _safe_run("opportunity_summarizer", summarize_new_opportunities),
            IntervalTrigger(minutes=gmail_minutes + 1),
            id="opportunity_summarizer",
            name="Opportunity Summarizer",
            replace_existing=True,
        )
    except ImportError:
        pass

    # Morning briefing
    try:
        from src.daily_anchor import send_briefing
        _scheduler.add_job(
            _safe_run("morning_briefing", send_briefing),
            CronTrigger(hour=int(briefing_hour), minute=int(briefing_minute)),
            id="morning_briefing",
            name="Morning Briefing",
            replace_existing=True,
        )
    except ImportError:
        print("  [scheduler] Daily anchor not available")

    # World headlines refresh (twice daily)
    try:
        from src.world_briefing import fetch_headlines
        _scheduler.add_job(
            _safe_run("world_briefing", fetch_headlines),
            CronTrigger(hour="6,18", minute=0),
            id="world_briefing",
            name="World Briefing",
            replace_existing=True,
        )
    except ImportError:
        pass

    # Micro-productivity check (every 30 min during working hours)
    try:
        from src.micro_productivity import analyze_today
        _scheduler.add_job(
            _safe_run("micro_productivity", analyze_today),
            CronTrigger(hour="8-20", minute=0),
            id="micro_productivity",
            name="Micro-Productivity",
            replace_existing=True,
        )
    except ImportError:
        pass

    return _scheduler


def start():
    """Start the scheduler."""
    global _scheduler
    if _scheduler is None:
        create_scheduler()
    _scheduler.start()
    log_activity("scheduler", "start", f"{len(_scheduler.get_jobs())} jobs registered")
    print(f"\n  [scheduler] Started with {len(_scheduler.get_jobs())} jobs:")
    for job in _scheduler.get_jobs():
        print(f"    • {job.name} ({job.trigger})")
    return _scheduler


def stop():
    """Stop the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        log_activity("scheduler", "stop", "Scheduler stopped")
        print("  [scheduler] Stopped")


def get_status():
    """Get scheduler status info."""
    global _scheduler
    if _scheduler is None:
        return {"running": False, "jobs": []}
    return {
        "running": _scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run": str(job.next_run_time) if job.next_run_time else "N/A",
            }
            for job in _scheduler.get_jobs()
        ],
    }


if __name__ == "__main__":
    from src.database import init_db

    init_db()
    print("\n--- Scheduler ---\n")
    start()
    print("\nScheduler running. Press Ctrl+C to stop.")
    try:
        import time
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        stop()
