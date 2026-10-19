from time_scheduler.google_calendar import task_to_event
from time_scheduler.models import Task, Timetable


def test_task_to_event_adds_reminders_and_stable_metadata():
    task = Task.model_validate(
        {
            "id": "class-1",
            "title": "COMP class",
            "start": "2030-03-01T10:00:00-05:00",
            "end": "2030-03-01T11:30:00-05:00",
        }
    )
    timetable = Timetable(tasks=[task])
    event = task_to_event(task, timetable, [20, 5])
    assert event["summary"] == "COMP class"
    assert event["reminders"]["overrides"] == [
        {"method": "popup", "minutes": 20},
        {"method": "popup", "minutes": 5},
    ]
    assert event["extendedProperties"]["private"]["timeSchedulerTaskId"] == "class-1"

