"""Client for retrieving structured timetable data from Hermes Agent."""

import json

import httpx

from .config import Settings
from .models import Timetable


SYSTEM_PROMPT = """You are exporting a timetable to TimeScheduler.
Respond with JSON only, with this exact shape:
{
  "source": "hermes",
  "timezone": "America/Toronto",
  "tasks": [
    {
      "id": "stable-unique-id",
      "title": "Task title",
      "description": "Optional details",
      "start": "2030-01-15T09:00:00-05:00",
      "end": "2030-01-15T10:00:00-05:00",
      "location": null,
      "reminders_minutes": [30, 10]
    }
  ]
}
Every start and end must be RFC 3339 and include a UTC offset. Reuse a task's id when
exporting an updated version of the same task. Never include markdown fences or commentary.
"""


def extract_json(content: str) -> dict:
    """Parse a JSON object, tolerating accidental Markdown fences or surrounding text."""
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Hermes did not return a JSON object") from None
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Hermes response must be a JSON object")
    return value


async def retrieve_timetable(instruction: str, settings: Settings) -> Timetable:
    """Ask Hermes for its timetable and validate the structured response."""
    headers = {"Content-Type": "application/json"}
    if settings.hermes_api_key:
        headers["Authorization"] = f"Bearer {settings.hermes_api_key}"
    payload = {
        "model": settings.hermes_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": instruction},
        ],
        "stream": False,
        "temperature": 0,
    }
    endpoint = f"{settings.hermes_api_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
    body = response.json()
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("Hermes returned an unexpected API response") from error
    return Timetable.model_validate(extract_json(content))

