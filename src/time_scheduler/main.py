"""Command-line entry point for running the API server."""

import uvicorn

from .config import get_settings


def run() -> None:
    """Start the FastAPI application using the configured local address."""
    settings = get_settings()
    uvicorn.run(
        "time_scheduler.api:app",
        host=settings.timescheduler_host,
        port=settings.timescheduler_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
