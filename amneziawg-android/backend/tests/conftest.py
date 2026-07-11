import pytest


@pytest.fixture(autouse=True)
def test_app_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
