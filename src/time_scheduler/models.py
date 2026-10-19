"""Validated request, timetable, and response models."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, model_validator


class Task(BaseModel):
    """A single scheduled task using timezone-aware RFC 3339 timestamps."""

    id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$")
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=8000)
    start: datetime
    end: datetime
    location: str | None = Field(default=None, max_length=1000)
    reminders_minutes: list[int] | None = Field(default=None, max_length=5)

    @model_validator(mode="after")
    def validate_times_and_reminders(self) -> "Task":
        """Require explicit UTC offsets, increasing times, and valid reminders."""
        if self.start.tzinfo is None or self.start.utcoffset() is None:
            raise ValueError("start must include a UTC offset, for example -04:00")
        if self.end.tzinfo is None or self.end.utcoffset() is None:
            raise ValueError("end must include a UTC offset, for example -04:00")
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if self.reminders_minutes is not None:
            if any(minutes < 0 or minutes > 40320 for minutes in self.reminders_minutes):
                raise ValueError("reminders must be between 0 and 40320 minutes")
            if len(set(self.reminders_minutes)) != len(self.reminders_minutes):
                raise ValueError("reminder values must be unique")
        return self


class Timetable(BaseModel):
    """A complete timetable produced by Hermes or another authorized client."""

    source: str = Field(default="hermes", min_length=1, max_length=100)
    timezone: str = "America/Toronto"
    generated_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    tasks: list[Task] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_timetable(self) -> "Timetable":
        """Validate the IANA timezone and ensure task identifiers are unique."""
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"unknown IANA timezone: {self.timezone}") from error
        ids = [task.id for task in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("task ids must be unique within a timetable")
        self.tasks.sort(key=lambda task: task.start)
        return self


class HermesImportRequest(BaseModel):
    """Instructions for asking Hermes to return its current timetable."""

    request: str = Field(
        default="Return the timetable you created for me.", min_length=1, max_length=4000
    )
    sync_calendar: bool = False


class ImportResult(BaseModel):
    """Result returned after storing a timetable and optionally syncing it."""

    timetable_id: str
    task_count: int
    calendar_synced: bool
    created_events: int = 0
    updated_events: int = 0


class SyncResult(BaseModel):
    """Counts from a Google Calendar synchronization run."""

    timetable_id: str
    created_events: int
    updated_events: int

