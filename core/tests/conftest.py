import pytest
from django.conf import settings


def pytest_configure(config):
    settings.STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"


@pytest.fixture(autouse=True)
def mock_async_task_calls(monkeypatch):
    """Avoid Redis dependency in tests by no-oping async task dispatchers."""
    monkeypatch.setattr("core.models.async_task", lambda *args, **kwargs: None)
    monkeypatch.setattr("core.signals.async_task", lambda *args, **kwargs: None)
    monkeypatch.setattr("core.adapters.async_task", lambda *args, **kwargs: None)
    monkeypatch.setattr("core.scheduled_tasks.async_task", lambda *args, **kwargs: None)
