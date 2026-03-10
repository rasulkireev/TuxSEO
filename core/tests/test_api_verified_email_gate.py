import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory, override_settings

from core.api.schemas import ProjectScanIn
from core.api.views import create_project, generate_blog_content


@pytest.mark.django_db
@override_settings(REQUIRE_VERIFIED_EMAIL_FOR_EXPENSIVE_ACTIONS=True)
def test_create_project_blocks_unverified_user_before_project_creation():
    user = User.objects.create_user(
        username="api-unverified-user",
        email="api-unverified@example.com",
        password="secret",
    )

    request = RequestFactory().post("/api/projects/")
    request.auth = user.profile

    response = create_project(request, ProjectScanIn(url="https://example.com", source="default"))

    assert response["status"] == "error"
    assert "verify your email" in response["message"]


@pytest.mark.django_db
@override_settings(REQUIRE_VERIFIED_EMAIL_FOR_EXPENSIVE_ACTIONS=True)
def test_generate_blog_content_blocks_unverified_user_before_lookup():
    user = User.objects.create_user(
        username="api-unverified-blog-user",
        email="api-unverified-blog@example.com",
        password="secret",
    )

    request = RequestFactory().post("/api/generate-blog-content/999/")
    request.auth = user.profile

    response = generate_blog_content(request, suggestion_id=999)

    assert response["status"] == "error"
    assert response["task_id"] is None
    assert "verify your email" in response["message"]
