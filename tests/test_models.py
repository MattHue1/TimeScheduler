from datetime import datetime

import pytest
from pydantic import ValidationError

from time_scheduler.models import Task, Timetable


def make_task(**overrides):
    values = {
        "id": "study-1",
        "title": "Study algorithms",
        "start": "2030-01-15T09:00:00-05:00",
        "end": "2030-01-15T10:00:00-05:00",
    }
    values.update(overrides)
    return Task.model_validate(values)


def test_task_requires_increasing_timezone_aware_times():
    with pytest.raises(ValidationError, match="end must be after start"):
        make_task(end="2030-01-15T08:00:00-05:00")
    with pytest.raises(ValidationError, match="must include a UTC offset"):
        make_task(start=datetime(2030, 1, 15, 9))


def test_timetable_sorts_tasks_and_rejects_duplicate_ids():
    later = make_task(
        id="later",
        start="2030-01-15T11:00:00-05:00",
        end="2030-01-15T12:00:00-05:00",
    )
    earlier = make_task(id="earlier")
    timetable = Timetable(tasks=[later, earlier])
    assert [task.id for task in timetable.tasks] == ["earlier", "later"]
    with pytest.raises(ValidationError, match="task ids must be unique"):
        Timetable(tasks=[earlier, earlier])

