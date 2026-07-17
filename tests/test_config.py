from src.config.settings import Settings, settings


def test_settings_defaults():
    assert settings.app_name == "BCREC AI"
    assert settings.debug is True
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.redis_session_ttl == 1800
    assert settings.use_redis_sessions is False
    assert settings.use_postgres_history is False
    assert settings.use_otel is False


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://test:6379/1")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("USE_REDIS_SESSIONS", "true")
    s = Settings()
    assert s.redis_url == "redis://test:6379/1"
    assert s.debug is False
    assert s.use_redis_sessions is True

