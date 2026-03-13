import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from core.api.auth import APIKeyAuth


@pytest.mark.django_db
def test_settings_page_shows_api_access_controls_without_exposing_raw_key(client):
    user = User.objects.create_user(
        username="settings-api-key-ui-user",
        email="settings-api-key-ui-user@example.com",
        password="secret",
    )
    client.force_login(user)

    response = client.get(reverse("settings"))

    assert response.status_code == 200

    content = response.content.decode()
    assert "API Access" in content
    assert "Reveal" in content
    assert "Copy" in content
    assert "Regenerate API Key" in content
    assert user.profile.key not in content


@pytest.mark.django_db
def test_get_api_key_returns_authenticated_users_key(client):
    user = User.objects.create_user(
        username="settings-api-key-get-user",
        email="settings-api-key-get-user@example.com",
        password="secret",
    )
    client.force_login(user)

    response = client.get("/api/settings/api-key")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["key"] == user.profile.key


@pytest.mark.django_db
def test_get_api_key_requires_authenticated_user(client):
    response = client.get("/api/settings/api-key")

    assert response.status_code == 401


@pytest.mark.django_db
def test_regenerate_api_key_replaces_current_key_and_invalidates_old_key(client):
    user = User.objects.create_user(
        username="settings-api-key-regen-user",
        email="settings-api-key-regen-user@example.com",
        password="secret",
    )
    profile = user.profile
    old_key = profile.key

    client.force_login(user)
    response = client.post("/api/settings/api-key/regenerate")

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    profile.refresh_from_db()
    assert profile.key != old_key
    assert response.json()["key"] == profile.key

    assert APIKeyAuth().authenticate(request=None, key=old_key) is None
    assert APIKeyAuth().authenticate(request=None, key=profile.key).id == profile.id


@pytest.mark.django_db
def test_regenerate_api_key_only_changes_authenticated_users_key(client):
    owner = User.objects.create_user(
        username="settings-api-key-owner",
        email="settings-api-key-owner@example.com",
        password="secret",
    )
    other = User.objects.create_user(
        username="settings-api-key-other",
        email="settings-api-key-other@example.com",
        password="secret",
    )
    other_original_key = other.profile.key

    client.force_login(owner)
    response = client.post("/api/settings/api-key/regenerate")

    assert response.status_code == 200

    owner.profile.refresh_from_db()
    other.profile.refresh_from_db()

    assert owner.profile.key == response.json()["key"]
    assert other.profile.key == other_original_key
