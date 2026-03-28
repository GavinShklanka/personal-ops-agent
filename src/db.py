"""
DB — Personal Ops Agent
SQLite connection and schema for goals, approvals, and conversation log.
All state lives in a single local database file.
"""

import sqlite3
import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "klara.db"


def get_conn() -> sqlite3.Connection:
    """Return a WAL-mode SQLite connection with row_factory set."""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables if they don't exist. Safe to call repeatedly."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            description TEXT    NOT NULL DEFAULT '',
            period      TEXT    NOT NULL DEFAULT 'weekly',
            status      TEXT    NOT NULL DEFAULT 'active',
            progress    INTEGER NOT NULL DEFAULT 0,
            due_date    TEXT,
            created_at  TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS approvals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT    NOT NULL,
            payload     TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'pending',
            created_at  TEXT    NOT NULL,
            decided_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS conversation_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            created_at  TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_goals_status       ON goals (status);
        CREATE INDEX IF NOT EXISTS idx_approvals_status   ON approvals (status);
        CREATE INDEX IF NOT EXISTS idx_convo_session      ON conversation_log (session_id);
        """)


def now_iso() -> str:
    return datetime.datetime.now().isoformat()
