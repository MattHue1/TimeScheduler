from pathlib import Path

from time_scheduler.database import TimetableRepository
from time_scheduler.models import Timetable


def test_repository_round_trip_and_event_mapping(tmp_path: Path):
    repository = TimetableRepository(tmp_path / "scheduler.db")
    repository.initialize()
    timetable = Timetable.model_validate(
        {
            "tasks": [
                {
                    "id": "task-1",
                    "title": "Write report",
                    "start": "2030-02-01T13:00:00-05:00",
                    "end": "2030-02-01T14:00:00-05:00",
                }
            ]
        }
    )
    timetable_id = repository.save(timetable)
    assert repository.get(timetable_id) == timetable
    assert repository.get_latest()[0] == timetable_id
    assert repository.get_event_id("task-1", "primary") is None
    repository.save_event_id("task-1", "primary", "google-123")
    assert repository.get_event_id("task-1", "primary") == "google-123"

