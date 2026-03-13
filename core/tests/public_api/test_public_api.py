from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from core.api.views import api
from core.public_api.auth import PublicAPIKeyAuth
from core.public_api.schemas import (
    PublicContentAutomationIn,
    PublicProjectIn,
    PublicProjectUpdateIn,
)
from core.public_api.views import (
    configure_content_automation,
    create_public_project,
    get_public_project,
    public_api,
    update_public_project,
)


def build_profile(**overrides):
    default_profile = {
        "id": 1,
        "user": SimpleNamespace(email="public-api-user@example.com"),
        "product_name": "Free",
        "is_on_pro_plan": False,
        "project_limit": 1,
        "number_of_active_projects": 0,
        "can_create_project": True,
        "is_on_free_plan": True,
    }
    default_profile.update(overrides)
    return SimpleNamespace(**default_profile)


def test_public_api_key_auth_returns_profile_for_valid_key():
    expected_profile = build_profile()

    with patch("core.public_api.auth.Profile.objects.get", return_value=expected_profile):
        authenticated_profile = PublicAPIKeyAuth().authenticate(request=None, key="valid-key")

    assert authenticated_profile.id == expected_profile.id


def test_public_api_key_auth_returns_none_for_invalid_key():
    from core.public_api import auth

    with patch(
        "core.public_api.auth.Profile.objects.get",
        side_effect=auth.Profile.DoesNotExist,
    ):
        authenticated_profile = PublicAPIKeyAuth().authenticate(request=None, key="invalid-key")

    assert authenticated_profile is None


def test_public_project_schema_requires_url_field():
    with pytest.raises(ValidationError):
        PublicProjectIn.model_validate({})


def test_public_content_automation_schema_requires_positive_posts_per_month():
    with pytest.raises(ValidationError):
        PublicContentAutomationIn.model_validate(
            {"endpoint_url": "https://example.com/publish", "posts_per_month": 0}
        )


def test_create_public_project_returns_error_for_invalid_url_scheme():
    request = SimpleNamespace(auth=build_profile())

    with patch("core.public_api.views.get_verified_email_gate_error", return_value=None):
        response_status_code, response_data = create_public_project(
            request,
            PublicProjectIn(url="example.com", source="public_api"),
        )

    assert response_status_code == 400
    assert response_data["message"] == "Project URL must start with http:// or https://"


def test_create_public_project_returns_error_for_duplicate_project_url():
    request = SimpleNamespace(auth=build_profile())

    project_filter_mock = Mock()
    project_filter_mock.exists.return_value = True

    with patch("core.public_api.views.get_verified_email_gate_error", return_value=None):
        with patch(
            "core.public_api.views.Project.objects.filter",
            return_value=project_filter_mock,
        ):
            response_status_code, response_data = create_public_project(
                request,
                PublicProjectIn(url="https://example.com", source="public_api"),
            )

    assert response_status_code == 400
    assert response_data["message"] == "You already added this project URL"


def test_create_public_project_returns_success():
    project_mock = Mock()
    project_mock.id = 10
    project_mock.name = "Project Name"
    project_mock.url = "https://example.com"
    project_mock.summary = "Summary"
    project_mock.get_type_display.return_value = "SaaS"
    project_mock.get_page_content.return_value = True
    project_mock.analyze_content.return_value = True

    profile = build_profile(get_or_create_project=Mock(return_value=project_mock))
    request = SimpleNamespace(auth=profile)

    project_filter_mock = Mock()
    project_filter_mock.exists.return_value = False

    with patch("core.public_api.views.get_verified_email_gate_error", return_value=None):
        with patch(
            "core.public_api.views.Project.objects.filter",
            return_value=project_filter_mock,
        ):
            response_data = create_public_project(
                request,
                PublicProjectIn(url="https://example.com", source="public_api"),
            )

    assert response_data["status"] == "success"
    assert response_data["project"]["project_id"] == 10


def test_get_public_project_returns_not_found_for_missing_project():
    request = SimpleNamespace(auth=build_profile())

    project_filter_mock = Mock()
    project_filter_mock.first.return_value = None

    with patch("core.public_api.views.Project.objects.filter", return_value=project_filter_mock):
        response_status_code, response_data = get_public_project(request, project_id=10)

    assert response_status_code == 404
    assert response_data["message"] == "Project not found"


def test_get_public_project_returns_success():
    project_mock = Mock()
    project_mock.id = 10
    project_mock.name = "Project Name"
    project_mock.url = "https://example.com"
    project_mock.summary = "Summary"
    project_mock.get_type_display.return_value = "SaaS"
    project_mock.blog_theme = "Founder-focused growth"
    project_mock.founders = "Jane Doe"
    project_mock.key_features = "SEO automation"
    project_mock.target_audience_summary = "Bootstrapped SaaS founders"
    project_mock.pain_points = "No time for content"
    project_mock.product_usage = "Weekly blog generation"
    project_mock.links = "https://example.com/docs"
    project_mock.language = "english"
    project_mock.location = "Global"

    request = SimpleNamespace(auth=build_profile())
    project_filter_mock = Mock()
    project_filter_mock.first.return_value = project_mock

    with patch("core.public_api.views.Project.objects.filter", return_value=project_filter_mock):
        response_data = get_public_project(request, project_id=10)

    assert response_data["status"] == "success"
    assert response_data["project"]["project_id"] == 10
    assert response_data["project"]["name"] == "Project Name"


