"""SQLite-Speicher: merkt sich alle gesehenen Stellen, damit nur neue gemeldet werden."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from .models import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    dedupe_key  TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    employer    TEXT,
    location    TEXT,
    published   TEXT,
    deadline    TEXT,
    score       INTEGER,
    fit         TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def upsert(self, jobs: list[Job], today: str | None = None) -> None:
        """Speichert die Stellen und setzt is_new/first_seen auf jedem Job-Objekt."""
        today = today or date.today().isoformat()
        cur = self.conn.cursor()
        for job in jobs:
            row = cur.execute("SELECT first_seen FROM jobs WHERE dedupe_key = ?", (job.dedupe_key,)).fetchone()
            if row is None:
                job.first_seen, job.is_new = today, True
                cur.execute(
                    "INSERT INTO jobs (dedupe_key, source, source_id, title, url, employer, location, published,"
                    " deadline, score, fit, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (job.dedupe_key, job.source, job.source_id, job.title, job.url, job.employer, job.location,
                     job.published, job.deadline, job.score, job.fit, today, today),
                )
            else:
                job.first_seen = row[0]
                job.is_new = job.first_seen == today   # mehrfacher Lauf am selben Tag bleibt "neu"
                cur.execute("UPDATE jobs SET last_seen = ?, score = ?, fit = ? WHERE dedupe_key = ?",
                            (today, job.score, job.fit, job.dedupe_key))
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
