import inspect
from unittest.mock import Mock, patch

from core.analytics import (
    ANALYTICS_EVENT_NAMES,
    ANALYTICS_EVENTS,
    DEPRECATED_ANALYTICS_EVENT_ALIASES,
    EVENT_TAXONOMY_VERSION,
    normalize_event_name,
)
from core.models import Profile
from core.tasks import track_event


def test_event_taxonomy_exposes_expected_canonical_events():
    assert ANALYTICS_EVENTS.SIGNUP_COMPLETED == "signup_completed"
    assert ANALYTICS_EVENTS.PROJECT_CREATED == "project_created"
    assert ANALYTICS_EVENTS.PROJECT_DELETED == "project_deleted"
    assert ANALYTICS_EVENTS.SIGNUP_COMPLETED in ANALYTICS_EVENT_NAMES


def test_deprecated_aliases_are_explicit_and_normalized():
    assert DEPRECATED_ANALYTICS_EVENT_ALIASES["user_signed_up"] == (
        ANALYTICS_EVENTS.SIGNUP_COMPLETED
    )
    assert normalize_event_name("user_signed_up") == ANALYTICS_EVENTS.SIGNUP_COMPLETED
    assert (
        normalize_event_name(ANALYTICS_EVENTS.PROJECT_CREATED)
        == ANALYTICS_EVENTS.PROJECT_CREATED
    )


def test_track_event_normalizes_deprecated_event_name_before_capture():
    fake_user = Mock(email="event-user@example.com")
    fake_profile = Mock(id=123, user=fake_user, state="active")

    with patch("core.tasks.Profile.objects.get", return_value=fake_profile):
        with patch("core.tasks.posthog.capture") as mock_capture:
            result = track_event(
                profile_id=fake_profile.id,
                event_name="user_signed_up",
                properties={"source": "unit-test"},
            )

    assert "signup_completed" in result
    mock_capture.assert_called_once()

    capture_kwargs = mock_capture.call_args.kwargs
    assert capture_kwargs["event"] == ANALYTICS_EVENTS.SIGNUP_COMPLETED
    assert capture_kwargs["properties"]["event_schema_version"] == EVENT_TAXONOMY_VERSION


def test_profile_model_uses_canonical_project_created_constant():
    profile_source = inspect.getsource(Profile.get_or_create_project)
    assert "ANALYTICS_EVENTS.PROJECT_CREATED" in profile_source
