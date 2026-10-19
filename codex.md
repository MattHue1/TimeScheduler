# Code map

This document explains the purpose of every tracked project file and every project-defined function. Keep it updated whenever code is added or behavior changes.

## Root files

- `.env.example` — copyable configuration template for the inbound API secret, Hermes endpoint, Google OAuth files, Calendar destination, database, timezone, and reminders.
- `.gitignore` — prevents local secrets, OAuth tokens, databases, virtual environments, caches, and coverage output from being committed.
- `pyproject.toml` — package metadata, runtime/development dependencies (including portable IANA timezone data for Windows), build configuration, pytest configuration, and the two command-line entry points.
- `README.md` — setup, Hermes connection, Google Calendar authorization, API usage, security notes, and test instructions.
- `codex.md` — this maintenance map of files and functions.

## Application package (`src/time_scheduler`)

### `__init__.py`

Marks the directory as the `time_scheduler` package and exposes its version.

### `config.py`

Centralizes configuration. Values come from environment variables or a local `.env` file.

- `Settings` — typed configuration model containing all Hermes, Google, storage, and reminder settings.
- `Settings.parse_reminders(value)` — converts `DEFAULT_REMINDERS_MINUTES=30,10` into `[30, 10]`.
- `get_settings()` — creates and caches one configuration object for normal application use.

### `models.py`

Defines and validates the JSON contracts at the system boundary.

- `Task` — one scheduled activity with a stable ID, title, timezone-aware start/end, optional details, and optional reminders.
- `Task.validate_times_and_reminders()` — rejects missing UTC offsets, non-increasing time ranges, duplicate reminders, and reminders outside Google's accepted range.
- `Timetable` — a complete Hermes schedule with its source, IANA timezone, generation time, and tasks.
- `Timetable.validate_timetable()` — checks the timezone, rejects duplicate task IDs, and sorts tasks chronologically.
- `HermesImportRequest` — request text sent to Hermes plus the choice to sync immediately.
- `ImportResult` — response after storing and optionally syncing an import.
- `SyncResult` — event create/update counts from an explicit Calendar sync.

### `database.py`

Provides local SQLite persistence without exposing SQL to route handlers.

- `TimetableRepository.__init__(database_path)` — records where the SQLite file lives.
- `TimetableRepository._connect()` — opens a SQLite connection whose rows support column names.
- `TimetableRepository.initialize()` — creates the parent directory and the timetable/event-mapping tables.
- `TimetableRepository.save(timetable)` — writes an immutable JSON timetable snapshot and returns a UUID.
- `TimetableRepository.get(timetable_id)` — retrieves and revalidates a snapshot by ID.
- `TimetableRepository.get_latest()` — retrieves the newest snapshot and ID.
- `TimetableRepository.get_event_id(task_id, calendar_id)` — finds an existing Google event mapping.
- `TimetableRepository.save_event_id(task_id, calendar_id, event_id)` — upserts the mapping used to prevent duplicate events.

### `hermes.py`

Retrieves timetable data from Hermes Agent's OpenAI-compatible endpoint. `SYSTEM_PROMPT` defines the strict interchange contract sent to Hermes.

- `extract_json(content)` — parses a JSON response and tolerates accidental Markdown fences or brief surrounding text.
- `retrieve_timetable(instruction, settings)` — calls Hermes, extracts its assistant response, and validates it as a `Timetable`.

### `google_calendar.py`

Transforms validated tasks into Google Calendar resources and synchronizes them. `SCOPES` requests only event-level Calendar access.

- `load_credentials(settings)` — loads the OAuth token, refreshes it if expired, and persists a refreshed token.
- `task_to_event(task, timetable, defaults)` — builds the Google event body, including times, popup reminders, and private stable-ID metadata.
- `sync_timetable(timetable, repository, settings)` — inserts new events, updates mapped events, recovers from externally deleted events, saves mappings, and returns counts.

### `google_auth.py`

Implements one-time Google OAuth authorization for the local user.

- `main()` — reads the downloaded Desktop OAuth client, opens the browser consent flow, and stores a refreshable `token.json`.

### `api.py`

Defines the HTTP application and its protected routes.

- `create_app(settings=None)` — constructs FastAPI, storage, authentication, handlers, and routes; optional settings make isolated tests possible.
- `lifespan(app)` — nested startup context that initializes the database before requests are served.
- `require_api_key(authorization)` — nested dependency that constant-time compares the bearer token with configuration.
- `store_and_optionally_sync(timetable, should_sync)` — nested shared workflow that saves an import and optionally synchronizes it.
- `health()` — nested public readiness handler.
- `receive_timetable(timetable, sync_calendar)` — nested handler for timetable JSON pushed by Hermes.
- `import_from_hermes(request)` — nested handler that actively asks Hermes for a timetable.
- `latest_timetable()` — nested handler returning the newest stored snapshot.
- `get_timetable(timetable_id)` — nested handler returning a selected snapshot.
- `sync_saved_timetable(timetable_id)` — nested handler that sends a stored snapshot to Calendar.
- `app` — the default application instance loaded by ASGI servers.

### `main.py`

Provides the local server command.

- `run()` — launches Uvicorn on `127.0.0.1:8080`.

## Tests (`tests`)

- `test_api.py` — its `test_push_endpoint_requires_auth_and_returns_latest()` function exercises the Hermes-facing push route, bearer authentication, persistence, and latest-timetable route end to end.
- `test_models.py` — validates time rules, unique IDs, and chronological sorting. `make_task(**overrides)` creates compact task fixtures; the two `test_*` functions cover invalid and valid model behavior.
- `test_hermes.py` — verifies JSON extraction from plain/fenced responses and rejection of non-object responses. Its two `test_*` functions each cover one behavior.
- `test_database.py` — its `test_repository_round_trip_and_event_mapping()` function verifies schema creation, snapshot round trips, latest lookup, and Calendar mapping persistence.
- `test_google_calendar.py` — its `test_task_to_event_adds_reminders_and_stable_metadata()` function checks Google event conversion without making a network request.

## Data flow

```text
Hermes Agent API ----pull----> /api/v1/hermes/import --+
                                                       |
Hermes tool/script ---push----> /api/v1/timetables ----+--> validation --> SQLite
                                                                            |
                                                                            v
                                                        Google Calendar events + reminders
```
