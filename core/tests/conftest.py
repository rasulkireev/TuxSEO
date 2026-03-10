import json

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


@pytest.fixture(autouse=True)
def mock_webpack_manifest(settings, tmp_path):
    """Provide a minimal webpack manifest so template rendering works in CI tests."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "entrypoints": {
                    "index": {
                        "assets": {
                            "js": [],
                            "css": [],
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    settings.WEBPACK_LOADER["MANIFEST_FILE"] = str(manifest_path)

    from webpack_boilerplate.loader import WebpackLoader

    WebpackLoader._assets = {}
