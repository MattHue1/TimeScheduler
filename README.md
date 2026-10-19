# Hermes Time Scheduler

Hermes Time Scheduler retrieves a structured timetable from a local [Hermes Agent](https://hermes-agent.nousresearch.com/docs/), stores each imported version in SQLite, and creates or updates tasks in Google Calendar. Google Calendar popup reminders provide task notifications.

The service supports two integration directions:

1. **Pull (recommended):** call Time Scheduler's `/api/v1/hermes/import` endpoint. Time Scheduler asks the Hermes OpenAI-compatible API for the timetable, validates it, stores it, and optionally syncs it to Google Calendar.
2. **Push:** tell Hermes to POST its timetable JSON to `/api/v1/timetables`. This is useful when a Hermes conversation or automation already knows that the schedule is ready.

## How the local services connect

The two applications and their API keys have different jobs:

```text
You or another local client
  │ Authorization: Bearer <TIMESCHEDULER_API_KEY>
  ▼
Time Scheduler http://127.0.0.1:8081
  │ Authorization: Bearer <HERMES_API_KEY>
  ▼
Hermes Agent http://127.0.0.1:8642
  │
  ▼
Google Calendar
```

- `TIMESCHEDULER_API_KEY` protects requests entering Time Scheduler on port `8081`.
- `HERMES_API_KEY` lets Time Scheduler call Hermes on port `8642`. It must exactly match Hermes's `API_SERVER_KEY`.
- Both local services must be running for the pull workflow.
- Keep both services bound to `127.0.0.1`; do not expose these development APIs directly to the internet.

## Requirements

- Python 3.11 or newer
- Hermes Agent installed and configured
- A Google account with Google Calendar
- A Google Cloud project for Calendar OAuth

## 1. Install Time Scheduler

PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Generate a random Time Scheduler secret:

```powershell
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToHexString($bytes).ToLower()
```

Copy the generated value into this project's `.env`:

```dotenv
TIMESCHEDULER_API_KEY=replace-with-the-generated-secret
```

Do not commit `.env`, `credentials.json`, or `token.json`.

### Start Time Scheduler

With the virtual environment activated, run:

```powershell
timescheduler
```

By default, it listens only on `http://127.0.0.1:8081`. Keep that terminal open. From a second PowerShell window, check it with:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8081/health"
```

The expected response is `status: ok`. Interactive API documentation is available at `http://127.0.0.1:8081/docs`.

The address is configurable in `.env`:

```dotenv
TIMESCHEDULER_HOST=127.0.0.1
TIMESCHEDULER_PORT=8081
```

Port `8081` is the default because Windows software such as PEM HTTPD, Apache, XAMPP, or another development server may already occupy port `8080`. If you change the port, update every Time Scheduler URL below to match.

## 2. Connect Hermes

These instructions target the Nous Research Hermes Agent. If your "Hermes" is a different product, use the push contract below.

### Enable the Hermes API server

1. Install and configure Hermes, then confirm `hermes chat` works.
2. Locate the Hermes `.env` file. A Windows installation may store it at:

   ```text
   C:\Users\YOUR_USERNAME\AppData\Local\hermes\.env
   ```

   Other installations may use `~/.hermes/.env`.
3. Add or update:

   ```dotenv
   API_SERVER_ENABLED=true
   API_SERVER_HOST=127.0.0.1
   API_SERVER_PORT=8642
   API_SERVER_KEY=replace-with-another-long-random-secret
   ```

4. Start Hermes in its own terminal and keep it running:

   ```powershell
   hermes gateway run
   ```

5. In the Time Scheduler `.env`, use the exact same secret and leave the local URL unchanged:

   ```dotenv
   HERMES_API_URL=http://127.0.0.1:8642/v1
   HERMES_API_KEY=the-exact-API_SERVER_KEY-from-Hermes
   HERMES_MODEL=hermes-agent
   ```

The Hermes API can access agent tools, so keep it on localhost. See the official [Hermes API-server integration guide](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/open-webui) for upstream details.

### Verify the Hermes API key

This PowerShell example reads the secret from the common Windows Hermes configuration path without printing it:

```powershell
$envFile = "$env:LOCALAPPDATA\hermes\.env"
$keyLine = Get-Content $envFile |
    Where-Object { $_ -match '^API_SERVER_KEY=' } |
    Select-Object -Last 1
$key = $keyLine.Split('=', 2)[1].Trim()
$headers = @{ Authorization = "Bearer $key" }

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8642/v1/models" `
    -Headers $headers
```

An `API server rejected invalid API key` message means the server is running, but the bearer value does not exactly match `API_SERVER_KEY`. Restart `hermes gateway run` after changing the Hermes `.env`.

Hermes may also warn that no messaging-platform allowlists are configured. That warning concerns Telegram, Discord, and similar integrations; it does not prevent local API access.

### Pull from Hermes (recommended)

With Hermes and Time Scheduler both running, open another PowerShell window:

```powershell
$headers = @{
    Authorization = "Bearer YOUR_ACTUAL_TIMESCHEDULER_API_KEY"
}

$body = @{
    request = "Return the timetable you made for my current week"
    sync_calendar = $true
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8081/api/v1/hermes/import" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
```

Replace `YOUR_ACTUAL_TIMESCHEDULER_API_KEY` with the value from the Time Scheduler `.env`. Time Scheduler gives Hermes a strict JSON schema and validates the returned dates. Every start and end value must include a UTC offset such as `-04:00`.

### Push from Hermes

Give Hermes the following instruction, replacing the token with the Time Scheduler key:

> POST my finished timetable as JSON to `http://127.0.0.1:8081/api/v1/timetables?sync_calendar=true`. Send `Authorization: Bearer YOUR_TIMESCHEDULER_API_KEY` and `Content-Type: application/json`. Use the Time Scheduler schema shown below. Use stable task IDs and RFC 3339 timestamps with UTC offsets.

Push payload shape:

```json
{
  "source": "hermes",
  "timezone": "America/Toronto",
  "tasks": [
    {
      "id": "comp3804-assignment-1",
      "title": "Work on COMP 3804 assignment",
      "description": "Finish questions 1-3",
      "start": "2030-01-15T18:00:00-05:00",
      "end": "2030-01-15T20:00:00-05:00",
      "location": "Library",
      "reminders_minutes": [30, 10]
    }
  ]
}
```

`127.0.0.1` works when both applications run on the same computer. For a VM or container, use a private reachable address and firewall it; do not expose the endpoint publicly without TLS and stronger access controls.

## 3. Connect Google Calendar

You do not need the optional Google Cloud $300 trial for this personal Calendar integration. Standard Google Calendar API use is available at no additional cost within its normal quotas. See Google's [Calendar API quota and pricing documentation](https://developers.google.com/workspace/calendar/api/guides/quota).

### Create the Google Cloud project and OAuth client

1. In [Google Cloud Console](https://console.cloud.google.com/), use **Select a project > New Project**. Make sure this project remains selected for all following steps.
2. Open **APIs & Services > Library**, find **Google Calendar API**, and enable it.
3. Open **Google Auth Platform** from the navigation menu or top search bar. If it is not configured, open **Overview** and click **Get started**.
4. Under **Branding**, provide an app name such as `Google Calendar Time Table`, your support email, and your developer contact email.
5. Under **Audience**, choose **External** for a regular Gmail account and leave the publishing status as **Testing**.
6. Under **Audience > Test users**, add the exact Google account that will authorize the app.
7. Under **Data Access**, add this scope:

   ```text
   https://www.googleapis.com/auth/calendar.events
   ```

8. Under **Clients**, click **Create client**, choose **Desktop app**, and create it.
9. Download the client JSON immediately, rename it `credentials.json`, and place it in the project root next to `.env`.

The official [Google Calendar Python quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python) documents the same desktop OAuth flow.

For a personal testing app, Google verification is not required. A `403: access_denied` message saying the app is limited to developer-approved testers normally means the signed-in email was not added under **Audience > Test users**, or `credentials.json` belongs to a different selected Cloud project. Testing-mode authorizations may expire after seven days and require authorization again.

### Authorize this application

With the virtual environment activated, run:

```powershell
timescheduler-google-auth
```

Sign in using the test-user account and approve Calendar event access. The command creates `token.json`, which contains private authorization tokens and must not be committed or shared.

### Choose the destination calendar

Keep this setting to create events in the authorized account's main calendar:

```dotenv
GOOGLE_CALENDAR_ID=primary
```

To use another calendar:

1. Open Google Calendar.
2. Find the calendar under **My calendars**.
3. Open its three-dot menu and select **Settings and sharing**.
4. Scroll to **Integrate calendar** and copy **Calendar ID**.
5. Put that value in `.env`, for example:

   ```dotenv
   GOOGLE_CALENDAR_ID=example@group.calendar.google.com
   ```

Restart Time Scheduler after changing `.env`.

## 4. Import and sync a timetable

Using `sync_calendar = $true` in the pull request stores the timetable and immediately creates or updates its Calendar events. The response includes a generated timetable ID:

```json
{
  "timetable_id": "7d8d2f-example-id",
  "task_count": 5,
  "calendar_synced": true,
  "created_events": 5,
  "updated_events": 0
}
```

If a timetable was initially stored without Calendar synchronization, copy its returned `timetable_id` and sync it later:

```powershell
$headers = @{
    Authorization = "Bearer YOUR_ACTUAL_TIMESCHEDULER_API_KEY"
}

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8081/api/v1/timetables/7d8d2f-example-id/sync" `
    -Headers $headers
```

Replace the example ID and key with real values; do not literally send `TIMETABLE_ID` or `YOUR_ACTUAL_TIMESCHEDULER_API_KEY`.

Stable task IDs make synchronization idempotent: the first sync creates an event and later syncs update it. The service deliberately does not delete Calendar events that disappear from a later timetable.

### Reminders

The default `.env` value creates popup reminders 30 and 10 minutes before every task:

```dotenv
DEFAULT_REMINDERS_MINUTES=30,10
```

For example, use `60,15,5` for reminders one hour, 15 minutes, and five minutes beforehand. A task's `reminders_minutes` array overrides these defaults. Google supports at most five reminder overrides per event.

Calendar reminders only produce visible notifications if notifications are allowed for Google Calendar in the browser, operating system, or mobile application. Restart Time Scheduler after changing `.env`.

## API summary

All `/api/v1/*` endpoints require `Authorization: Bearer <TIMESCHEDULER_API_KEY>`. `/health` does not require authentication.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Readiness check |
| `POST` | `/api/v1/hermes/import` | Retrieve a timetable from Hermes |
| `POST` | `/api/v1/timetables` | Receive and store a pushed timetable |
| `GET` | `/api/v1/timetables/latest` | Read the newest timetable |
| `GET` | `/api/v1/timetables/{id}` | Read a timetable snapshot |
| `POST` | `/api/v1/timetables/{id}/sync` | Sync a snapshot to Google Calendar |

## Troubleshooting

### PowerShell requests use the wrong URL or return an Apache 404

Use plain quoted URLs in PowerShell:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8081/health"
```

Do not paste Markdown link syntax such as:

```text
[http://127.0.0.1:8081/health](http://127.0.0.1:8081/health)
```

An Apache 404 indicates that Apache or another HTTP server received the request, not Time Scheduler. Check which process owns a port with:

```powershell
netstat -ano | Select-String ':8080|:8081|:8642'
```

Change `TIMESCHEDULER_PORT` in `.env` if `8081` is already occupied.

### `ModuleNotFoundError: No module named 'time_scheduler'`

Activate the virtual environment and repair the editable installation:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### `error parsing value for field "default_reminders_minutes"`

Update to the current project code. It accepts both the documented comma-separated format and JSON-list format:

```dotenv
DEFAULT_REMINDERS_MINUTES=30,10
```

or:

```dotenv
DEFAULT_REMINDERS_MINUTES=[30,10]
```

### Nothing is listening on a local port

Each server runs in its own terminal:

```powershell
hermes gateway run
```

```powershell
.venv\Scripts\Activate.ps1
timescheduler
```

Closing either terminal stops that service.

## Test

```powershell
pytest
```

## Current scope

This is a local single-user service. Before an internet-facing deployment, add HTTPS through a reverse proxy, secret management, rate limiting, and a real user/account model. SQLite records schedule snapshots; Google Calendar is the visual timetable and notification interface.
