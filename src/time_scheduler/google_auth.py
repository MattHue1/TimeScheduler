"""One-time interactive OAuth setup for a user's Google Calendar."""

from google_auth_oauthlib.flow import InstalledAppFlow

from .config import get_settings
from .google_calendar import SCOPES


def main() -> None:
    """Open Google's consent flow and persist the resulting refreshable token."""
    settings = get_settings()
    if not settings.google_credentials_file.exists():
        raise SystemExit(
            f"Missing {settings.google_credentials_file}. Download an OAuth Desktop client JSON first."
        )
    flow = InstalledAppFlow.from_client_secrets_file(
        str(settings.google_credentials_file), SCOPES
    )
    credentials = flow.run_local_server(port=0)
    settings.google_token_file.parent.mkdir(parents=True, exist_ok=True)
    settings.google_token_file.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Google authorization saved to {settings.google_token_file}")


if __name__ == "__main__":
    main()