def test_update_public_project_returns_not_found_for_missing_project():
    request = SimpleNamespace(auth=build_profile())

    project_filter_mock = Mock()
    project_filter_mock.first.return_value = None

    with patch("core.public_api.views.Project.objects.filter", return_value=project_filter_mock):
        response_status_code, response_data = update_public_project(
            request,
            project_id=10,
            data=PublicProjectUpdateIn(name="Updated"),
        )

    assert response_status_code == 404
    assert response_data["message"] == "Project not found"


def test_update_public_project_returns_error_when_no_fields_are_provided():
    request = SimpleNamespace(auth=build_profile())
    project_mock = Mock()
    project_filter_mock = Mock()
    project_filter_mock.first.return_value = project_mock

    with patch("core.public_api.views.Project.objects.filter", return_value=project_filter_mock):
        response_status_code, response_data = update_public_project(
            request,
            project_id=10,
            data=PublicProjectUpdateIn(),
        )

    assert response_status_code == 400
    assert response_data["message"] == "At least one field is required for update"


def test_update_public_project_updates_only_provided_fields():
    request = SimpleNamespace(auth=build_profile())
    project_mock = Mock()
    project_filter_mock = Mock()
    project_filter_mock.first.return_value = project_mock

    with patch("core.public_api.views.Project.objects.filter", return_value=project_filter_mock):
        response_data = update_public_project(
            request,
            project_id=10,
            data=PublicProjectUpdateIn(name="Updated Project", summary="Updated summary"),
        )

    assert response_data["status"] == "success"
    assert response_data["project"]["name"] == "Updated Project"
    assert response_data["project"]["summary"] == "Updated summary"
    project_mock.save.assert_called_once_with(update_fields=["name", "summary"])


def test_configure_content_automation_returns_not_found_for_missing_project():
    request = SimpleNamespace(auth=build_profile())

    project_filter_mock = Mock()
    project_filter_mock.first.return_value = None

    with patch("core.public_api.views.Project.objects.filter", return_value=project_filter_mock):
        response_status_code, response_data = configure_content_automation(
            request,
            project_id=10,
            data=PublicContentAutomationIn(endpoint_url="https://example.com/publish"),
        )

    assert response_status_code == 404
    assert response_data["message"] == "Project not found"


def test_configure_content_automation_returns_plan_error_for_free_profile():
    project_mock = Mock()
    project_filter_mock = Mock()
    project_filter_mock.first.return_value = project_mock

    request = SimpleNamespace(auth=build_profile(is_on_pro_plan=False))

    with patch("core.public_api.views.Project.objects.filter", return_value=project_filter_mock):
        response_status_code, response_data = configure_content_automation(
            request,
            project_id=10,
            data=PublicContentAutomationIn(endpoint_url="https://example.com/publish"),
        )

    assert response_status_code == 400
    assert "Pro plan" in response_data["message"]


def test_configure_content_automation_returns_success_for_pro_profile():
    project_mock = Mock()
    project_mock.id = 10
    project_filter_mock = Mock()
    project_filter_mock.first.return_value = project_mock

    profile = build_profile(is_on_pro_plan=True)
    request = SimpleNamespace(auth=profile)

    content_automation_mock = Mock()
    content_automation_mock.id = 22

    with patch("core.public_api.views.Project.objects.filter", return_value=project_filter_mock):
        with patch(
            "core.public_api.views.AutoSubmissionSetting.objects.update_or_create",
            return_value=(content_automation_mock, True),
        ):
            response_data = configure_content_automation(
                request,
                project_id=10,
                data=PublicContentAutomationIn(
                    endpoint_url="https://example.com/publish",
                    request_body_json={"title": "{{title}}"},
                    request_headers_json={"Authorization": "Bearer token"},
                    posts_per_month=2,
                    enable_automatic_post_submission=True,
                ),
            )

    assert response_data["status"] == "success"
    assert response_data["content_automation_id"] == 22


def test_configure_content_automation_returns_error_when_save_fails():
    project_mock = Mock()
    project_filter_mock = Mock()
    project_filter_mock.first.return_value = project_mock

    profile = build_profile(is_on_pro_plan=True)
    request = SimpleNamespace(auth=profile)

    with patch("core.public_api.views.Project.objects.filter", return_value=project_filter_mock):
        with patch(
            "core.public_api.views.AutoSubmissionSetting.objects.update_or_create",
            side_effect=RuntimeError("database failure"),
        ):
            response_status_code, response_data = configure_content_automation(
                request,
                project_id=10,
                data=PublicContentAutomationIn(endpoint_url="https://example.com/publish"),
            )

    assert response_status_code == 500
    assert response_data["message"] == "Failed to save content automation settings"


def test_public_openapi_includes_public_routes_only():
    openapi_schema = public_api.get_openapi_schema()
    schema_paths = openapi_schema["paths"]

    assert "/public-api/account" in schema_paths
    assert "/public-api/projects" in schema_paths
    assert "/public-api/projects/{project_id}" in schema_paths
    assert "/public-api/projects/{project_id}/content-automation" in schema_paths
    assert "/public-api/validate-url" not in schema_paths


def test_internal_openapi_is_not_exposed():
    assert api.openapi_url is None
