from pathlib import Path

from fastapi.testclient import TestClient

from time_scheduler.api import create_app
from time_scheduler.config import Settings


def test_push_endpoint_requires_auth_and_returns_latest(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        timescheduler_api_key="test-secret",
        database_path=tmp_path / "api.db",
    )
    payload = {
        "source": "hermes",
        "timezone": "America/Toronto",
        "tasks": [
            {
                "id": "api-task-1",
                "title": "Review timetable",
                "start": "2030-04-01T09:00:00-04:00",
                "end": "2030-04-01T09:30:00-04:00",
            }
        ],
    }
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/v1/timetables", json=payload).status_code == 401
        headers = {"Authorization": "Bearer test-secret"}
        imported = client.post("/api/v1/timetables", headers=headers, json=payload)
        assert imported.status_code == 200
        assert imported.json()["task_count"] == 1
        latest = client.get("/api/v1/timetables/latest", headers=headers)
        assert latest.status_code == 200
        assert latest.json()["tasks"][0]["id"] == "api-task-1"

