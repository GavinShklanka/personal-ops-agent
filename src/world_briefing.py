"""
World Briefing — Personal Ops Agent
Fetches top headlines from configurable RSS feeds.
No API keys needed — uses free RSS/Atom feeds.
"""

import yaml
import feedparser
from pathlib import Path
from datetime import datetime

from src.database import get_connection, log_activity

CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def _load_feeds():
    """Load RSS feed config from settings.yaml."""
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    return config.get("world_briefing", {}).get("rss_feeds", [])


def fetch_headlines(max_per_feed=3):
    """
    Fetch headlines from all configured RSS feeds.
    Stores in database and returns formatted list.

    Returns:
        List of dicts: [{"source": ..., "title": ..., "url": ..., "published": ...}]
    """
    feeds = _load_feeds()
    all_headlines = []

    for feed_config in feeds:
        name = feed_config.get("name", "Unknown")
        url = feed_config.get("url", "")
        if not url:
            continue

        try:
            feed = feedparser.parse(url)
            entries = feed.entries[:max_per_feed]

            for entry in entries:
                headline = {
                    "source": name,
                    "title": entry.get("title", "").strip(),
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                }
                all_headlines.append(headline)
        except Exception as e:
            print(f"Warning: Failed to fetch {name}: {e}")

    # Store in database
    if all_headlines:
        _store_headlines(all_headlines)
        log_activity(
            "world_briefing",
            "fetch",
            f"Fetched {len(all_headlines)} headlines from {len(feeds)} feeds",
        )

    return all_headlines


def _store_headlines(headlines):
    """Store fetched headlines in the database."""
    conn = get_connection()
    # Clear old headlines (keep only latest fetch)
    conn.execute("DELETE FROM world_headlines")
    for h in headlines:
        conn.execute(
            """INSERT INTO world_headlines (source, title, url, published_at)
               VALUES (?, ?, ?, ?)""",
            (h["source"], h["title"], h["url"], h["published"]),
        )
    conn.commit()
    conn.close()


def get_stored_headlines(limit=10):
    """Get headlines from the database."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM world_headlines ORDER BY fetched_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def format_briefing(headlines=None, max_headlines=5):
    """Format headlines into a readable briefing text."""
    if headlines is None:
        headlines = fetch_headlines()

    if not headlines:
        return "No headlines available at this time."

    lines = ["📰 World Briefing", ""]
    seen_titles = set()
    count = 0

    for h in headlines:
        if count >= max_headlines:
            break
        # Deduplicate by title
        title_key = h["title"].lower().strip()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        lines.append(f"• [{h['source']}] {h['title']}")
        count += 1

    return "\n".join(lines)


if __name__ == "__main__":
    from src.database import init_db

    init_db()
    print("\n--- World Briefing ---\n")
    headlines = fetch_headlines()
    if headlines:
        print(format_briefing(headlines))
    else:
        print("No headlines fetched. Check your internet connection and RSS feed URLs.")
