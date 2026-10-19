"""Small SQLite repository for timetable snapshots and Calendar ID mappings."""

import sqlite3
from pathlib import Path
from uuid import uuid4

from .models import Timetable


class TimetableRepository:
    """Persist timetable JSON and its Google Calendar event identifiers."""

    def __init__(self, database_path: Path) -> None:
        """Store the database path; schema creation is explicit via initialize()."""
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        """Open a connection configured to return named columns."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        """Create the data directory and database tables when absent."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS timetables (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS calendar_events (
                    task_id TEXT NOT NULL,
                    calendar_id TEXT NOT NULL,
                    google_event_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (task_id, calendar_id)
                );
                """
            )

    def save(self, timetable: Timetable) -> str:
        """Save a validated timetable snapshot and return its generated ID."""
        timetable_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO timetables (id, payload) VALUES (?, ?)",
                (timetable_id, timetable.model_dump_json()),
            )
        return timetable_id

    def get(self, timetable_id: str) -> Timetable | None:
        """Load one timetable by ID, or return None when it does not exist."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM timetables WHERE id = ?", (timetable_id,)
            ).fetchone()
        return Timetable.model_validate_json(row["payload"]) if row else None

    def get_latest(self) -> tuple[str, Timetable] | None:
        """Load the newest stored timetable together with its ID."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, payload FROM timetables ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
        return (row["id"], Timetable.model_validate_json(row["payload"])) if row else None

    def get_event_id(self, task_id: str, calendar_id: str) -> str | None:
        """Find the Google event previously associated with a stable task ID."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT google_event_id FROM calendar_events WHERE task_id = ? AND calendar_id = ?",
                (task_id, calendar_id),
            ).fetchone()
        return row["google_event_id"] if row else None

    def save_event_id(self, task_id: str, calendar_id: str, event_id: str) -> None:
        """Insert or update the Google event mapping used for idempotent sync."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO calendar_events (task_id, calendar_id, google_event_id)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id, calendar_id) DO UPDATE SET
                    google_event_id = excluded.google_event_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (task_id, calendar_id, event_id),
            )

