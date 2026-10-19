"""FastAPI routes for Hermes imports, timetable storage, and Calendar sync."""

import hmac
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import ValidationError

from .config import Settings, get_settings
from .database import TimetableRepository
from .google_calendar import sync_timetable
from .hermes import retrieve_timetable
from .models import HermesImportRequest, ImportResult, SyncResult, Timetable


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an application, allowing isolated settings to be supplied by tests."""
    app_settings = settings or get_settings()
    repository = TimetableRepository(app_settings.database_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        """Initialize durable storage before serving requests."""
        repository.initialize()
        yield

    app = FastAPI(
        title="Hermes Time Scheduler",
        version="0.1.0",
        description="Retrieve or receive Hermes timetables and sync them to Google Calendar.",
        lifespan=lifespan,
    )

    def require_api_key(authorization: Annotated[str | None, Header()] = None) -> None:
        """Reject requests without the configured bearer token."""
        expected = f"Bearer {app_settings.timescheduler_api_key}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid bearer token",
            )

    def store_and_optionally_sync(timetable: Timetable, should_sync: bool) -> ImportResult:
        """Persist a timetable and optionally send all its tasks to Google."""
        timetable_id = repository.save(timetable)
        created = updated = 0
        if should_sync:
            try:
                created, updated = sync_timetable(timetable, repository, app_settings)
            except Exception as error:
                raise HTTPException(status_code=502, detail=f"Google Calendar sync failed: {error}") from error
        return ImportResult(
            timetable_id=timetable_id,
            task_count=len(timetable.tasks),
            calendar_synced=should_sync,
            created_events=created,
            updated_events=updated,
        )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Report that the HTTP process is ready."""
        return {"status": "ok"}

    @app.post(
        "/api/v1/timetables",
        response_model=ImportResult,
        dependencies=[Depends(require_api_key)],
        tags=["timetables"],
    )
    def receive_timetable(
        timetable: Timetable,
        sync_calendar: Annotated[bool, Query()] = False,
    ) -> ImportResult:
        """Receive a timetable pushed by Hermes or another authorized client."""
        return store_and_optionally_sync(timetable, sync_calendar)

    @app.post(
        "/api/v1/hermes/import",
        response_model=ImportResult,
        dependencies=[Depends(require_api_key)],
        tags=["hermes"],
    )
    async def import_from_hermes(request: HermesImportRequest) -> ImportResult:
        """Retrieve a structured timetable from Hermes and store or sync it."""
        try:
            timetable = await retrieve_timetable(request.request, app_settings)
        except (httpx.HTTPError, ValueError, ValidationError) as error:
            raise HTTPException(status_code=502, detail=f"Hermes import failed: {error}") from error
        return store_and_optionally_sync(timetable, request.sync_calendar)

    @app.get(
        "/api/v1/timetables/latest",
        dependencies=[Depends(require_api_key)],
        tags=["timetables"],
    )
    def latest_timetable() -> dict:
        """Return the most recently stored timetable snapshot."""
        result = repository.get_latest()
        if result is None:
            raise HTTPException(status_code=404, detail="No timetable has been imported")
        timetable_id, timetable = result
        return {"id": timetable_id, **timetable.model_dump(mode="json")}

    @app.get(
        "/api/v1/timetables/{timetable_id}",
        response_model=Timetable,
        dependencies=[Depends(require_api_key)],
        tags=["timetables"],
    )
    def get_timetable(timetable_id: str) -> Timetable:
        """Return one stored timetable by ID."""
        timetable = repository.get(timetable_id)
        if timetable is None:
            raise HTTPException(status_code=404, detail="Timetable not found")
        return timetable

    @app.post(
        "/api/v1/timetables/{timetable_id}/sync",
        response_model=SyncResult,
        dependencies=[Depends(require_api_key)],
        tags=["calendar"],
    )
    def sync_saved_timetable(timetable_id: str) -> SyncResult:
        """Synchronize a stored timetable to the configured Google Calendar."""
        timetable = repository.get(timetable_id)
        if timetable is None:
            raise HTTPException(status_code=404, detail="Timetable not found")
        try:
            created, updated = sync_timetable(timetable, repository, app_settings)
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"Google Calendar sync failed: {error}") from error
        return SyncResult(
            timetable_id=timetable_id,
            created_events=created,
            updated_events=updated,
        )

    return app


app = create_app()

