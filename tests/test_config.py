from time_scheduler.config import Settings


def test_settings_use_safe_local_server_defaults():
    settings = Settings(_env_file=None)

    assert settings.timescheduler_host == "127.0.0.1"
    assert settings.timescheduler_port == 8081


def test_settings_parse_comma_separated_reminders_from_environment(monkeypatch):
    monkeypatch.setenv("DEFAULT_REMINDERS_MINUTES", "30,10")

    settings = Settings(_env_file=None)

    assert settings.default_reminders_minutes == [30, 10]


def test_settings_parse_json_reminders_from_environment(monkeypatch):
    monkeypatch.setenv("DEFAULT_REMINDERS_MINUTES", "[15, 5]")

    settings = Settings(_env_file=None)

    assert settings.default_reminders_minutes == [15, 5]
