"""
Database — Personal Ops Agent
SQLite database setup, schema management, and query helpers.
All modules read from and write to a single local DB file.
"""

import sqlite3
import os
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "db" / "ops_agent.db"
SCHEMA_VERSION = 1


def get_connection():
    """Get a database connection with row_factory set to sqlite3.Row."""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database schema. Safe to call multiple times."""
    conn = get_connection()
    c = conn.cursor()

    # Check if already at current schema version
    c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    if c.fetchone():
        c.execute("SELECT MAX(version) FROM schema_version")
        row = c.fetchone()
        if row and row[0] and row[0] >= SCHEMA_VERSION:
            tables = [
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            ]
            print(f"Database ready at: {DB_PATH}")
            print(f"Schema version: {row[0]}")
            print(f"Tables ({len(tables)}): {', '.join(tables)}")
            conn.close()
            return True

    c.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            summary TEXT,
            description TEXT,
            location TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            all_day INTEGER DEFAULT 0,
            status TEXT DEFAULT 'confirmed',
            calendar_id TEXT DEFAULT 'primary',
            raw_json TEXT,
            last_synced TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            deadline TEXT,
            estimated_minutes INTEGER,
            priority TEXT DEFAULT 'medium'
                CHECK(priority IN ('low','medium','high','urgent')),
            status TEXT DEFAULT 'active'
                CHECK(status IN ('active','completed','archived')),
            progress_pct INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER REFERENCES goals(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            estimated_minutes INTEGER DEFAULT 30,
            status TEXT DEFAULT 'todo'
                CHECK(status IN ('todo','in_progress','done')),
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS emails (
            id TEXT PRIMARY KEY,
            thread_id TEXT,
            sender TEXT,
            sender_email TEXT,
            subject TEXT,
            snippet TEXT,
            labels TEXT,
            received_at TEXT,
            is_job_related INTEGER DEFAULT 0,
            job_score REAL DEFAULT 0.0,
            last_synced TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS job_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT REFERENCES emails(id),
            company TEXT,
            role TEXT,
            summary TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'new'
                CHECK(status IN ('new','reviewed','applied','rejected','expired')),
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            title TEXT,
            body TEXT,
            priority TEXT DEFAULT 'default',
            sent_at TEXT,
            status TEXT DEFAULT 'pending'
                CHECK(status IN ('pending','sent','failed','suppressed')),
            error TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT NOT NULL,
            description TEXT,
            payload TEXT,
            status TEXT DEFAULT 'pending'
                CHECK(status IN ('pending','approved','rejected','expired')),
            decided_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS briefings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT DEFAULT 'morning',
            content TEXT,
            headlines TEXT,
            sent INTEGER DEFAULT 0,
            generated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS world_headlines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            title TEXT NOT NULL,
            url TEXT,
            published_at TEXT,
            fetched_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    c.execute(
        "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
        (SCHEMA_VERSION,),
    )
    conn.commit()

    tables = [
        r[0]
        for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]

    print(f"Database ready at: {DB_PATH}")
    print(f"Schema version: {SCHEMA_VERSION}")
    print(f"Tables ({len(tables)}): {', '.join(tables)}")
    conn.close()
    return True


def log_activity(module, action, details=None):
    """Log an agent activity for audit/debugging."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO activity_log (module, action, details) VALUES (?, ?, ?)",
        (module, action, details),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
