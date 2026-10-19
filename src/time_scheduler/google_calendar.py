"""Google Calendar conversion and synchronization."""

from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import Settings
from .database import TimetableRepository
from .models import Task, Timetable

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def load_credentials(settings: Settings) -> Credentials:
    """Load and refresh the saved Google OAuth token when necessary."""
    if not settings.google_token_file.exists():
        raise RuntimeError("Google token is missing; run timescheduler-google-auth first")
    credentials = Credentials.from_authorized_user_file(
        str(settings.google_token_file), SCOPES
    )
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        settings.google_token_file.write_text(credentials.to_json(), encoding="utf-8")
    if not credentials.valid:
        raise RuntimeError("Google credentials are invalid; run timescheduler-google-auth again")
    return credentials


def task_to_event(task: Task, timetable: Timetable, defaults: list[int]) -> dict[str, Any]:
    """Convert a task into a Google Calendar event resource."""
    reminders = task.reminders_minutes
    if reminders is None:
        reminders = defaults
    event = {
        "summary": task.title,
        "description": task.description,
        "start": {"dateTime": task.start.isoformat(), "timeZone": timetable.timezone},
        "end": {"dateTime": task.end.isoformat(), "timeZone": timetable.timezone},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": minute} for minute in reminders],
        },
        "extendedProperties": {
            "private": {"timeSchedulerTaskId": task.id, "source": timetable.source}
        },
    }
    if task.location is not None:
        event["location"] = task.location
    return event


def sync_timetable(
    timetable: Timetable, repository: TimetableRepository, settings: Settings
) -> tuple[int, int]:
    """Create or update each timetable task in Google Calendar."""
    service = build("calendar", "v3", credentials=load_credentials(settings), cache_discovery=False)
    created = updated = 0
    for task in timetable.tasks:
        event = task_to_event(task, timetable, settings.default_reminders_minutes)
        event_id = repository.get_event_id(task.id, settings.google_calendar_id)
        if event_id:
            try:
                result = (
                    service.events()
                    .update(
                        calendarId=settings.google_calendar_id,
                        eventId=event_id,
                        body=event,
                    )
                    .execute()
                )
                updated += 1
            except HttpError as error:
                if error.resp.status != 404:
                    raise
                result = (
                    service.events()
                    .insert(calendarId=settings.google_calendar_id, body=event)
                    .execute()
                )
                created += 1
        else:
            result = (
                service.events()
                .insert(calendarId=settings.google_calendar_id, body=event)
                .execute()
            )
            created += 1
        repository.save_event_id(task.id, settings.google_calendar_id, result["id"])
    return created, updated
